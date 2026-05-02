from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

from .views import frontend_asset, frontend_index, health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("fruit_api.urls")),
    path("api/health/", health_check, name="health_check"),
    re_path(
        r"^(?P<path>(assets|fonts)/.*|favicon\.ico|config\.json)$",
        frontend_asset,
        name="frontend_asset",
    ),
    re_path(
        r"^(?!api/|admin/|media/|static/).*$",
        frontend_index,
        name="frontend_index",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
