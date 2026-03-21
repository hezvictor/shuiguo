# login_app/urls.py
from django.urls import path
from . import views

app_name = 'login_app'

urlpatterns = [
    # 原有路径
    path('', views.login_view, name='login'),
    path('home/', views.home_view, name='home'),
    path('predict/', views.predict_view, name='predict'),
    path('predict_with_ripeness/', views.predict_with_ripeness, name='predict_with_ripeness'),
    path('predict_ripeness_by_type/', views.predict_ripeness_by_type, name='predict_ripeness_by_type'),
    path('yolo_detect/', views.yolo_detect_with_boxes, name='yolo_detect'),
    path('yolo_report/', views.yolo_report, name='yolo_report'),

    # 新增用户接口
    path('api/register/', views.register_view, name='api_register'),
    path('api/login/', views.api_login_view, name='api_login'),
    path('api/update_profile/', views.update_profile, name='update_profile'),
    path('api/change_password/', views.change_password, name='change_password'),
    path('logout/', views.logout_view, name='logout'),
]