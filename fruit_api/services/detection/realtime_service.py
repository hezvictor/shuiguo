from __future__ import annotations

import json
import os
import uuid
from typing import Dict

from django.apps import apps
from django.conf import settings

from fruit_api.models import DetectionHistory
from fruit_api.services.detection.image_batch_service import (
    create_detection_history_from_batch_result,
    execute_image_detection_batch,
)
from fruit_api.services.detection.realtime_session_service import get_realtime_session_service
from fruit_api.services.history_normalization_service import (
    build_realtime_history_detail,
    normalize_diameter_statistics,
)


class RealtimePayloadError(Exception):
    pass


def validate_realtime_payload(data: Dict) -> None:
    if data.get("session_id"):
        return
    required_keys = ["total_targets", "fruit_counts", "ripeness_counts"]
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise RealtimePayloadError(f'缺少必要字段: {", ".join(missing)}')


def build_realtime_summary(data: Dict) -> Dict:
    summary = {
        "total_targets": int(data.get("total_targets") or 0),
        "fruit_counts": data.get("fruit_counts") or {},
        "ripeness_counts": data.get("ripeness_counts") or {},
    }
    for key in [
        "mode",
        "interval_ms",
        "sample_count",
        "valid_measurements",
        "valid_measurements_by_axis",
        "measurement_axes",
        "statistics",
        "camera_profile",
        "runtime_device",
    ]:
        if key in data:
            summary[key] = data.get(key)
    diameter_statistics = normalize_diameter_statistics(
        data.get("diameter_statistics") or data.get("statistics")
    )
    if diameter_statistics:
        summary["diameter_statistics"] = diameter_statistics
        summary.setdefault("statistics", diameter_statistics)
    return summary


def save_realtime_report_file(summary: Dict) -> str:
    report_dir = os.path.join(settings.MEDIA_ROOT, "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_filename = f"reports/realtime_report_{uuid.uuid4().hex}.json"
    report_path = os.path.join(settings.MEDIA_ROOT, report_filename)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    return report_filename


def create_realtime_history(user, summary: Dict, report_filename: str, detail_data: Dict) -> None:
    mode = summary.get("mode") or "single"
    DetectionHistory.objects.create(
        user=user,
        detection_type="realtime",
        title=f"实时检测会话({mode})",
        options={
            "mode": mode,
            "interval_ms": summary.get("interval_ms"),
            "camera_profile": summary.get("camera_profile"),
        },
        summary=summary,
        detail_data=build_realtime_history_detail(detail_data.get("session_report") or detail_data),
        report_file=report_filename,
    )


def _save_legacy_realtime_report(user, data: Dict) -> Dict:
    summary = build_realtime_summary(data)
    report_filename = save_realtime_report_file(summary)
    create_realtime_history(
        user,
        summary,
        report_filename,
        {
            "session_report": data,
        },
    )
    return {
        "status": "success",
        "message": "报告已保存",
        "report_file": report_filename,
    }


def _save_realtime_session_report(user, data: Dict) -> Dict:
    session_id = data.get("session_id")
    if not session_id:
        raise RealtimePayloadError("缺少实时会话 session_id")

    session_service = get_realtime_session_service()
    try:
        batch_inputs = session_service.build_batch_inputs(user_id=user.id, session_id=session_id)
    except ValueError as exc:
        raise RealtimePayloadError("当前实时会话已保存或已失效，请重新开始实时检测。") from exc
    except FileNotFoundError as exc:
        raise RealtimePayloadError("当前实时会话采样文件缺失，无法再次生成报告。") from exc
    sample_count = batch_inputs["sample_count"]
    if sample_count <= 0:
        raise RealtimePayloadError("当前实时会话没有可生成报告的采样图片")

    app_config = apps.get_app_config("fruit_api")
    app_config.ensure_models_loaded()

    mode = batch_inputs["mode"]
    detect_ripeness = bool((batch_inputs["meta"] or {}).get("detect_ripeness"))
    detect_classification = mode != "dual"
    detect_diameter = mode in {"dual", "hybrid"}

    batch_result = execute_image_detection_batch(
        standard_images=batch_inputs["standard_images"],
        diameter_groups=batch_inputs["diameter_groups"],
        mixed_groups=batch_inputs["mixed_groups"],
        options={
            "detect_classification": detect_classification,
            "detect_ripeness": detect_ripeness,
            "detect_diameter": detect_diameter,
        },
        app_config=app_config,
    )

    history = create_detection_history_from_batch_result(
        user=user,
        detection_type="realtime",
        batch_result=batch_result,
        options={
            "mode": mode,
            "interval_ms": (batch_inputs["meta"] or {}).get("interval_ms"),
            "camera_profile": (batch_inputs["meta"] or {}).get("camera_profile"),
            "runtime_device": (batch_inputs["meta"] or {}).get("runtime_device"),
            "sample_count": sample_count,
            "session_source": "realtime_session",
            "has_mixed_inputs": bool(batch_inputs["mixed_groups"]),
        },
    )
    session_service.delete_session(user_id=user.id, session_id=session_id)

    return {
        "status": "success",
        "message": "报告已保存",
        "history_id": history.id,
        "title": history.title,
        "summary": history.summary,
        "detail_data": history.detail_data,
        "artifacts": history.artifacts,
        "report_file": history.report_file,
        "report_url": f"{settings.MEDIA_URL.rstrip('/')}/{history.report_file}" if history.report_file else None,
        "cover_image": history.cover_image,
        "cover_image_url": f"{settings.MEDIA_URL.rstrip('/')}/{history.cover_image}" if history.cover_image else None,
    }


def save_realtime_report(user, data: Dict) -> Dict:
    validate_realtime_payload(data)
    if data.get("session_id"):
        return _save_realtime_session_report(user, data)
    return _save_legacy_realtime_report(user, data)
