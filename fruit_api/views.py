# fruit_api/views.py
import io
import json
import os
import uuid

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.shortcuts import redirect, render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .forms import LoginForm
from .serializers import ImageUploadSerializer, TypeUploadSerializer
from django.apps import apps
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.contrib.auth.decorators import login_required
import uuid
import threading
import cv2
import os
from django.conf import settings
# 原有的登录视图
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


# 原有的水果分类预测视图
@api_view(['POST'])
@login_required
def predict_view(request):
    """
    接收图片，返回预测结果。
    """
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    image_file = serializer.validated_data['image']

    try:
        # 打开图片并转换为RGB
        img = Image.open(image_file).convert('RGB')
    except Exception:
        return Response({'error': '无效的图片文件'}, status=status.HTTP_400_BAD_REQUEST)

    # 从 app config 获取模型和预处理函数
    app_config = apps.get_app_config('fruit_api')
    model = app_config.fruit_model
    preprocess = app_config.fruit_preprocess
    class_names = app_config.fruit_class_names

    # 预处理
    img_t = preprocess(img)
    batch_t = torch.unsqueeze(img_t, 0).to(app_config.device)

    # 预测
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


# 接口1：自动检测熟度
@api_view(['POST'])
@login_required
def predict_with_ripeness(request):
    """
    接口1：上传图片，先水果分类，如果是芒果/香蕉/草莓则进一步做熟度检测。
    """
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    image_file = serializer.validated_data['image']
    try:
        img = Image.open(image_file).convert('RGB')
    except Exception:
        return Response({'error': '无效的图片文件'}, status=status.HTTP_400_BAD_REQUEST)

    app_config = apps.get_app_config('fruit_api')

    # 1. 水果分类预测
    img_t = app_config.fruit_preprocess(img)
    batch_t = torch.unsqueeze(img_t, 0).to(app_config.device)
    with torch.no_grad():
        output = app_config.fruit_model(batch_t)
    probs = F.softmax(output, dim=1)[0]
    predicted_idx = torch.argmax(probs).item()
    fruit_label = app_config.fruit_class_names[predicted_idx]
    fruit_confidence = probs[predicted_idx].item()

    # 2. 判断是否需要熟度检测
    model, classes = app_config.get_ripeness_info(fruit_label)
    if model is not None:
        # 预处理并预测
        img_t_ripe = app_config.ripeness_preprocess(img)
        batch_t_ripe = torch.unsqueeze(img_t_ripe, 0).to(app_config.device)
        with torch.no_grad():
            ripe_output = model(batch_t_ripe)
        ripe_probs = F.softmax(ripe_output, dim=1)[0]
        ripe_conf, ripe_idx = torch.max(ripe_probs, 0)

        # 构造概率字典
        prob_dict = {}
        for i, name in enumerate(classes):
            prob_dict[name] = ripe_probs[i].item()

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
        # 非目标水果，返回水果分类结果
        return Response({
            'status': 'success',
            'fruit_type': fruit_label,
            'message': '该水果不属于芒果、香蕉、草莓，无需熟度检测',
            'predicted_class': fruit_label,
            'confidence': fruit_confidence
        }, status=status.HTTP_200_OK)


