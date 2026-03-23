# fruit_api/urls.py
from django.urls import path, include
from . import views

app_name = 'fruit_api'

urlpatterns = [
    # ---------- 前端界面（测试用途）----------
    path('', views.login_view, name='login'),
    path('home/', views.home_view, name='home'),
    path('logout/', views.logout_view, name='logout'),

    # ---------- API 接口（正式接口）----------
    path('api/', include([
        # 用户相关
        path('register/', views.register_view, name='api_register'),
        path('login/', views.api_login_view, name='api_login'),
        path('logout/', views.api_logout_view, name='api_logout'),
        path('user_info/', views.get_user_info, name='user_info'),
        path('update_profile/', views.update_profile, name='update_profile'),
        path('change_password/', views.change_password, name='change_password'),

        # 检测相关
        path('predict/', views.predict_view, name='predict'),                          # 仅水果分类
        path('predict_with_ripeness/', views.predict_with_ripeness, name='predict_with_ripeness'),  # 自动熟度
        path('predict_ripeness_by_type/', views.predict_ripeness_by_type, name='predict_ripeness_by_type'),  # 指定类型熟度

        # YOLO 相关
        path('yolo_detect/', views.yolo_detect_with_boxes, name='yolo_detect'),        # 返回带框图片
        path('yolo_detect_info/', views.yolo_detect_info, name='yolo_detect_info'),    # 返回目标信息
        path('yolo_report/', views.yolo_report, name='yolo_report'),                   # 生成报告
        path('yolo_detect_with_boxes/', views.yolo_detect_with_boxes, name='yolo_detect_with_boxes'),
    ])),
]