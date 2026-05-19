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


def _icp_footer_markup() -> str:
    icp_number = "桂ICP备2025060160号"
    icp_url = "https://beian.miit.gov.cn/"
    return (
        "<style>"
        "body{padding-bottom:56px;box-sizing:border-box;}"
        ".site-beian-footer{position:fixed;left:0;right:0;bottom:0;z-index:9999;"
        "display:flex;justify-content:center;align-items:center;gap:8px;padding:10px 16px;"
        "background:rgba(255,255,255,.96);border-top:1px solid rgba(44,62,80,.12);"
        "box-shadow:0 -6px 18px rgba(44,62,80,.08);backdrop-filter:blur(8px);"
        "font-size:13px;line-height:1.4;color:#4a5a4a;text-align:center;}"
        ".site-beian-footer a{color:#1f6feb;text-decoration:none;}"
        ".site-beian-footer a:hover,.site-beian-footer a:focus{text-decoration:underline;}"
        "@media (max-width: 640px){"
        ".site-beian-footer{padding:12px;font-size:12px;line-height:1.5;}"
        "}"
        "</style>"
        f'<footer class="site-beian-footer">'
        f'<span>备案号：</span>'
        f'<a href="{icp_url}" target="_blank" rel="noopener noreferrer">{icp_number}</a>'
        "</footer>"
    )


def _inject_icp_footer(html: str) -> str:
    footer = _icp_footer_markup()
    if "site-beian-footer" in html or "桂ICP备2025060160号" in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", f"{footer}</body>", 1)
    return f"{html}{footer}"


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

    html = index_path.read_text(encoding="utf-8")
    return HttpResponse(_inject_icp_footer(html), content_type="text/html; charset=utf-8")
