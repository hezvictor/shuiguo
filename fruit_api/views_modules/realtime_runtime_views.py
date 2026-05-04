from django.apps import apps
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from fruit_api.serializers import RealtimeCurrentFrameDetectSerializer
from fruit_api.services.detection.realtime_pipeline_service import (
    run_dual_camera_realtime_detection,
    run_hybrid_camera_realtime_detection,
    run_single_camera_realtime_detection,
    run_single_preview_frame_realtime_detection,
)
from fruit_api.services.detection.realtime_session_service import get_realtime_session_service
from fruit_api.views_modules.response_utils import serializer_error_response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def realtime_detect_current_frame(request):
    serializer = RealtimeCurrentFrameDetectSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    app_config = apps.get_app_config("fruit_api")
    app_config.ensure_models_loaded()
    data = serializer.validated_data
    mode = data["mode"]

    if mode == "single":
        if data.get("frame_data_url"):
            payload = run_single_preview_frame_realtime_detection(
                app_config=app_config,
                frame_data_url=data["frame_data_url"],
                camera_index=data.get("camera_index"),
                detect_ripeness=data.get("detect_ripeness", False),
            )
        else:
            payload = run_single_camera_realtime_detection(
                app_config=app_config,
                camera_index=data.get("camera_index"),
                detect_ripeness=data.get("detect_ripeness", False),
                backend=data.get("backend"),
            )
    elif mode == "dual":
        payload = run_dual_camera_realtime_detection(
            app_config=app_config,
            left_camera_index=data.get("left_camera_index"),
            right_camera_index=data.get("right_camera_index"),
            detect_classification=data.get("detect_classification", False),
            detect_ripeness=data.get("detect_ripeness", False),
            backend=data.get("backend"),
        )
    else:
        payload = run_hybrid_camera_realtime_detection(
            app_config=app_config,
            left_camera_index=data.get("left_camera_index"),
            right_camera_index=data.get("right_camera_index"),
            detect_ripeness=data.get("detect_ripeness", False),
            backend=data.get("backend"),
        )

    sample_payload = payload.pop("_session_sample", None)
    if data.get("collect_sample") and sample_payload is not None:
        session_meta = get_realtime_session_service().record_sample(
            user_id=request.user.id,
            session_id=data.get("session_id"),
            mode=mode,
            target_group_count=data.get("target_group_count") or 10,
            sample_payload=sample_payload,
            metadata={
                "interval_ms": data.get("interval_ms"),
                "camera_profile": {
                    "camera_index": data.get("camera_index"),
                    "left_camera_index": data.get("left_camera_index"),
                    "right_camera_index": data.get("right_camera_index"),
                },
                "runtime_device": payload.get("frame_source"),
                "detect_classification": data.get("detect_classification", False),
                "detect_ripeness": data.get("detect_ripeness", False),
                "detect_diameter": data.get("detect_diameter", False),
            },
        )
        payload.update(session_meta)

    return Response(payload, status=status.HTTP_200_OK)
