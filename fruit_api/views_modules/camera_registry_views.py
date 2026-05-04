from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from fruit_api.serializers import CameraRegistrySelectionSerializer
from fruit_api.services.camera import probe_camera_indices
from fruit_api.services.camera.registry_service import get_camera_registry_service
from fruit_api.views_modules.response_utils import error_response, serializer_error_response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def camera_registry_get(request):
    return Response(get_camera_registry_service().snapshot(), status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def camera_registry_scan(request):
    try:
        max_index = int(request.data.get("max_index", 8))
        backend = request.data.get("backend") or None
        payload = probe_camera_indices(max_index=max_index, backend=backend)
        state = get_camera_registry_service().update_scan(payload)
    except ValueError as exc:
        return error_response(str(exc), http_status=status.HTTP_400_BAD_REQUEST)
    return Response(state, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def camera_registry_select(request):
    serializer = CameraRegistrySelectionSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)
    payload = get_camera_registry_service().update_selection(serializer.validated_data)
    return Response(payload, status=status.HTTP_200_OK)
