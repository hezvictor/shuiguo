import os

from django.conf import settings

from fruit_api.models import DetectionHistory


def history_queryset_for_user(user, detection_type=None):
    queryset = DetectionHistory.objects.filter(user=user).order_by('-created_at')
    if detection_type:
        queryset = queryset.filter(detection_type=detection_type)
    return queryset


def delete_history_with_report(instance):
    if instance.report_file:
        file_path = os.path.join(settings.MEDIA_ROOT, instance.report_file)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                print(f'Delete report file failed: {e}')
    instance.delete()
