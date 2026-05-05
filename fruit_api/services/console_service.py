from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.db.models import QuerySet
from django.utils import timezone

from fruit_api.models import DetectionHistory
from fruit_api.serializers import DetectionHistoryListSerializer
from fruit_api.services.camera import get_stereo_calibration_service, get_stereo_camera_service
from fruit_api.services.detection.diameter_app_service import get_measure_runtime_status


VALID_DETECTION_TYPES = {"image", "realtime", "diameter"}
ALL_DETECTION_TYPE_VALUES = {"", "all"}
RANGE_TYPE_ALIASES = {
    "today": "today",
    "1d": "today",
    "7d": "7d",
    "last7days": "7d",
    "last_7_days": "7d",
    "30d": "30d",
    "last30days": "30d",
    "last_30_days": "30d",
    "custom": "custom",
}


def _pick_axis_values(stats: dict | None, axis_name: str) -> tuple[float | None, float | None, float | None]:
    stats = stats or {}
    axis_stats = stats.get(axis_name) or {}
    avg_value = axis_stats.get("avg_diameter_mm", axis_stats.get("avg_distance_mm"))
    min_value = axis_stats.get("min_diameter_mm", axis_stats.get("min_distance_mm"))
    max_value = axis_stats.get("max_diameter_mm", axis_stats.get("max_distance_mm"))
    return avg_value, min_value, max_value


def _build_axis_stats(avg_values: list[float], min_values: list[float], max_values: list[float]) -> dict:
    return {
        "avg_diameter_mm": round(sum(avg_values) / len(avg_values), 6) if avg_values else None,
        "min_diameter_mm": min(min_values) if min_values else None,
        "max_diameter_mm": max(max_values) if max_values else None,
    }


def _resolve_time_range(range_type: str, start_date: str | None, end_date: str | None, tz_name: str) -> tuple[datetime, datetime]:
    range_type = RANGE_TYPE_ALIASES.get((range_type or "").strip().lower(), "today")
    tz = ZoneInfo(tz_name or "UTC")
    today = timezone.now().astimezone(tz).date()

    if range_type == "custom":
        if not start_date or not end_date:
            raise ValueError("custom range requires start_date and end_date")
        start_day = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_day = datetime.strptime(end_date, "%Y-%m-%d").date()
    elif range_type == "7d":
        end_day = today
        start_day = today - timedelta(days=6)
    elif range_type == "30d":
        end_day = today
        start_day = today - timedelta(days=29)
    else:
        end_day = today
        start_day = today

    start_dt = datetime.combine(start_day, time.min, tzinfo=tz).astimezone(dt_timezone.utc)
    end_dt = datetime.combine(end_day, time.max, tzinfo=tz).astimezone(dt_timezone.utc)
    return start_dt, end_dt


def _filter_queryset(user, *, range_type: str, start_date: str | None, end_date: str | None, tz_name: str, detection_type: str | None = None) -> QuerySet:
    normalized_type = (detection_type or "").strip().lower()
    if normalized_type in ALL_DETECTION_TYPE_VALUES:
        normalized_type = ""

    if normalized_type and normalized_type not in VALID_DETECTION_TYPES:
        raise ValueError("invalid detection_type")

    start_dt, end_dt = _resolve_time_range(range_type, start_date, end_date, tz_name)
    queryset = DetectionHistory.objects.filter(user=user, created_at__gte=start_dt, created_at__lte=end_dt).order_by("-created_at")
    if normalized_type:
        queryset = queryset.filter(detection_type=normalized_type)
    return queryset


