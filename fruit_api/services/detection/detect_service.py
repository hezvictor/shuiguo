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


def load_rgb_image(image_file) -> Image.Image:
    try:
        return Image.open(image_file).convert('RGB')
    except Exception as exc:
        raise InvalidImageError('无效的图片文件') from exc


def classify_fruit(img: Image.Image, app_config) -> Dict:
    return classify_fruit_crop(img, app_config)


def classify_fruit_crop(img: Image.Image, app_config) -> Dict:
    img_t = app_config.fruit_preprocess(img)
    batch_t = torch.unsqueeze(img_t, 0).to(app_config.device)

    with torch.no_grad():
        output = app_config.fruit_model(batch_t)

    probabilities = F.softmax(output, dim=1)[0]
    predicted_idx = torch.argmax(probabilities).item()
    predicted_label = app_config.fruit_class_names[predicted_idx]
    predicted_probability = probabilities[predicted_idx].item()

    return {
        'predicted_class': predicted_label,
        'confidence': predicted_probability,
    }


def classify_with_ripeness(img: Image.Image, app_config) -> Dict:
    fruit_result = classify_fruit_crop(img, app_config)
    fruit_label = fruit_result['predicted_class']

    ripeness_result = classify_ripeness_for_fruit_crop(img, fruit_label, app_config)
    if ripeness_result is None:
        return {
            'status': 'success',
            'fruit_type': fruit_label,
            'message': '该水果无需熟度检测',
            'predicted_class': fruit_label,
            'confidence': fruit_result['confidence'],
        }

    return {
        'status': 'success',
        'fruit_type': fruit_label,
        'ripeness_result': ripeness_result,
    }


def classify_ripeness_by_type(img: Image.Image, fruit_type: str, app_config) -> Dict:
    type_map = {
        'mango': (app_config.mango_model, app_config.mango_classes),
        'banana': (app_config.banana_model, app_config.banana_classes),
        'strawberry': (app_config.strawberry_model, app_config.strawberry_classes),
    }
    if fruit_type not in type_map:
        raise InvalidParamError('不支持的水果类型，仅支持 mango/banana/strawberry')

    model, classes = type_map[fruit_type]

    img_t = app_config.ripeness_preprocess(img)
    batch_t = torch.unsqueeze(img_t, 0).to(app_config.device)
    with torch.no_grad():
        output = model(batch_t)
    probs = F.softmax(output, dim=1)[0]
    conf, idx = torch.max(probs, 0)

    prob_dict = {name: probs[i].item() for i, name in enumerate(classes)}

    return {
        'status': 'success',
        'fruit_type': fruit_type,
        'ripeness_result': {
            'predicted_class': classes[idx],
            'confidence': conf.item(),
            'probabilities': prob_dict,
        },
    }


def classify_ripeness_for_fruit_crop(img: Image.Image, fruit_label: str, app_config) -> Optional[Dict]:
    model, classes = app_config.get_ripeness_info(fruit_label)
    if model is None:
        return None

    img_t_ripe = app_config.ripeness_preprocess(img)
    batch_t_ripe = torch.unsqueeze(img_t_ripe, 0).to(app_config.device)
    with torch.no_grad():
        ripe_output = model(batch_t_ripe)
    ripe_probs = F.softmax(ripe_output, dim=1)[0]
    ripe_conf, ripe_idx = torch.max(ripe_probs, 0)
    return {
        'predicted_class': classes[ripe_idx],
        'confidence': ripe_conf.item(),
        'probabilities': {name: ripe_probs[i].item() for i, name in enumerate(classes)},
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
    pil_img.save(img_io, format='JPEG')
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
            label = result.names[cls]
            targets.append({'bbox': [x1, y1, x2, y2], 'label': label, 'confidence': score})
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
        raise InvalidParamError('selected_indices 格式错误') from exc


def build_report_data(img: Image.Image, app_config, selected_indices: Optional[List[int]] = None) -> Dict:
    result = run_yolo_prediction(img, app_config, conf=0.25)
    boxes = result.boxes

    targets = []
    if boxes is not None and len(boxes) > 0:
        for i, box in enumerate(boxes):
            if selected_indices is not None and i not in selected_indices:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            cropped_img = img.crop((x1, y1, x2, y2))

            fruit_result = classify_fruit_crop(cropped_img, app_config)
            fruit_label = fruit_result['predicted_class']
            fruit_confidence = fruit_result['confidence']
            ripeness_result = classify_ripeness_for_fruit_crop(cropped_img, fruit_label, app_config)

            targets.append(
                {
                    'bbox': [x1, y1, x2, y2],
                    'fruit_classification': {'class': fruit_label, 'confidence': fruit_confidence},
                    'ripeness': ripeness_result,
                }
            )

    fruit_counts = defaultdict(int)
    ripeness_counts = defaultdict(lambda: defaultdict(int))
    for target in targets:
        fruit = target['fruit_classification']['class']
        fruit_counts[fruit] += 1
        if target['ripeness']:
            ripe_class = target['ripeness']['predicted_class']
            ripeness_counts[fruit][ripe_class] += 1

    report_data = {'total_targets': len(targets), 'targets': targets}
    summary = {
        'total_targets': len(targets),
        'fruit_counts': dict(fruit_counts),
        'ripeness_counts': {k: dict(v) for k, v in ripeness_counts.items()},
    }

    return {'report_data': report_data, 'targets': targets, 'summary': summary}


def save_report(report_data: Dict) -> str:
    report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_filename = f"reports/report_{uuid.uuid4().hex}.json"
    report_path = os.path.join(settings.MEDIA_ROOT, report_filename)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    return report_filename
