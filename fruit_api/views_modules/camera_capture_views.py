from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from fruit_api.serializers import CameraCaptureDownloadSerializer, CameraCaptureSerializer, CameraCaptureStageSaveSerializer
from fruit_api.services.camera.capture_service import get_camera_capture_service
from fruit_api.views_modules.response_utils import error_response, serializer_error_response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def camera_capture(request):
    serializer = CameraCaptureSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)
    payload = get_camera_capture_service().capture(user_id=request.user.id, **serializer.validated_data)
    http_status = status.HTTP_201_CREATED if payload.get("persisted") else status.HTTP_200_OK
    return Response(payload, status=http_status)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def camera_capture_stage_save(request):
    serializer = CameraCaptureStageSaveSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)
    try:
        record = get_camera_capture_service().save_staged(user_id=request.user.id, stage_ids=serializer.validated_data["stage_ids"])
    except ValueError as exc:
        return error_response(str(exc), http_status=status.HTTP_400_BAD_REQUEST)
    return Response({"record": record}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def camera_capture_list(request):
    service = get_camera_capture_service()
    service.cleanup_expired_staged()
    records = service.list_records(user_id=request.user.id)
    staged_groups = service.list_staged(user_id=request.user.id)
    return Response({"records": records, "staged_groups": staged_groups}, status=status.HTTP_200_OK)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def camera_capture_stage_delete(request, stage_id: str):
    get_camera_capture_service().delete_staged(user_id=request.user.id, stage_id=stage_id)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def camera_capture_delete(request, record_id: str):
    get_camera_capture_service().delete_record(user_id=request.user.id, record_id=record_id)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def camera_capture_download(request):
    serializer = CameraCaptureDownloadSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)
    payload = get_camera_capture_service().build_zip_bytes(user_id=request.user.id, record_ids=serializer.validated_data["record_ids"])
    response = HttpResponse(payload["content"], content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{payload["file_name"]}"'
    return response
