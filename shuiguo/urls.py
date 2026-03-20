from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', include('login_app.urls')),
    path('', lambda request: redirect('login_app:login')),  # 根路径重定向到登录页
]