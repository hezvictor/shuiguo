from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from fruit_api.diameter_service import SimpleImageWrapper
from fruit_api.serializers import StereoCameraMeasureSerializer, StereoCameraStartSerializer
from fruit_api.serializers import StereoCalibrationCaptureSerializer, StereoCalibrationRunSerializer
from fruit_api.services.camera import (
    CameraDependencyError,
    CameraOpenError,
    CameraStateError,
    CalibrationExecutionError,
    CalibrationStateError,
    StereoCalibrationConfig,
    StereoCameraConfig,
    get_stereo_calibration_service,
    get_stereo_camera_service,
    get_stereo_preview_manager,
    probe_camera_indices,
)
from fruit_api.services.detection.diameter_app_service import (
    DiameterDependencyError,
    DiameterExecutionError,
    DiameterParamError,
    get_measure_runtime_status,
    measure_and_save_history,
    reset_diameter_service,
)
from fruit_api.views_modules.response_utils import error_response, serializer_error_response


def _camera_stream_url():
    return "/api/camera/stream/"


def _camera_preview_ws_path():
    return "/ws/camera/preview/"


def _camera_debug_url():
    return "/camera/debug/"


def _get_camera_service():
    return get_stereo_camera_service(default_config=getattr(settings, "CAMERA_CONFIG", {}))


def _get_yolo_model():
    app_config = apps.get_app_config("fruit_api")
    app_config.ensure_models_loaded()
    return app_config.yolo_model


def _get_preview_manager():
    return get_stereo_preview_manager(
        camera_service_getter=_get_camera_service,
        yolo_model_getter=_get_yolo_model,
    )


@login_required
def camera_debug_page(request):
    return render(
        request,
        "camera/debug.html",
        {
            "camera_stream_url": _camera_stream_url(),
            "camera_preview_ws_path": _camera_preview_ws_path(),
            "camera_status_url": "/api/camera/status/",
            "camera_start_url": "/api/camera/start/",
            "camera_stop_url": "/api/camera/stop/",
            "camera_measure_url": "/api/camera/measure/",
        },
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def camera_status(request):
    payload = _get_camera_service().status()
    payload["stream_url"] = _camera_stream_url()
    payload["preview_ws_path"] = _camera_preview_ws_path()
    payload["debug_url"] = _camera_debug_url()
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def camera_probe(request):
    try:
        max_index = int(request.GET.get("max_index", "4"))
        if max_index < 1 or max_index > 16:
            raise ValueError("max_index must be between 1 and 16")
        backend = request.GET.get("backend") or None
        payload = probe_camera_indices(max_index=max_index, backend=backend)
        return Response(payload, status=status.HTTP_200_OK)
    except ValueError as exc:
        return error_response(exc)
    except CameraDependencyError as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def camera_calibration_status(request):
    session_id = request.GET.get("session_id") or None
    payload = get_stereo_calibration_service().session_status(session_id)
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def camera_calibration_capture(request):
    serializer = StereoCalibrationCaptureSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        left_frame, right_frame, _ = _get_camera_service().read_stereo_frames()
        payload = get_stereo_calibration_service().capture_pair(
            left_frame,
            right_frame,
            session_id=serializer.validated_data.get("session_id"),
        )
        return Response(payload, status=status.HTTP_200_OK)
    except (CameraDependencyError, CameraOpenError, CameraStateError) as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except (CalibrationStateError, CalibrationExecutionError) as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def camera_calibration_run(request):
    serializer = StereoCalibrationRunSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        session_id = serializer.validated_data.get("session_id")
        if not session_id:
            raise CalibrationStateError("session_id is required to run calibration")
        payload = get_stereo_calibration_service().run_calibration(
            session_id=session_id,
            config=StereoCalibrationConfig(
                cols=serializer.validated_data.get("cols", 9),
                rows=serializer.validated_data.get("rows", 6),
                square_mm=serializer.validated_data.get("square_mm", 25.0),
                min_pairs=serializer.validated_data.get("min_pairs", 8),
            ),
            activate=serializer.validated_data.get("activate", True),
        )
        reset_diameter_service()
        payload["runtime_status"] = get_measure_runtime_status()
        return Response(payload, status=status.HTTP_200_OK)
    except (CalibrationStateError, CalibrationExecutionError) as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def measure_runtime_status(request):
    try:
        payload = get_measure_runtime_status()
        payload["calib_path"] = str(settings.MEASURE_CONFIG["CALIB_NPZ"])
        payload["device_setting"] = settings.MEASURE_CONFIG.get("DEVICE", "auto")
        return Response(payload, status=status.HTTP_200_OK)
    except DiameterDependencyError as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def camera_start(request):
    serializer = StereoCameraStartSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        payload = _get_camera_service().open(StereoCameraConfig(**serializer.validated_data))
    except (CameraDependencyError, CameraOpenError, CameraStateError) as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    payload["stream_url"] = _camera_stream_url()
    payload["preview_ws_path"] = _camera_preview_ws_path()
    payload["debug_url"] = _camera_debug_url()
    _get_preview_manager().notify_camera_started()
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def camera_stop(request):
    _get_camera_service().close()
    _get_preview_manager().notify_camera_stopped()
    return Response(
        {
            "status": "success",
            "message": "camera stopped",
            "active": False,
        },
        status=status.HTTP_200_OK,
    )


@login_required
def camera_stream(request):
    detect = request.GET.get("detect", "0") in {"1", "true", "True"}
    try:
        conf = float(request.GET.get("conf", "0.25"))
        yolo_model = _get_yolo_model() if detect else None
        generator = _get_camera_service().mjpeg_stream(detect=detect, yolo_model=yolo_model, conf=conf)
        response = StreamingHttpResponse(generator, content_type="multipart/x-mixed-replace; boundary=frame")
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response
    except ValueError as exc:
        return JsonResponse({"status": "error", "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except (CameraDependencyError, CameraOpenError, CameraStateError) as exc:
        return JsonResponse({"status": "error", "error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except RuntimeError as exc:
        return JsonResponse({"status": "error", "error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def camera_measure_current(request):
    serializer = StereoCameraMeasureSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        left_frame, right_frame, _ = _get_camera_service().read_stereo_frames()
        payload = measure_and_save_history(
            user=request.user,
            yolo_model=_get_yolo_model(),
            left_image=SimpleImageWrapper(left_frame, "camera_left.png"),
            right_image=SimpleImageWrapper(right_frame, "camera_right.png"),
            conf=serializer.validated_data.get("conf", 0.25),
            save_vis=serializer.validated_data.get("save_vis", True),
        )
    except (CameraDependencyError, CameraOpenError, CameraStateError) as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DiameterDependencyError as exc:
        return error_response(f"measurement dependency missing: {exc}", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DiameterParamError as exc:
        return error_response(f"invalid measurement request: {exc}")
    except DiameterExecutionError as exc:
        return error_response(f"diameter measurement failed: {exc}", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except RuntimeError as exc:
        return error_response(str(exc), http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(payload, status=status.HTTP_200_OK)


__all__ = [
    "camera_debug_page",
    "camera_calibration_capture",
    "camera_calibration_run",
    "camera_calibration_status",
    "camera_probe",
    "camera_measure_current",
    "camera_start",
    "camera_status",
    "camera_stop",
    "camera_stream",
    "measure_runtime_status",
]
