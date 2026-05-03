from fruit_api.models import DetectionHistory
from fruit_api.services.storage import (
    collect_media_cleanup_targets,
    delete_media_file,
    delete_media_tree,
    normalize_media_path,
)


def history_queryset_for_user(user, detection_type=None):
    queryset = DetectionHistory.objects.filter(user=user).order_by("-created_at")
    if detection_type:
        queryset = queryset.filter(detection_type=detection_type)
    return queryset


def delete_history_with_report(instance):
    paths_to_delete = set()
    directories_to_delete = set()

    for value in [instance.report_file, getattr(instance, "cover_image", None)]:
        normalized = normalize_media_path(value)
        if normalized is not None:
            paths_to_delete.add(normalized)

    collect_media_cleanup_targets(instance.artifacts, paths_to_delete, directories_to_delete)
    collect_media_cleanup_targets(instance.detail_data, paths_to_delete, directories_to_delete)

    for file_path in sorted(paths_to_delete, key=lambda item: len(item.parts), reverse=True):
        delete_media_file(file_path)

    for directory_path in sorted(directories_to_delete, key=lambda item: len(item.parts), reverse=True):
        delete_media_tree(directory_path)

    instance.delete()
