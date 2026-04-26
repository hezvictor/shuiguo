from django.apps import apps
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from fruit_api.serializers import MeasureDistanceSerializer, MeasureInferSerializer, StereoDiameterSerializer
from fruit_api.services.detection.diameter_app_service import (
    DiameterDependencyError,
    DiameterExecutionError,
    DiameterParamError,
    get_diameter_service,
    measure_and_save_history,
    run_measure_distance,
    run_measure_inference,
)
from fruit_api.views_modules.response_utils import error_response, serializer_error_response


def _get_yolo_model():
    app_config = apps.get_app_config("fruit_api")
    app_config.ensure_models_loaded()
    return app_config.yolo_model


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def measure_infer(request):
    serializer = MeasureInferSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        payload = run_measure_inference(
            yolo_model=_get_yolo_model(),
            left_file=serializer.validated_data.get("left_image"),
            right_file=serializer.validated_data.get("right_image"),
            left_image_path=serializer.validated_data.get("left_image_path"),
            right_image_path=serializer.validated_data.get("right_image_path"),
            calib_path=serializer.validated_data.get("calib_path"),
            ckpt_path=serializer.validated_data.get("ckpt_path"),
            valid_iters=serializer.validated_data.get("valid_iters"),
            save_color=serializer.validated_data.get("save_color", True),
            save_npy=serializer.validated_data.get("save_npy", True),
            detect_conf=serializer.validated_data.get("detect_conf"),
            request_id=serializer.validated_data.get("request_id"),
            return_debug=serializer.validated_data.get("return_debug", False),
        )
    except RuntimeError as exc:
        return error_response(str(exc), http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DiameterDependencyError as exc:
        return error_response(f"测量依赖缺失: {exc}", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DiameterParamError as exc:
        return error_response(f"参数错误: {exc}")
    except DiameterExecutionError as exc:
        return error_response(f"推理失败: {exc}", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def measure_distance(request):
    serializer = MeasureDistanceSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        payload = run_measure_distance(
            user=request.user,
            save_history=True,
            inference_id=serializer.validated_data.get("inference_id"),
            disp_npy_path=serializer.validated_data.get("disp_npy_path"),
            calib_path=serializer.validated_data.get("calib_path"),
            point1=serializer.validated_data.get("point1"),
            point2=serializer.validated_data.get("point2"),
            patch_size=serializer.validated_data.get("patch_size"),
            distance_unit=serializer.validated_data.get("distance_unit", "mm"),
            save_annotated=serializer.validated_data.get("save_annotated", True),
            request_id=serializer.validated_data.get("request_id"),
            target_index=serializer.validated_data.get("target_index"),
            measure_all_targets=serializer.validated_data.get("measure_all_targets", False),
            bbox=serializer.validated_data.get("bbox"),
            return_debug=serializer.validated_data.get("return_debug", False),
        )
    except DiameterDependencyError as exc:
        return error_response(f"测量依赖缺失: {exc}", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DiameterParamError as exc:
        return error_response(f"参数错误: {exc}")
    except DiameterExecutionError as exc:
        return error_response(f"测量失败: {exc}", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def measure_fruit_diameter(request):
    serializer = StereoDiameterSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        payload = measure_and_save_history(
            user=request.user,
            yolo_model=_get_yolo_model(),
            image=serializer.validated_data.get("image"),
            left_image=serializer.validated_data.get("left_image"),
            right_image=serializer.validated_data.get("right_image"),
            split_mode=serializer.validated_data.get("split_mode", "left_right"),
            conf=serializer.validated_data.get("conf", 0.25),
            save_vis=serializer.validated_data.get("save_vis", True),
        )
    except RuntimeError as exc:
        return error_response(str(exc), http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DiameterDependencyError as exc:
        return error_response(f"测量依赖缺失: {exc}", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DiameterParamError as exc:
        return error_response(f"参数错误: {exc}")
    except DiameterExecutionError as exc:
        return error_response(f"果径测量失败: {exc}", http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(payload, status=status.HTTP_200_OK)


__all__ = [
    "get_diameter_service",
    "measure_infer",
    "measure_distance",
    "measure_fruit_diameter",
]