def build_console_overview(user, *, range_type: str, start_date: str | None, end_date: str | None, tz_name: str, detection_type: str | None):
    queryset = list(_filter_queryset(user, range_type=range_type, start_date=start_date, end_date=end_date, tz_name=tz_name, detection_type=detection_type))
    tz = ZoneInfo(tz_name or "UTC")

    detection_count = len(queryset)
    total_targets = sum(int((row.summary or {}).get("total_targets") or 0) for row in queryset)
    valid_diameter_measurements = sum(int((row.summary or {}).get("valid_measurements") or 0) for row in queryset)
    image_detection_count = sum(1 for row in queryset if row.detection_type == "image")
    realtime_detection_count = sum(1 for row in queryset if row.detection_type == "realtime")
    diameter_detection_count = sum(1 for row in queryset if row.detection_type == "diameter")

    daily_detection = Counter()
    daily_targets = Counter()
    daily_type = defaultdict(lambda: {"image": 0, "realtime": 0, "diameter": 0})
    daily_diameter_values = defaultdict(list)

    fruit_counter = Counter()
    ripeness_counter = Counter()

    diameter_measure_count = 0
    diameter_total_targets = 0
    diameter_valid = 0
    diameter_avg_values = []
    diameter_min_values = []
    diameter_max_values = []
    axis_measurement_totals = {"horizontal": 0, "vertical": 0}
    diameter_axis_aggregates = {
        "horizontal": {"avg_values": [], "min_values": [], "max_values": []},
        "vertical": {"avg_values": [], "min_values": [], "max_values": []},
    }

    for row in queryset:
        local_day = row.created_at.astimezone(tz).date().isoformat()
        summary = row.summary or {}
        target_count = int(summary.get("total_targets") or 0)
        daily_detection[local_day] += 1
        daily_targets[local_day] += target_count
        daily_type[local_day][row.detection_type] += 1

        for fruit, count in (summary.get("fruit_counts") or {}).items():
            fruit_counter[fruit] += int(count or 0)
        for fruit, ripeness_map in (summary.get("ripeness_counts") or {}).items():
            for ripeness, count in (ripeness_map or {}).items():
                ripeness_counter[(fruit, ripeness)] += int(count or 0)

        stats = summary.get("diameter_statistics") or summary.get("statistics") or {}
        valid_by_axis = summary.get("valid_measurements_by_axis") or {}
        options = getattr(row, "options", {}) or {}
        has_axis_values = any(
            value is not None
            for axis_name in ("horizontal", "vertical")
            for value in _pick_axis_values(stats, axis_name)
        )
        has_diameter_summary = (
            row.detection_type == "diameter"
            or bool(options.get("detect_diameter"))
            or bool(options.get("has_mixed_inputs"))
            or (options.get("mode") in {"dual", "hybrid"})
            or int(valid_by_axis.get("horizontal") or 0) > 0
            or int(valid_by_axis.get("vertical") or 0) > 0
            or has_axis_values
        )
        if has_diameter_summary:
            diameter_measure_count += 1
            diameter_total_targets += target_count
            diameter_valid += int(summary.get("valid_measurements") or 0)
            axis_measurement_totals["horizontal"] += int(valid_by_axis.get("horizontal") or 0)
            axis_measurement_totals["vertical"] += int(valid_by_axis.get("vertical") or 0)
            avg_value = stats.get("avg_diameter_mm", stats.get("avg_distance_mm"))
            min_value = stats.get("min_diameter_mm", stats.get("min_distance_mm"))
            max_value = stats.get("max_diameter_mm", stats.get("max_distance_mm"))
            if avg_value is not None:
                avg_value = float(avg_value)
                daily_diameter_values[local_day].append(avg_value)
                diameter_avg_values.append(avg_value)
            if min_value is not None:
                diameter_min_values.append(float(min_value))
            if max_value is not None:
                diameter_max_values.append(float(max_value))
            for axis_name in ("horizontal", "vertical"):
                axis_avg_value, axis_min_value, axis_max_value = _pick_axis_values(stats, axis_name)
                if axis_avg_value is not None:
                    diameter_axis_aggregates[axis_name]["avg_values"].append(float(axis_avg_value))
                if axis_min_value is not None:
                    diameter_axis_aggregates[axis_name]["min_values"].append(float(axis_min_value))
                if axis_max_value is not None:
                    diameter_axis_aggregates[axis_name]["max_values"].append(float(axis_max_value))

    daily_detection_trend = [{"date": key, "count": daily_detection[key]} for key in sorted(daily_detection)]
    daily_target_trend = [{"date": key, "count": daily_targets[key]} for key in sorted(daily_targets)]
    daily_type_trend = [{"date": key, **daily_type[key]} for key in sorted(daily_type)]
    daily_avg_diameter_trend = [
        {"date": key, "avg_diameter_mm": round(sum(values) / len(values), 6)}
        for key, values in sorted(daily_diameter_values.items())
        if values
    ]

    total_for_distribution = max(1, detection_count)
    detection_type_distribution = [
        {
            "type": type_name,
            "label": {"image": "图片检测", "realtime": "实时检测", "diameter": "果径测量"}[type_name],
            "count": count,
            "percentage": round((count / total_for_distribution) * 100, 2) if detection_count else 0.0,
        }
        for type_name, count in (
            ("image", image_detection_count),
            ("realtime", realtime_detection_count),
            ("diameter", diameter_detection_count),
        )
    ]

    avg_targets = round(total_targets / detection_count, 2) if detection_count else 0.0
    success_rate = round((diameter_valid / diameter_total_targets) * 100, 2) if diameter_total_targets else 0.0

    return {
        "summary_cards": {
            "detection_count": detection_count,
            "total_targets": total_targets,
            "image_detection_count": image_detection_count,
            "realtime_detection_count": realtime_detection_count,
            "diameter_detection_count": diameter_detection_count,
            "valid_diameter_measurements": valid_diameter_measurements,
            "avg_targets_per_record": avg_targets,
        },
        "trends": {
            "daily_detection_trend": daily_detection_trend,
            "daily_target_trend": daily_target_trend,
            "daily_type_trend": daily_type_trend,
            "daily_avg_diameter_trend": daily_avg_diameter_trend,
        },
        "analysis": {
            "detection_type_distribution": detection_type_distribution,
            "fruit_ranking": [{"fruit": fruit, "count": count} for fruit, count in fruit_counter.most_common(5)],
            "ripeness_distribution": [
                {"fruit": fruit, "ripeness": ripeness, "count": count}
                for (fruit, ripeness), count in ripeness_counter.most_common()
            ],
        },
        "diameter_analysis": {
            "measure_count": diameter_measure_count,
            "total_targets": diameter_total_targets,
            "valid_measurements": diameter_valid,
            "valid_measurements_by_axis": axis_measurement_totals,
            "success_rate": success_rate,
            "avg_diameter_mm": round(sum(diameter_avg_values) / len(diameter_avg_values), 6) if diameter_avg_values else None,
            "min_diameter_mm": min(diameter_min_values) if diameter_min_values else None,
            "max_diameter_mm": max(diameter_max_values) if diameter_max_values else None,
            "horizontal": _build_axis_stats(
                diameter_axis_aggregates["horizontal"]["avg_values"],
                diameter_axis_aggregates["horizontal"]["min_values"],
                diameter_axis_aggregates["horizontal"]["max_values"],
            ),
            "vertical": _build_axis_stats(
                diameter_axis_aggregates["vertical"]["avg_values"],
                diameter_axis_aggregates["vertical"]["min_values"],
                diameter_axis_aggregates["vertical"]["max_values"],
            ),
        },
    }


def build_console_recent(user, *, range_type: str, start_date: str | None, end_date: str | None, tz_name: str, detection_type: str | None):
    queryset = _filter_queryset(
        user,
        range_type=range_type,
        start_date=start_date,
        end_date=end_date,
        tz_name=tz_name,
        detection_type=detection_type,
    )[:10]
    serializer = DetectionHistoryListSerializer(queryset, many=True)
    return {"recent_histories": serializer.data}


def build_console_system_status():
    camera_status = get_stereo_camera_service().status()
    camera_status["stream_url"] = "/api/camera/stream/"
    runtime_status = get_measure_runtime_status()
    runtime_status["calib_path"] = "calib_stereo.npz"
    calibration_status = get_stereo_calibration_service().session_status(None)
    return {
        "backend_health": {
            "status": "ok",
            "message": "Service is healthy",
        },
        "camera_status": camera_status,
        "measure_runtime_status": runtime_status,
        "calibration_status": calibration_status,
    }
