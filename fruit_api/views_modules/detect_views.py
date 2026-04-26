from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from fruit_api.models import DetectionHistory
from fruit_api.serializers import ImageUploadSerializer, TypeUploadSerializer
from fruit_api.views_modules.response_utils import error_response, serializer_error_response
from fruit_api.services.detection.detect_service import (
    InvalidImageError,
    InvalidParamError,
    build_report_data,
    classify_fruit,
    classify_ripeness_by_type,
    classify_with_ripeness,
    load_rgb_image,
    parse_selected_indices,
    save_report,
    yolo_boxes_image_bytes,
    yolo_targets,
)


@api_view(['POST'])
@login_required
def predict_view(request):
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        img = load_rgb_image(serializer.validated_data['image'])
    except InvalidImageError as exc:
        return error_response(exc)

    app_config = apps.get_app_config('fruit_api')
    try:
        app_config.ensure_models_loaded()
    except RuntimeError as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    result = classify_fruit(img, app_config)
    return Response(result, status=status.HTTP_200_OK)


@api_view(['POST'])
@login_required
def predict_with_ripeness(request):
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        img = load_rgb_image(serializer.validated_data['image'])
    except InvalidImageError as exc:
        return error_response(exc)

    app_config = apps.get_app_config('fruit_api')
    try:
        app_config.ensure_models_loaded()
    except RuntimeError as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    result = classify_with_ripeness(img, app_config)
    return Response(result, status=status.HTTP_200_OK)


@api_view(['POST'])
@login_required
def predict_ripeness_by_type(request):
    serializer = TypeUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        img = load_rgb_image(serializer.validated_data['image'])
    except InvalidImageError as exc:
        return error_response(exc)

    app_config = apps.get_app_config('fruit_api')
    try:
        app_config.ensure_models_loaded()
    except RuntimeError as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    try:
        result = classify_ripeness_by_type(img, serializer.validated_data['type'], app_config)
    except InvalidParamError as exc:
        return error_response(exc)

    return Response(result, status=status.HTTP_200_OK)


@api_view(['POST'])
@login_required
def yolo_detect_with_boxes(request):
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        img = load_rgb_image(serializer.validated_data['image'])
    except InvalidImageError as exc:
        return error_response(exc)

    app_config = apps.get_app_config('fruit_api')
    try:
        app_config.ensure_models_loaded()
    except RuntimeError as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    image_bytes = yolo_boxes_image_bytes(img, app_config)
    return HttpResponse(image_bytes, content_type='image/jpeg')


@api_view(['POST'])
@login_required
def yolo_detect_info(request):
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        img = load_rgb_image(serializer.validated_data['image'])
    except InvalidImageError as exc:
        return error_response(exc)

    app_config = apps.get_app_config('fruit_api')
    try:
        app_config.ensure_models_loaded()
    except RuntimeError as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    targets = yolo_targets(img, app_config)
    return Response(
        {
            'status': 'success',
            'targets': targets,
            'image_width': img.width,
            'image_height': img.height,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@login_required
def yolo_report(request):
    serializer = ImageUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error_response(serializer.errors)

    try:
        selected_indices = parse_selected_indices(request.data.get('selected_indices'))
        img = load_rgb_image(serializer.validated_data['image'])
    except (InvalidParamError, InvalidImageError) as exc:
        return error_response(exc)

    app_config = apps.get_app_config('fruit_api')
    try:
        app_config.ensure_models_loaded()
    except RuntimeError as exc:
        return error_response(exc, http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    result = build_report_data(img, app_config, selected_indices)
    report_filename = save_report(result['report_data'])

    if result['targets']:
        DetectionHistory.objects.create(
            user=request.user,
            detection_type='image',
            summary=result['summary'],
            report_file=report_filename,
        )

    return Response(
        {
            'status': 'success',
            'report': result['report_data'],
            'report_file': f"{settings.MEDIA_URL.rstrip('/')}/{report_filename}",
        },
        status=status.HTTP_200_OK,
    )

