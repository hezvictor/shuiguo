import argparse
import csv
import gc
import io
import json
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import psutil
import torch
import torch.nn as nn
from django.conf import settings
from PIL import Image
from torch.serialization import add_safe_globals


@dataclass
class MeasureConfig:
    monster_dir: Path
    calib_npz: Path
    restore_ckpt: Path
    output_dir: Path
    patch_size: int = 5
    default_conf: float = 0.25
    infer_valid_iters: int = 16
    preferred_device: str = "auto"
    allow_cpu_fallback: bool = True


class MeasurementEnvironmentError(RuntimeError):
    pass


def _resolve_measure_device(preferred_device: str) -> str:
    choice = (preferred_device or "auto").strip().lower()
    if choice == "cpu":
        return "cpu"
    if choice == "cuda":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _bytes_to_gib(value: int | float) -> float:
    return round(float(value) / (1024 ** 3), 2)


def get_diameter_runtime_host_status(config: MeasureConfig) -> Dict[str, Any]:
    preferred_device = str(config.preferred_device or "auto")
    resolved_device = _resolve_measure_device(preferred_device)
    virtual_memory = psutil.virtual_memory()
    swap_memory = psutil.swap_memory()
    min_cpu_total_memory_gb = float(getattr(settings, "MEASURE_CONFIG", {}).get("MIN_CPU_TOTAL_MEMORY_GB", 8))
    min_cpu_available_memory_gb = float(getattr(settings, "MEASURE_CONFIG", {}).get("MIN_CPU_AVAILABLE_MEMORY_GB", 2))

    status = {
        "preferred_device": preferred_device,
        "resolved_device": resolved_device,
        "cuda_available": bool(torch.cuda.is_available()),
        "device_count": int(torch.cuda.device_count()),
        "total_memory_gb": _bytes_to_gib(virtual_memory.total),
        "available_memory_gb": _bytes_to_gib(virtual_memory.available),
        "swap_total_gb": _bytes_to_gib(swap_memory.total),
        "swap_free_gb": _bytes_to_gib(swap_memory.free),
        "min_cpu_total_memory_gb": min_cpu_total_memory_gb,
        "min_cpu_available_memory_gb": min_cpu_available_memory_gb,
        "supported": True,
        "reason": None,
    }

    if resolved_device == "cpu":
        if status["total_memory_gb"] < min_cpu_total_memory_gb:
            status["supported"] = False
            status["reason"] = (
                "diameter runtime disabled on cpu-only host: "
                f"total memory {status['total_memory_gb']} GiB is below required {min_cpu_total_memory_gb} GiB"
            )
        elif status["available_memory_gb"] < min_cpu_available_memory_gb:
            status["supported"] = False
            status["reason"] = (
                "diameter runtime disabled on cpu-only host: "
                f"available memory {status['available_memory_gb']} GiB is below required {min_cpu_available_memory_gb} GiB"
            )

    return status


def ensure_diameter_runtime_supported(config: MeasureConfig) -> Dict[str, Any]:
    status = get_diameter_runtime_host_status(config)
    if not status["supported"]:
        raise MeasurementEnvironmentError(status["reason"] or "diameter runtime is unsupported on this host")
    return status


class MonsterRuntime:
    def __init__(self, runtime_dir: Path, restore_ckpt: Path, preferred_device: str = "auto"):
        self.runtime_dir = runtime_dir
        self.restore_ckpt = restore_ckpt
        self.preferred_device = preferred_device
        self.device = self._resolve_device(preferred_device)
        self._load_lock = threading.Lock()
        self._model: Optional[nn.Module] = None
        self._padder_cls = None

    @staticmethod
    def _resolve_device(preferred_device: str) -> torch.device:
        return torch.device(_resolve_measure_device(preferred_device))

    @staticmethod
    def is_cuda_oom(exc: Exception) -> bool:
        oom_types = []
        for candidate in (getattr(torch, "OutOfMemoryError", None), getattr(torch.cuda, "OutOfMemoryError", None)):
            if isinstance(candidate, type):
                oom_types.append(candidate)
        if oom_types and isinstance(exc, tuple(oom_types)):
            return True

        message = str(exc).lower()
        return "out of memory" in message and ("cuda" in message or "acceleratorerror" in exc.__class__.__name__.lower())

    def release_device_cache(self) -> None:
        if self.device.type == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()

    @staticmethod
    def _default_args() -> SimpleNamespace:
        return SimpleNamespace(
            encoder="vitl",
            hidden_dims=[128, 128, 128],
            corr_implementation="reg",
            shared_backbone=False,
            corr_levels=2,
            corr_radius=4,
            n_downsample=2,
            slow_fast_gru=False,
            n_gru_layers=3,
            max_disp=192,
        )

    def _prepare_imports(self) -> None:
        runtime_paths = [
            self.runtime_dir,
            self.runtime_dir / "Depth-Anything-V2-list3",
        ]
        for path in runtime_paths:
            path_str = str(path)
            if path_str not in sys.path:
                sys.path.insert(0, path_str)

    def _load_model(self) -> None:
        self._prepare_imports()
        from core.monster import Monster
        from core.utils.utils import InputPadder

        add_safe_globals([argparse.Namespace, SimpleNamespace])

        model = Monster(self._default_args())
        model.to(self.device)

        state = torch.load(str(self.restore_ckpt), map_location="cpu", weights_only=True)
        state_dict = state.get("state_dict", state)
        normalized_state = {}
        for key, value in state_dict.items():
            normalized_state[key.replace("module.", "", 1)] = value
        model.load_state_dict(normalized_state, strict=False)
        model.eval()

        self._model = model
        self._padder_cls = InputPadder

    def ensure_ready(self) -> None:
        if self._model is not None and self._padder_cls is not None:
            return

        with self._load_lock:
            if self._model is None or self._padder_cls is None:
                self._load_model()

    def status(self) -> Dict[str, object]:
        return {
            "preferred_device": self.preferred_device,
            "device_type": self.device.type,
            "torch_version": torch.__version__,
            "torch_cuda_version": torch.version.cuda,
            "cuda_available": bool(torch.cuda.is_available()),
            "device_count": int(torch.cuda.device_count()),
            "devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
            "model_loaded": self._model is not None,
            "checkpoint_path": str(self.restore_ckpt),
        }

    def infer_disparity(self, left_bgr: np.ndarray, right_bgr: np.ndarray, valid_iters: int) -> np.ndarray:
        self.ensure_ready()
        if self._model is None or self._padder_cls is None:
            raise RuntimeError("MonSter runtime is not initialized")

        left_rgb = cv2.cvtColor(left_bgr, cv2.COLOR_BGR2RGB)
        right_rgb = cv2.cvtColor(right_bgr, cv2.COLOR_BGR2RGB)

        image1 = torch.from_numpy(left_rgb).permute(2, 0, 1).float()[None].to(self.device)
        image2 = torch.from_numpy(right_rgb).permute(2, 0, 1).float()[None].to(self.device)

        if image1.shape[-2:] != image2.shape[-2:]:
            raise ValueError(f"left/right image size mismatch: {image1.shape[-2:]} vs {image2.shape[-2:]}")

        padder = self._padder_cls(image1.shape, divis_by=32)
        image1, image2 = padder.pad(image1, image2)

        with torch.no_grad():
            disp = self._model(image1, image2, iters=valid_iters, test_mode=True)

        disp = padder.unpad(disp)[0, 0].float().cpu().numpy().astype(np.float32)
        return disp


