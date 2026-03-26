# fruit_api/views.py
import io
import json
import os
import uuid
import threading
from collections import defaultdict

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageFont, ImageDraw
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .forms import LoginForm
from .models import DetectionHistory
from .serializers import (
    DetectionHistorySerializer,
    ImageUploadSerializer,
    TypeUploadSerializer,
)
from django.apps import apps


# ==================== 历史记录视图 ====================
class DetectionHistoryListView(generics.ListAPIView):
    """获取当前用户的历史记录列表"""
    serializer_class = DetectionHistorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination   # 支持前端分页

    def get_queryset(self):
        return DetectionHistory.objects.filter(user=self.request.user).order_by('-created_at')


class DetectionHistoryDetailView(generics.RetrieveAPIView):
    """获取单条历史记录详情"""
    serializer_class = DetectionHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DetectionHistory.objects.filter(user=self.request.user)


# ==================== 登录/主页视图 ====================
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('fruit_api:home')
            else:
                messages.error(request, '用户名或密码错误')
    else:
        form = LoginForm()
    return render(request, 'login/login.html', {'form': form})


@login_required
def home_view(request):
    if request.user.is_authenticated:
        return render(request, 'login/home.html', {'user': request.user})
    else:
        return redirect('fruit_api:home')


def logout_view(request):
    logout(request)
    return redirect('fruit_api:home')


