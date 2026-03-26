# fruit_api/urls.py
from django.urls import path, include
from . import views

app_name = 'fruit_api'
# daphne -b 0.0.0.0 -p 8000 shuiguo.asgi:application
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
        path('predict/', views.predict_view, name='predict'),
        path('predict_with_ripeness/', views.predict_with_ripeness, name='predict_with_ripeness'),
        path('predict_ripeness_by_type/', views.predict_ripeness_by_type, name='predict_ripeness_by_type'),

        # YOLO 相关
        path('yolo_detect/', views.yolo_detect_with_boxes, name='yolo_detect'),
        path('yolo_detect_info/', views.yolo_detect_info, name='yolo_detect_info'),
        path('yolo_report/', views.yolo_report, name='yolo_report'),
        path('yolo_detect_with_boxes/', views.yolo_detect_with_boxes, name='yolo_detect_with_boxes'),

        # 视频相关
        path('video/upload/', views.video_upload, name='video_upload'),
        path('video/progress/<str:task_id>/', views.video_progress, name='video_progress'),
        path('video/download/<str:task_id>/', views.video_download, name='video_download'),
        path('video/cleanup/<str:task_id>/', views.video_cleanup, name='video_cleanup'),
        path('video/report/<str:task_id>/', views.video_report, name='video_report'),

        # 检测历史
        path('detection/history/', views.DetectionHistoryListView.as_view(), name='detection_history'),
        path('detection/history/<int:pk>/', views.DetectionHistoryDetailView.as_view(), name='detection_history_detail'),

        # 实时检测报告保存（移动到此）
        path('realtime/save_report/', views.save_realtime_report, name='save_realtime_report'),
    ])),
    # 原单独的 realtime 路由已移除
]