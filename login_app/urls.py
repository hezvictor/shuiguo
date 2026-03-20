from django.urls import path
from . import views

app_name = 'login_app'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('home/', views.home_view, name='home'),
    path('predict/', views.predict_view, name='predict'),   # 新增预测接口
]