# ==================== 用户认证 API ====================
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email', '')

    if not username or not password:
        return Response({'status': 'error', 'error': '用户名和密码不能为空'}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({'status': 'error', 'error': '用户名已存在'}, status=400)

    try:
        user = User.objects.create_user(username=username, password=password, email=email)
        login(request, user)
        return Response({
            'status': 'success',
            'message': '注册成功',
            'user': {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'email': user.email,
            }
        }, status=201)
    except Exception as e:
        return Response({'status': 'error', 'error': str(e)}, status=500)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def api_login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({'status': 'error', 'error': '用户名和密码不能为空'}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return Response({
            'status': 'success',
            'message': '登录成功',
            'user': {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'email': user.email,
            }
        })
    else:
        return Response({'status': 'error', 'error': '用户名或密码错误'}, status=401)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_logout_view(request):
    logout(request)
    return Response({'status': 'success', 'message': '已退出登录'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    first_name = request.data.get('first_name', '').strip()
    email = request.data.get('email', '').strip()

    if first_name:
        user.first_name = first_name
    if email:
        user.email = email
    user.save()
    return Response({'status': 'success', 'message': '个人信息更新成功'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')

    if not old_password or not new_password:
        return Response({'status': 'error', 'error': '旧密码和新密码不能为空'}, status=400)
    if not user.check_password(old_password):
        return Response({'status': 'error', 'error': '旧密码错误'}, status=400)
    if len(new_password) < 6:
        return Response({'status': 'error', 'error': '新密码长度至少6位'}, status=400)

    user.set_password(new_password)
    user.save()
    return Response({'status': 'success', 'message': '密码修改成功，请重新登录'})


@api_view(['GET'])
@login_required
def get_user_info(request):
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'email': user.email,
    })


# ==================== 水果分类预测 ====================
@api_view(['POST'])
@login_required
def predict_view(request):
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    image_file = serializer.validated_data['image']
    try:
        img = Image.open(image_file).convert('RGB')
    except Exception:
        return Response({'error': '无效的图片文件'}, status=status.HTTP_400_BAD_REQUEST)

    app_config = apps.get_app_config('fruit_api')
    model = app_config.fruit_model
    preprocess = app_config.fruit_preprocess
    class_names = app_config.fruit_class_names

    img_t = preprocess(img)
    batch_t = torch.unsqueeze(img_t, 0).to(app_config.device)

    with torch.no_grad():
        output = model(batch_t)

    probabilities = F.softmax(output, dim=1)[0]
    predicted_idx = torch.argmax(probabilities).item()
    predicted_label = class_names[predicted_idx]
    predicted_probability = probabilities[predicted_idx].item()

    return Response({
        'predicted_class': predicted_label,
        'confidence': predicted_probability
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@login_required
def predict_with_ripeness(request):
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    image_file = serializer.validated_data['image']
    try:
        img = Image.open(image_file).convert('RGB')
    except Exception:
        return Response({'error': '无效的图片文件'}, status=status.HTTP_400_BAD_REQUEST)

    app_config = apps.get_app_config('fruit_api')

    img_t = app_config.fruit_preprocess(img)
    batch_t = torch.unsqueeze(img_t, 0).to(app_config.device)
    with torch.no_grad():
        output = app_config.fruit_model(batch_t)
    probs = F.softmax(output, dim=1)[0]
    predicted_idx = torch.argmax(probs).item()
    fruit_label = app_config.fruit_class_names[predicted_idx]
    fruit_confidence = probs[predicted_idx].item()

    model, classes = app_config.get_ripeness_info(fruit_label)
    if model is not None:
        img_t_ripe = app_config.ripeness_preprocess(img)
        batch_t_ripe = torch.unsqueeze(img_t_ripe, 0).to(app_config.device)
        with torch.no_grad():
            ripe_output = model(batch_t_ripe)
        ripe_probs = F.softmax(ripe_output, dim=1)[0]
        ripe_conf, ripe_idx = torch.max(ripe_probs, 0)

        prob_dict = {name: ripe_probs[i].item() for i, name in enumerate(classes)}

        return Response({
            'status': 'success',
            'fruit_type': fruit_label,
            'ripeness_result': {
                'predicted_class': classes[ripe_idx],
                'confidence': ripe_conf.item(),
                'probabilities': prob_dict
            }
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            'status': 'success',
            'fruit_type': fruit_label,
            'message': '该水果不属于芒果、香蕉、草莓，无需熟度检测',
            'predicted_class': fruit_label,
            'confidence': fruit_confidence
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@login_required
def predict_ripeness_by_type(request):
    serializer = TypeUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    image_file = serializer.validated_data['image']
    fruit_type = serializer.validated_data['type']
    try:
        img = Image.open(image_file).convert('RGB')
    except Exception:
        return Response({'error': '无效的图片文件'}, status=status.HTTP_400_BAD_REQUEST)

    app_config = apps.get_app_config('fruit_api')
    type_map = {
        'mango': (app_config.mango_model, app_config.mango_classes),
        'banana': (app_config.banana_model, app_config.banana_classes),
        'strawberry': (app_config.strawberry_model, app_config.strawberry_classes),
    }
    if fruit_type not in type_map:
        return Response({'error': '不支持的水果类型，仅支持 mango/banana/strawberry'}, status=status.HTTP_400_BAD_REQUEST)

    model, classes = type_map[fruit_type]

    img_t = app_config.ripeness_preprocess(img)
    batch_t = torch.unsqueeze(img_t, 0).to(app_config.device)
    with torch.no_grad():
        output = model(batch_t)
    probs = F.softmax(output, dim=1)[0]
    conf, idx = torch.max(probs, 0)

    prob_dict = {name: probs[i].item() for i, name in enumerate(classes)}

    return Response({
        'status': 'success',
        'fruit_type': fruit_type,
        'ripeness_result': {
            'predicted_class': classes[idx],
            'confidence': conf.item(),
            'probabilities': prob_dict
        }
    }, status=status.HTTP_200_OK)


# ==================== YOLO 检测接口 ====================
@api_view(['POST'])
@login_required
def yolo_detect_with_boxes(request):
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    image_file = serializer.validated_data['image']
    try:
        img = Image.open(image_file).convert('RGB')
    except Exception:
        return Response({'error': '无效的图片文件'}, status=status.HTTP_400_BAD_REQUEST)

    app_config = apps.get_app_config('fruit_api')
    yolo_model = app_config.yolo_model

    results = yolo_model.predict(source=img, conf=0.25, save=False)
    result = results[0]
    boxes = result.boxes

    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    if boxes is not None and len(boxes) > 0:
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = box.conf[0].item()
            cls = int(box.cls[0].item())
            label = f"{result.names[cls]} {conf:.2f}"
            cv2.rectangle(img_cv, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img_cv, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    img_io = io.BytesIO()
    pil_img.save(img_io, format='JPEG')
    img_io.seek(0)
    return HttpResponse(img_io.read(), content_type='image/jpeg')


@api_view(['POST'])
@login_required
def yolo_detect_info(request):
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    image_file = serializer.validated_data['image']
    try:
        img = Image.open(image_file).convert('RGB')
    except Exception:
        return Response({'error': '无效的图片文件'}, status=status.HTTP_400_BAD_REQUEST)

    app_config = apps.get_app_config('fruit_api')
    yolo_model = app_config.yolo_model

    results = yolo_model.predict(source=img, conf=0.25, save=False)
    result = results[0]
    boxes = result.boxes

    targets = []
    if boxes is not None and len(boxes) > 0:
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = box.conf[0].item()
            cls = int(box.cls[0].item())
            label = result.names[cls]
            targets.append({
                'bbox': [x1, y1, x2, y2],
                'label': label,
                'confidence': conf
            })

    return Response({
        'status': 'success',
        'targets': targets,
        'image_width': img.width,
        'image_height': img.height
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@login_required
def yolo_report(request):
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    image_file = serializer.validated_data['image']
    selected_indices = request.data.get('selected_indices')
    if selected_indices:
        try:
            selected_indices = json.loads(selected_indices)
            if not isinstance(selected_indices, list):
                raise ValueError
            selected_indices = [int(i) for i in selected_indices]
        except:
            return Response({'error': 'selected_indices 格式错误'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        img = Image.open(image_file).convert('RGB')
    except Exception:
        return Response({'error': '无效的图片文件'}, status=status.HTTP_400_BAD_REQUEST)

    app_config = apps.get_app_config('fruit_api')
    yolo_model = app_config.yolo_model
    fruit_model = app_config.fruit_model
    fruit_preprocess = app_config.fruit_preprocess
    fruit_class_names = app_config.fruit_class_names
    ripeness_preprocess = app_config.ripeness_preprocess
    device = app_config.device

    results = yolo_model.predict(source=img, conf=0.25, save=False)
    result = results[0]
    boxes = result.boxes

    targets = []
    if boxes is not None and len(boxes) > 0:
        for i, box in enumerate(boxes):
            if selected_indices is not None and i not in selected_indices:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            cropped_img = img.crop((x1, y1, x2, y2))

            # 水果分类
            img_t = fruit_preprocess(cropped_img)
            batch_t = torch.unsqueeze(img_t, 0).to(device)
            with torch.no_grad():
                output = fruit_model(batch_t)
            probs = F.softmax(output, dim=1)[0]
            predicted_idx = torch.argmax(probs).item()
            fruit_label = fruit_class_names[predicted_idx]
            fruit_confidence = probs[predicted_idx].item()

            # 熟度分析
            model, classes = app_config.get_ripeness_info(fruit_label)
            ripeness_result = None
            if model:
                img_t_ripe = ripeness_preprocess(cropped_img)
                batch_t_ripe = torch.unsqueeze(img_t_ripe, 0).to(device)
                with torch.no_grad():
                    ripe_output = model(batch_t_ripe)
                ripe_probs = F.softmax(ripe_output, dim=1)[0]
                ripe_conf, ripe_idx = torch.max(ripe_probs, 0)
                ripeness_result = {
                    'predicted_class': classes[ripe_idx],
                    'confidence': ripe_conf.item(),
                    'probabilities': {classes[i]: ripe_probs[i].item() for i in range(len(classes))}
                }

            targets.append({
                'bbox': [x1, y1, x2, y2],
                'fruit_classification': {
                    'class': fruit_label,
                    'confidence': fruit_confidence
                },
                'ripeness': ripeness_result
            })

    # 生成报告数据
    report_data = {
        'total_targets': len(targets),
        'targets': targets
    }

    # 统计水果分类和成熟度（用于历史记录）
    fruit_counts = defaultdict(int)
    ripeness_counts = defaultdict(lambda: defaultdict(int))

    for target in targets:
        fruit = target['fruit_classification']['class']
        fruit_counts[fruit] += 1
        if target['ripeness']:
            ripe_class = target['ripeness']['predicted_class']
            ripeness_counts[fruit][ripe_class] += 1

    # 保存报告文件（相对路径，包含 reports/ 子目录）
    report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_filename = f'reports/report_{uuid.uuid4().hex}.json'
    report_path = os.path.join(settings.MEDIA_ROOT, report_filename)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    # 保存历史记录
    if targets:
        DetectionHistory.objects.create(
            user=request.user,
            detection_type='image',
            summary={
                'total_targets': len(targets),
                'fruit_counts': dict(fruit_counts),
                'ripeness_counts': {k: dict(v) for k, v in ripeness_counts.items()}
            },
            report_file=report_filename
        )

    return Response({
        'status': 'success',
        'report': report_data,
        'report_file': os.path.join(settings.MEDIA_URL, report_filename)
    }, status=status.HTTP_200_OK)


# ==================== 视频任务管理 ====================
video_tasks = {}


class VideoTask:
    def __init__(self, task_id, original_file_name, input_path, output_path, process_fps=5, user_id=None):
        self.task_id = task_id
        self.original_file_name = original_file_name
        self.input_path = input_path
        self.output_path = output_path
        self.process_fps = process_fps
        self.status = 'processing'
        self.progress = 0
        self.processed_frames = 0
        self.total_frames = 0
        self.frame_rate = 0
        self.video_width = 0
        self.video_height = 0
        self.message = '任务已创建'
        self.error = None
        self.report_data = None
        self.report_file = None   # 相对路径
        self.user_id = user_id


def process_video_task(task_id):
    task = video_tasks.get(task_id)
    if not task:
        return

    font_path = os.path.join(settings.BASE_DIR, 'fonts', 'SimHei.ttf')
    try:
        font = ImageFont.truetype(font_path, 20)
    except:
        font = ImageFont.load_default()

    app_config = apps.get_app_config('fruit_api')
    yolo_model = app_config.yolo_model
    fruit_model = app_config.fruit_model
    fruit_preprocess = app_config.fruit_preprocess
    fruit_class_names = app_config.fruit_class_names
    ripeness_preprocess = app_config.ripeness_preprocess
    device = app_config.device

    cap = cv2.VideoCapture(str(task.input_path))
    if not cap.isOpened():
        task.status = 'error'
        task.message = '无法打开视频文件'
        return

    task.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    task.frame_rate = cap.get(cv2.CAP_PROP_FPS)
    task.video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    task.video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if task.frame_rate > 0 and task.process_fps > 0:
        sample_interval = max(1, int(task.frame_rate / task.process_fps))
    else:
        sample_interval = 1

    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(str(task.output_path), fourcc, task.frame_rate,
                          (task.video_width, task.video_height))
    frame_count = 0
    processed_count = 0
    total_to_process = task.total_frames

    fruit_counts = {}
    ripeness_counts = {}

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % sample_interval == 0:
                processed_count += 1
                task.progress = int((processed_count / total_to_process) * 100) if total_to_process else 0
                task.processed_frames = processed_count
                task.message = f'正在处理第 {processed_count} / {total_to_process} 帧'

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                draw = ImageDraw.Draw(pil_img)

                results = yolo_model.predict(source=pil_img, conf=0.25, save=False)
                result = results[0]
                boxes = result.boxes

                if boxes is not None and len(boxes) > 0:
                    for box in boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        conf = box.conf[0].item()
                        cls = int(box.cls[0].item())
                        label = result.names[cls]

                        cropped = pil_img.crop((x1, y1, x2, y2))

                        # 水果分类
                        img_t = fruit_preprocess(cropped)
                        batch_t = torch.unsqueeze(img_t, 0).to(device)
                        with torch.no_grad():
                            fruit_output = fruit_model(batch_t)
                        fruit_probs = F.softmax(fruit_output, dim=1)[0]
                        fruit_idx = torch.argmax(fruit_probs).item()
                        fruit_label = fruit_class_names[fruit_idx]
                        fruit_conf = fruit_probs[fruit_idx].item()

                        # 熟度检测
                        model, classes = app_config.get_ripeness_info(fruit_label)
                        ripeness_label = None
                        ripeness_conf = None
                        if model:
                            img_t_ripe = ripeness_preprocess(cropped)
                            batch_t_ripe = torch.unsqueeze(img_t_ripe, 0).to(device)
                            with torch.no_grad():
                                ripe_output = model(batch_t_ripe)
                            ripe_probs = F.softmax(ripe_output, dim=1)[0]
                            ripe_idx = torch.argmax(ripe_probs).item()
                            ripeness_label = classes[ripe_idx]
                            ripeness_conf = ripe_probs[ripe_idx].item()

                        # 更新统计
                        fruit_counts[fruit_label] = fruit_counts.get(fruit_label, 0) + 1
                        if ripeness_label:
                            if fruit_label not in ripeness_counts:
                                ripeness_counts[fruit_label] = {}
                            ripeness_counts[fruit_label][ripeness_label] = ripeness_counts[fruit_label].get(ripeness_label, 0) + 1

                        # 绘制框和标签
                        display_text = f"{fruit_label} {fruit_conf:.2f}"
                        try:
                            bbox = draw.textbbox((0, 0), display_text, font=font)
                            text_w = bbox[2] - bbox[0]
                            text_h = bbox[3] - bbox[1]
                        except:
                            text_w, text_h = 100, 20
                        draw.rectangle([x1, y1, x2, y2], outline=(0, 255, 0), width=2)
                        draw.rectangle([x1, y1 - text_h - 5, x1 + text_w, y1 - 5], fill=(0, 255, 0))
                        draw.text((x1, y1 - text_h - 5), display_text, fill=(0, 0, 0), font=font)

                frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            out.write(frame)
            frame_count += 1

        cap.release()
        out.release()

        report_data = {
            'total_targets': sum(fruit_counts.values()),
            'fruit_counts': fruit_counts,
            'ripeness_counts': ripeness_counts,
        }

        # 保存报告文件（相对路径）
        report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
        os.makedirs(report_dir, exist_ok=True)
        report_filename = f'reports/video_report_{task_id}.json'
        report_path = os.path.join(settings.MEDIA_ROOT, report_filename)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        task.report_data = report_data
        task.report_file = report_filename   # 存储相对路径
        task.status = 'completed'
        task.progress = 100
        task.message = '处理完成'

        # 保存历史记录
        if task.user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=task.user_id)
                DetectionHistory.objects.create(
                    user=user,
                    detection_type='video',
                    summary={
                        'total_targets': report_data['total_targets'],
                        'fruit_counts': report_data['fruit_counts'],
                        'ripeness_counts': report_data['ripeness_counts']
                    },
                    report_file=report_filename
                )
            except User.DoesNotExist:
                pass

    except Exception as e:
        task.status = 'error'
        task.message = str(e)
        task.error = str(e)
        import traceback
        traceback.print_exc()
    finally:
        cap.release()
        if 'out' in locals():
            out.release()


@csrf_exempt
@api_view(['POST'])
@login_required
def video_upload(request):
    if 'file' not in request.FILES:
        return Response({'error': '请选择视频文件'}, status=status.HTTP_400_BAD_REQUEST)

    video_file = request.FILES['file']
    process_fps = int(request.POST.get('processFps', 5))
    process_fps = max(1, min(30, process_fps))

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

    task = VideoTask(
        task_id=task_id,
        original_file_name=video_file.name,
        input_path=input_path,
        output_path=output_path,
        process_fps=process_fps,
        user_id=request.user.id
    )
    video_tasks[task_id] = task

    thread = threading.Thread(target=process_video_task, args=(task_id,))
    thread.daemon = True
    thread.start()

    return Response({
        'status': 'success',
        'taskId': task_id,
        'message': '视频已上传，正在后台处理'
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@login_required
def video_progress(request, task_id):
    task = video_tasks.get(task_id)
    if not task:
        return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

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
        'originalFileName': task.original_file_name
    }

    if task.status == 'completed' and task.report_data:
        response_data['report'] = task.report_data
        if task.report_file:
            response_data['report_file'] = os.path.join(settings.MEDIA_URL, task.report_file)

    return Response(response_data)


@api_view(['GET'])
@login_required
def video_download(request, task_id):
    task = video_tasks.get(task_id)
    if not task:
        return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)
    if task.status != 'completed':
        return Response({'error': '视频尚未处理完成'}, status=status.HTTP_400_BAD_REQUEST)
    if not os.path.exists(task.output_path):
        return Response({'error': '输出文件丢失'}, status=status.HTTP_404_NOT_FOUND)

    with open(task.output_path, 'rb') as f:
        video_data = f.read()

    response = HttpResponse(video_data, content_type='video/mp4')
    response['Content-Disposition'] = f'attachment; filename="processed_{task.original_file_name}"'
    response['Access-Control-Expose-Headers'] = 'Content-Disposition'
    return response


@api_view(['DELETE'])
@login_required
def video_cleanup(request, task_id):
    task = video_tasks.pop(task_id, None)
    if task:
        if os.path.exists(task.input_path):
            os.remove(task.input_path)
        if os.path.exists(task.output_path):
            os.remove(task.output_path)
        if task.report_file:
            report_abs_path = os.path.join(settings.MEDIA_ROOT, task.report_file)
            if os.path.exists(report_abs_path):
                os.remove(report_abs_path)
        return Response({'status': 'success', 'message': '任务已清理'})
    else:
        return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@login_required
def video_report(request, task_id):
    task = video_tasks.get(task_id)
    if not task:
        return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)
    if task.status != 'completed':
        return Response({'error': '视频尚未处理完成'}, status=status.HTTP_400_BAD_REQUEST)
    if not task.report_file:
        return Response({'error': '报告文件不存在'}, status=status.HTTP_404_NOT_FOUND)

    report_abs_path = os.path.join(settings.MEDIA_ROOT, task.report_file)
    if not os.path.exists(report_abs_path):
        return Response({'error': '报告文件丢失'}, status=status.HTTP_404_NOT_FOUND)

    with open(report_abs_path, 'r', encoding='utf-8') as f:
        report_data = json.load(f)
    return Response(report_data)

# views.py
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_realtime_report(request):
    """
    保存实时检测报告
    请求体示例:
    {
        "total_targets": 10,
        "fruit_counts": {"苹果": 3, "香蕉": 2},
        "ripeness_counts": {"香蕉": {"Ripe": 2}}
    }
    """
    data = request.data
    required_keys = ['total_targets', 'fruit_counts', 'ripeness_counts']
    if not all(k in data for k in required_keys):
        return Response({'error': '缺少必要字段'}, status=status.HTTP_400_BAD_REQUEST)

    # 构建 summary
    summary = {
        'total_targets': data['total_targets'],
        'fruit_counts': data['fruit_counts'],
        'ripeness_counts': data['ripeness_counts'],
    }

    # 创建历史记录
    DetectionHistory.objects.create(
        user=request.user,
        detection_type='realtime',
        summary=summary,
        report_file=None   # 实时检测不生成文件
    )

    return Response({'status': 'success', 'message': '报告已保存'}, status=status.HTTP_201_CREATED)