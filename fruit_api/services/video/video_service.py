import json
import os
import threading
import uuid

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFont
from django.apps import apps
from django.conf import settings

from fruit_api.models import DetectionHistory, VideoProcessingTask


# Backward-compatible exports (legacy code may import these names)
VideoTask = VideoProcessingTask
video_tasks = {}


class VideoTaskNotFoundError(Exception):
    pass


class VideoTaskStateError(Exception):
    pass


def _get_font():
    font_candidates = [
        os.path.join(settings.BASE_DIR, "public", "fonts", "simhei.ttf"),
        os.path.join(settings.BASE_DIR, "fonts", "SimHei.ttf"),
    ]
    for font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, 20)
            except Exception:
                continue
    return ImageFont.load_default()


def _save_task(task, **kwargs):
    for k, v in kwargs.items():
        setattr(task, k, v)
    update_fields = list(kwargs.keys())
    if 'updated_at' not in update_fields:
        update_fields.append('updated_at')
    task.save(update_fields=update_fields)


def _process_frame(frame, app_config, font, fruit_counts, ripeness_counts):
    yolo_model = app_config.yolo_model
    fruit_model = app_config.fruit_model
    fruit_preprocess = app_config.fruit_preprocess
    fruit_class_names = app_config.fruit_class_names
    ripeness_preprocess = app_config.ripeness_preprocess
    device = app_config.device

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(frame_rgb)
    draw = ImageDraw.Draw(pil_img)

    results = yolo_model.predict(source=pil_img, conf=0.25, save=False)
    result = results[0]
    boxes = result.boxes

    if boxes is not None and len(boxes) > 0:
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            cropped = pil_img.crop((x1, y1, x2, y2))

            img_t = fruit_preprocess(cropped)
            batch_t = torch.unsqueeze(img_t, 0).to(device)
            with torch.no_grad():
                fruit_output = fruit_model(batch_t)
            fruit_probs = F.softmax(fruit_output, dim=1)[0]
            fruit_idx = torch.argmax(fruit_probs).item()
            fruit_label = fruit_class_names[fruit_idx]
            fruit_conf = fruit_probs[fruit_idx].item()

            model, classes = app_config.get_ripeness_info(fruit_label)
            ripeness_label = None
            if model:
                img_t_ripe = ripeness_preprocess(cropped)
                batch_t_ripe = torch.unsqueeze(img_t_ripe, 0).to(device)
                with torch.no_grad():
                    ripe_output = model(batch_t_ripe)
                ripe_probs = F.softmax(ripe_output, dim=1)[0]
                ripe_idx = torch.argmax(ripe_probs).item()
                ripeness_label = classes[ripe_idx]

            fruit_counts[fruit_label] = fruit_counts.get(fruit_label, 0) + 1
            if ripeness_label:
                if fruit_label not in ripeness_counts:
                    ripeness_counts[fruit_label] = {}
                ripeness_counts[fruit_label][ripeness_label] = (
                    ripeness_counts[fruit_label].get(ripeness_label, 0) + 1
                )

            display_text = f"{fruit_label} {fruit_conf:.2f}"
            try:
                bbox = draw.textbbox((0, 0), display_text, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
            except Exception:
                text_w, text_h = 100, 20
            draw.rectangle([x1, y1, x2, y2], outline=(0, 255, 0), width=2)
            draw.rectangle([x1, y1 - text_h - 5, x1 + text_w, y1 - 5], fill=(0, 255, 0))
            draw.text((x1, y1 - text_h - 5), display_text, fill=(0, 0, 0), font=font)

    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def process_video_task(task_id):
    try:
        task = VideoProcessingTask.objects.get(task_id=task_id)
    except VideoProcessingTask.DoesNotExist:
        return

    app_config = apps.get_app_config('fruit_api')
    app_config.ensure_models_loaded()
    font = _get_font()

    cap = cv2.VideoCapture(str(task.input_path))
    if not cap.isOpened():
        _save_task(task, status='error', message='无法打开视频文件', error='无法打开视频文件')
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    _save_task(
        task,
        total_frames=total_frames,
        frame_rate=frame_rate,
        video_width=video_width,
        video_height=video_height,
        status='processing',
    )

    if frame_rate > 0 and task.process_fps > 0:
        sample_interval = max(1, int(frame_rate / task.process_fps))
    else:
        sample_interval = 1

    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(str(task.output_path), fourcc, frame_rate, (video_width, video_height))

    frame_count = 0
    processed_count = 0

    fruit_counts = {}
    ripeness_counts = {}

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % sample_interval == 0:
                processed_count += 1
                progress = int((processed_count / total_frames) * 100) if total_frames else 0
                _save_task(
                    task,
                    progress=progress,
                    processed_frames=processed_count,
                    message=f'正在处理第 {processed_count} / {total_frames} 帧',
                )
                frame = _process_frame(frame, app_config, font, fruit_counts, ripeness_counts)

            out.write(frame)
            frame_count += 1

        report_data = {
            'total_targets': sum(fruit_counts.values()),
            'fruit_counts': fruit_counts,
            'ripeness_counts': ripeness_counts,
        }

        report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
        os.makedirs(report_dir, exist_ok=True)
        report_filename = f'reports/video_report_{task_id}.json'
        report_path = os.path.join(settings.MEDIA_ROOT, report_filename)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        _save_task(
            task,
            report_data=report_data,
            report_file=report_filename,
            status='completed',
            progress=100,
            message='处理完成',
            error='',
        )

        if task.user_id:
            DetectionHistory.objects.create(
                user_id=task.user_id,
                detection_type='video',
                summary={
                    'total_targets': report_data['total_targets'],
                    'fruit_counts': report_data['fruit_counts'],
                    'ripeness_counts': report_data['ripeness_counts'],
                },
                report_file=report_filename,
            )
    except Exception as e:
        _save_task(task, status='error', message=str(e), error=str(e))
        import traceback

        traceback.print_exc()
    finally:
        cap.release()
        out.release()


def create_video_task(video_file, process_fps: int, user_id: int) -> VideoTask:
    process_fps = max(1, min(30, int(process_fps)))
    task_id = uuid.uuid4().hex

    input_dir = os.path.join(settings.MEDIA_ROOT, 'video_input')
    os.makedirs(input_dir, exist_ok=True)
    input_path = os.path.join(input_dir, f'{task_id}_{video_file.name}')
    with open(input_path, 'wb+') as f:
        for chunk in video_file.chunks():
            f.write(chunk)

    output_dir = os.path.join(settings.MEDIA_ROOT, 'video_output')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'processed_{task_id}.mp4')

    return VideoProcessingTask.objects.create(
        task_id=task_id,
        user_id=user_id,
        original_file_name=video_file.name,
        input_path=input_path,
        output_path=output_path,
        process_fps=process_fps,
        status='processing',
        progress=0,
        processed_frames=0,
        total_frames=0,
        frame_rate=0,
        video_width=0,
        video_height=0,
        message='任务已创建',
    )


