from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.decorators import login_required
from fruit_api.views_modules.response_utils import error_response

from fruit_api.services.video.video_service import (
    VideoTask,
    VideoTaskNotFoundError,
    VideoTaskStateError,
    cleanup_task,
    create_video_task,
    get_task,
    load_video_output_bytes,
    load_video_report,
    progress_payload,
    process_video_task,
    start_video_task,
    video_tasks,
)


@csrf_exempt
@api_view(['POST'])
@login_required
def video_upload(request):
    if 'file' not in request.FILES:
        return error_response('请选择视频文件')

    video_file = request.FILES['file']
    process_fps = request.POST.get('processFps', 5)

    task = create_video_task(video_file, process_fps=process_fps, user_id=request.user.id)
    start_video_task(task.task_id)

    return Response(
        {
            'status': 'success',
            'taskId': task.task_id,
            'message': '视频已上传，正在后台处理',
        },
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(['GET'])
@login_required
def video_progress(request, task_id):
    try:
        task = get_task(task_id)
    except VideoTaskNotFoundError as exc:
        return error_response(exc, http_status=status.HTTP_404_NOT_FOUND)

    return Response(progress_payload(task))


@api_view(['GET'])
@login_required
def video_download(request, task_id):
    try:
        task = get_task(task_id)
        video_data = load_video_output_bytes(task)
    except VideoTaskNotFoundError as exc:
        return error_response(exc, http_status=status.HTTP_404_NOT_FOUND)
    except VideoTaskStateError as exc:
        return error_response(exc)
    except FileNotFoundError as exc:
        return error_response(exc, http_status=status.HTTP_404_NOT_FOUND)

    response = HttpResponse(video_data, content_type='video/mp4')
    response['Content-Disposition'] = f'attachment; filename="processed_{task.original_file_name}"'
    response['Access-Control-Expose-Headers'] = 'Content-Disposition'
    return response


@api_view(['DELETE'])
@login_required
def video_cleanup(request, task_id):
    try:
        cleanup_task(task_id)
    except VideoTaskNotFoundError as exc:
        return error_response(exc, http_status=status.HTTP_404_NOT_FOUND)

    return Response({'status': 'success', 'message': '任务已清理'})


@api_view(['GET'])
@login_required
def video_report(request, task_id):
    try:
        task = get_task(task_id)
        report_data = load_video_report(task)
    except VideoTaskNotFoundError as exc:
        return error_response(exc, http_status=status.HTTP_404_NOT_FOUND)
    except VideoTaskStateError as exc:
        return error_response(exc)
    except FileNotFoundError as exc:
        return error_response(exc, http_status=status.HTTP_404_NOT_FOUND)

    return Response(report_data)


__all__ = [
    'VideoTask',
    'process_video_task',
    'video_tasks',
    'video_upload',
    'video_progress',
    'video_download',
    'video_cleanup',
    'video_report',
]

