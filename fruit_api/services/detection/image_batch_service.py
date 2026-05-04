from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from openpyxl import Workbook
from PIL import Image, ImageDraw

from django.conf import settings

from fruit_api.diameter_service import SimpleImageWrapper
from fruit_api.models import DetectionHistory
from fruit_api.services.detection.detect_service import (
    build_detection_target,
    summarize_targets,
    yolo_targets,
)
from fruit_api.services.detection.diameter_app_service import get_diameter_service


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _relative_media_path(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.resolve().relative_to(_media_root()).as_posix()


def _task_dir() -> Path:
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    root = _media_root() / "image_tasks" / task_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def _image_from_bytes(content: bytes) -> Image.Image:
    return Image.open(io.BytesIO(content)).convert("RGB")


def _bgr_from_bytes(content: bytes) -> np.ndarray:
    image = _image_from_bytes(content)
    rgb = np.array(image)
    return rgb[:, :, ::-1].copy()


def _save_bytes(path: Path, content: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return _relative_media_path(path)


def _save_pil(path: Path, image: Image.Image, *, format_name: str = "JPEG") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format=format_name)
    return _relative_media_path(path)


def _save_numpy_as_jpeg(path: Path, frame_bgr: np.ndarray) -> str:
    rgb = frame_bgr[:, :, ::-1] if frame_bgr.ndim == 3 and frame_bgr.shape[2] == 3 else frame_bgr
    image = Image.fromarray(rgb)
    return _save_pil(path, image, format_name="JPEG")


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


def _render_annotated_image(image: Image.Image, detections: List[Dict[str, Any]]) -> Image.Image:
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
        label = f"{index + 1}. {display_label}"
        draw.text((x1 + 4, max(0, y1 - 16)), label, fill=(255, 64, 64))

        diameter = detection.get("diameter")
        point1 = _extract_xy((diameter or {}).get("point1"))
        point2 = _extract_xy((diameter or {}).get("point2"))
        distance_label = _diameter_text(diameter)
        if point1 and point2:
            draw.line((point1, point2), fill=(255, 0, 0), width=3)
            radius = 4
            draw.ellipse((point1[0] - radius, point1[1] - radius, point1[0] + radius, point1[1] + radius), fill=(255, 0, 0))
            draw.ellipse((point2[0] - radius, point2[1] - radius, point2[0] + radius, point2[1] + radius), fill=(255, 0, 0))
            if distance_label:
                midpoint = ((point1[0] + point2[0]) // 2, (point1[1] + point2[1]) // 2)
                draw.text((midpoint[0] + 6, max(0, midpoint[1] - 16)), distance_label, fill=(255, 0, 0))
        elif distance_label:
            draw.text((x1 + 4, min(y2 + 4, annotated.height - 16)), distance_label, fill=(255, 0, 0))
    return annotated


def _measure_bbox_with_inference(*, inference_id: str, bbox: List[int]):
    measure_payload = get_diameter_service().measure_distance(
        inference_id=inference_id,
        bbox=[int(v) for v in bbox],
        save_annotated=False,
    )
    targets = measure_payload.get("targets") or []
    return targets[0] if targets else None


def _process_standard_image(item: Dict[str, Any], *, task_root: Path, app_config, detect_ripeness: bool) -> Tuple[Dict[str, Any], Dict[str, int], Dict[str, Dict[str, int]], List[float]]:
    image = _image_from_bytes(item["content"])
    input_dir = task_root / "inputs"
    output_dir = task_root / "outputs"
    original_rel = _save_bytes(input_dir / item["file_name"], item["content"])
    detections = yolo_targets(image, app_config)

    targets = []

    for detection in detections:
        targets.append(
            build_detection_target(
                image,
                detection,
                app_config,
                detect_ripeness=detect_ripeness,
                source_mode="single",
            )
        )
    counts = summarize_targets(targets)

    annotated_rel = _save_pil(
        output_dir / f"{Path(item['file_name']).stem}_annotated.jpg",
        _render_annotated_image(image, targets or detections),
        format_name="JPEG",
    )

    return (
        {
            "item_type": "image",
            "display_name": item["display_name"],
            "original_image": original_rel,
            "annotated_image": annotated_rel,
            "archive_name": item.get("archive_name"),
            "archive_path": item.get("archive_path"),
            "input_source": item.get("input_source"),
            "targets": targets,
        },
        counts["fruit_counts"],
        counts["ripeness_counts"],
        [],
    )


def _process_diameter_group(item: Dict[str, Any], *, task_root: Path, app_config) -> Tuple[Dict[str, Any], Dict[str, int], Dict[str, Dict[str, int]], List[float]]:
    input_dir = task_root / "diameter_inputs" / item["label"]
    left_rel = _save_bytes(input_dir / item["left_name"], item["left_content"])
    right_rel = _save_bytes(input_dir / item["right_name"], item["right_content"])

    right_image = _image_from_bytes(item["right_content"])
    detections = yolo_targets(right_image, app_config)

    inference_payload = get_diameter_service().run_inference(
        yolo_model=app_config.yolo_model,
        left_file=SimpleImageWrapper(_bgr_from_bytes(item["left_content"]), item["left_name"]),
        right_file=SimpleImageWrapper(_bgr_from_bytes(item["right_content"]), item["right_name"]),
        save_color=True,
        detect_conf=0.25,
    )

    targets = []
    diameters = []
    for detection in detections:
        measured = _measure_bbox_with_inference(
            inference_id=inference_payload["inference_id"],
            bbox=detection["bbox"],
        )
        diameter = {
            "distance_mm": measured.get("distance_mm"),
            "distance": measured.get("distance"),
            "distance_unit": measured.get("distance_unit"),
            "status": measured.get("status"),
            "point1": measured.get("point1"),
            "point2": measured.get("point2"),
        } if measured is not None else None
        if measured is not None and measured.get("distance_mm") is not None:
            diameters.append(float(measured["distance_mm"]))
        targets.append(
            {
                "bbox": detection.get("bbox"),
                "label": detection.get("label"),
                "confidence": detection.get("confidence"),
                "classification": None,
                "ripeness": None,
                "diameter": diameter,
                "source_mode": "dual",
            }
        )

    annotated_rel = _save_pil(
        task_root / "diameter_outputs" / f"{item['label']}_annotated.jpg",
        _render_annotated_image(right_image, targets or detections),
        format_name="JPEG",
    )

    return (
        {
            "item_type": "diameter_group",
            "display_name": item["label"],
            "original_image": left_rel,
            "right_image": right_rel,
            "annotated_image": annotated_rel,
            "archive_name": item.get("archive_name"),
            "archive_path": item.get("archive_path"),
            "input_source": item.get("input_source"),
            "targets": targets,
            "statistics": _diameter_stats(diameters),
        },
        {},
        {},
        diameters,
    )


def _process_mixed_group(item: Dict[str, Any], *, task_root: Path, app_config, detect_ripeness: bool) -> Tuple[Dict[str, Any], Dict[str, int], Dict[str, Dict[str, int]], List[float]]:
    input_dir = task_root / "mixed_inputs" / item["label"]
    left_rel = _save_bytes(input_dir / item["left_name"], item["left_content"])
    right_rel = _save_bytes(input_dir / item["right_name"], item["right_content"])

    right_image = _image_from_bytes(item["right_content"])
    detections = yolo_targets(right_image, app_config)

    inference_payload = get_diameter_service().run_inference(
        yolo_model=app_config.yolo_model,
        left_file=SimpleImageWrapper(_bgr_from_bytes(item["left_content"]), item["left_name"]),
        right_file=SimpleImageWrapper(_bgr_from_bytes(item["right_content"]), item["right_name"]),
        save_color=True,
        detect_conf=0.25,
    )

    diameters: List[float] = []
    targets = []

    for detection in detections:
        measured = _measure_bbox_with_inference(inference_id=inference_payload["inference_id"], bbox=detection["bbox"])
        diameter = None
        if measured is not None:
            diameter = {
                "distance_mm": measured.get("distance_mm"),
                "distance": measured.get("distance"),
                "distance_unit": measured.get("distance_unit"),
                "status": measured.get("status"),
                "point1": measured.get("point1"),
                "point2": measured.get("point2"),
            }
            if measured.get("distance_mm") is not None:
                diameters.append(float(measured["distance_mm"]))

        targets.append(
            build_detection_target(
                right_image,
                detection,
                app_config,
                detect_ripeness=detect_ripeness,
                source_mode="hybrid",
                diameter=diameter,
            )
        )
    counts = summarize_targets(targets)

    annotated_rel = _save_pil(
        task_root / "mixed_outputs" / f"{item['label']}_annotated.jpg",
        _render_annotated_image(right_image, targets or detections),
        format_name="JPEG",
    )

    return (
        {
            "item_type": "mixed_group",
            "display_name": item["label"],
            "original_image": left_rel,
            "right_image": right_rel,
            "annotated_image": annotated_rel,
            "archive_name": item.get("archive_name"),
            "archive_path": item.get("archive_path"),
            "input_source": item.get("input_source"),
            "targets": targets,
            "statistics": _diameter_stats(diameters),
        },
        counts["fruit_counts"],
        counts["ripeness_counts"],
        diameters,
    )


def _diameter_stats(values: List[float]) -> Dict[str, Any]:
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


def _compose_title(*, detect_classification: bool, detect_ripeness: bool, detect_diameter: bool) -> str:
    parts = []
    if detect_classification:
        parts.append("种类")
    if detect_ripeness:
        parts.append("熟度")
    if detect_diameter:
        parts.append("果径")
    return f"图片检测任务({' + '.join(parts)})" if parts else "图片检测任务"


def _merge_counts(target: Dict[str, int], source: Dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + int(value or 0)


def _merge_nested_counts(target: Dict[str, Dict[str, int]], source: Dict[str, Dict[str, int]]) -> None:
    for fruit, mapping in source.items():
        target.setdefault(fruit, {})
        for key, value in mapping.items():
            target[fruit][key] = target[fruit].get(key, 0) + int(value or 0)


def _export_report(task_root: Path, *, title: str, items: List[Dict[str, Any]], summary: Dict[str, Any]) -> str:
    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "summary"
    summary_sheet.append(["title", title])
    summary_sheet.append(["total_targets", summary.get("total_targets", 0)])
    summary_sheet.append(["valid_measurements", summary.get("valid_measurements", 0)])
    summary_sheet.append(["fruit_counts", json.dumps(summary.get("fruit_counts", {}), ensure_ascii=False)])
    summary_sheet.append(["ripeness_counts", json.dumps(summary.get("ripeness_counts", {}), ensure_ascii=False)])
    summary_sheet.append(["diameter_statistics", json.dumps(summary.get("diameter_statistics", {}), ensure_ascii=False)])

    detail_sheet = workbook.create_sheet("targets")
    detail_sheet.append(["item", "item_type", "bbox", "class", "class_conf", "ripeness", "ripeness_conf", "diameter_mm", "status"])
    for item in items:
        for target in item.get("targets") or []:
            detail_sheet.append(
                [
                    item.get("display_name"),
                    item.get("item_type"),
                    json.dumps(target.get("bbox"), ensure_ascii=False),
                    (target.get("classification") or {}).get("class") if target.get("classification") else None,
                    (target.get("classification") or {}).get("confidence") if target.get("classification") else None,
                    (target.get("ripeness") or {}).get("predicted_class") if target.get("ripeness") else None,
                    (target.get("ripeness") or {}).get("confidence") if target.get("ripeness") else None,
                    (target.get("diameter") or {}).get("distance_mm") if target.get("diameter") else None,
                    (target.get("diameter") or {}).get("status") if target.get("diameter") else None,
                ]
            )

    report_path = task_root / "report.xlsx"
    workbook.save(report_path)
    return _relative_media_path(report_path)


def execute_image_detection_batch(
    *,
    standard_images: List[Dict],
    diameter_groups: List[Dict],
    options: Dict[str, Any],
    app_config,
    mixed_groups: List[Dict] | None = None,
    task_root: Path | None = None,
):
    mixed_groups = mixed_groups or []
    task_root = task_root or _task_dir()
    items = []
    fruit_counts: Dict[str, int] = {}
    ripeness_counts: Dict[str, Dict[str, int]] = {}
    diameter_values: List[float] = []

    total_inputs = len(standard_images) + len(diameter_groups) + len(mixed_groups)
    processed = 0

    for image_item in standard_images:
        item, item_fruits, item_ripeness, item_diameters = _process_standard_image(
            image_item,
            task_root=task_root,
            app_config=app_config,
            detect_ripeness=bool(options.get("detect_ripeness")),
        )
        items.append(item)
        _merge_counts(fruit_counts, item_fruits)
        _merge_nested_counts(ripeness_counts, item_ripeness)
        diameter_values.extend(item_diameters)
        processed += 1

    for group_item in diameter_groups:
        item, item_fruits, item_ripeness, item_diameters = _process_diameter_group(
            group_item,
            task_root=task_root,
            app_config=app_config,
        )
        items.append(item)
        _merge_counts(fruit_counts, item_fruits)
        _merge_nested_counts(ripeness_counts, item_ripeness)
        diameter_values.extend(item_diameters)
        processed += 1

    for mixed_item in mixed_groups:
        item, item_fruits, item_ripeness, item_diameters = _process_mixed_group(
            mixed_item,
            task_root=task_root,
            app_config=app_config,
            detect_ripeness=bool(options.get("detect_ripeness")),
        )
        items.append(item)
        _merge_counts(fruit_counts, item_fruits)
        _merge_nested_counts(ripeness_counts, item_ripeness)
        diameter_values.extend(item_diameters)
        processed += 1

    total_targets = sum(len(item.get("targets") or []) for item in items)
    valid_measurements = sum(1 for value in diameter_values if value is not None)
    summary = {
        "input_count": total_inputs,
        "total_targets": total_targets,
        "fruit_counts": fruit_counts,
        "ripeness_counts": ripeness_counts,
        "valid_measurements": valid_measurements,
        "diameter_statistics": _diameter_stats([float(v) for v in diameter_values if v is not None]),
        "progress": {
            "processed_items": processed,
            "total_items": total_inputs,
            "progress_percent": 100.0 if total_inputs else 0.0,
            "current_item_label": "",
        },
    }
    detail_data = {
        "task_root": _relative_media_path(task_root),
        "items": items,
        "progress": summary["progress"],
    }
    title = _compose_title(
        detect_classification=bool(options.get("detect_classification") or mixed_groups),
        detect_ripeness=bool(options.get("detect_ripeness")),
        detect_diameter=bool(options.get("detect_diameter") or mixed_groups),
    )
    report_file = _export_report(task_root, title=title, items=items, summary=summary)
    cover_image = next((item.get("annotated_image") or item.get("right_image") or item.get("original_image") for item in items if item), None)

    return {
        "title": title,
        "summary": summary,
        "detail_data": detail_data,
        "artifacts": {"excel_report": report_file},
        "cover_image": cover_image,
        "report_file": report_file,
        "input_count": total_inputs,
        "options": {
            **options,
            "has_mixed_inputs": bool(mixed_groups),
        },
    }


def create_detection_history_from_batch_result(
    *,
    user,
    detection_type: str,
    batch_result: Dict[str, Any],
    options: Dict[str, Any] | None = None,
):
    return DetectionHistory.objects.create(
        user=user,
        detection_type=detection_type,
        title=batch_result["title"],
        status="completed",
        input_count=batch_result.get("input_count", batch_result.get("summary", {}).get("input_count", 0)),
        options=options if options is not None else batch_result.get("options", {}),
        summary=batch_result["summary"],
        detail_data=batch_result["detail_data"],
        artifacts=batch_result.get("artifacts", {}),
        cover_image=batch_result.get("cover_image"),
        report_file=batch_result.get("report_file"),
    )


def create_image_detection_task(
    *,
    user,
    standard_images: List[Dict],
    diameter_groups: List[Dict],
    options: Dict[str, Any],
    app_config,
    mixed_groups: List[Dict] | None = None,
):
    batch_result = execute_image_detection_batch(
        standard_images=standard_images,
        diameter_groups=diameter_groups,
        options=options,
        app_config=app_config,
        mixed_groups=mixed_groups,
    )

    history = create_detection_history_from_batch_result(
        user=user,
        detection_type="image",
        batch_result=batch_result,
        options=batch_result["options"],
    )
    return history


def create_image_detection_task_from_camera_measurement(*, user, left_frame: np.ndarray, right_frame: np.ndarray, payload: Dict[str, Any], options: Dict[str, Any], app_config):
    left_buffer = io.BytesIO()
    right_buffer = io.BytesIO()
    Image.fromarray(left_frame[:, :, ::-1]).save(left_buffer, format="PNG")
    Image.fromarray(right_frame[:, :, ::-1]).save(right_buffer, format="PNG")

    if options.get("detect_classification"):
        mixed_groups = [
            {
                "label": "camera_measurement",
                "left_name": "camera_left.png",
                "right_name": "camera_right.png",
                "left_content": left_buffer.getvalue(),
                "right_content": right_buffer.getvalue(),
                "input_source": "stereo_camera",
                "archive_name": None,
                "archive_path": None,
            }
        ]
        return create_image_detection_task(
            user=user,
            standard_images=[],
            diameter_groups=[],
            mixed_groups=mixed_groups,
            options={
                "detect_classification": True,
                "detect_ripeness": bool(options.get("detect_ripeness")),
                "detect_diameter": True,
            },
            app_config=app_config,
        )

    diameter_groups = [
        {
            "label": "camera_measurement",
            "left_name": "camera_left.png",
            "right_name": "camera_right.png",
            "left_content": left_buffer.getvalue(),
            "right_content": right_buffer.getvalue(),
            "input_source": "stereo_camera",
            "archive_name": None,
            "archive_path": None,
        }
    ]
    return create_image_detection_task(
        user=user,
        standard_images=[],
        diameter_groups=diameter_groups,
        options={
            "detect_classification": False,
            "detect_ripeness": False,
            "detect_diameter": True,
        },
        app_config=app_config,
    )
