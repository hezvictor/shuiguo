from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from fruit_api.services.camera.stereo_camera_service import StereoCameraConfig, StereoCameraService


_preview_cache_lock = threading.RLock()
_cached_preview_frame_snapshot: Dict[str, Any] | None = None


def get_cached_preview_frame_snapshot() -> Dict[str, Any] | None:
    with _preview_cache_lock:
        if _cached_preview_frame_snapshot is None:
            return None
        snapshot = dict(_cached_preview_frame_snapshot)
        for key in ("single_frame", "left_frame", "right_frame"):
            frame = snapshot.get(key)
            snapshot[key] = None if frame is None else np.array(frame, copy=True)
        return snapshot


def clear_cached_preview_frame_snapshot() -> None:
    global _cached_preview_frame_snapshot
    with _preview_cache_lock:
        _cached_preview_frame_snapshot = None


def _cache_preview_frame_snapshot(snapshot: Dict[str, Any]) -> None:
    global _cached_preview_frame_snapshot
    with _preview_cache_lock:
        cached = dict(snapshot)
        for key in ("single_frame", "left_frame", "right_frame"):
            frame = cached.get(key)
            cached[key] = None if frame is None else np.array(frame, copy=True)
        _cached_preview_frame_snapshot = cached


@dataclass
class DevicePreviewConfig:
    mode: str = "single"
    camera_index: int = 0
    left_camera_index: int = 0
    right_camera_index: int = 1
    backend: str = ""
    detect: bool = False
    conf: float = 0.25
    fps: int = 6

    def to_payload(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "camera_index": self.camera_index,
            "left_camera_index": self.left_camera_index,
            "right_camera_index": self.right_camera_index,
            "backend": self.backend,
            "detect": self.detect,
            "conf": self.conf,
            "stream_fps": self.fps,
        }


