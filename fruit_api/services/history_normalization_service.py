from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


def normalize_diameter_statistics(stats: Dict[str, Any] | None) -> Dict[str, Any]:
    stats = dict(stats or {})
    return {
        "avg_diameter_mm": stats.get("avg_diameter_mm", stats.get("avg_distance_mm")),
        "min_diameter_mm": stats.get("min_diameter_mm", stats.get("min_distance_mm")),
        "max_diameter_mm": stats.get("max_diameter_mm", stats.get("max_distance_mm")),
    }


def _normalize_realtime_target(target: Dict[str, Any]) -> Dict[str, Any]:
    item = deepcopy(target)
    classification = item.get("classification")
    if classification is None:
        fruit_class = item.get("fruit_class") or item.get("label")
        fruit_conf = item.get("fruit_confidence", item.get("confidence"))
        classification = {
            "class": fruit_class,
            "confidence": fruit_conf,
        }
    ripeness = item.get("ripeness")
    if ripeness and "predicted_class" not in ripeness:
        ripeness = {
            "predicted_class": ripeness.get("class"),
            "confidence": ripeness.get("confidence"),
        }
    item["classification"] = classification
    item["ripeness"] = ripeness
    return item


def build_realtime_history_detail(detail_payload: Dict[str, Any] | None) -> Dict[str, Any]:
    payload = deepcopy(detail_payload or {})
    session_report = payload.get("session_report") or payload
    mode = session_report.get("mode") or "single"
    last_capture = session_report.get("last_capture") or {}

    items: List[Dict[str, Any]] = []
    if mode == "single":
        items.append(
            {
                "item_type": "realtime_single",
                "display_name": "实时检测结果",
                "annotated_image": last_capture.get("annotated_image") or session_report.get("annotated_image"),
                "targets": [_normalize_realtime_target(item) for item in (last_capture.get("targets") or session_report.get("targets") or [])],
            }
        )
    elif mode == "dual":
        items.append(
            {
                "item_type": "realtime_dual",
                "display_name": "实时果径结果",
                "annotated_image": last_capture.get("annotated_image") or session_report.get("annotated_image"),
                "targets": [_normalize_realtime_target(item) for item in (last_capture.get("targets") or session_report.get("targets") or [])],
                "statistics": normalize_diameter_statistics(session_report.get("statistics")),
            }
        )
    else:
        items.append(
            {
                "item_type": "realtime_hybrid",
                "display_name": "实时混合检测结果",
                "annotated_image": last_capture.get("annotated_image") or session_report.get("annotated_image"),
                "targets": [_normalize_realtime_target(item) for item in (last_capture.get("targets") or session_report.get("targets") or [])],
                "statistics": normalize_diameter_statistics(session_report.get("statistics")),
            }
        )

    return {
        "mode": mode,
        "session_report": session_report,
        "items": items,
    }


def build_diameter_history_detail(detail_payload: Dict[str, Any] | None) -> Dict[str, Any]:
    payload = deepcopy(detail_payload or {})
    normalized_targets = []
    for target in payload.get("targets") or []:
        normalized_targets.append(
            {
                "bbox": target.get("bbox"),
                "label": target.get("label"),
                "confidence": target.get("confidence"),
                "classification": target.get("classification"),
                "ripeness": target.get("ripeness"),
                "diameter": {
                    "distance_mm": target.get("distance_mm"),
                    "distance": target.get("distance"),
                    "distance_unit": target.get("distance_unit"),
                    "status": target.get("status"),
                    "point1": target.get("point1"),
                    "point2": target.get("point2"),
                },
            }
        )
    return {
        "items": [
            {
                "item_type": "diameter_group",
                "display_name": payload.get("display_name") or "果径测量结果",
                "original_image": payload.get("left_image"),
                "right_image": payload.get("right_image"),
                "annotated_image": payload.get("annotated_image"),
                "targets": normalized_targets,
                "statistics": normalize_diameter_statistics(payload.get("statistics")),
                "distance_unit": payload.get("distance_unit") or "mm",
            }
        ]
    }


def normalize_history_summary(instance) -> Dict[str, Any]:
    summary = deepcopy(getattr(instance, "summary", {}) or {})
    if getattr(instance, "detection_type", "") == "diameter":
        summary["diameter_statistics"] = normalize_diameter_statistics(
            summary.get("diameter_statistics") or summary.get("statistics")
        )
    return summary


def normalize_history_detail(instance) -> Dict[str, Any]:
    detail_data = deepcopy(getattr(instance, "detail_data", {}) or {})
    detection_type = getattr(instance, "detection_type", "")

    if detection_type == "realtime":
        if detail_data.get("items"):
            items = detail_data.get("items") or []
            detail_data["items"] = [
                {
                    **item,
                    "targets": [_normalize_realtime_target(target) for target in (item.get("targets") or [])],
                }
                for item in items
            ]
            return detail_data
        return build_realtime_history_detail(detail_data)

    if detection_type == "diameter":
        if detail_data.get("items"):
            items = detail_data.get("items") or []
            for item in items:
                if item.get("statistics") is not None:
                    item["statistics"] = normalize_diameter_statistics(item.get("statistics"))
            return detail_data
        return build_diameter_history_detail(
            {
                "targets": [],
                "statistics": getattr(instance, "summary", {}).get("statistics"),
                "annotated_image": getattr(instance, "report_file", None),
            }
        )

    return detail_data
