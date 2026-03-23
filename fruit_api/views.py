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