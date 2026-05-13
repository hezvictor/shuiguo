from __future__ import annotations

import base64
import io
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image, ImageDraw

from django.conf import settings

from fruit_api.diameter_service import SimpleImageWrapper
from fruit_api.services.camera import capture_dual_camera_frames, capture_single_camera_frame, get_cached_preview_frame_snapshot
from fruit_api.services.camera.registry_service import get_camera_registry_service
from fruit_api.services.detection.detect_service import build_detection_target, summarize_targets, yolo_targets
from fruit_api.services.detection.diameter_app_service import (
    run_diameter_distance,
    run_diameter_full_measurement,
    run_diameter_inference,
)
from fruit_api.services.history_normalization_service import normalize_diameter_payload


_last_realtime_frame_cleanup_at = 0.0


def _frame_dir() -> Path:
    path = Path(settings.MEDIA_ROOT) / "realtime_frames"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _relative_media_path(path: Path) -> str:
    return path.resolve().relative_to(Path(settings.MEDIA_ROOT).resolve()).as_posix()


def _media_url(relative_path: str) -> str:
    return f"{settings.MEDIA_URL.rstrip('/')}/{relative_path}"


def _cleanup_saved_frames(output_dir: Path) -> None:
    global _last_realtime_frame_cleanup_at
    now = time.time()
    interval = int(getattr(settings, "REALTIME_FRAME_CLEANUP_INTERVAL_SECONDS", 300))
    if now - _last_realtime_frame_cleanup_at < interval:
        return
    _last_realtime_frame_cleanup_at = now

    retention_seconds = int(getattr(settings, "REALTIME_FRAME_RETENTION_SECONDS", 3600))
    max_files = int(getattr(settings, "REALTIME_FRAME_MAX_FILES", 200))
    files = sorted((item for item in output_dir.glob("*.jpg") if item.is_file()), key=lambda item: item.stat().st_mtime)

    for file_path in list(files):
        if now - file_path.stat().st_mtime > retention_seconds:
            try:
                file_path.unlink()
            except OSError:
                pass

    files = sorted((item for item in output_dir.glob("*.jpg") if item.is_file()), key=lambda item: item.stat().st_mtime)
    while len(files) > max_files:
        file_path = files.pop(0)
        try:
            file_path.unlink()
        except OSError:
            pass


def _save_pil_image(image: Image.Image, prefix: str) -> str:
    output_dir = _frame_dir()
    _cleanup_saved_frames(output_dir)
    file_path = output_dir / f"{prefix}_{uuid.uuid4().hex[:12]}.jpg"
    image.save(file_path, format="JPEG", quality=88)
    _cleanup_saved_frames(output_dir)
    return _relative_media_path(file_path)


def _decode_data_url_image(frame_data_url: str) -> Image.Image:
    payload = frame_data_url.split(",", 1)[1] if "," in frame_data_url else frame_data_url
    image_bytes = base64.b64decode(payload)
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def _encode_pil_to_jpeg_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def _bgr_to_pil(frame_bgr: np.ndarray) -> Image.Image:
    rgb = frame_bgr[:, :, ::-1] if frame_bgr.ndim == 3 and frame_bgr.shape[2] == 3 else frame_bgr
    return Image.fromarray(rgb)


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    rgb = np.array(image)
    return rgb[:, :, ::-1].copy()


def _encode_bgr_to_jpeg_bytes(frame_bgr: np.ndarray) -> bytes:
    return _encode_pil_to_jpeg_bytes(_bgr_to_pil(frame_bgr))


def _extract_xy(point: Dict[str, Any] | None) -> tuple[int, int] | None:
    if not isinstance(point, dict):
        return None
    if point.get("x") is None or point.get("y") is None:
        return None
    return int(point["x"]), int(point["y"])


def _diameter_text(diameter: Dict[str, Any] | None) -> str | None:
    if not diameter:
        return None
    distance = diameter.get("distance")
    unit = diameter.get("distance_unit") or "mm"
    if distance is not None:
        return f"{float(distance):.2f} {unit}"
    distance_mm = diameter.get("distance_mm")
    if distance_mm is not None:
        return f"{float(distance_mm):.2f} mm"
    return None


