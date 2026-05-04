from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from fruit_api.services.console_service import (
    build_console_overview,
    build_console_recent,
    build_console_system_status,
)
from fruit_api.views_modules.response_utils import error_response


def _query_param(request, key: str, default=None):
    return request.query_params.get(key, default)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def console_overview(request):
    try:
        payload = build_console_overview(
            request.user,
            range_type=_query_param(request, "range_type", "today"),
            start_date=_query_param(request, "start_date"),
            end_date=_query_param(request, "end_date"),
            tz_name=_query_param(request, "timezone", "UTC"),
            detection_type=_query_param(request, "detection_type") or None,
        )
    except ValueError as exc:
        return error_response(str(exc), http_status=status.HTTP_400_BAD_REQUEST)
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def console_recent(request):
    try:
        payload = build_console_recent(
            request.user,
            range_type=_query_param(request, "range_type", "today"),
            start_date=_query_param(request, "start_date"),
            end_date=_query_param(request, "end_date"),
            tz_name=_query_param(request, "timezone", "UTC"),
            detection_type=_query_param(request, "detection_type") or None,
        )
    except ValueError as exc:
        return error_response(str(exc), http_status=status.HTTP_400_BAD_REQUEST)
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def console_system_status(request):
    return Response(build_console_system_status(), status=status.HTTP_200_OK)
