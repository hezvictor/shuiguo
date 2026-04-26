from rest_framework import status
from rest_framework.response import Response


def error_response(message, *, http_status=status.HTTP_400_BAD_REQUEST, details=None):
    payload = {
        'status': 'error',
        'error': str(message),
    }
    if details is not None:
        payload['details'] = details
    return Response(payload, status=http_status)


def serializer_error_response(errors, *, http_status=status.HTTP_400_BAD_REQUEST):
    return error_response('请求参数校验失败', http_status=http_status, details=errors)
