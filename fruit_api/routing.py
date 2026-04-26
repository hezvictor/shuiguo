# fruit_api/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/fruit-recognition/$', consumers.FruitRecognitionConsumer.as_asgi()),
    re_path(r'ws/camera/preview/$', consumers.StereoPreviewConsumer.as_asgi()),
]