def _diameter_warning(exc: Exception) -> str:
    return f"果径检测暂不可用，已降级为无果径结果: {exc}"


def _diameter_axes(diameter: Dict[str, Any] | None) -> List[tuple[str, Dict[str, Any]]]:
    normalized = normalize_diameter_payload(diameter)
    if not normalized:
        return []
    axes = normalized.get("diameter_axes") or {}
    results: List[tuple[str, Dict[str, Any]]] = []
    for orientation in ("horizontal", "vertical"):
        axis = axes.get(orientation)
        if isinstance(axis, dict):
            results.append((orientation, axis))
    return results


def _build_detection_diameter(measured: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if measured is None:
        return None
    return normalize_diameter_payload(
        {
            "distance_mm": measured.get("distance_mm"),
            "distance": measured.get("distance"),
            "distance_unit": measured.get("distance_unit"),
            "status": measured.get("status"),
            "point1": measured.get("point1"),
            "point2": measured.get("point2"),
            "diameter_axes": measured.get("diameter_axes"),
        }
    )


def _dual_target_without_diameter(detection: Dict[str, Any], *, measurement_warning: str | None = None) -> Dict[str, Any]:
    target = {
        "bbox": detection.get("bbox"),
        "label": detection.get("label"),
        "confidence": detection.get("confidence"),
        "classification": None,
        "ripeness": None,
        "diameter": None,
        "source_mode": "dual",
    }
    if measurement_warning:
        target["measurement_warning"] = measurement_warning
    return target


def _append_diameter_values(diameter: Dict[str, Any] | None, horizontal_values: List[float], vertical_values: List[float]) -> None:
    normalized = normalize_diameter_payload(diameter)
    if not normalized:
        return
    axes = normalized.get("diameter_axes") or {}
    horizontal = axes.get("horizontal") or {}
    vertical = axes.get("vertical") or {}
    if horizontal.get("distance_mm") is not None:
        horizontal_values.append(float(horizontal["distance_mm"]))
    if vertical.get("distance_mm") is not None:
        vertical_values.append(float(vertical["distance_mm"]))


def _diameter_axis_stats(horizontal_values: List[float], vertical_values: List[float]) -> Dict[str, Any]:
    def _single(values: List[float]) -> Dict[str, Any]:
        if not values:
            return {
                "avg_diameter_mm": None,
                "min_diameter_mm": None,
                "max_diameter_mm": None,
            }
        return {
            "avg_diameter_mm": round(sum(values) / len(values), 6),
            "min_diameter_mm": round(min(values), 6),
            "max_diameter_mm": round(max(values), 6),
        }

    horizontal_stats = _single(horizontal_values)
    vertical_stats = _single(vertical_values)
    return {
        **horizontal_stats,
        "horizontal": horizontal_stats,
        "vertical": vertical_stats,
    }


def _empty_axis_aggregate() -> Dict[str, Any]:
    return {
        "sum_mm": 0.0,
        "count": 0,
        "min_mm": None,
        "max_mm": None,
    }


def build_empty_realtime_axis_summary() -> Dict[str, Any]:
    return {
        "valid_measurements_by_axis": {
            "horizontal": 0,
            "vertical": 0,
        },
        "diameter_axes": {
            "horizontal": _empty_axis_aggregate(),
            "vertical": _empty_axis_aggregate(),
        },
    }


def _has_valid_diameter(diameter: Dict[str, Any] | None) -> bool:
    normalized = normalize_diameter_payload(diameter)
    if not normalized:
        return False
    axes = normalized.get("diameter_axes") or {}
    horizontal = axes.get("horizontal") or {}
    vertical = axes.get("vertical") or {}
    return horizontal.get("distance_mm") is not None or vertical.get("distance_mm") is not None


def _render_annotated(image: Image.Image, detections: List[Dict[str, Any]]) -> Image.Image:
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    for index, detection in enumerate(detections):
        x1, y1, x2, y2 = [int(v) for v in detection["bbox"]]
        draw.rectangle((x1, y1, x2, y2), outline=(0, 255, 0), width=3)
        display_label = (
            (detection.get("classification") or {}).get("class")
            or detection.get("fruit_class")
            or detection.get("label")
            or "fruit"
        )
        ripeness = detection.get("ripeness") or {}
        if ripeness.get("predicted_class"):
            display_label = f"{display_label}/{ripeness['predicted_class']}"
        draw.text((x1 + 4, max(0, y1 - 16)), f"{index + 1}. {display_label}", fill=(255, 64, 64))

        axis_rendered = False
        ordered_axes = sorted(
            _diameter_axes(detection.get("diameter")),
            key=lambda item: 0 if item[0] == "vertical" else 1,
        )
        for orientation, axis in ordered_axes:
            point1 = _extract_xy(axis.get("point1"))
            point2 = _extract_xy(axis.get("point2"))
            distance_label = _diameter_text(axis)
            axis_tag = "H" if orientation == "horizontal" else "V"
            color = (255, 0, 0) if orientation == "horizontal" else (0, 102, 255)
            if point1 and point2:
                draw.line((point1, point2), fill=color, width=3)
                radius = 4
                draw.ellipse((point1[0] - radius, point1[1] - radius, point1[0] + radius, point1[1] + radius), fill=color)
                draw.ellipse((point2[0] - radius, point2[1] - radius, point2[0] + radius, point2[1] + radius), fill=color)
                if distance_label:
                    midpoint = ((point1[0] + point2[0]) // 2, (point1[1] + point2[1]) // 2)
                    draw.text((midpoint[0] + 6, max(0, midpoint[1] - 16)), f"{axis_tag}: {distance_label}", fill=color)
                axis_rendered = True
        if not axis_rendered:
            diameter = detection.get("diameter")
            distance_label = _diameter_text(diameter)
            if distance_label:
                draw.text((x1 + 4, min(y2 + 4, annotated.height - 16)), distance_label, fill=(255, 0, 0))
    return annotated


def _classify_detection_image_targets(image: Image.Image, *, app_config, detect_ripeness: bool, source_mode: str) -> tuple[List[Dict[str, Any]], Dict[str, int], Dict[str, Dict[str, int]]]:
    targets = []
    for detection in yolo_targets(image, app_config):
        targets.append(
            build_detection_target(
                image,
                detection,
                app_config,
                detect_ripeness=detect_ripeness,
                source_mode=source_mode,
            )
        )
    counts = summarize_targets(targets)
    return targets, counts["fruit_counts"], counts["ripeness_counts"]


def _suggested_interval_ms(mode: str) -> int:
    registry = get_camera_registry_service().snapshot()
    suggested = registry.get("suggested_intervals") or {}
    if mode in {"dual", "hybrid"}:
        return int(suggested.get("dual_interval_ms") or 6000)
    return int(suggested.get("single_interval_ms") or 2000)


def _result_item(*, mode: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    summary = payload.get("summary") or {}
    if mode == "single":
        item_type = "image"
        display_name = "实时检测结果"
    elif mode == "dual":
        item_type = "diameter_group"
        display_name = "实时果径检测结果"
    else:
        item_type = "mixed_group"
        display_name = "实时混合检测结果"
    return {
        "item_type": item_type,
        "display_name": display_name,
        "annotated_image": payload.get("annotated_image"),
        "targets": payload.get("targets") or [],
        "statistics": summary.get("diameter_statistics") or summary.get("statistics"),
        "runtime_warning": payload.get("runtime_warning"),
    }


def run_single_camera_realtime_detection(*, app_config, camera_index: int | None = None, detect_ripeness: bool = False, backend: str | None = None) -> Dict[str, Any]:
    registry = get_camera_registry_service().snapshot()
    if camera_index is None:
        camera_index = int((registry.get("selection") or {}).get("single_camera_index", 0))
    backend = backend if backend is not None else (registry.get("selection") or {}).get("backend") or None
    snapshot = get_cached_preview_frame_snapshot()
    if snapshot and (snapshot.get("config") or {}).get("mode") == "single":
        config = snapshot.get("config") or {}
        if int(config.get("camera_index", -1)) == int(camera_index) and snapshot.get("single_frame") is not None:
            image = _bgr_to_pil(np.array(snapshot["single_frame"], copy=True))
            return _run_single_image_realtime_detection(
                image=image,
                app_config=app_config,
                camera_index=int(camera_index),
                detect_ripeness=detect_ripeness,
                frame_source="preview",
            )

    frame = capture_single_camera_frame(int(camera_index), backend=backend)
    image = _bgr_to_pil(frame)
    return _run_single_image_realtime_detection(
        image=image,
        app_config=app_config,
        camera_index=int(camera_index),
        detect_ripeness=detect_ripeness,
        frame_source="camera",
    )


def run_single_preview_frame_realtime_detection(*, app_config, frame_data_url: str, camera_index: int | None = None, detect_ripeness: bool = False) -> Dict[str, Any]:
    image = _decode_data_url_image(frame_data_url)
    return _run_single_image_realtime_detection(image=image, app_config=app_config, camera_index=int(camera_index or 0), detect_ripeness=detect_ripeness, frame_source="preview")


def _run_single_image_realtime_detection(*, image: Image.Image, app_config, camera_index: int, detect_ripeness: bool, frame_source: str) -> Dict[str, Any]:
    detections = yolo_targets(image, app_config)
    targets, fruit_counts, ripeness_counts = _classify_detection_image_targets(
        image,
        app_config=app_config,
        detect_ripeness=detect_ripeness,
        source_mode="single",
    )
    annotated_rel = _save_pil_image(_render_annotated(image, targets or detections), "single")
    payload = {
        "status": "success",
        "mode": "single",
        "camera_index": camera_index,
        "frame_source": frame_source,
        "targets": targets,
        "summary": {
            "total_targets": len(targets),
            "fruit_counts": fruit_counts,
            "ripeness_counts": ripeness_counts,
        },
        "annotated_image": annotated_rel,
        "annotated_image_url": _media_url(annotated_rel),
        "suggested_interval_ms": _suggested_interval_ms("single"),
        "items": [],
        "_session_sample": {
            "mode": "single",
            "image_bytes": _encode_pil_to_jpeg_bytes(image),
        },
    }
    payload["items"] = [_result_item(mode="single", payload=payload)]
    return payload


def _run_dual_realtime_detection_from_frames(
    *,
    left_frame: np.ndarray,
    right_frame: np.ndarray,
    app_config,
    detect_classification: bool = False,
    detect_ripeness: bool = False,
    mode: str = "dual",
) -> Dict[str, Any]:
    left_image = _bgr_to_pil(left_frame)
    detections = yolo_targets(left_image, app_config)

    if not detect_classification and mode == "dual":
        try:
            payload = run_diameter_full_measurement(
                yolo_model=app_config.yolo_model,
                left_file=SimpleImageWrapper(left_frame, "realtime_left.png"),
                right_file=SimpleImageWrapper(right_frame, "realtime_right.png"),
                save_vis=True,
                conf=0.25,
            )
            targets = []
            horizontal_diameters: List[float] = []
            vertical_diameters: List[float] = []
            for item in payload.get("targets") or []:
                diameter = _build_detection_diameter(item)
                _append_diameter_values(diameter, horizontal_diameters, vertical_diameters)
                targets.append(
                    {
                        "bbox": item.get("bbox"),
                        "label": item.get("label"),
                        "confidence": item.get("confidence"),
                        "classification": None,
                        "ripeness": None,
                        "diameter": diameter,
                        "source_mode": "dual",
                    }
                )
            stats = _diameter_axis_stats(horizontal_diameters, vertical_diameters)
            annotated_image = payload.get("visualization_file")
            return {
                "status": "success",
                "mode": "dual",
                "targets": targets,
                "summary": {
                    "total_targets": len(targets),
                    "valid_measurements": sum(1 for target in targets if _has_valid_diameter(target.get("diameter"))),
                    "valid_measurements_by_axis": {
                        "horizontal": len(horizontal_diameters),
                        "vertical": len(vertical_diameters),
                    },
                    "measurement_axes": ["horizontal", "vertical"],
                    "fruit_counts": {},
                    "ripeness_counts": {},
                    "statistics": stats,
                    "diameter_statistics": stats,
                },
                "annotated_image": annotated_image,
                "annotated_image_url": _media_url(annotated_image) if annotated_image else None,
                "suggested_interval_ms": _suggested_interval_ms("dual"),
                "items": [],
                "_session_sample": {
                    "mode": "dual",
                    "left_bytes": _encode_bgr_to_jpeg_bytes(left_frame),
                    "right_bytes": _encode_bgr_to_jpeg_bytes(right_frame),
                },
                "runtime_warning": payload.get("runtime_warning"),
            }
        except Exception as exc:
            warning = _diameter_warning(exc)
            targets = [_dual_target_without_diameter(detection, measurement_warning=warning) for detection in detections]
            annotated_rel = _save_pil_image(_render_annotated(left_image, targets or detections), "dual")
            empty_stats = _diameter_axis_stats([], [])
            return {
                "status": "success",
                "mode": "dual",
                "targets": targets,
                "summary": {
                    "total_targets": len(targets),
                    "valid_measurements": 0,
                    "valid_measurements_by_axis": {
                        "horizontal": 0,
                        "vertical": 0,
                    },
                    "measurement_axes": ["horizontal", "vertical"],
                    "fruit_counts": {},
                    "ripeness_counts": {},
                    "statistics": empty_stats,
                    "diameter_statistics": empty_stats,
                },
                "annotated_image": annotated_rel,
                "annotated_image_url": _media_url(annotated_rel),
                "suggested_interval_ms": _suggested_interval_ms("dual"),
                "items": [],
                "_session_sample": {
                    "mode": "dual",
                    "left_bytes": _encode_bgr_to_jpeg_bytes(left_frame),
                    "right_bytes": _encode_bgr_to_jpeg_bytes(right_frame),
                },
                "runtime_warning": warning,
            }

    inference = None
    measurement_warning = None
    try:
        inference = run_diameter_inference(
            yolo_model=app_config.yolo_model,
            left_file=SimpleImageWrapper(left_frame, "realtime_left.png"),
            right_file=SimpleImageWrapper(right_frame, "realtime_right.png"),
            save_color=True,
            detect_conf=0.25,
        )
    except Exception as exc:
        measurement_warning = _diameter_warning(exc)
    classified_targets, fruit_counts, ripeness_counts = _classify_detection_image_targets(
        left_image,
        app_config=app_config,
        detect_ripeness=detect_ripeness,
        source_mode="hybrid",
    )
    horizontal_diameters: List[float] = []
    vertical_diameters: List[float] = []
    merged_targets = []
    for target in classified_targets:
        measured_target = None
        if inference is not None:
            try:
                measured = run_diameter_distance(
                    inference_id=inference["inference_id"],
                    bbox=target["bbox"],
                    save_annotated=False,
                )
                measured_target = (measured.get("targets") or [None])[0]
            except Exception as exc:
                measurement_warning = measurement_warning or _diameter_warning(exc)
        diameter = _build_detection_diameter(measured_target)
        _append_diameter_values(diameter, horizontal_diameters, vertical_diameters)
        target["diameter"] = diameter
        if measurement_warning and diameter is None:
            target["measurement_warning"] = measurement_warning
        merged_targets.append(target)

    stats = _diameter_axis_stats(horizontal_diameters, vertical_diameters)
    annotated_rel = _save_pil_image(_render_annotated(left_image, merged_targets or detections), "hybrid")
    return {
        "status": "success",
        "mode": mode,
        "targets": merged_targets,
        "summary": {
            "total_targets": len(merged_targets),
            "valid_measurements": sum(1 for target in merged_targets if _has_valid_diameter(target.get("diameter"))),
            "valid_measurements_by_axis": {
                "horizontal": len(horizontal_diameters),
                "vertical": len(vertical_diameters),
            },
            "measurement_axes": ["horizontal", "vertical"],
            "fruit_counts": fruit_counts,
            "ripeness_counts": ripeness_counts,
            "statistics": stats,
            "diameter_statistics": stats,
        },
        "annotated_image": annotated_rel,
        "annotated_image_url": _media_url(annotated_rel),
        "suggested_interval_ms": _suggested_interval_ms(mode),
        "items": [],
        "runtime_warning": measurement_warning,
        "_session_sample": {
            "mode": mode,
            "left_bytes": _encode_bgr_to_jpeg_bytes(left_frame),
            "right_bytes": _encode_bgr_to_jpeg_bytes(right_frame),
        },
    }


def run_dual_camera_realtime_detection(
    *,
    app_config,
    left_camera_index: int | None = None,
    right_camera_index: int | None = None,
    detect_classification: bool = False,
    detect_ripeness: bool = False,
    backend: str | None = None,
) -> Dict[str, Any]:
    registry = get_camera_registry_service().snapshot()
    selection = registry.get("selection") or {}
    left_camera_index = int(left_camera_index if left_camera_index is not None else selection.get("dual_left_camera_index", 0))
    right_camera_index = int(right_camera_index if right_camera_index is not None else selection.get("dual_right_camera_index", 1))
    backend = backend if backend is not None else selection.get("backend") or None

    snapshot = get_cached_preview_frame_snapshot()
    if snapshot and (snapshot.get("config") or {}).get("mode") == "dual":
        config = snapshot.get("config") or {}
        if int(config.get("left_camera_index", -1)) == left_camera_index and int(config.get("right_camera_index", -1)) == right_camera_index:
            payload = _run_dual_realtime_detection_from_frames(
                left_frame=snapshot["left_frame"],
                right_frame=snapshot["right_frame"],
                app_config=app_config,
                detect_classification=detect_classification,
                detect_ripeness=detect_ripeness,
                mode="dual",
            )
            payload["frame_source"] = "preview"
            payload["left_camera_index"] = left_camera_index
            payload["right_camera_index"] = right_camera_index
            payload["items"] = [_result_item(mode="dual", payload=payload)]
            return payload

    left_frame, right_frame = capture_dual_camera_frames(left_camera_index, right_camera_index, backend=backend)
    payload = _run_dual_realtime_detection_from_frames(
        left_frame=left_frame,
        right_frame=right_frame,
        app_config=app_config,
        detect_classification=detect_classification,
        detect_ripeness=detect_ripeness,
        mode="dual",
    )
    payload["frame_source"] = "camera"
    payload["left_camera_index"] = left_camera_index
    payload["right_camera_index"] = right_camera_index
    payload["items"] = [_result_item(mode="dual", payload=payload)]
    return payload


def run_hybrid_camera_realtime_detection(
    *,
    app_config,
    left_camera_index: int | None = None,
    right_camera_index: int | None = None,
    detect_ripeness: bool = False,
    backend: str | None = None,
) -> Dict[str, Any]:
    registry = get_camera_registry_service().snapshot()
    selection = registry.get("selection") or {}
    left_camera_index = int(left_camera_index if left_camera_index is not None else selection.get("dual_left_camera_index", 0))
    right_camera_index = int(right_camera_index if right_camera_index is not None else selection.get("dual_right_camera_index", 1))
    backend = backend if backend is not None else selection.get("backend") or None

    snapshot = get_cached_preview_frame_snapshot()
    if snapshot and (snapshot.get("config") or {}).get("mode") == "dual":
        config = snapshot.get("config") or {}
        if int(config.get("left_camera_index", -1)) == left_camera_index and int(config.get("right_camera_index", -1)) == right_camera_index:
            payload = _run_dual_realtime_detection_from_frames(
                left_frame=snapshot["left_frame"],
                right_frame=snapshot["right_frame"],
                app_config=app_config,
                detect_classification=True,
                detect_ripeness=detect_ripeness,
                mode="hybrid",
            )
            payload["frame_source"] = "preview"
            payload["left_camera_index"] = left_camera_index
            payload["right_camera_index"] = right_camera_index
            payload["camera_index"] = int(selection.get("single_camera_index", 0))
            payload["items"] = [_result_item(mode="hybrid", payload=payload)]
            return payload

    left_frame, right_frame = capture_dual_camera_frames(left_camera_index, right_camera_index, backend=backend)
    payload = _run_dual_realtime_detection_from_frames(
        left_frame=left_frame,
        right_frame=right_frame,
        app_config=app_config,
        detect_classification=True,
        detect_ripeness=detect_ripeness,
        mode="hybrid",
    )
    payload["frame_source"] = "camera"
    payload["left_camera_index"] = left_camera_index
    payload["right_camera_index"] = right_camera_index
    payload["camera_index"] = int(selection.get("single_camera_index", 0))
    payload["items"] = [_result_item(mode="hybrid", payload=payload)]
    return payload
