import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shuiguo.settings')

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Initialize Django before importing modules that may touch ORM models.
django_asgi_app = get_asgi_application()

from fruit_api.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
