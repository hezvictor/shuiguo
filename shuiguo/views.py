# shuiguo/views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def health_check(request):
    """
    健康检查接口，用于测试服务是否正常运行。
    """
    return Response({
        "status": "ok",
        "message": "Service is healthy"
    })