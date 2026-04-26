from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from fruit_api.services.detection.realtime_service import RealtimePayloadError, save_realtime_report as save_realtime_report_service
from fruit_api.views_modules.response_utils import error_response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_realtime_report(request):
    try:
        payload = save_realtime_report_service(request.user, request.data)
    except RealtimePayloadError as exc:
        return error_response(exc)

    return Response(payload, status=status.HTTP_201_CREATED)

