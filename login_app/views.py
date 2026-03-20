from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from .forms import LoginForm

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('login_app:home')   # 使用命名空间
            else:
                messages.error(request, '用户名或密码错误')
    else:
        form = LoginForm()
    return render(request, 'login/login.html', {'form': form})

def home_view(request):
    if request.user.is_authenticated:
        return render(request, 'login/home.html', {'user': request.user})
    else:
        return redirect('login_app:login')   # 重定向到登录页