# 接口2：指定类型检测熟度
@api_view(['POST'])
@login_required
def predict_ripeness_by_type(request):
    """
    接口2：上传图片并指定类型（mango/banana/strawberry），直接进行熟度检测。
    """
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

    # 根据类型选择模型
    type_map = {
        'mango': (app_config.mango_model, app_config.mango_classes),
        'banana': (app_config.banana_model, app_config.banana_classes),
        'strawberry': (app_config.strawberry_model, app_config.strawberry_classes),
    }
    if fruit_type not in type_map:
        return Response({'error': '不支持的水果类型，仅支持 mango/banana/strawberry'}, status=status.HTTP_400_BAD_REQUEST)

    model, classes = type_map[fruit_type]

    # 预处理并预测
    img_t = app_config.ripeness_preprocess(img)
    batch_t = torch.unsqueeze(img_t, 0).to(app_config.device)
    with torch.no_grad():
        output = model(batch_t)
    probs = F.softmax(output, dim=1)[0]
    conf, idx = torch.max(probs, 0)

    prob_dict = {}
    for i, name in enumerate(classes):
        prob_dict[name] = probs[i].item()

    return Response({
        'status': 'success',
        'fruit_type': fruit_type,
        'ripeness_result': {
            'predicted_class': classes[idx],
            'confidence': conf.item(),
            'probabilities': prob_dict
        }
    }, status=status.HTTP_200_OK)


# ========== 新增的 YOLO 接口 ==========

@api_view(['POST'])
@login_required
def yolo_detect_with_boxes(request):
    """
    接口1：上传图片，YOLO检测并绘制边界框，返回带框的图片。
    """
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

    # 运行YOLO预测，save=False 不保存到文件，只返回结果
    results = yolo_model.predict(source=img, conf=0.25, save=False)
    result = results[0]
    boxes = result.boxes

    # 转换为OpenCV格式并绘制框
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    if boxes is not None and len(boxes) > 0:
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = box.conf[0].item()
            cls = int(box.cls[0].item())
            label = f"{result.names[cls]} {conf:.2f}"
            cv2.rectangle(img_cv, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img_cv, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # 将结果转为JPEG字节流返回
    img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    img_io = io.BytesIO()
    pil_img.save(img_io, format='JPEG')
    img_io.seek(0)
    return HttpResponse(img_io.read(), content_type='image/jpeg')

@api_view(['POST'])
@login_required
def yolo_detect_info(request):
    """
    接口：上传图片，YOLO检测，返回目标列表（不含图片）。
    """
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
    # 获取选中的目标索引（JSON 字符串）
    selected_indices = request.data.get('selected_indices')
    if selected_indices:
        try:
            selected_indices = json.loads(selected_indices)   # 解析 JSON 列表
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

    # YOLO 检测
    results = yolo_model.predict(source=img, conf=0.25, save=False)
    result = results[0]
    boxes = result.boxes

    targets = []
    if boxes is not None and len(boxes) > 0:
        for i, box in enumerate(boxes):
            # 如果提供了 selected_indices，则只处理选中的目标
            if selected_indices is not None and i not in selected_indices:
                continue

            # 裁剪目标区域
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            cropped_img = img.crop((x1, y1, x2, y2))

            # 1. 水果分类
            img_t = fruit_preprocess(cropped_img)
            batch_t = torch.unsqueeze(img_t, 0).to(device)
            with torch.no_grad():
                output = fruit_model(batch_t)
            probs = F.softmax(output, dim=1)[0]
            predicted_idx = torch.argmax(probs).item()
            fruit_label = fruit_class_names[predicted_idx]
            fruit_confidence = probs[predicted_idx].item()

            # 2. 熟度分析（仅支持芒果、香蕉、草莓）
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

    # 保存报告文件（可选）
    report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_filename = f'report_{uuid.uuid4().hex}.json'
    report_path = os.path.join(report_dir, report_filename)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    return Response({
        'status': 'success',
        'report': report_data,
        'report_file': os.path.join(settings.MEDIA_URL, 'reports', report_filename)
    }, status=status.HTTP_200_OK)
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
        login(request, user)  # 自动登录
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
# 新增登录API
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
        # 返回用户信息，供前端直接存储
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
    from django.contrib.auth import logout
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
    # 修改密码后，使当前会话失效（需要重新登录）
    return Response({'status': 'success', 'message': '密码修改成功，请重新登录'})

# 退出登录视图（用于前端链接）
from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    logout(request)
    return redirect('fruit_api:home')

@api_view(['GET'])
@login_required
def get_user_info(request):
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'email': user.email,
        # 如果需要更多字段，可以扩展 User 模型
    })







