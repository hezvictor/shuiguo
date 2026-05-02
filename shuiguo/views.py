import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health_check(request):
    return Response(
        {
            "status": "ok",
            "message": "Service is healthy",
        }
    )


def _frontend_dist_dir() -> Path:
    return Path(settings.FRONTEND_DIST_DIR).resolve()


def _frontend_index_path() -> Path:
    return _frontend_dist_dir() / "index.html"


def _safe_frontend_path(relative_path: str) -> Path:
    dist_dir = _frontend_dist_dir()
    target = (dist_dir / relative_path).resolve()
    try:
        target.relative_to(dist_dir)
    except ValueError as exc:
        raise Http404("Invalid frontend asset path") from exc
    return target


def frontend_asset(request, path: str):
    target = _safe_frontend_path(path)
    if not target.exists() or not target.is_file():
        raise Http404("Frontend asset not found")

    content_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(target.open("rb"), content_type=content_type or "application/octet-stream")


def frontend_index(request):
    index_path = _frontend_index_path()
    if not index_path.exists():
        return HttpResponse(
            (
                "Frontend build not found. Build the frontend first and copy the dist contents into "
                f"{settings.FRONTEND_DIST_DIR}."
            ),
            status=404,
            content_type="text/plain; charset=utf-8",
        )

    return FileResponse(index_path.open("rb"), content_type="text/html; charset=utf-8")
