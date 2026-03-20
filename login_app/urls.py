# login_app/urls.py
from django.urls import path
from . import views

app_name = 'login_app'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('home/', views.home_view, name='home'),
    path('predict/', views.predict_view, name='predict'),
    path('predict_with_ripeness/', views.predict_with_ripeness, name='predict_with_ripeness'),
    path('predict_ripeness_by_type/', views.predict_ripeness_by_type, name='predict_ripeness_by_type'),
    path('yolo_detect/', views.yolo_detect_with_boxes, name='yolo_detect'),          # 新增
    path('yolo_report/', views.yolo_report, name='yolo_report'),                      # 新增
]