# ========== 视频任务管理 ==========
video_tasks = {}


class VideoTask:
    """视频任务状态"""
    def __init__(self, task_id, original_file_name, input_path, output_path, process_fps=5):
        self.task_id = task_id
        self.original_file_name = original_file_name
        self.input_path = input_path
        self.output_path = output_path
        self.process_fps = process_fps
        self.status = 'processing'   # processing, completed, error
        self.progress = 0
        self.processed_frames = 0
        self.total_frames = 0
        self.frame_rate = 0
        self.video_width = 0
        self.video_height = 0
        self.message = '任务已创建'
        self.error = None
        self.report_data = None       # 报告数据字典
        self.report_file = None       # 报告文件路径


def process_video_task(task_id):
    """后台处理视频（在线程中运行），并生成报告"""
    task = video_tasks.get(task_id)
    if not task:
        return

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

    # 获取视频信息
    task.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    task.frame_rate = cap.get(cv2.CAP_PROP_FPS)
    task.video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    task.video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 计算采样间隔：每多少帧处理一次（target_fps = process_fps）
    if task.frame_rate > 0 and task.process_fps > 0:
        sample_interval = max(1, int(task.frame_rate / task.process_fps))
    else:
        sample_interval = 1

    # 准备视频写入器
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(task.output_path), fourcc, task.frame_rate,
                          (task.video_width, task.video_height))
    frame_count = 0
    processed_count = 0
    total_to_process = task.total_frames

    # 统计变量
    fruit_counts = {}           # 水果分类计数
    ripeness_counts = {}        # 成熟度分类计数，按水果类型组织

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 每隔 sample_interval 帧处理一次
            if frame_count % sample_interval == 0:
                processed_count += 1
                # 更新进度
                task.progress = int((processed_count / total_to_process) * 100) if total_to_process else 0
                task.processed_frames = processed_count
                task.message = f'正在处理第 {processed_count} / {total_to_process} 帧'

                # 将 OpenCV 帧 (BGR) 转为 PIL Image (RGB)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)

                # YOLO 检测
                results = yolo_model.predict(source=pil_img, conf=0.25, save=False)
                result = results[0]
                boxes = result.boxes

                # 绘制检测框和标签
                if boxes is not None and len(boxes) > 0:
                    for box in boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        conf = box.conf[0].item()
                        cls = int(box.cls[0].item())
                        label = result.names[cls]

                        # 裁剪目标区域进行水果分类和熟度检测
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

                        # 熟度检测（仅支持芒果、香蕉、草莓）
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

                        # 在帧上绘制信息
                        display_text = f"{label} {conf:.2f}"
                        if fruit_label:
                            display_text += f" | {fruit_label} {fruit_conf:.2f}"
                        if ripeness_label:
                            display_text += f" | {ripeness_label} {ripeness_conf:.2f}"

                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        # 背景
                        (text_w, text_h), _ = cv2.getTextSize(display_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                        cv2.rectangle(frame, (x1, y1 - text_h - 5), (x1 + text_w, y1), (0, 255, 0), -1)
                        cv2.putText(frame, display_text, (x1, y1 - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

            # 写入帧（无论是否处理，都写入以保持视频长度）
            out.write(frame)
            frame_count += 1

        cap.release()
        out.release()

        # 生成报告
        report_data = {
            'total_targets': sum(fruit_counts.values()),  # 总目标数（帧级）
            'fruit_counts': fruit_counts,
            'ripeness_counts': ripeness_counts,
        }

        # 保存报告文件
        report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
        os.makedirs(report_dir, exist_ok=True)
        report_filename = f'video_report_{task_id}.json'
        report_path = os.path.join(report_dir, report_filename)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        task.report_data = report_data
        task.report_file = report_path
        task.status = 'completed'
        task.progress = 100
        task.message = '处理完成'
    except Exception as e:
        task.status = 'error'
        task.message = str(e)
        task.error = str(e)
        import traceback
        traceback.print_exc()
    finally:
        # 确保资源释放
        cap.release()
        if 'out' in locals():
            out.release()


# ================== API 视图 ==================
@csrf_exempt
@api_view(['POST'])
@login_required
def video_upload(request):
    """
    上传视频，创建后台任务，返回 task_id
    """
    if 'file' not in request.FILES:
        return Response({'error': '请选择视频文件'}, status=status.HTTP_400_BAD_REQUEST)

    video_file = request.FILES['file']
    process_fps = int(request.POST.get('processFps', 5))
    process_fps = max(1, min(30, process_fps))   # 限制 1~30

    # 生成唯一任务ID
    task_id = uuid.uuid4().hex

    # 保存上传视频到临时目录
    input_dir = os.path.join(settings.MEDIA_ROOT, 'video_input')
    os.makedirs(input_dir, exist_ok=True)
    input_path = os.path.join(input_dir, f'{task_id}_{video_file.name}')
    with open(input_path, 'wb+') as f:
        for chunk in video_file.chunks():
            f.write(chunk)

    output_dir = os.path.join(settings.MEDIA_ROOT, 'video_output')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'processed_{task_id}.mp4')

    # 创建任务对象
    task = VideoTask(
        task_id=task_id,
        original_file_name=video_file.name,
        input_path=input_path,
        output_path=output_path,
        process_fps=process_fps
    )
    video_tasks[task_id] = task

    # 启动后台线程处理
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
    """查询任务进度，完成时返回报告"""
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
        # 可选：提供报告文件URL
        if task.report_file:
            response_data['report_file'] = os.path.join(settings.MEDIA_URL, 'reports', f'video_report_{task_id}.json')

    return Response(response_data)


@api_view(['GET'])
@login_required
def video_download(request, task_id):
    """下载处理后的视频"""
    task = video_tasks.get(task_id)
    if not task:
        return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)
    if task.status != 'completed':
        return Response({'error': '视频尚未处理完成'}, status=status.HTTP_400_BAD_REQUEST)
    if not os.path.exists(task.output_path):
        return Response({'error': '输出文件丢失'}, status=status.HTTP_404_NOT_FOUND)

    with open(task.output_path, 'rb') as f:
        video_data = f.read()

    # 构建响应，明确指定 Content-Type 和 Content-Disposition
    response = HttpResponse(video_data, content_type='video/mp4')
    response['Content-Disposition'] = f'attachment; filename="processed_{task.original_file_name}"'
    # 添加 CORS 头，允许前端访问（生产环境应具体配置）
    response['Access-Control-Expose-Headers'] = 'Content-Disposition'
    return response


@api_view(['DELETE'])
@login_required
def video_cleanup(request, task_id):
    """清理任务及临时文件"""
    task = video_tasks.pop(task_id, None)
    if task:
        # 删除输入输出文件
        if os.path.exists(task.input_path):
            os.remove(task.input_path)
        if os.path.exists(task.output_path):
            os.remove(task.output_path)
        # 删除报告文件
        if task.report_file and os.path.exists(task.report_file):
            os.remove(task.report_file)
        return Response({'status': 'success', 'message': '任务已清理'})
    else:
        return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@login_required
def video_report(request, task_id):
    """获取视频处理报告（JSON）"""
    task = video_tasks.get(task_id)
    if not task:
        return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)
    if task.status != 'completed':
        return Response({'error': '视频尚未处理完成'}, status=status.HTTP_400_BAD_REQUEST)
    if not task.report_file or not os.path.exists(task.report_file):
        return Response({'error': '报告文件丢失'}, status=status.HTTP_404_NOT_FOUND)

    with open(task.report_file, 'r', encoding='utf-8') as f:
        report_data = json.load(f)
    return Response(report_data)