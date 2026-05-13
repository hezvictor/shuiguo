import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any, Dict, Optional

from django.conf import settings
from fruit_api.diameter_service import build_measure_service
from fruit_api.models import DetectionHistory
from fruit_api.services.history_normalization_service import build_diameter_history_detail, normalize_diameter_statistics


class DiameterDependencyError(Exception):
    pass


class DiameterParamError(Exception):
    pass


class DiameterExecutionError(Exception):
    pass


_diameter_service = None
_diameter_service_lock = threading.Lock()
_diameter_disabled_until = 0.0
_diameter_disabled_reason: str | None = None
_PRIVATE_MEASURE_KEYS = {
    "annotated_image_path",
    "calib_path",
    "ckpt_path",
    "csv_path",
    "detect_vis_path",
    "disp_npy_path",
    "disp_vis_path",
    "left_image_path",
    "rectified_left_path",
    "rectified_right_path",
    "result_json_path",
    "right_image_path",
}


def get_diameter_service():
    global _diameter_service
    with _diameter_service_lock:
        if _diameter_service is None:
            _diameter_service = build_measure_service()
        return _diameter_service


def reset_diameter_service() -> None:
    global _diameter_service, _diameter_disabled_until, _diameter_disabled_reason
    with _diameter_service_lock:
        _diameter_service = None
        _diameter_disabled_until = 0.0
        _diameter_disabled_reason = None


def _drop_diameter_service() -> None:
    global _diameter_service
    with _diameter_service_lock:
        _diameter_service = None


def _measure_config() -> Dict[str, Any]:
    return getattr(settings, "MEASURE_CONFIG", {}) or {}


def _diameter_call_timeout_seconds() -> int:
    config = _measure_config()
    configured_timeout = config.get("REQUEST_TIMEOUT_SECONDS")
    if configured_timeout is None:
        configured_timeout = config.get("INFER_TIMEOUT_SECONDS")
    if configured_timeout is None:
        configured_timeout = 20
    return max(1, int(configured_timeout))


def _diameter_failure_cooldown_seconds() -> int:
    config = _measure_config()
    configured_cooldown = config.get("FAILURE_COOLDOWN_SECONDS")
    if configured_cooldown is None:
        configured_cooldown = 120
    return max(5, int(configured_cooldown))


def _diameter_is_temporarily_disabled() -> tuple[bool, str | None]:
    global _diameter_disabled_until, _diameter_disabled_reason
    now = time.time()
    if _diameter_disabled_until and now < _diameter_disabled_until:
        remaining = int(math.ceil(_diameter_disabled_until - now))
        reason = _diameter_disabled_reason or "previous diameter failure"
        return True, f"{reason} (cooldown {remaining}s remaining)"
    if _diameter_disabled_until and now >= _diameter_disabled_until:
        _diameter_disabled_until = 0.0
        _diameter_disabled_reason = None
    return False, None


def _mark_diameter_unavailable(reason: str) -> None:
    global _diameter_disabled_until, _diameter_disabled_reason
    _drop_diameter_service()
    _diameter_disabled_reason = reason
    _diameter_disabled_until = time.time() + _diameter_failure_cooldown_seconds()


def _invoke_diameter_operation(method_name: str, **kwargs) -> Any:
    disabled, message = _diameter_is_temporarily_disabled()
    if disabled:
        raise DiameterExecutionError(message or "diameter service is temporarily unavailable")

    timeout_seconds = kwargs.pop("_timeout_seconds", _diameter_call_timeout_seconds())

    def _call() -> Any:
        service = get_diameter_service()
        method = getattr(service, method_name)
        return method(**kwargs)

    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"diameter-{method_name}")
    future = executor.submit(_call)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError as exc:
        reason = f"{method_name} timed out after {timeout_seconds}s"
        _mark_diameter_unavailable(reason)
        raise DiameterExecutionError(reason) from exc
    except Exception as exc:
        if isinstance(exc, (FileNotFoundError, ValueError)):
            raise
        _mark_diameter_unavailable(str(exc) or exc.__class__.__name__)
        raise
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def run_diameter_inference(**kwargs) -> Dict:
    try:
        payload = _invoke_diameter_operation("run_inference", **kwargs)
    except FileNotFoundError as exc:
        raise DiameterDependencyError(str(exc)) from exc
    except ValueError as exc:
        raise DiameterParamError(str(exc)) from exc
    except DiameterExecutionError:
        raise
    except Exception as exc:
        raise DiameterExecutionError(str(exc)) from exc
    return _sanitize_measure_payload(payload)


def run_diameter_distance(**kwargs) -> Dict:
    try:
        payload = _invoke_diameter_operation("measure_distance", **kwargs)
    except FileNotFoundError as exc:
        raise DiameterDependencyError(str(exc)) from exc
    except ValueError as exc:
        raise DiameterParamError(str(exc)) from exc
    except DiameterExecutionError:
        raise
    except Exception as exc:
        raise DiameterExecutionError(str(exc)) from exc

    return _normalize_measure_result_payload(payload)


def run_diameter_full_measurement(**kwargs) -> Dict:
    try:
        payload = _invoke_diameter_operation("run_full_measurement", **kwargs)
    except FileNotFoundError as exc:
        raise DiameterDependencyError(str(exc)) from exc
    except ValueError as exc:
        raise DiameterParamError(str(exc)) from exc
    except DiameterExecutionError:
        raise
    except Exception as exc:
        raise DiameterExecutionError(str(exc)) from exc

    return _normalize_measure_result_payload(payload)