class FruitDiameterService:
    def __init__(self, config: MeasureConfig):
        self.config = config
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.runtime = MonsterRuntime(
            config.monster_dir,
            config.restore_ckpt,
            preferred_device=config.preferred_device,
        )
        self._cpu_runtime: Optional[MonsterRuntime] = None
        self._prefer_cpu_runtime = False
        self._calib_cache: Dict[str, Dict[str, Any]] = {}
        self._rectify_cache: Dict[Tuple[str, int, int], Tuple[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray], np.ndarray]] = {}

    def _get_cpu_runtime(self) -> MonsterRuntime:
        if self._cpu_runtime is None:
            self._cpu_runtime = MonsterRuntime(
                self.config.monster_dir,
                self.config.restore_ckpt,
                preferred_device="cpu",
            )
        return self._cpu_runtime

    def _infer_disparity_with_fallback(
        self,
        left_bgr: np.ndarray,
        right_bgr: np.ndarray,
        valid_iters: int,
    ) -> Tuple[np.ndarray, str, bool, Optional[str]]:
        if self._prefer_cpu_runtime and self.config.allow_cpu_fallback:
            disp = self._get_cpu_runtime().infer_disparity(left_bgr, right_bgr, valid_iters)
            return disp, "cpu", True, "cuda out of memory detected previously; using cpu fallback"

        try:
            disp = self.runtime.infer_disparity(left_bgr, right_bgr, valid_iters)
            return disp, self.runtime.device.type, False, None
        except Exception as exc:
            if (
                self.runtime.device.type != "cuda"
                or not self.config.allow_cpu_fallback
                or not MonsterRuntime.is_cuda_oom(exc)
            ):
                raise

            self._prefer_cpu_runtime = True
            self.runtime.release_device_cache()
            gc.collect()

            disp = self._get_cpu_runtime().infer_disparity(left_bgr, right_bgr, valid_iters)
            return disp, "cpu", True, "cuda out of memory; switched to cpu fallback"

    @staticmethod
    def _imwrite_unicode(path: Path, image: np.ndarray) -> None:
        suffix = path.suffix or ".png"
        ok, encoded = cv2.imencode(suffix, image)
        if not ok:
            raise RuntimeError(f"failed to encode image: {path}")
        encoded.tofile(str(path))

    @staticmethod
    def _load_uploaded_image(uploaded_file) -> np.ndarray:
        uploaded_file.seek(0)
        pil_image = Image.open(uploaded_file).convert("RGB")
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    @staticmethod
    def _load_path_image(image_path: str) -> np.ndarray:
        data = np.fromfile(image_path, dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"unable to read image: {image_path}")
        return image

    def _resolve_image(self, uploaded_file=None, image_path: Optional[str] = None) -> Tuple[np.ndarray, str]:
        if uploaded_file is not None:
            return self._load_uploaded_image(uploaded_file), uploaded_file.name
        if image_path:
            path = Path(image_path)
            if not path.is_file():
                raise FileNotFoundError(f"image path not found: {image_path}")
            return self._load_path_image(str(path)), str(path)
        raise ValueError("missing image input")

    @staticmethod
    def _save_disp_vis(path: Path, disp: np.ndarray) -> None:
        normalized = disp.copy()
        normalized[~np.isfinite(normalized)] = 0.0
        denom = float(normalized.max() - normalized.min())
        if denom <= 1e-6:
            denom = 1.0
        normalized = (normalized - normalized.min()) / denom
        color = cv2.applyColorMap((normalized * 255.0).astype(np.uint8), cv2.COLORMAP_JET)
        FruitDiameterService._imwrite_unicode(path, color)

    @staticmethod
    def _parse_calibration(npz_path: Path) -> Dict[str, Any]:
        z = np.load(str(npz_path), allow_pickle=False)
        kl = z["KL"]
        dl = z["DL"]
        kr = z["KR"]
        dr = z["DR"]
        r = z["R"]
        t = z["T"]

        if "image_size" in z.files:
            width, height = [int(v) for v in z["image_size"]]
        elif "img_size" in z.files:
            width, height = [int(v) for v in z["img_size"]]
        elif "w" in z.files and "h" in z.files:
            width, height = int(z["w"]), int(z["h"])
        else:
            width, height = None, None

        baseline = float(abs(np.ravel(t)[0])) if np.ravel(t).size else 0.0
        return {
            "KL": kl,
            "DL": dl,
            "KR": kr,
            "DR": dr,
            "R": r,
            "T": t,
            "width": width,
            "height": height,
            "summary": {
                "fx": float(kl[0, 0]),
                "fy": float(kl[1, 1]),
                "cx": float(kl[0, 2]),
                "cy": float(kl[1, 2]),
                "baseline": baseline,
                "baseline_unit": "mm",
                "q_exists": True,
                "native_width": width,
                "native_height": height,
            },
        }

    @staticmethod
    def _scale_camera_matrix(matrix: np.ndarray, scale_x: float, scale_y: float) -> np.ndarray:
        scaled = matrix.astype(np.float64).copy()
        scaled[0, 0] *= scale_x
        scaled[1, 1] *= scale_y
        scaled[0, 2] *= scale_x
        scaled[1, 2] *= scale_y
        return scaled

    def _load_calibration(self, calib_path: Path) -> Dict[str, Any]:
        cache_key = str(calib_path.resolve())
        if cache_key not in self._calib_cache:
            self._calib_cache[cache_key] = self._parse_calibration(calib_path)
        return self._calib_cache[cache_key]

    def _get_rectify_data(self, calib_path: Path, width: int, height: int) -> Tuple[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray], np.ndarray]:
        key = (str(calib_path.resolve()), width, height)
        if key in self._rectify_cache:
            return self._rectify_cache[key]

        calib = self._load_calibration(calib_path)
        size = (width, height)
        native_width = calib.get("width")
        native_height = calib.get("height")
        if native_width and native_height and (native_width != width or native_height != height):
            scale_x = float(width) / float(native_width)
            scale_y = float(height) / float(native_height)
            kl = self._scale_camera_matrix(calib["KL"], scale_x, scale_y)
            kr = self._scale_camera_matrix(calib["KR"], scale_x, scale_y)
        else:
            kl = calib["KL"]
            kr = calib["KR"]

        r1, r2, p1, p2, q, _, _ = cv2.stereoRectify(
            kl,
            calib["DL"],
            kr,
            calib["DR"],
            size,
            calib["R"],
            calib["T"],
            flags=cv2.CALIB_ZERO_DISPARITY,
            alpha=0,
        )
        map_l1, map_l2 = cv2.initUndistortRectifyMap(kl, calib["DL"], r1, p1, size, cv2.CV_32FC1)
        map_r1, map_r2 = cv2.initUndistortRectifyMap(kr, calib["DR"], r2, p2, size, cv2.CV_32FC1)
        self._rectify_cache[key] = ((map_l1, map_l2), (map_r1, map_r2), q)
        return self._rectify_cache[key]

    def _resolve_calib_path(self, calib_path: Optional[str]) -> Path:
        path = Path(calib_path) if calib_path else self.config.calib_npz
        if not path.exists():
            raise FileNotFoundError(f"calibration file not found: {path}")
        return path

    def _resolve_ckpt_path(self, ckpt_path: Optional[str]) -> Path:
        path = Path(ckpt_path) if ckpt_path else self.config.restore_ckpt
        if not path.exists():
            raise FileNotFoundError(f"checkpoint file not found: {path}")
        return path

    @staticmethod
    def _media_url(relative_path: Optional[str]) -> Optional[str]:
        if not relative_path:
            return None
        normalized_path = relative_path.replace("\\", "/")
        return f"{settings.MEDIA_URL.rstrip('/')}/{normalized_path}"

    @staticmethod
    def _relative_media_path(absolute_path: Path) -> Optional[str]:
        try:
            return str(absolute_path.resolve().relative_to(Path(settings.MEDIA_ROOT).resolve())).replace("\\", "/")
        except ValueError:
            return None

    def _job_dir(self, inference_id: str) -> Path:
        return self.config.output_dir / inference_id

    def _manifest_path(self, inference_id: str) -> Path:
        return self._job_dir(inference_id) / "manifest.json"

    def _result_json_path(self, job_dir: Path, slug: str) -> Path:
        return job_dir / f"{slug}.json"

    def _result_csv_path(self, job_dir: Path, slug: str) -> Path:
        return job_dir / f"{slug}.csv"

    def _load_manifest(self, inference_id: str) -> Dict[str, Any]:
        manifest_path = self._manifest_path(inference_id)
        if not manifest_path.is_file():
            raise FileNotFoundError(f"inference result not found: {inference_id}")
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    @staticmethod
    def _serialize_detection(index: int, label: str, confidence: float, bbox: List[int]) -> Dict[str, Any]:
        return {
            "index": index,
            "label": label,
            "confidence": round(float(confidence), 6),
            "bbox": [int(v) for v in bbox],
        }

    @staticmethod
    def _serialize_point(x: int, y: int, disp: float, point_3d: np.ndarray) -> Dict[str, Any]:
        z_m = float(point_3d[2]) / 1000.0
        return {
            "x": int(x),
            "y": int(y),
            "disp": round(float(disp), 6),
            "depth_m": round(z_m, 6),
            "point_3d": {
                "X": round(float(point_3d[0]) / 1000.0, 6),
                "Y": round(float(point_3d[1]) / 1000.0, 6),
                "Z": round(z_m, 6),
            },
        }

    @staticmethod
    def _distance_to_unit(distance_mm: float, unit: str) -> float:
        if unit == "m":
            return distance_mm / 1000.0
        return distance_mm

    @staticmethod
    def _read_disp(path: Path) -> np.ndarray:
        disp = np.load(str(path))
        return disp.astype(np.float32)

    @staticmethod
    def _median_disp(disp: np.ndarray, x: int, y: int, patch_size: int) -> float:
        h, w = disp.shape[:2]
        radius = max(1, patch_size // 2)
        x0, x1 = max(0, x - radius), min(w, x + radius + 1)
        y0, y1 = max(0, y - radius), min(h, y + radius + 1)
        patch = disp[y0:y1, x0:x1]
        valid = patch[np.isfinite(patch)]
        if valid.size == 0:
            return float("nan")
        value = float(np.median(valid))
        if value <= 0:
            return float("nan")
        return value

    @staticmethod
    def _bbox_points(bbox: List[int], orientation: str = "horizontal") -> Tuple[Dict[str, int], Dict[str, int]]:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x_center = int(round((x1 + x2) / 2.0))
        y_center = int(round((y1 + y2) / 2.0))
        if orientation == "vertical":
            return {"x": x_center, "y": y1}, {"x": x_center, "y": y2}
        return {"x": x1, "y": y_center}, {"x": x2, "y": y_center}

    def _measure_points(self, disp: np.ndarray, q: np.ndarray, point1: Dict[str, int], point2: Dict[str, int], patch_size: int) -> Dict[str, Any]:
        h, w = disp.shape[:2]

        def clamp(point: Dict[str, int]) -> Tuple[int, int]:
            return (
                int(np.clip(point["x"], 0, w - 1)),
                int(np.clip(point["y"], 0, h - 1)),
            )

        x1, y1 = clamp(point1)
        x2, y2 = clamp(point2)

        d1 = self._median_disp(disp, x1, y1, patch_size)
        d2 = self._median_disp(disp, x2, y2, patch_size)
        if not (np.isfinite(d1) and np.isfinite(d2)):
            raise ValueError("invalid disparity at one or both measurement points")

        disp_copy = disp.astype(np.float32).copy()
        disp_copy[y1, x1] = d1
        disp_copy[y2, x2] = d2
        pts3d = cv2.reprojectImageTo3D(disp_copy, q)

        p1_3d = pts3d[y1, x1]
        p2_3d = pts3d[y2, x2]
        if not np.all(np.isfinite(np.concatenate([p1_3d, p2_3d]))):
            raise ValueError("failed to reconstruct 3d points")

        distance_mm = float(np.linalg.norm(p1_3d - p2_3d))
        return {
            "distance_mm": distance_mm,
            "point1": self._serialize_point(x1, y1, d1, p1_3d),
            "point2": self._serialize_point(x2, y2, d2, p2_3d),
        }

    @staticmethod
    def _draw_measurement(image: np.ndarray, point1: Dict[str, Any], point2: Dict[str, Any], label: str, color: Tuple[int, int, int]) -> None:
        p1 = (int(point1["x"]), int(point1["y"]))
        p2 = (int(point2["x"]), int(point2["y"]))
        cv2.circle(image, p1, 5, color, -1)
        cv2.circle(image, p2, 5, color, -1)
        cv2.line(image, p1, p2, color, 2)
        cv2.putText(image, label, (p1[0], max(24, p1[1] - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA)

    @staticmethod
    def _draw_bbox(image: np.ndarray, bbox: List[int], label: str, color: Tuple[int, int, int]) -> None:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.putText(image, label, (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

    @staticmethod
    def _stats(values: List[float]) -> Dict[str, Optional[float]]:
        if not values:
            return {
                "avg_distance_mm": None,
                "min_distance_mm": None,
                "max_distance_mm": None,
                "avg_diameter_mm": None,
                "min_diameter_mm": None,
                "max_diameter_mm": None,
            }
        stats = {
            "avg_distance_mm": round(float(np.mean(values)), 6),
            "min_distance_mm": round(float(np.min(values)), 6),
            "max_distance_mm": round(float(np.max(values)), 6),
        }
        stats["avg_diameter_mm"] = stats["avg_distance_mm"]
        stats["min_diameter_mm"] = stats["min_distance_mm"]
        stats["max_diameter_mm"] = stats["max_distance_mm"]
        return stats

    @classmethod
    def _axis_stats(cls, horizontal_values: List[float], vertical_values: List[float]) -> Dict[str, Any]:
        horizontal_stats = cls._stats(horizontal_values)
        vertical_stats = cls._stats(vertical_values)
        return {
            **horizontal_stats,
            "horizontal": horizontal_stats,
            "vertical": vertical_stats,
        }

    def run_inference(
        self,
        *,
        yolo_model,
        left_file=None,
        right_file=None,
        left_image_path: Optional[str] = None,
        right_image_path: Optional[str] = None,
        calib_path: Optional[str] = None,
        ckpt_path: Optional[str] = None,
        valid_iters: Optional[int] = None,
        save_color: bool = True,
        save_npy: bool = True,
        detect_conf: Optional[float] = None,
        request_id: Optional[str] = None,
        return_debug: bool = False,
    ) -> Dict[str, Any]:
        calib_file = self._resolve_calib_path(calib_path)
        ckpt_file = self._resolve_ckpt_path(ckpt_path)
        if ckpt_file.resolve() != self.config.restore_ckpt.resolve():
            raise ValueError("custom ckpt_path is not supported by the in-process runtime")

        left_bgr, left_source = self._resolve_image(left_file, left_image_path)
        right_bgr, right_source = self._resolve_image(right_file, right_image_path)

        if left_bgr.shape[:2] != right_bgr.shape[:2]:
            right_bgr = cv2.resize(right_bgr, (left_bgr.shape[1], left_bgr.shape[0]), interpolation=cv2.INTER_AREA)

        calib = self._load_calibration(calib_file)
        target_width = left_bgr.shape[1]
        target_height = left_bgr.shape[0]

        (map_l1, map_l2), (map_r1, map_r2), _ = self._get_rectify_data(calib_file, target_width, target_height)
        left_rect = cv2.remap(left_bgr, map_l1, map_l2, interpolation=cv2.INTER_LINEAR)
        right_rect = cv2.remap(right_bgr, map_r1, map_r2, interpolation=cv2.INTER_LINEAR)

        inference_id = uuid.uuid4().hex
        job_dir = self._job_dir(inference_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        left_input_path = job_dir / "left_input.png"
        right_input_path = job_dir / "right_input.png"
        left_rect_path = job_dir / "left_rectified.png"
        right_rect_path = job_dir / "right_rectified.png"
        disp_npy_path = job_dir / "disp.npy"
        disp_vis_path = job_dir / "disp_color.png"
        detect_vis_path = job_dir / "left_detected.png"

        self._imwrite_unicode(left_input_path, left_bgr)
        self._imwrite_unicode(right_input_path, right_bgr)
        self._imwrite_unicode(left_rect_path, left_rect)
        self._imwrite_unicode(right_rect_path, right_rect)

        infer_start = time.perf_counter()
        disp, runtime_device, used_cpu_fallback, runtime_warning = self._infer_disparity_with_fallback(
            left_rect,
            right_rect,
            valid_iters or self.config.infer_valid_iters,
        )
        time_ms = int(round((time.perf_counter() - infer_start) * 1000))

        detections: List[Dict[str, Any]] = []
        detect_canvas = left_rect.copy()
        detect_threshold = detect_conf if detect_conf is not None else self.config.default_conf
        predict_kwargs = {
            "source": Image.fromarray(cv2.cvtColor(left_rect, cv2.COLOR_BGR2RGB)),
            "conf": detect_threshold,
            "save": False,
            "verbose": False,
        }
        if runtime_device == "cpu":
            predict_kwargs["device"] = "cpu"
        yolo_results = yolo_model.predict(**predict_kwargs)
        if yolo_results:
            result = yolo_results[0]
            boxes = result.boxes
            if boxes is not None and len(boxes) > 0:
                for index, box in enumerate(boxes):
                    bbox = [int(v) for v in box.xyxy[0].tolist()]
                    label = result.names[int(box.cls[0].item())]
                    confidence = float(box.conf[0].item())
                    detections.append(self._serialize_detection(index, label, confidence, bbox))
                    self._draw_bbox(detect_canvas, bbox, f"{index + 1}. {label} {confidence:.2f}", (0, 255, 0))

        np.save(str(disp_npy_path), disp.astype(np.float32))
        if save_color:
            self._save_disp_vis(disp_vis_path, disp)
        self._imwrite_unicode(detect_vis_path, detect_canvas)

        manifest = {
            "inference_id": inference_id,
            "request_id": request_id,
            "left_image_path": str(left_input_path.resolve()),
            "right_image_path": str(right_input_path.resolve()),
            "rectified_left_path": str(left_rect_path.resolve()),
            "rectified_right_path": str(right_rect_path.resolve()),
            "disp_npy_path": str(disp_npy_path.resolve()),
            "disp_vis_path": str(disp_vis_path.resolve()) if save_color else None,
            "detect_vis_path": str(detect_vis_path.resolve()),
            "image_width": target_width,
            "image_height": target_height,
            "calib_path": str(calib_file.resolve()),
            "ckpt_path": str(ckpt_file.resolve()),
            "calib_summary": calib["summary"],
            "valid_iters": valid_iters or self.config.infer_valid_iters,
            "runtime_device": runtime_device,
            "used_cpu_fallback": used_cpu_fallback,
            "runtime_warning": runtime_warning,
            "detections": detections,
        }
        self._manifest_path(inference_id).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        response = {
            "success": True,
            "message": "inference ok",
            "inference_id": inference_id,
            "left_image_path": manifest["left_image_path"],
            "right_image_path": manifest["right_image_path"],
            "rectified_left_path": manifest["rectified_left_path"],
            "rectified_right_path": manifest["rectified_right_path"],
            "disp_npy_path": manifest["disp_npy_path"],
            "disp_vis_path": manifest["disp_vis_path"],
            "depth_npy_path": None,
            "image_width": target_width,
            "image_height": target_height,
            "calib_path": manifest["calib_path"],
            "ckpt_path": manifest["ckpt_path"],
            "calib_summary": manifest["calib_summary"],
            "time_ms": time_ms,
            "runtime_device": runtime_device,
            "used_cpu_fallback": used_cpu_fallback,
            "runtime_warning": runtime_warning,
            "detections": detections,
            "detect_vis_path": manifest["detect_vis_path"],
            "disp_vis_url": self._media_url(self._relative_media_path(disp_vis_path) if save_color else None),
            "detect_vis_url": self._media_url(self._relative_media_path(detect_vis_path)),
            "request_id": request_id,
        }
        if return_debug:
            response["debug"] = {
                "left_source": left_source,
                "right_source": right_source,
                "valid_iters": manifest["valid_iters"],
                "detect_conf": detect_threshold,
                "runtime_device": runtime_device,
                "used_cpu_fallback": used_cpu_fallback,
            }
        return response

    def measure_distance(
        self,
        *,
        inference_id: Optional[str] = None,
        disp_npy_path: Optional[str] = None,
        calib_path: Optional[str] = None,
        point1: Optional[Dict[str, int]] = None,
        point2: Optional[Dict[str, int]] = None,
        patch_size: Optional[int] = None,
        distance_unit: str = "mm",
        save_annotated: bool = True,
        request_id: Optional[str] = None,
        target_index: Optional[int] = None,
        measure_all_targets: bool = False,
        bbox: Optional[List[int]] = None,
        return_debug: bool = False,
    ) -> Dict[str, Any]:
        manifest = self._load_manifest(inference_id) if inference_id else None
        effective_disp_path = Path(disp_npy_path) if disp_npy_path else Path(manifest["disp_npy_path"]) if manifest else None
        if effective_disp_path is None or not effective_disp_path.is_file():
            raise FileNotFoundError("disp_npy_path not found")

        effective_calib_path = self._resolve_calib_path(calib_path or (manifest["calib_path"] if manifest else None))
        disp = self._read_disp(effective_disp_path)
        q = self._get_rectify_data(effective_calib_path, disp.shape[1], disp.shape[0])[2]
        actual_patch = int(patch_size or self.config.patch_size)

        if point1 and point2:
            mode = "points"
            targets_to_measure: List[Dict[str, Any]] = []
        elif bbox is not None:
            mode = "bbox"
            targets_to_measure = [{"index": target_index, "label": None, "confidence": None, "bbox": bbox}]
        else:
            mode = "targets"
            detections = manifest.get("detections", []) if manifest else []
            if target_index is not None:
                if target_index < 0 or target_index >= len(detections):
                    raise ValueError("target_index out of range")
                targets_to_measure = [detections[target_index]]
            else:
                if not measure_all_targets:
                    measure_all_targets = True
                if not detections:
                    raise ValueError("no fruit detected by YOLO; place a fruit clearly in the left camera view and try again")
                targets_to_measure = detections

        left_rect_path = Path(manifest["rectified_left_path"]) if manifest and manifest.get("rectified_left_path") else None
        annotated_canvas = self._load_path_image(str(left_rect_path)) if save_annotated and left_rect_path and left_rect_path.is_file() else None

        if mode == "points":
            result = self._measure_points(disp, q, point1, point2, actual_patch)
            display_distance = round(self._distance_to_unit(result["distance_mm"], distance_unit), 6)

            annotated_path = None
            if annotated_canvas is not None:
                self._draw_measurement(
                    annotated_canvas,
                    result["point1"],
                    result["point2"],
                    f"{display_distance:.2f} {distance_unit}",
                    (0, 255, 0),
                )
                annotated_path = self._job_dir(inference_id) / "measure_points.png" if inference_id else None
                if annotated_path is not None:
                    self._imwrite_unicode(annotated_path, annotated_canvas)

            payload = {
                "success": True,
                "message": "measure ok",
                "inference_id": inference_id,
                "distance": display_distance,
                "distance_unit": distance_unit,
                "point1": result["point1"],
                "point2": result["point2"],
                "annotated_image_path": str(annotated_path.resolve()) if annotated_path else None,
                "annotated_image_url": self._media_url(self._relative_media_path(annotated_path)) if annotated_path else None,
                "result_json_path": None,
                "csv_path": None,
                "calib_path": str(effective_calib_path.resolve()),
                "disp_npy_path": str(effective_disp_path.resolve()),
                "patch_size": actual_patch,
                "request_id": request_id,
            }
            if return_debug:
                payload["debug"] = {"mode": mode}
            return payload

        target_results: List[Dict[str, Any]] = []
        horizontal_distances_mm: List[float] = []
        vertical_distances_mm: List[float] = []
        valid_target_count = 0
        for measured in targets_to_measure:
            current_bbox = [int(v) for v in measured["bbox"]]
            item: Dict[str, Any] = {
                "index": measured.get("index"),
                "label": measured.get("label"),
                "confidence": measured.get("confidence"),
                "bbox": current_bbox,
            }
            axis_results: Dict[str, Dict[str, Any]] = {}
            axis_has_success = False
            for orientation, color, short_label in (
                ("horizontal", (255, 0, 0), "H"),
                ("vertical", (0, 165, 255), "V"),
            ):
                p1, p2 = self._bbox_points(current_bbox, orientation=orientation)
                axis_item: Dict[str, Any] = {
                    "orientation": orientation,
                    "distance": None,
                    "distance_unit": distance_unit,
                    "distance_mm": None,
                    "point1": p1,
                    "point2": p2,
                }
                try:
                    measurement = self._measure_points(disp, q, p1, p2, actual_patch)
                    distance_mm = measurement["distance_mm"]
                    axis_item.update(
                        {
                            "distance": round(self._distance_to_unit(distance_mm, distance_unit), 6),
                            "distance_mm": round(distance_mm, 6),
                            "point1": measurement["point1"],
                            "point2": measurement["point2"],
                            "status": "ok",
                        }
                    )
                    axis_has_success = True
                    if orientation == "horizontal":
                        horizontal_distances_mm.append(distance_mm)
                    else:
                        vertical_distances_mm.append(distance_mm)
                    if annotated_canvas is not None:
                        label = measured.get("label") or "target"
                        self._draw_measurement(
                            annotated_canvas,
                            measurement["point1"],
                            measurement["point2"],
                            f"{label} {short_label} {axis_item['distance']:.2f} {distance_unit}",
                            color,
                        )
                except Exception as exc:
                    axis_item["status"] = str(exc)
                axis_results[orientation] = axis_item

            primary_axis = axis_results["horizontal"]
            item.update(
                {
                    "distance": primary_axis.get("distance"),
                    "distance_unit": primary_axis.get("distance_unit", distance_unit),
                    "distance_mm": primary_axis.get("distance_mm"),
                    "point1": primary_axis.get("point1"),
                    "point2": primary_axis.get("point2"),
                    "status": primary_axis.get("status"),
                    "diameter_axes": axis_results,
                }
            )
            if axis_has_success:
                valid_target_count += 1
            if annotated_canvas is not None:
                label = measured.get("label") or "target"
                self._draw_bbox(annotated_canvas, current_bbox, label, (0, 255, 0))
            target_results.append(item)

        job_dir = self._job_dir(inference_id) if inference_id else effective_disp_path.parent
        annotated_path = job_dir / "measure_targets.png" if save_annotated and annotated_canvas is not None else None
        result_json_path = self._result_json_path(job_dir, "measure_targets")
        csv_path = self._result_csv_path(job_dir, "measure_targets")

        if annotated_path is not None and annotated_canvas is not None:
            self._imwrite_unicode(annotated_path, annotated_canvas)

        result_json_path.write_text(
            json.dumps(
                {
                    "inference_id": inference_id,
                    "request_id": request_id,
                    "targets": target_results,
                    "measurement_axes": ["horizontal", "vertical"],
                    "valid_measurements": valid_target_count,
                    "valid_measurements_by_axis": {
                        "horizontal": len(horizontal_distances_mm),
                        "vertical": len(vertical_distances_mm),
                    },
                    "statistics": self._axis_stats(horizontal_distances_mm, vertical_distances_mm),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        with csv_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(
                [
                    "index",
                    "label",
                    "confidence",
                    "bbox",
                    "horizontal_distance",
                    "horizontal_distance_mm",
                    "horizontal_status",
                    "vertical_distance",
                    "vertical_distance_mm",
                    "vertical_status",
                    "distance_unit",
                ]
            )
            for item in target_results:
                horizontal_axis = (item.get("diameter_axes") or {}).get("horizontal") or {}
                vertical_axis = (item.get("diameter_axes") or {}).get("vertical") or {}
                writer.writerow(
                    [
                        item.get("index"),
                        item.get("label"),
                        item.get("confidence"),
                        json.dumps(item.get("bbox", []), ensure_ascii=False),
                        horizontal_axis.get("distance"),
                        horizontal_axis.get("distance_mm"),
                        horizontal_axis.get("status"),
                        vertical_axis.get("distance"),
                        vertical_axis.get("distance_mm"),
                        vertical_axis.get("status"),
                        item.get("distance_unit"),
                    ]
                )

        response = {
            "success": True,
            "message": "measure ok",
            "inference_id": inference_id,
            "targets": target_results,
            "total_targets": len(target_results),
            "valid_measurements": valid_target_count,
            "valid_measurements_by_axis": {
                "horizontal": len(horizontal_distances_mm),
                "vertical": len(vertical_distances_mm),
            },
            "measurement_axes": ["horizontal", "vertical"],
            "statistics": self._axis_stats(horizontal_distances_mm, vertical_distances_mm),
            "annotated_image_path": str(annotated_path.resolve()) if annotated_path else None,
            "annotated_image_url": self._media_url(self._relative_media_path(annotated_path)) if annotated_path else None,
            "result_json_path": str(result_json_path.resolve()),
            "csv_path": str(csv_path.resolve()),
            "calib_path": str(effective_calib_path.resolve()),
            "disp_npy_path": str(effective_disp_path.resolve()),
            "patch_size": actual_patch,
            "distance_unit": distance_unit,
            "request_id": request_id,
        }
        if return_debug:
            response["debug"] = {"mode": mode}
        return response

    def run_full_measurement(
        self,
        *,
        yolo_model,
        image_file=None,
        left_file=None,
        right_file=None,
        split_mode: str = "left_right",
        conf: Optional[float] = None,
        save_vis: bool = True,
    ) -> Dict[str, Any]:
        if image_file is not None:
            stereo_bgr = self._load_uploaded_image(image_file)
            height, width = stereo_bgr.shape[:2]
            if split_mode == "top_bottom":
                left_bgr = stereo_bgr[: height // 2, :]
                right_bgr = stereo_bgr[height // 2 :, :]
            else:
                left_bgr = stereo_bgr[:, : width // 2]
                right_bgr = stereo_bgr[:, width // 2 :]

            infer_result = self.run_inference(
                yolo_model=yolo_model,
                left_file=SimpleImageWrapper(left_bgr, "left_split.png"),
                right_file=SimpleImageWrapper(right_bgr, "right_split.png"),
                save_color=save_vis,
                detect_conf=conf,
            )
        else:
            infer_result = self.run_inference(
                yolo_model=yolo_model,
                left_file=left_file,
                right_file=right_file,
                save_color=save_vis,
                detect_conf=conf,
            )

        if not infer_result.get("detections"):
            empty_stats = self._axis_stats([], [])
            empty_measurement = {
                "success": True,
                "message": "no fruit detected",
                "inference_id": infer_result["inference_id"],
                "targets": [],
                "total_targets": 0,
                "valid_measurements": 0,
                "valid_measurements_by_axis": {
                    "horizontal": 0,
                    "vertical": 0,
                },
                "measurement_axes": ["horizontal", "vertical"],
                "statistics": empty_stats,
                "annotated_image_path": infer_result.get("detect_vis_path"),
                "annotated_image_url": infer_result.get("detect_vis_url"),
                "result_json_path": None,
                "csv_path": None,
                "calib_path": infer_result["calib_path"],
                "disp_npy_path": infer_result["disp_npy_path"],
                "patch_size": self.config.patch_size,
                "runtime_device": infer_result.get("runtime_device"),
                "used_cpu_fallback": infer_result.get("used_cpu_fallback", False),
                "runtime_warning": infer_result.get("runtime_warning"),
            }
            return {
                "status": "success",
                "message": "未检测到水果，请调整水果位置后重试",
                "inference": infer_result,
                "measurement": empty_measurement,
                "targets": [],
                "total_targets": 0,
                "valid_measurements": 0,
                "valid_measurements_by_axis": {
                    "horizontal": 0,
                    "vertical": 0,
                },
                "measurement_axes": ["horizontal", "vertical"],
                "statistics": empty_stats,
                "visualization_url": infer_result.get("detect_vis_url"),
                "visualization_file": self._relative_media_path(Path(infer_result["detect_vis_path"])) if infer_result.get("detect_vis_path") else None,
                "runtime_device": infer_result.get("runtime_device"),
                "used_cpu_fallback": infer_result.get("used_cpu_fallback", False),
                "runtime_warning": infer_result.get("runtime_warning"),
            }

        measure_result = self.measure_distance(
            inference_id=infer_result["inference_id"],
            measure_all_targets=True,
            save_annotated=save_vis,
        )
        return {
            "status": "success",
            "message": "果径测量完成",
            "inference": infer_result,
            "measurement": measure_result,
            "targets": measure_result["targets"],
            "total_targets": measure_result["total_targets"],
            "valid_measurements": measure_result["valid_measurements"],
            "valid_measurements_by_axis": measure_result["valid_measurements_by_axis"],
            "measurement_axes": measure_result["measurement_axes"],
            "statistics": measure_result["statistics"],
            "diameter_statistics": measure_result["statistics"],
            "visualization_url": measure_result["annotated_image_url"],
            "visualization_file": self._relative_media_path(Path(measure_result["annotated_image_path"])) if measure_result.get("annotated_image_path") else None,
            "runtime_device": infer_result.get("runtime_device"),
            "used_cpu_fallback": infer_result.get("used_cpu_fallback", False),
            "runtime_warning": infer_result.get("runtime_warning"),
        }


class SimpleImageWrapper(io.BytesIO):
    def __init__(self, image_bgr: np.ndarray, name: str):
        ok, buffer = cv2.imencode(".png", image_bgr)
        if not ok:
            raise RuntimeError("failed to encode split image")
        super().__init__(buffer.tobytes())
        self.name = name


def build_measure_service() -> FruitDiameterService:
    cfg = settings.MEASURE_CONFIG
    config = MeasureConfig(
        monster_dir=Path(cfg["MONSTER_DIR"]),
        calib_npz=Path(cfg["CALIB_NPZ"]),
        restore_ckpt=Path(cfg["RESTORE_CKPT"]),
        output_dir=Path(cfg.get("OUTPUT_DIR", Path(settings.MEDIA_ROOT) / "diameter_tmp")),
        patch_size=int(cfg.get("PATCH_SIZE", 5)),
        default_conf=float(cfg.get("YOLO_CONF", 0.25)),
        infer_valid_iters=int(cfg.get("INFER_VALID_ITERS", 16)),
        preferred_device=str(cfg.get("DEVICE", "auto")),
        allow_cpu_fallback=bool(cfg.get("ALLOW_CPU_FALLBACK", True)),
    )
    for path in (config.monster_dir, config.calib_npz, config.restore_ckpt):
        if not path.exists():
            raise FileNotFoundError(f"missing measurement dependency: {path}")
    ensure_diameter_runtime_supported(config)
    return FruitDiameterService(config)
