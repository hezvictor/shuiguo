import os
import shutil
from pathlib import Path

from django.conf import settings

from fruit_api.models import DetectionHistory


def history_queryset_for_user(user, detection_type=None):
    queryset = DetectionHistory.objects.filter(user=user).order_by("-created_at")
    if detection_type:
        queryset = queryset.filter(detection_type=detection_type)
    return queryset


def delete_history_with_report(instance):
    paths_to_delete = set()
    directories_to_delete = set()
    for value in [instance.report_file, getattr(instance, "cover_image", None)]:
        normalized = _normalize_media_path(value)
        if normalized:
            paths_to_delete.add(normalized)

    _collect_media_paths(instance.artifacts, paths_to_delete, directories_to_delete)
    _collect_media_paths(instance.detail_data, paths_to_delete, directories_to_delete)

    for file_path in sorted(paths_to_delete):
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as exc:
                print(f"Delete report file failed: {exc}")

    for directory_path in sorted(directories_to_delete, reverse=True):
        if os.path.isdir(directory_path):
            try:
                shutil.rmtree(directory_path)
            except OSError as exc:
                print(f"Delete report directory failed: {exc}")
    instance.delete()


def _collect_media_paths(value, collected, directories):
    if isinstance(value, dict):
        task_root = value.get("task_root")
        if isinstance(task_root, str):
            normalized_dir = _normalize_media_dir(task_root)
            if normalized_dir:
                directories.add(normalized_dir)
        for key, item in value.items():
            if key == "task_root":
                continue
            _collect_media_paths(item, collected, directories)
        return
    if isinstance(value, list):
        for item in value:
            _collect_media_paths(item, collected, directories)
        return
    if isinstance(value, str):
        normalized = _normalize_media_path(value)
        if normalized:
            collected.add(normalized)


def _normalize_media_path(value):
    if not value or not isinstance(value, str):
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return None

    media_root = Path(settings.MEDIA_ROOT).resolve()
    if value.startswith("/media/"):
        relative = value[len("/media/") :].lstrip("/\\")
        return str((media_root / relative).resolve())

    path = Path(value)
    if path.is_absolute():
        return str(path.resolve())

    candidate = (media_root / value).resolve()
    try:
        candidate.relative_to(media_root)
    except ValueError:
        return None
    return str(candidate)


def _normalize_media_dir(value):
    if not value or not isinstance(value, str):
        return None

    media_root = Path(settings.MEDIA_ROOT).resolve()
    if value.startswith("/media/"):
        relative = value[len("/media/") :].lstrip("/\\")
        candidate = (media_root / relative).resolve()
    else:
        path = Path(value)
        candidate = path.resolve() if path.is_absolute() else (media_root / value).resolve()

    try:
        candidate.relative_to(media_root)
    except ValueError:
        return None
    return str(candidate)
