import io
import json
import os
import uuid
from collections import defaultdict
from typing import Dict, List, Optional

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from django.conf import settings


class DetectServiceError(Exception):
    pass


class InvalidImageError(DetectServiceError):
    pass


class InvalidParamError(DetectServiceError):
    pass


SUPPORTED_RIPENESS_TYPES = ("mango", "banana", "strawberry")
YOLO_LABEL_MAPPING = {
    "banana": "banana",
    "mango": "mango",
    "strawberry": "strawberry",
}


def load_rgb_image(image_file) -> Image.Image:
    try:
        return Image.open(image_file).convert("RGB")
    except Exception as exc:
        raise InvalidImageError("无效的图片文件") from exc


def normalize_yolo_label(label: Optional[str]) -> str:
    normalized = (label or "").strip().lower()
    return YOLO_LABEL_MAPPING.get(normalized, normalized)


def classify_yolo_detection(detection: Dict) -> Dict:
    raw_label = detection.get("label")
    normalized_label = detection.get("normalized_label") or normalize_yolo_label(raw_label)
    confidence = float(detection.get("confidence") or 0.0)
    classification = {
        "predicted_class": normalized_label,
        "confidence": confidence,
        "raw_label": raw_label,
    }
    if detection.get("class_id") is not None:
        classification["class_id"] = int(detection["class_id"])
    return classification


def classify_fruit(img: Image.Image, app_config) -> Dict:
    targets = extract_detection_targets(img, app_config, detect_ripeness=False, source_mode="single")
    if not targets:
        return {
            "status": "success",
            "total_targets": 0,
            "targets": [],
            "message": "未检测到支持的水果目标",
        }

    primary = targets[0]
    classification = primary["classification"]
    return {
        "status": "success",
        "predicted_class": classification["class"],
        "confidence": classification["confidence"],
        "total_targets": len(targets),
        "targets": targets,
    }


def classify_with_ripeness(img: Image.Image, app_config) -> Dict:
    targets = extract_detection_targets(img, app_config, detect_ripeness=True, source_mode="single")
    if not targets:
        return {
            "status": "success",
            "total_targets": 0,
            "targets": [],
            "message": "未检测到支持的水果目标",
        }

    primary = targets[0]
    classification = primary["classification"]
    return {
        "status": "success",
        "fruit_type": classification["class"],
        "predicted_class": classification["class"],
        "confidence": classification["confidence"],
        "ripeness_result": primary.get("ripeness"),
        "total_targets": len(targets),
        "targets": targets,
    }


def classify_ripeness_by_type(img: Image.Image, fruit_type: str, app_config) -> Dict:
    normalized_type = normalize_yolo_label(fruit_type)
    model, classes = app_config.get_ripeness_info(normalized_type)
    if model is None:
        raise InvalidParamError(f"不支持的水果类型，仅支持 {'/'.join(SUPPORTED_RIPENESS_TYPES)}")

    return {
        "status": "success",
        "fruit_type": normalized_type,
        "ripeness_result": _predict_ripeness(img, model, classes, app_config),
    }


def classify_ripeness_for_fruit_crop(img: Image.Image, fruit_label: str, app_config) -> Optional[Dict]:
    normalized_label = normalize_yolo_label(fruit_label)
    model, classes = app_config.get_ripeness_info(normalized_label)
    if model is None:
        return None

    return _predict_ripeness(img, model, classes, app_config)


def _predict_ripeness(img: Image.Image, model, classes: List[str], app_config) -> Dict:
    img_t_ripe = app_config.ripeness_preprocess(img)
    batch_t_ripe = torch.unsqueeze(img_t_ripe, 0).to(app_config.device)
    with torch.no_grad():
        ripe_output = model(batch_t_ripe)
    ripe_probs = F.softmax(ripe_output, dim=1)[0]
    ripe_conf, ripe_idx = torch.max(ripe_probs, 0)
    predicted_index = ripe_idx.item()
    return {
        "predicted_class": classes[predicted_index],
        "confidence": ripe_conf.item(),
        "probabilities": {name: ripe_probs[i].item() for i, name in enumerate(classes)},
    }


def yolo_boxes_image_bytes(img: Image.Image, app_config, conf: float = 0.25) -> bytes:
    result = run_yolo_prediction(img, app_config, conf=conf)
    boxes = result.boxes

    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    if boxes is not None and len(boxes) > 0:
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            score = box.conf[0].item()
            cls = int(box.cls[0].item())
            label = f"{result.names[cls]} {score:.2f}"
            cv2.rectangle(img_cv, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img_cv, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    img_io = io.BytesIO()
    pil_img.save(img_io, format="JPEG")
    img_io.seek(0)
    return img_io.read()


def yolo_targets(img: Image.Image, app_config, conf: float = 0.25) -> List[Dict]:
    result = run_yolo_prediction(img, app_config, conf=conf)
    boxes = result.boxes

    targets: List[Dict] = []
    if boxes is not None and len(boxes) > 0:
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            score = box.conf[0].item()
            cls = int(box.cls[0].item())
            raw_label = result.names[cls]
            targets.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "label": raw_label,
                    "normalized_label": normalize_yolo_label(raw_label),
                    "confidence": score,
                    "class_id": cls,
                }
            )
    return targets


