# login_app/views.py
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

from .forms import LoginForm
from .serializers import ImageUploadSerializer, TypeUploadSerializer
from django.apps import apps

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
                return redirect('login_app:home')
            else:
                messages.error(request, '用户名或密码错误')
    else:
        form = LoginForm()
    return render(request, 'login/login.html', {'form': form})


def home_view(request):
    if request.user.is_authenticated:
        return render(request, 'login/home.html', {'user': request.user})
    else:
        return redirect('login_app:login')


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
    app_config = apps.get_app_config('login_app')
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

    app_config = apps.get_app_config('login_app')

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
    fruit_to_model = {
        '芒果': ('mango', app_config.mango_model, app_config.mango_classes),
        '香蕉': ('banana', app_config.banana_model, app_config.banana_classes),
        '草莓': ('strawberry', app_config.strawberry_model, app_config.strawberry_classes),
    }

    if fruit_label in fruit_to_model:
        fruit_key, model, classes = fruit_to_model[fruit_label]
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

    app_config = apps.get_app_config('login_app')

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

    app_config = apps.get_app_config('login_app')
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
def yolo_report(request):
    """
    接口2：上传图片，YOLO检测目标，对每个目标裁剪、分类、熟度分析，生成报告并保存。
    """
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    image_file = serializer.validated_data['image']
    try:
        img = Image.open(image_file).convert('RGB')
    except Exception:
        return Response({'error': '无效的图片文件'}, status=status.HTTP_400_BAD_REQUEST)

    app_config = apps.get_app_config('login_app')
    yolo_model = app_config.yolo_model
    fruit_model = app_config.fruit_model
    fruit_preprocess = app_config.fruit_preprocess
    fruit_class_names = app_config.fruit_class_names
    ripeness_preprocess = app_config.ripeness_preprocess
    device = app_config.device

    # YOLO检测
    results = yolo_model.predict(source=img, conf=0.25, save=False)
    result = results[0]
    boxes = result.boxes

    targets = []  # 存储每个目标的信息

    if boxes is not None and len(boxes) > 0:
        for i, box in enumerate(boxes):
            # 裁剪目标区域
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            cropped_img = img.crop((x1, y1, x2, y2))

            # 1. 水果分类（使用EfficientNet模型）
            img_t = fruit_preprocess(cropped_img)
            batch_t = torch.unsqueeze(img_t, 0).to(device)
            with torch.no_grad():
                output = fruit_model(batch_t)
            probs = F.softmax(output, dim=1)[0]
            predicted_idx = torch.argmax(probs).item()
            fruit_label = fruit_class_names[predicted_idx]
            fruit_confidence = probs[predicted_idx].item()

            # 2. 熟度分析（仅支持芒果、香蕉、草莓）
            ripeness_result = None
            if fruit_label == '芒果':
                model = app_config.mango_model
                classes = app_config.mango_classes
            elif fruit_label == '香蕉':
                model = app_config.banana_model
                classes = app_config.banana_classes
            elif fruit_label == '草莓':
                model = app_config.strawberry_model
                classes = app_config.strawberry_classes
            else:
                model = None

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

    # 保存报告文件到 media/reports 目录
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


