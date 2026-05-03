from __future__ import annotations

import os
import json
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Dict, Generator, List, Optional, Tuple

import numpy as np
from PIL import Image
from fruit_api.services.detection.yolo_service import draw_yolo_targets_on_bgr, predict_yolo_targets_from_bgr


class CameraDependencyError(Exception):
    pass


class CameraOpenError(Exception):
    pass


class CameraStateError(Exception):
    pass


_TRANSIENT_CAPTURE_LOCK = threading.RLock()


def _require_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise CameraDependencyError("opencv-python is required for camera access") from exc
    return cv2


def _list_windows_camera_devices() -> List[Dict[str, str]]:
    if os.name != "nt":
        return []

    script = r"""
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $devices = Get-CimInstance Win32_PnPEntity | Where-Object {
      $_.PNPClass -in @('Camera', 'Image') -or $_.Service -eq 'usbvideo'
    } | Select-Object Name, PNPDeviceID, Status, Service
    if ($null -eq $devices) {
      '[]'
    } else {
      $devices | ConvertTo-Json -Compress
    }
    """

    candidates = [
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
        "powershell.exe",
        "pwsh.exe",
    ]
    last_error: Optional[Exception] = None

    for executable in candidates:
        try:
            completed = subprocess.run(
                [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=8,
                check=False,
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
            last_error = exc
            continue

        if completed.returncode != 0:
            last_error = RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "powershell failed")
            continue

        raw = (completed.stdout or "").strip()
        if not raw:
            return []

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []

        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return []

        devices: List[Dict[str, str]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name") or "").strip()
            if not name:
                continue
            devices.append(
                {
                    "device_name": name,
                    "device_id": str(item.get("PNPDeviceID") or "").strip(),
                    "device_status": str(item.get("Status") or "").strip(),
                    "device_service": str(item.get("Service") or "").strip(),
                }
            )
        return devices

    if last_error:
        return []
    return []


def _enrich_probe_results_with_device_names(
    results: List[Dict[str, object]],
    pair_results: List[Dict[str, object]],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Dict[str, str]]]:
    device_catalog = _list_windows_camera_devices()
    if not device_catalog:
        return results, pair_results, []

    preferred_devices = [item for item in device_catalog if item.get("device_status", "").upper() == "OK"] or device_catalog
    opened_results = [item for item in results if item.get("opened")]
    name_map: Dict[int, Dict[str, str]] = {}

    for device_info, result in zip(preferred_devices, opened_results):
        camera_index = int(result["camera_index"])
        name_map[camera_index] = device_info

    enriched_results: List[Dict[str, object]] = []
    for item in results:
        enriched = dict(item)
        device_info = name_map.get(int(item["camera_index"]))
        if device_info:
            enriched.update(device_info)
            enriched["device_name_inferred"] = True
        enriched_results.append(enriched)

    enriched_pairs: List[Dict[str, object]] = []
    for item in pair_results:
        enriched = dict(item)
        left_info = name_map.get(int(item["left_camera_index"]))
        right_info = name_map.get(int(item["right_camera_index"]))
        if left_info:
            enriched["left_device_name"] = left_info["device_name"]
        if right_info:
            enriched["right_device_name"] = right_info["device_name"]
        enriched_pairs.append(enriched)

    return enriched_results, enriched_pairs, preferred_devices


@dataclass
class StereoCameraConfig:
    source_mode: str = "single"
    camera_index: int = 0
    left_camera_index: int = 0
    right_camera_index: int = 1
    frame_width: Optional[int] = None
    frame_height: Optional[int] = None
    fps: Optional[int] = None
    split_mode: str = "left_right"
    backend: Optional[str] = None

    def to_payload(self) -> Dict[str, Optional[int]]:
        return asdict(self)


class StereoCameraService:
    OPEN_WARMUP_FRAMES = 8
    OPEN_WARMUP_DELAY = 0.05
    READ_RETRIES = 5
    READ_RETRY_DELAY = 0.03
    STREAM_RETRY_DELAY = 0.2
    PREVIEW_FAILURE_LIMIT = 2
    PREVIEW_JPEG_QUALITY = 80

    def __init__(self, default_config: Optional[Dict] = None):
        config_payload = dict(default_config or {})
        self._default_config = StereoCameraConfig(**config_payload)
        self._active_config = StereoCameraConfig(**self._default_config.to_payload())
        self._single_capture = None
        self._left_capture = None
        self._right_capture = None
        self._lock = threading.RLock()
        self._is_running = False
        self._last_open_error: Optional[str] = None
        self._last_stream_error: Optional[str] = None
        self._last_frame_ts: Optional[float] = None
        self._consecutive_failures = 0

    @staticmethod
    def _backend_flag(config: StereoCameraConfig) -> int:
        cv2 = _require_cv2()
        if not config.backend:
            return cv2.CAP_ANY
        return getattr(cv2, config.backend, cv2.CAP_ANY)

    @staticmethod
    def _backend_name_candidates(config: StereoCameraConfig) -> List[str]:
        requested = (config.backend or "").strip().upper()
        candidates: List[str] = []
        if requested and requested not in {"AUTO", "DEFAULT"}:
            candidates.append(requested)
        if os.name == "nt":
            for name in ("CAP_MSMF", "CAP_DSHOW", "CAP_ANY"):
                if name not in candidates:
                    candidates.append(name)
        elif not candidates:
            candidates.append("CAP_ANY")
        elif "CAP_ANY" not in candidates:
            candidates.append("CAP_ANY")
        return candidates

    @staticmethod
    def _backend_flag_by_name(backend_name: str) -> int:
        cv2 = _require_cv2()
        if not backend_name or backend_name == "CAP_ANY":
            return cv2.CAP_ANY
        return getattr(cv2, backend_name, cv2.CAP_ANY)

    @staticmethod
    def _release_capture(capture) -> None:
        if capture is None:
            return
        try:
            capture.release()
        except Exception:
            return

    @staticmethod
    def _apply_capture_options(capture, config: StereoCameraConfig) -> None:
        cv2 = _require_cv2()
        if config.frame_width:
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(config.frame_width))
        if config.frame_height:
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(config.frame_height))
        if config.fps:
            capture.set(cv2.CAP_PROP_FPS, int(config.fps))
        if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    @staticmethod
    def _has_visible_signal(frame: np.ndarray) -> bool:
        return bool(frame.size > 0 and int(frame.max()) > 0)

    def _open_capture(self, camera_index: int, config: StereoCameraConfig):
        cv2 = _require_cv2()
        errors: List[str] = []

        for backend_name in self._backend_name_candidates(config):
            backend_flag = self._backend_flag_by_name(backend_name)
            capture = cv2.VideoCapture(int(camera_index), backend_flag)
            if not capture.isOpened():
                capture.release()
                errors.append(f"{backend_name}: open failed")
                continue

            self._apply_capture_options(capture, config)
            usable = False
            for _ in range(self.OPEN_WARMUP_FRAMES):
                ok, frame = capture.read()
                if ok and frame is not None and frame.size > 0 and self._has_visible_signal(frame):
                    usable = True
                    break
                time.sleep(self.OPEN_WARMUP_DELAY)

            if usable:
                return capture

            capture.release()
            errors.append(f"{backend_name}: opened but no visible frame")

        detail = "; ".join(errors) if errors else "unknown error"
        raise CameraOpenError(f"unable to open camera index {camera_index} ({detail})")

    @staticmethod
    def _read_frame(capture, camera_label: str) -> np.ndarray:
        last_error = f"unable to read frame from {camera_label}"
        for attempt in range(StereoCameraService.READ_RETRIES):
            ok, frame = capture.read()
            if ok and frame is not None and frame.size > 0:
                if StereoCameraService._has_visible_signal(frame) or attempt == StereoCameraService.READ_RETRIES - 1:
                    return frame
                last_error = f"received empty-looking frame from {camera_label}"
            else:
                last_error = f"unable to read frame from {camera_label}"
            time.sleep(StereoCameraService.READ_RETRY_DELAY)
        raise CameraOpenError(last_error)

    @staticmethod
    def _split_single_frame(frame: np.ndarray, split_mode: str) -> Tuple[np.ndarray, np.ndarray]:
        height, width = frame.shape[:2]
        if split_mode == "top_bottom":
            midpoint = max(1, height // 2)
            left = frame[:midpoint, :]
            right = frame[midpoint:, :]
        else:
            midpoint = max(1, width // 2)
            left = frame[:, :midpoint]
            right = frame[:, midpoint:]

        if left.size == 0 or right.size == 0:
            raise CameraOpenError("failed to split stereo frame; check split_mode and camera output format")
        return left, right

    @staticmethod
    def _resize_to_match(left: np.ndarray, right: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if left.shape[:2] == right.shape[:2]:
            return left, right
        cv2 = _require_cv2()
        target_size = (left.shape[1], left.shape[0])
        resized = cv2.resize(right, target_size, interpolation=cv2.INTER_LINEAR)
        return left, resized

    @staticmethod
    def _draw_label(frame: np.ndarray, text: str, color: Tuple[int, int, int]) -> None:
        cv2 = _require_cv2()
        cv2.rectangle(frame, (8, 8), (220, 38), color, -1)
        cv2.putText(frame, text, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA)

    @staticmethod
    def _draw_detections(frame: np.ndarray, yolo_model, conf: float) -> None:
        targets = predict_yolo_targets_from_bgr(
            yolo_model=yolo_model,
            image_bgr=frame,
            conf=conf,
            translate_labels=False,
        )
        annotated = draw_yolo_targets_on_bgr(frame, targets)
        frame[:, :] = annotated

    def open(self, config: Optional[StereoCameraConfig] = None) -> Dict:
        effective = config or self._default_config
        with self._lock:
            self.close()
            try:
                if effective.source_mode == "dual":
                    self._left_capture = self._open_capture(effective.left_camera_index, effective)
                    try:
                        self._right_capture = self._open_capture(effective.right_camera_index, effective)
                    except Exception:
                        self._left_capture.release()
                        self._left_capture = None
                        raise
                    self._read_frame(self._left_capture, "left camera")
                    self._read_frame(self._right_capture, "right camera")
                else:
                    self._single_capture = self._open_capture(effective.camera_index, effective)
                    frame = self._read_frame(self._single_capture, "stereo camera")
                    self._split_single_frame(frame, effective.split_mode)
            except Exception as exc:
                self._last_open_error = str(exc)
                self.close()
                raise

            self._active_config = StereoCameraConfig(**effective.to_payload())
            self._is_running = True
            self._last_open_error = None
            self._last_frame_ts = time.time()
            return self.status()

    def close(self) -> None:
        with self._lock:
            for attr_name in ("_single_capture", "_left_capture", "_right_capture"):
                capture = getattr(self, attr_name)
                if capture is not None:
                    try:
                        capture.release()
                    finally:
                        setattr(self, attr_name, None)
            self._is_running = False

    def ensure_open(self) -> None:
        with self._lock:
            if self._is_running:
                return
        self.open()

    def read_stereo_frames(self) -> Tuple[np.ndarray, np.ndarray, Dict]:
        self.ensure_open()
        with self._lock:
            config = self._active_config
            if config.source_mode == "dual":
                if self._left_capture is None or self._right_capture is None:
                    raise CameraStateError("camera is not active")
                left = self._read_frame(self._left_capture, "left camera")
                right = self._read_frame(self._right_capture, "right camera")
            else:
                if self._single_capture is None:
                    raise CameraStateError("camera is not active")
                frame = self._read_frame(self._single_capture, "stereo camera")
                left, right = self._split_single_frame(frame, config.split_mode)

            left, right = self._resize_to_match(left, right)
            self._last_frame_ts = time.time()
            return left, right, self.status()

    def render_preview_frame(self, *, detect: bool = False, yolo_model=None, conf: float = 0.25) -> np.ndarray:
        cv2 = _require_cv2()
        left, right, status = self.read_stereo_frames()
        left_preview = left.copy()
        right_preview = right.copy()
        self._draw_label(left_preview, "LEFT", (80, 220, 255))
        self._draw_label(right_preview, "RIGHT", (80, 220, 255))

        if detect and yolo_model is not None:
            self._draw_detections(left_preview, yolo_model, conf)

        preview = np.concatenate([left_preview, right_preview], axis=1)
        mid_x = left_preview.shape[1]
        cv2.line(preview, (mid_x, 0), (mid_x, preview.shape[0]), (255, 255, 255), 2)
        footer = (
            f"mode={status['config']['source_mode']} "
            f"split={status['config']['split_mode']} "
            f"time={time.strftime('%H:%M:%S')}"
        )
        cv2.putText(
            preview,
            footer,
            (16, max(32, preview.shape[0] - 16)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return preview

    @staticmethod
    def _encode_mjpeg_chunk(frame_bytes: bytes) -> bytes:
        return (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )

    def _encode_error_jpeg(self, message: str) -> bytes:
        cv2 = _require_cv2()
        canvas = np.zeros((480, 1280, 3), dtype=np.uint8)
        canvas[:] = (20, 20, 20)
        title = "Stereo camera preview unavailable"
        lines = [title, message[:120] or "unknown error"]
        if len(message) > 120:
            lines.append(message[120:240])
        for index, line in enumerate(lines):
            cv2.putText(
                canvas,
                line,
                (32, 80 + index * 42),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9 if index == 0 else 0.7,
                (0, 200, 255) if index == 0 else (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
        ok, encoded = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            raise CameraStateError("failed to encode preview error frame")
        return encoded.tobytes()

    def encode_preview_jpeg(self, *, detect: bool = False, yolo_model=None, conf: float = 0.25) -> bytes:
        cv2 = _require_cv2()
        frame = self.render_preview_frame(detect=detect, yolo_model=yolo_model, conf=conf)
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.PREVIEW_JPEG_QUALITY])
        if not ok:
            raise CameraStateError("failed to encode preview frame")
        return encoded.tobytes()

    def record_preview_success(self) -> None:
        with self._lock:
            self._last_stream_error = None
            self._consecutive_failures = 0

    def record_preview_failure(self, message: str) -> None:
        with self._lock:
            self._last_open_error = message
            self._last_stream_error = message
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.PREVIEW_FAILURE_LIMIT:
                self.close()

    def mjpeg_stream(self, *, detect: bool = False, yolo_model=None, conf: float = 0.25) -> Generator[bytes, None, None]:
        while True:
            try:
                frame_bytes = self.encode_preview_jpeg(detect=detect, yolo_model=yolo_model, conf=conf)
                self.record_preview_success()
            except (CameraDependencyError, CameraOpenError, CameraStateError) as exc:
                self.record_preview_failure(str(exc))
                frame_bytes = self._encode_error_jpeg(str(exc))
                yield self._encode_mjpeg_chunk(frame_bytes)
                time.sleep(self.STREAM_RETRY_DELAY)
                continue

            yield self._encode_mjpeg_chunk(frame_bytes)
            time.sleep(0.03)

    def status(self) -> Dict:
        return {
            "active": self._is_running,
            "config": self._active_config.to_payload(),
            "last_open_error": self._last_open_error,
            "last_stream_error": self._last_stream_error,
            "last_frame_ts": self._last_frame_ts,
            "consecutive_failures": self._consecutive_failures,
        }


def probe_camera_indices(max_index: int = 4, backend: Optional[str] = None) -> Dict[str, object]:
    requested_backend = (backend or "").strip()
    config = StereoCameraConfig(backend=requested_backend or None)
    results: List[Dict[str, object]] = []
    cv2 = _require_cv2()

    def probe_single_index(camera_index: int) -> Dict[str, object]:
        attempted_backends: List[str] = []
        partial_info: Optional[Dict[str, object]] = None

        for backend_name in StereoCameraService._backend_name_candidates(config):
            attempted_backends.append(backend_name)
            capture = None
            try:
                capture = cv2.VideoCapture(camera_index, StereoCameraService._backend_flag_by_name(backend_name))
                opened = bool(capture is not None and capture.isOpened())
                info: Dict[str, object] = {
                    "camera_index": camera_index,
                    "opened": opened,
                    "read_ok": False,
                    "backend": requested_backend or "auto",
                    "backend_used": backend_name,
                }
                if not opened:
                    continue

                StereoCameraService._apply_capture_options(capture, config)
                fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
                if fps > 0:
                    info["fps"] = round(fps, 3)

                for _ in range(StereoCameraService.OPEN_WARMUP_FRAMES):
                    ok, frame = capture.read()
                    if ok and frame is not None and frame.size > 0:
                        height, width = frame.shape[:2]
                        info["read_ok"] = True
                        info["frame_width"] = int(width)
                        info["frame_height"] = int(height)
                        return info
                    time.sleep(StereoCameraService.OPEN_WARMUP_DELAY)

                if partial_info is None:
                    partial_info = info
            finally:
                StereoCameraService._release_capture(capture)

        if partial_info is not None:
            partial_info["attempted_backends"] = attempted_backends
            return partial_info

        return {
            "camera_index": camera_index,
            "opened": False,
            "read_ok": False,
            "backend": requested_backend or "auto",
            "attempted_backends": attempted_backends,
        }

    with _TRANSIENT_CAPTURE_LOCK:
        for camera_index in range(max(0, int(max_index))):
            results.append(probe_single_index(camera_index))

    opened_results = [item for item in results if item["opened"]]
    readable_results = [item for item in opened_results if item.get("read_ok")]
    pair_results: List[Dict[str, object]] = []
    readable_by_index = {int(item["camera_index"]): item for item in readable_results}
    readable_indices = [int(item["camera_index"]) for item in readable_results]
    for left_index, right_index in combinations(readable_indices, 2):
        left_info = readable_by_index[left_index]
        right_info = readable_by_index[right_index]
        pair_info: Dict[str, object] = {
            "left_camera_index": left_index,
            "right_camera_index": right_index,
            "backend": requested_backend or "auto",
            "validation_mode": "individual_probe",
            "left_opened": True,
            "right_opened": True,
            "left_read_ok": True,
            "right_read_ok": True,
            "simultaneous_ok": True,
            "left_frame_width": left_info.get("frame_width"),
            "left_frame_height": left_info.get("frame_height"),
            "right_frame_width": right_info.get("frame_width"),
            "right_frame_height": right_info.get("frame_height"),
            "left_backend_used": left_info.get("backend_used"),
            "right_backend_used": right_info.get("backend_used"),
        }
        pair_results.append(pair_info)

    results, pair_results, device_catalog = _enrich_probe_results_with_device_names(results, pair_results)
    successful_pairs = [item for item in pair_results if item["simultaneous_ok"]]
    recommended_pair = None
    if successful_pairs:
        recommended_pair = [
            successful_pairs[0]["left_camera_index"],
            successful_pairs[0]["right_camera_index"],
        ]
    elif len(readable_results) >= 2:
        recommended_pair = [
            int(readable_results[0]["camera_index"]),
            int(readable_results[1]["camera_index"]),
        ]
    return {
        "backend": requested_backend or "auto",
        "max_index": int(max_index),
        "results": results,
        "pair_results": pair_results,
        "device_catalog": device_catalog,
        "opened_count": len(opened_results),
        "recommended_dual_pair": recommended_pair,
    }


_camera_service: Optional[StereoCameraService] = None


def get_stereo_camera_service(default_config: Optional[Dict] = None) -> StereoCameraService:
    global _camera_service
    if _camera_service is None:
        _camera_service = StereoCameraService(default_config=default_config)
    return _camera_service


def capture_single_camera_frame(
    camera_index: int,
    *,
    backend: Optional[str] = None,
    frame_width: Optional[int] = None,
    frame_height: Optional[int] = None,
    fps: Optional[int] = None,
) -> np.ndarray:
    service = StereoCameraService(
        default_config={
            "camera_index": int(camera_index),
            "backend": backend or None,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "fps": fps,
        }
    )
    config = StereoCameraConfig(
        source_mode="single",
        camera_index=int(camera_index),
        split_mode="left_right",
        backend=backend or None,
        frame_width=frame_width,
        frame_height=frame_height,
        fps=fps,
    )

    with _TRANSIENT_CAPTURE_LOCK:
        capture = None
        try:
            capture = service._open_capture(int(camera_index), config)
            return service._read_frame(capture, f"camera {camera_index}")
        finally:
            StereoCameraService._release_capture(capture)


def capture_dual_camera_frames(
    left_camera_index: int,
    right_camera_index: int,
    *,
    backend: Optional[str] = None,
    frame_width: Optional[int] = None,
    frame_height: Optional[int] = None,
    fps: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    service = StereoCameraService(
        default_config={
            "left_camera_index": int(left_camera_index),
            "right_camera_index": int(right_camera_index),
            "backend": backend or None,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "fps": fps,
        }
    )
    config = StereoCameraConfig(
        source_mode="dual",
        left_camera_index=int(left_camera_index),
        right_camera_index=int(right_camera_index),
        backend=backend or None,
        frame_width=frame_width,
        frame_height=frame_height,
        fps=fps,
    )

    with _TRANSIENT_CAPTURE_LOCK:
        left_capture = None
        right_capture = None
        try:
            left_capture = service._open_capture(int(left_camera_index), config)
            right_capture = service._open_capture(int(right_camera_index), config)
            left = service._read_frame(left_capture, f"left camera {left_camera_index}")
            right = service._read_frame(right_capture, f"right camera {right_camera_index}")
            return service._resize_to_match(left, right)
        finally:
            StereoCameraService._release_capture(left_capture)
            StereoCameraService._release_capture(right_capture)
