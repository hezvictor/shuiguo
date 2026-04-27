from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from fruit_api.forms import LoginForm
from fruit_api.services.auth.auth_service import (
    AuthConflictError,
    AuthCredentialError,
    AuthValidationError,
    change_password_for_user,
    login_with_credentials,
    register_user,
    update_profile_fields,
    user_to_dto,
)


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            try:
                user = login_with_credentials(username, password)
                login(request, user)
                return redirect('fruit_api:home')
            except AuthCredentialError:
                messages.error(request, '用户名或密码错误')
            except AuthValidationError:
                messages.error(request, '用户名或密码不能为空')
    else:
        form = LoginForm()
    return render(request, 'login/login.html', {'form': form})


@login_required
def home_view(request):
    if request.user.is_authenticated:
        return render(request, 'login/home.html', {'user': request.user})
    return redirect('fruit_api:home')


def logout_view(request):
    logout(request)
    return redirect('fruit_api:home')


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email', '')

    try:
        user = register_user(username, password, email)
        login(request, user)
        return Response(
            {
                'status': 'success',
                'message': '注册成功',
                'user': user_to_dto(user).to_dict(),
            },
            status=201,
        )
    except AuthValidationError as exc:
        return Response({'status': 'error', 'error': str(exc)}, status=400)
    except AuthConflictError as exc:
        return Response({'status': 'error', 'error': str(exc)}, status=400)
    except Exception as e:
        return Response({'status': 'error', 'error': str(e)}, status=500)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def api_login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')

    try:
        user = login_with_credentials(username, password)
        login(request, user)
        return Response(
            {
                'status': 'success',
                'message': '登录成功',
                'user': user_to_dto(user).to_dict(),
                'redirect': '/console',
            }
        )
    except AuthValidationError as exc:
        return Response({'status': 'error', 'error': str(exc)}, status=400)
    except AuthCredentialError as exc:
        return Response({'status': 'error', 'error': str(exc)}, status=401)
    except Exception as exc:
        payload = {
            'status': 'error',
            'error': '登录服务异常，请检查数据库连接与迁移状态',
        }
        if settings.DEBUG:
            payload['detail'] = str(exc)
        return Response(payload, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_logout_view(request):
    logout(request)
    return Response({'status': 'success', 'message': '已退出登录'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = update_profile_fields(
        request.user,
        first_name=request.data.get('first_name', ''),
        email=request.data.get('email', ''),
    )
    return Response({'status': 'success', 'message': '个人信息更新成功', 'user': user_to_dto(user).to_dict()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    try:
        change_password_for_user(
            request.user,
            old_password=request.data.get('old_password'),
            new_password=request.data.get('new_password'),
        )
    except AuthValidationError as exc:
        return Response({'status': 'error', 'error': str(exc)}, status=400)
    except AuthCredentialError as exc:
        return Response({'status': 'error', 'error': str(exc)}, status=400)

    return Response({'status': 'success', 'message': '密码修改成功，请重新登录'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_info(request):
    return Response(user_to_dto(request.user).to_dict())