def run_yolo_prediction(img: Image.Image, app_config, conf: float = 0.25):
    yolo_model = app_config.yolo_model
    results = yolo_model.predict(source=img, conf=conf, save=False, verbose=False)
    return results[0]


def parse_selected_indices(raw: Optional[str]) -> Optional[List[int]]:
    if not raw:
        return None
    try:
        selected_indices = json.loads(raw)
        if not isinstance(selected_indices, list):
            raise ValueError
        return [int(i) for i in selected_indices]
    except Exception as exc:
        raise InvalidParamError("selected_indices 格式错误") from exc


def build_detection_target(
    img: Image.Image,
    detection: Dict,
    app_config,
    *,
    detect_ripeness: bool = False,
    source_mode: str = "single",
    diameter: Optional[Dict] = None,
) -> Dict:
    x1, y1, x2, y2 = detection["bbox"]
    crop = img.crop((x1, y1, x2, y2))
    classification = classify_yolo_detection(detection)
    ripeness = (
        classify_ripeness_for_fruit_crop(crop, classification["predicted_class"], app_config)
        if detect_ripeness
        else None
    )

    target = {
        "bbox": [int(v) for v in detection["bbox"]],
        "label": detection.get("label"),
        "normalized_label": classification["predicted_class"],
        "class_id": detection.get("class_id"),
        "confidence": classification["confidence"],
        "fruit_class": classification["predicted_class"],
        "fruit_confidence": classification["confidence"],
        "classification": {
            "class": classification["predicted_class"],
            "confidence": classification["confidence"],
            "source": "yolo",
            "raw_label": classification.get("raw_label"),
            "class_id": classification.get("class_id"),
        },
        "ripeness": {
            "predicted_class": ripeness.get("predicted_class"),
            "confidence": ripeness.get("confidence"),
        }
        if ripeness
        else None,
        "diameter": diameter,
        "source_mode": source_mode,
    }
    return target


def extract_detection_targets(
    img: Image.Image,
    app_config,
    *,
    conf: float = 0.25,
    selected_indices: Optional[List[int]] = None,
    detect_ripeness: bool = False,
    source_mode: str = "single",
) -> List[Dict]:
    detections = yolo_targets(img, app_config, conf=conf)
    targets = []
    for index, detection in enumerate(detections):
        if selected_indices is not None and index not in selected_indices:
            continue
        targets.append(
            build_detection_target(
                img,
                detection,
                app_config,
                detect_ripeness=detect_ripeness,
                source_mode=source_mode,
            )
        )
    return targets


def summarize_targets(targets: List[Dict]) -> Dict:
    fruit_counts = defaultdict(int)
    ripeness_counts = defaultdict(lambda: defaultdict(int))
    for target in targets:
        fruit = ((target.get("classification") or {}).get("class") or target.get("fruit_class"))
        if not fruit:
            continue
        fruit_counts[fruit] += 1
        ripeness = target.get("ripeness") or {}
        ripe_class = ripeness.get("predicted_class")
        if ripe_class:
            ripeness_counts[fruit][ripe_class] += 1

    return {
        "fruit_counts": dict(fruit_counts),
        "ripeness_counts": {key: dict(value) for key, value in ripeness_counts.items()},
    }


def build_report_data(img: Image.Image, app_config, selected_indices: Optional[List[int]] = None) -> Dict:
    targets = extract_detection_targets(
        img,
        app_config,
        selected_indices=selected_indices,
        detect_ripeness=True,
        source_mode="single",
    )
    counts = summarize_targets(targets)

    report_targets = []
    for target in targets:
        report_targets.append(
            {
                "bbox": target["bbox"],
                "fruit_classification": {
                    "class": target["classification"]["class"],
                    "confidence": target["classification"]["confidence"],
                    "source": target["classification"].get("source"),
                    "raw_label": target["classification"].get("raw_label"),
                },
                "ripeness": target.get("ripeness"),
            }
        )

    report_data = {"total_targets": len(report_targets), "targets": report_targets}
    summary = {
        "total_targets": len(report_targets),
        "fruit_counts": counts["fruit_counts"],
        "ripeness_counts": counts["ripeness_counts"],
    }

    return {"report_data": report_data, "targets": targets, "summary": summary}


def save_report(report_data: Dict) -> str:
    report_dir = os.path.join(settings.MEDIA_ROOT, "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_filename = f"reports/report_{uuid.uuid4().hex}.json"
    report_path = os.path.join(settings.MEDIA_ROOT, report_filename)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    return report_filename
