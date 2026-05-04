from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from fruit_api.exceptions import AppError


def _payload(message: str, *, code: str, details=None):
    payload = {
        "status": "error",
        "error": message,
        "code": code,
    }
    if details is not None:
        payload["details"] = details
    return payload


def api_exception_handler(exc, context):
    if isinstance(exc, AppError):
        return Response(
            _payload(exc.message, code=exc.code, details=exc.details),
            status=exc.status_code,
        )

    if isinstance(exc, ValidationError):
        return Response(
            _payload("请求参数校验失败", code="validation_error", details=exc.detail),
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, APIException):
        detail = getattr(exc, "detail", None)
        if isinstance(detail, (list, dict)):
            message = "请求失败"
            details = detail
        else:
            message = str(detail or "请求失败")
            details = None
        response.data = _payload(message, code=getattr(exc, "default_code", "error"), details=details)
    return response
