from __future__ import annotations

import io
import os
import posixpath
import re
import zipfile
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from django.conf import settings


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
ARCHIVE_EXTENSIONS = {".zip"}
SIDE_PATTERN = re.compile(r"(^|[_\-\s])(?P<side>left|right)(?=$|[_\-\s])", re.IGNORECASE)


class UploadResolveError(Exception):
    pass


@dataclass
class ArchiveEntry:
    path: str
    content: bytes
    archive_name: str
    archive_path: str


def _max_archive_bytes() -> int:
    return int(getattr(settings, "IMAGE_TASK_MAX_ARCHIVE_BYTES", 32 * 1024 * 1024))


def _max_archive_depth() -> int:
    return int(getattr(settings, "IMAGE_TASK_MAX_ARCHIVE_NESTING_DEPTH", 1))


def _is_image_name(name: str) -> bool:
    return os.path.splitext(name.lower())[1] in IMAGE_EXTENSIONS


def _is_archive_name(name: str) -> bool:
    return os.path.splitext(name.lower())[1] in ARCHIVE_EXTENSIONS


def _sanitize_zip_path(path: str) -> str:
    normalized = posixpath.normpath(path.replace("\\", "/")).lstrip("/")
    if normalized in {"", "."} or normalized.startswith("../") or normalized == "..":
        raise UploadResolveError(f"压缩包包含非法路径: {path}")
    return normalized


def _read_upload_bytes(upload) -> bytes:
    content = upload.read()
    if hasattr(upload, "seek"):
        upload.seek(0)
    return content


def _walk_archive(*, archive_name: str, payload: bytes, depth: int, parent_path: str = "") -> List[ArchiveEntry]:
    if len(payload) > _max_archive_bytes():
        raise UploadResolveError(f"压缩包超过上传大小限制: {archive_name}")
    if depth > _max_archive_depth():
        raise UploadResolveError(f"压缩包嵌套层级超过限制: {archive_name}")

    entries: List[ArchiveEntry] = []
    with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            inner_path = _sanitize_zip_path(info.filename)
            if inner_path.startswith("__MACOSX/"):
                continue
            content = archive.read(info)
            visible_path = posixpath.join(parent_path, inner_path) if parent_path else inner_path
            if _is_archive_name(inner_path):
                entries.extend(
                    _walk_archive(
                        archive_name=archive_name,
                        payload=content,
                        depth=depth + 1,
                        parent_path=visible_path,
                    )
                )
                continue
            entries.append(
                ArchiveEntry(
                    path=visible_path,
                    content=content,
                    archive_name=archive_name,
                    archive_path=visible_path,
                )
            )
    return entries


def _resolve_standard_inputs(single_inputs: Iterable) -> List[Dict]:
    resolved: List[Dict] = []
    for upload in single_inputs:
        name = str(getattr(upload, "name", "") or "")
        if _is_archive_name(name):
            for entry in _walk_archive(archive_name=name, payload=_read_upload_bytes(upload), depth=0):
                if not _is_image_name(entry.path):
                    continue
                resolved.append(
                    {
                        "display_name": posixpath.basename(entry.path),
                        "file_name": posixpath.basename(entry.path),
                        "content": entry.content,
                        "input_source": "zip_archive",
                        "archive_name": entry.archive_name,
                        "archive_path": entry.archive_path,
                    }
                )
            continue

        if not _is_image_name(name):
            raise UploadResolveError(f"不支持的单图输入文件: {name}")
        resolved.append(
            {
                "display_name": name,
                "file_name": name,
                "content": _read_upload_bytes(upload),
                "input_source": "direct_upload",
                "archive_name": None,
                "archive_path": None,
            }
        )
    return resolved


def _extract_side_info(file_name: str) -> Tuple[str, str]:
    stem = os.path.splitext(posixpath.basename(file_name))[0]
    match = SIDE_PATTERN.search(stem)
    if not match:
        raise UploadResolveError(f"果径图片文件名必须包含 left 或 right: {file_name}")
    label_source = f"{stem[:match.start()]} {stem[match.end():]}"
    label = re.sub(r"[_\-\s]+", "_", label_source).strip(" _-") or "group"
    side = match.group("side").lower()
    return label, side


def _pair_direct_groups(diameter_inputs: Iterable) -> List[Dict]:
    grouped: Dict[str, Dict[str, Dict]] = {}
    for upload in diameter_inputs:
        name = str(getattr(upload, "name", "") or "")
        if _is_archive_name(name):
            continue
        if not _is_image_name(name):
            raise UploadResolveError(f"不支持的果径输入文件: {name}")
        label, side = _extract_side_info(name)
        grouped.setdefault(label, {})[side] = {
            "name": name,
            "content": _read_upload_bytes(upload),
        }

    result: List[Dict] = []
    for label, pair in sorted(grouped.items()):
        if "left" not in pair or "right" not in pair:
            raise UploadResolveError(f"果径图片组缺少 {'left' if 'left' not in pair else 'right'} 图片: {label}")
        result.append(
            {
                "label": label,
                "left_name": pair["left"]["name"],
                "right_name": pair["right"]["name"],
                "left_content": pair["left"]["content"],
                "right_content": pair["right"]["content"],
                "input_source": "direct_upload",
                "archive_name": None,
                "archive_path": None,
            }
        )
    return result


def _resolve_grouped_archive_inputs(archive_uploads: Iterable) -> List[Dict]:
    grouped: Dict[tuple[str, str], Dict] = {}
    for upload in archive_uploads:
        archive_name = str(getattr(upload, "name", "") or "")
        if not _is_archive_name(archive_name):
            continue
        entries = _walk_archive(archive_name=archive_name, payload=_read_upload_bytes(upload), depth=0)
        non_images = [entry.archive_path for entry in entries if not _is_image_name(entry.path)]
        if non_images:
            raise UploadResolveError(f"果径压缩包分组内只能包含图片文件: {non_images[0]}")

        for entry in entries:
            parts = [item for item in entry.path.split("/") if item]
            if len(parts) < 2:
                raise UploadResolveError("果径压缩包中的图片必须放在分组文件夹内，不能直接放在压缩包根目录")
            group_name = parts[-2]
            label, side = _extract_side_info(parts[-1])
            key = (archive_name, group_name)
            grouped.setdefault(
                key,
                {
                    "label": label,
                    "left_name": None,
                    "right_name": None,
                    "left_content": None,
                    "right_content": None,
                    "input_source": "zip_archive",
                    "archive_name": archive_name,
                    "archive_path": "/".join(parts[:-1]),
                },
            )
            grouped[key][f"{side}_name"] = parts[-1]
            grouped[key][f"{side}_content"] = entry.content

    result: List[Dict] = []
    for (_archive_name, group_name), pair in sorted(grouped.items()):
        if not pair.get("left_content") or not pair.get("right_content"):
            raise UploadResolveError(f"果径图片组缺少成对图片: {group_name}")
        result.append(pair)
    return result


def resolve_image_detection_inputs(*, single_inputs: Iterable, diameter_inputs: Iterable, mixed_inputs: Iterable | None = None):
    standard_images = _resolve_standard_inputs(single_inputs)
    diameter_inputs = list(diameter_inputs)
    direct_groups = _pair_direct_groups(diameter_inputs)
    archive_groups = _resolve_grouped_archive_inputs(diameter_inputs)
    diameter_groups = direct_groups + archive_groups

    if mixed_inputs is None:
        return standard_images, diameter_groups

    mixed_groups = _resolve_grouped_archive_inputs(list(mixed_inputs))
    return standard_images, diameter_groups, mixed_groups
