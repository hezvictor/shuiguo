from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from .views import health_check   # 导入健康检查视图

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', include('login_app.urls')),
    path('', lambda request: redirect('login_app:login')),  # 根路径重定向到登录页
    path('api/health/', health_check, name='health_check'), # 健康检查接口
]