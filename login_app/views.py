from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required   # 新增导入
from django.apps import apps                                 # 新增导入
from rest_framework.decorators import api_view               # 新增导入
from rest_framework.response import Response                 # 新增导入
from rest_framework import status                            # 新增导入
from .forms import LoginForm
from .serializers import ImageUploadSerializer               # 新增导入
import torch                                                 # 新增导入
import torch.nn.functional as F                              # 新增导入
from PIL import Image                                        # 新增导入

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

@api_view(['POST'])
@login_required   # 可选：要求登录后才能调用
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
    model = app_config.model
    preprocess = app_config.preprocess
    class_names = app_config.class_names

    # 预处理
    img_t = preprocess(img)
    batch_t = torch.unsqueeze(img_t, 0)

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