def start_video_task(task_id: str) -> None:
    thread = threading.Thread(target=process_video_task, args=(task_id,))
    thread.daemon = True
    thread.start()


def get_task(task_id: str) -> VideoTask:
    try:
        return VideoProcessingTask.objects.get(task_id=task_id)
    except VideoProcessingTask.DoesNotExist as exc:
        raise VideoTaskNotFoundError('任务不存在') from exc


def progress_payload(task) -> dict:
    response_data = {
        'taskId': task.task_id,
        'status': task.status,
        'progress': task.progress,
        'processedFrames': task.processed_frames,
        'totalFrames': task.total_frames,
        'videoWidth': task.video_width,
        'videoHeight': task.video_height,
        'frameRate': task.frame_rate,
        'message': task.message,
        'originalFileName': task.original_file_name,
    }

    if task.status == 'completed' and task.report_data:
        response_data['report'] = task.report_data
        if task.report_file:
            response_data['report_file'] = os.path.join(settings.MEDIA_URL, task.report_file)

    return response_data


def validate_completed_task(task):
    if task.status != 'completed':
        raise VideoTaskStateError('视频尚未处理完成')


def cleanup_task(task_id: str) -> None:
    task = get_task(task_id)

    if os.path.exists(task.input_path):
        os.remove(task.input_path)
    if os.path.exists(task.output_path):
        os.remove(task.output_path)
    if task.report_file:
        report_abs_path = os.path.join(settings.MEDIA_ROOT, task.report_file)
        if os.path.exists(report_abs_path):
            os.remove(report_abs_path)

    task.delete()


def load_video_output_bytes(task) -> bytes:
    validate_completed_task(task)
    if not os.path.exists(task.output_path):
        raise FileNotFoundError('输出文件丢失')
    with open(task.output_path, 'rb') as f:
        return f.read()


def load_video_report(task) -> dict:
    validate_completed_task(task)
    if not task.report_file:
        raise FileNotFoundError('报告文件不存在')

    report_abs_path = os.path.join(settings.MEDIA_ROOT, task.report_file)
    if not os.path.exists(report_abs_path):
        raise FileNotFoundError('报告文件丢失')

    with open(report_abs_path, 'r', encoding='utf-8') as f:
        return json.load(f)
