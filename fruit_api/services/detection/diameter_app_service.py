from pathlib import Path
from typing import Dict, Optional

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
    if _diameter_service is None:
        _diameter_service = build_measure_service()
    return _diameter_service


def reset_diameter_service() -> None:
    global _diameter_service
    _diameter_service = None


def get_measure_runtime_status() -> Dict:
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
    try:
        payload = get_diameter_service().run_inference(yolo_model=yolo_model, **kwargs)
    except FileNotFoundError as exc:
        raise DiameterDependencyError(str(exc)) from exc
    except ValueError as exc:
        raise DiameterParamError(str(exc)) from exc
    except Exception as exc:
        raise DiameterExecutionError(str(exc)) from exc
    return _sanitize_measure_payload(payload)


def run_measure_distance(*, user=None, save_history: bool = False, **kwargs) -> Dict:
    try:
        payload = get_diameter_service().measure_distance(**kwargs)
    except FileNotFoundError as exc:
        raise DiameterDependencyError(str(exc)) from exc
    except ValueError as exc:
        raise DiameterParamError(str(exc)) from exc
    except Exception as exc:
        raise DiameterExecutionError(str(exc)) from exc

    payload = _normalize_measure_result_payload(payload)

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
    try:
        payload = get_diameter_service().run_full_measurement(
            yolo_model=yolo_model,
            image_file=image,
            left_file=left_image,
            right_file=right_image,
            split_mode=split_mode,
            conf=conf,
            save_vis=save_vis,
        )
    except FileNotFoundError as exc:
        raise DiameterDependencyError(str(exc)) from exc
    except ValueError as exc:
        raise DiameterParamError(str(exc)) from exc
    except Exception as exc:
        raise DiameterExecutionError(str(exc)) from exc

    payload = _normalize_measure_result_payload(payload)

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