def get_measure_runtime_status() -> Dict:
    disabled, message = _diameter_is_temporarily_disabled()
    if disabled:
        return {
            "available": False,
            "status": "disabled",
            "reason": message,
            "cooldown_remaining_seconds": max(0, int(math.ceil(_diameter_disabled_until - time.time()))),
        }

    payload = dict(get_diameter_service().runtime.status())
    checkpoint_path = payload.pop("checkpoint_path", None)
    if checkpoint_path:
        payload["checkpoint_file"] = Path(checkpoint_path).name
    return payload


def _sanitize_measure_payload(value):
    if isinstance(value, dict):
        return {
            key: _sanitize_measure_payload(item)
            for key, item in value.items()
            if key not in _PRIVATE_MEASURE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_measure_payload(item) for item in value]
    return value


def _normalize_measure_result_payload(payload: Dict) -> Dict:
    normalized = dict(payload or {})
    statistics = normalize_diameter_statistics(
        normalized.get("diameter_statistics") or normalized.get("statistics")
    )
    if statistics is not None:
        normalized["statistics"] = statistics
        normalized["diameter_statistics"] = statistics
    if normalized.get("measurement"):
        measurement = dict(normalized.get("measurement") or {})
        if statistics is not None:
            measurement["statistics"] = statistics
            measurement["diameter_statistics"] = statistics
        normalized["measurement"] = measurement
    return normalized


def _save_history(user, payload: Dict) -> None:
    detail_payload = _build_history_payload(payload)
    summary = _build_history_summary(detail_payload)
    report_file = detail_payload.get("annotated_image") or detail_payload.get("result_json_file")
    detail_data = build_diameter_history_detail(detail_payload)

    DetectionHistory.objects.create(
        user=user,
        detection_type="diameter",
        title="双目果径测量",
        input_count=1,
        summary=summary,
        detail_data=detail_data,
        cover_image=detail_payload.get("annotated_image"),
        report_file=report_file,
    )


def _build_history_summary(payload: Dict) -> Dict:
    return {
        "type": "fruit_diameter",
        "input_count": 1,
        "total_targets": int(payload.get("total_targets") or 0),
        "valid_measurements": int(payload.get("valid_measurements") or 0),
        "valid_measurements_by_axis": payload.get("valid_measurements_by_axis") or {
            "horizontal": int(payload.get("valid_measurements") or 0),
            "vertical": 0,
        },
        "measurement_axes": payload.get("measurement_axes") or ["horizontal", "vertical"],
        "statistics": normalize_diameter_statistics(payload.get("statistics")),
        "diameter_statistics": normalize_diameter_statistics(payload.get("statistics")),
        "inference_id": payload.get("inference_id"),
        "fruit_counts": payload.get("fruit_counts") or {},
        "ripeness_counts": payload.get("ripeness_counts") or {},
    }


def _build_history_payload(payload: Dict) -> Dict:
    measurement = payload.get("measurement", {}) or {}
    return {
        "message": payload.get("message"),
        "total_targets": payload.get("total_targets"),
        "valid_measurements": payload.get("valid_measurements"),
        "valid_measurements_by_axis": payload.get("valid_measurements_by_axis"),
        "measurement_axes": payload.get("measurement_axes"),
        "statistics": payload.get("statistics"),
        "inference_id": measurement.get("inference_id") or payload.get("inference_id"),
        "targets": payload.get("targets") or measurement.get("targets") or [],
        "annotated_image": _relative_media_path(payload.get("visualization_file")) or _relative_media_path(payload.get("annotated_image_path")),
        "result_json_file": _relative_media_path(measurement.get("result_json_path")) or _relative_media_path(payload.get("result_json_path")),
        "csv_file": _relative_media_path(measurement.get("csv_path")) or _relative_media_path(payload.get("csv_path")),
        "left_image": _relative_media_path((payload.get("inference") or {}).get("left_image_path")),
        "right_image": _relative_media_path((payload.get("inference") or {}).get("right_image_path")),
        "distance_unit": payload.get("distance_unit") or "mm",
        "split_mode": payload.get("split_mode"),
        "conf": payload.get("conf"),
        "save_vis": payload.get("save_vis"),
    }


def run_measure_inference(*, yolo_model, **kwargs) -> Dict:
    return run_diameter_inference(yolo_model=yolo_model, **kwargs)


def run_measure_distance(*, user=None, save_history: bool = False, **kwargs) -> Dict:
    payload = run_diameter_distance(**kwargs)

    if save_history and user is not None:
        _save_history(user, payload)
    return _sanitize_measure_payload(payload)


def measure_and_save_history(
    *,
    user,
    yolo_model,
    image=None,
    left_image=None,
    right_image=None,
    split_mode: str = "left_right",
    conf: float,
    save_vis: bool,
) -> Dict:
    payload = run_diameter_full_measurement(
        yolo_model=yolo_model,
        image_file=image,
        left_file=left_image,
        right_file=right_image,
        split_mode=split_mode,
        conf=conf,
        save_vis=save_vis,
    )

    _save_history(
        user,
        {
            **payload,
            "split_mode": split_mode,
            "conf": conf,
            "save_vis": save_vis,
        },
    )
    return _sanitize_measure_payload(payload)


def _relative_media_path(path_str: Optional[str]) -> Optional[str]:
    if not path_str:
        return None
    path = Path(path_str)
    if not path.is_absolute():
        return path_str.replace("\\", "/")
    media_root = Path(settings.MEDIA_ROOT).resolve()
    try:
        return path.resolve().relative_to(media_root).as_posix()
    except ValueError:
        return str(path.resolve())
