from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Iterable

from django.conf import settings

from fruit_api.exceptions import FileLifecycleError


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _strip_media_prefix(value: str) -> str:
    media_url = (getattr(settings, "MEDIA_URL", "/media/") or "/media/").rstrip("/")
    if value.startswith(media_url + "/"):
        return value[len(media_url) + 1 :]
    if value.startswith("/media/"):
        return value[len("/media/") :]
    return value


def ensure_media_path(path_value: str | os.PathLike[str]) -> Path:
    raw = str(path_value or "").strip()
    if not raw:
        raise FileLifecycleError("媒体路径不能为空")
    raw = _strip_media_prefix(raw).replace("\\", "/")
    if raw.startswith("http://") or raw.startswith("https://"):
        raise FileLifecycleError("不允许操作外部媒体路径")

    media_root = _media_root()
    target = (media_root / raw).resolve() if not os.path.isabs(raw) else Path(raw).resolve()
    try:
        target.relative_to(media_root)
    except ValueError as exc:
        raise FileLifecycleError(f"非法媒体路径: {path_value}") from exc
    return target


def normalize_media_path(value: Any) -> Path | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw.startswith("http://") or raw.startswith("https://"):
        return None
    return ensure_media_path(raw)


def _prune_empty_parents(path: Path) -> None:
    media_root = _media_root()
    current = path.parent
    while current != media_root and current.exists():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def delete_media_file(path_value: str | Path) -> None:
    path = ensure_media_path(path_value)
    if path.exists() and path.is_file():
        path.unlink()
        _prune_empty_parents(path)


def delete_media_tree(path_value: str | Path) -> None:
    path = ensure_media_path(path_value)
    if path.exists():
        if path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path, ignore_errors=True)
        _prune_empty_parents(path)


def collect_media_cleanup_targets(value: Any, files: set[Path], directories: set[Path]) -> None:
    if value is None:
        return

    if isinstance(value, dict):
        for key, item in value.items():
            if key == "task_root":
                normalized = normalize_media_path(item)
                if normalized is not None:
                    directories.add(normalized)
                continue
            collect_media_cleanup_targets(item, files, directories)
        return

    if isinstance(value, (list, tuple, set)):
        for item in value:
            collect_media_cleanup_targets(item, files, directories)
        return

    if isinstance(value, str):
        normalized = normalize_media_path(value)
        if normalized is not None:
            files.add(normalized)


def delete_many(paths: Iterable[str | Path]) -> None:
    for item in paths:
        delete_media_file(item)
