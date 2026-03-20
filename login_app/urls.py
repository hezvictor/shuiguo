from django.urls import path
from . import views

app_name = 'login_app'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('home/', views.home_view, name='home'),
    path('predict/', views.predict_view, name='predict'),
    path('predict_with_ripeness/', views.predict_with_ripeness, name='predict_with_ripeness'),   # 新接口1
    path('predict_ripeness_by_type/', views.predict_ripeness_by_type, name='predict_ripeness_by_type'), # 新接口2
]