from rest_framework import status
from rest_framework.response import Response

from fruit_api.exceptions import AppError


def build_error_payload(message, *, code="error", details=None):
    payload = {
        "status": "error",
        "error": str(message),
        "code": code,
    }
    if details is not None:
        payload["details"] = details
    return payload


def error_response(message, *, http_status=status.HTTP_400_BAD_REQUEST, details=None, code=None):
    resolved_code = code or "error"
    if isinstance(message, AppError):
        http_status = message.status_code if http_status == status.HTTP_400_BAD_REQUEST else http_status
        details = message.details if details is None else details
        resolved_code = code or message.code
        message = message.message
    return Response(build_error_payload(message, code=resolved_code, details=details), status=http_status)


def serializer_error_response(errors, *, http_status=status.HTTP_400_BAD_REQUEST):
    return error_response("请求参数校验失败", http_status=http_status, details=errors, code="validation_error")