class DevicePreviewSession:
    PREVIEW_JPEG_QUALITY = 72
    SINGLE_PREVIEW_MAX_WIDTH = 960
    DUAL_PREVIEW_MAX_WIDTH = 1280

    def __init__(self, *, yolo_model_getter):
        self._yolo_model_getter = yolo_model_getter
        self._config = DevicePreviewConfig()
        self._lock = threading.RLock()
        self._last_error: Optional[str] = None
        self._last_frame_ts: Optional[float] = None
        self._consecutive_failures = 0
        self._camera_service = StereoCameraService()
        self._single_capture = None
        self._left_capture = None
        self._right_capture = None
        self._opened_capture_key: Optional[tuple] = None

    @staticmethod
    def _capture_key(config: DevicePreviewConfig) -> tuple:
        return (
            config.mode,
            int(config.camera_index),
            int(config.left_camera_index),
            int(config.right_camera_index),
            str(config.backend or ""),
            int(config.fps),
        )

    def update_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            previous_key = self._capture_key(self._config)
            if payload.get("mode") is not None:
                self._config.mode = str(payload.get("mode"))
            if payload.get("camera_index") is not None:
                self._config.camera_index = int(payload.get("camera_index"))
            if payload.get("left_camera_index") is not None:
                self._config.left_camera_index = int(payload.get("left_camera_index"))
            if payload.get("right_camera_index") is not None:
                self._config.right_camera_index = int(payload.get("right_camera_index"))
            if payload.get("backend") is not None:
                self._config.backend = str(payload.get("backend") or "")
            if payload.get("detect") is not None:
                self._config.detect = bool(payload.get("detect"))
            if payload.get("conf") is not None:
                self._config.conf = max(0.01, min(1.0, float(payload.get("conf"))))
            if payload.get("fps") is not None:
                self._config.fps = max(1, int(payload.get("fps")))
            if self._capture_key(self._config) != previous_key:
                self._close_captures_locked()
            return self.status_payload()

    def status_payload(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "type": "preview.status",
                "camera_active": True,
                "config": self._config.to_payload(),
                "last_frame_ts": self._last_frame_ts,
                "consecutive_failures": self._consecutive_failures,
                "message": self._last_error,
            }

    def record_success(self) -> None:
        with self._lock:
            self._last_error = None
            self._consecutive_failures = 0
            self._last_frame_ts = time.time()

    def record_failure(self, message: str) -> None:
        with self._lock:
            self._last_error = message
            self._consecutive_failures += 1

    def close(self) -> None:
        with self._lock:
            self._close_captures_locked()
        clear_cached_preview_frame_snapshot()

    def _close_captures_locked(self) -> None:
        StereoCameraService._release_capture(self._single_capture)
        StereoCameraService._release_capture(self._left_capture)
        StereoCameraService._release_capture(self._right_capture)
        self._single_capture = None
        self._left_capture = None
        self._right_capture = None
        self._opened_capture_key = None

    def _ensure_captures_locked(self, config: DevicePreviewConfig) -> None:
        capture_key = self._capture_key(config)
        if self._opened_capture_key == capture_key:
            return

        self._close_captures_locked()
        effective = StereoCameraConfig(
            source_mode=config.mode,
            camera_index=int(config.camera_index),
            left_camera_index=int(config.left_camera_index),
            right_camera_index=int(config.right_camera_index),
            backend=config.backend or None,
            fps=int(config.fps),
        )
        if config.mode == "dual":
            self._left_capture = self._camera_service._open_capture(int(config.left_camera_index), effective)
            try:
                self._right_capture = self._camera_service._open_capture(int(config.right_camera_index), effective)
            except Exception:
                StereoCameraService._release_capture(self._left_capture)
                self._left_capture = None
                raise
        else:
            self._single_capture = self._camera_service._open_capture(int(config.camera_index), effective)
        self._opened_capture_key = capture_key

    @staticmethod
    def _resize_preview_frame(frame: np.ndarray, *, max_width: int) -> np.ndarray:
        if frame.shape[1] <= max_width:
            return frame
        from fruit_api.services.camera.stereo_camera_service import _require_cv2

        cv2 = _require_cv2()
        scale = max_width / float(frame.shape[1])
        target_size = (max(1, int(frame.shape[1] * scale)), max(1, int(frame.shape[0] * scale)))
        return cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)

    def _render_single(self, frame: np.ndarray) -> np.ndarray:
        if self._config.detect:
            StereoCameraService._draw_detections(frame, self._yolo_model_getter(), self._config.conf)
        return frame

    def _render_dual(self, left_frame: np.ndarray, right_frame: np.ndarray) -> np.ndarray:
        preview = np.concatenate([left_frame, right_frame], axis=1)
        return preview

    def encode_preview_frame(self) -> bytes:
        with self._lock:
            config = DevicePreviewConfig(**self._config.__dict__)
            try:
                self._ensure_captures_locked(config)
                if config.mode == "dual":
                    left_frame = self._camera_service._read_frame(self._left_capture, f"left camera {config.left_camera_index}")
                    right_frame = self._camera_service._read_frame(self._right_capture, f"right camera {config.right_camera_index}")
                    left_frame, right_frame = StereoCameraService._resize_to_match(left_frame, right_frame)
                    rendered = self._render_dual(left_frame.copy(), right_frame.copy())
                    snapshot = {
                        "config": config.to_payload(),
                        "captured_at": time.time(),
                        "single_frame": None,
                        "left_frame": left_frame,
                        "right_frame": right_frame,
                    }
                    rendered = self._resize_preview_frame(rendered, max_width=self.DUAL_PREVIEW_MAX_WIDTH)
                else:
                    frame = self._camera_service._read_frame(self._single_capture, f"camera {config.camera_index}")
                    rendered = self._render_single(frame.copy())
                    snapshot = {
                        "config": config.to_payload(),
                        "captured_at": time.time(),
                        "single_frame": frame,
                        "left_frame": None,
                        "right_frame": None,
                    }
                    rendered = self._resize_preview_frame(rendered, max_width=self.SINGLE_PREVIEW_MAX_WIDTH)
            except Exception:
                self._close_captures_locked()
                raise

        _cache_preview_frame_snapshot(snapshot)
        return _encode_frame(rendered, quality=self.PREVIEW_JPEG_QUALITY)


def _encode_frame(frame: np.ndarray, *, quality: int = 85) -> bytes:
    from fruit_api.services.camera.stereo_camera_service import _require_cv2

    cv2 = _require_cv2()
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise RuntimeError("failed to encode preview frame")
    return encoded.tobytes()
