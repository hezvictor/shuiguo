from __future__ import annotations

import io
import json
import os
import shutil
import threading
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image

from django.conf import settings

from fruit_api.services.camera import get_cached_preview_frame_snapshot
from fruit_api.services.camera.registry_service import get_camera_registry_service
from fruit_api.services.camera.stereo_camera_service import capture_dual_camera_frames, capture_single_camera_frame
from fruit_api.services.storage import delete_media_file, delete_media_tree


def _image_from_bgr(frame: np.ndarray) -> Image.Image:
    if frame.ndim == 3 and frame.shape[2] == 3:
        rgb = frame[:, :, ::-1]
        return Image.fromarray(rgb)
    return Image.fromarray(frame)


class CameraCaptureService:
    def __init__(self) -> None:
        self._index_lock = threading.RLock()
        self._cleanup_lock = threading.RLock()
        self._last_cleanup_at = 0.0

    @staticmethod
    def _capture_from_preview_snapshot(*, camera_indices: List[int], capture_mode: str):
        snapshot = get_cached_preview_frame_snapshot()
        if not snapshot:
            return None

        config = snapshot.get("config") or {}
        if capture_mode == "dual":
            expected_left, expected_right = camera_indices[:2]
            if (
                config.get("mode") == "dual"
                and int(config.get("left_camera_index", -1)) == int(expected_left)
                and int(config.get("right_camera_index", -1)) == int(expected_right)
                and snapshot.get("left_frame") is not None
                and snapshot.get("right_frame") is not None
            ):
                return [
                    {"role": "left", "frame": np.array(snapshot["left_frame"], copy=True)},
                    {"role": "right", "frame": np.array(snapshot["right_frame"], copy=True)},
                ]
            return None

        expected_index = camera_indices[0]
        if (
            config.get("mode") == "single"
            and int(config.get("camera_index", -1)) == int(expected_index)
            and snapshot.get("single_frame") is not None
        ):
            return [{"role": "image", "frame": np.array(snapshot["single_frame"], copy=True)}]
        return None

    @staticmethod
    def _root_dir() -> Path:
        root = Path(settings.MEDIA_ROOT) / "camera_captures"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @classmethod
    def _index_path(cls) -> Path:
        return cls._root_dir() / "index.json"

    @classmethod
    def _stage_root(cls, user_id: int) -> Path:
        root = cls._root_dir() / "staging" / str(user_id)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _stage_dir(self, user_id: int, stage_id: str) -> Path:
        return self._stage_root(user_id) / stage_id

    @staticmethod
    def _stage_retention_seconds() -> int:
        return int(getattr(settings, "CAMERA_CAPTURE_STAGE_RETENTION_SECONDS", 72 * 60 * 60))

    @staticmethod
    def _stage_cleanup_interval_seconds() -> int:
        return int(getattr(settings, "CAMERA_CAPTURE_STAGE_CLEANUP_INTERVAL_SECONDS", 10 * 60))

    @staticmethod
    def _parse_timestamp(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None

    def _should_cleanup_staged(self, *, force: bool = False) -> bool:
        if force:
            return True
        interval = max(0, self._stage_cleanup_interval_seconds())
        if interval == 0:
            return True
        return (time.time() - self._last_cleanup_at) >= interval

    def cleanup_expired_staged(self, *, force: bool = False) -> int:
        if not self._should_cleanup_staged(force=force):
            return 0

        with self._cleanup_lock:
            if not self._should_cleanup_staged(force=force):
                return 0

            deleted = 0
            retention_seconds = max(0, self._stage_retention_seconds())
            expiry_cutoff = time.time() - retention_seconds
            stage_parent = self._root_dir() / "staging"
            if stage_parent.exists():
                for user_root in stage_parent.iterdir():
                    if not user_root.is_dir():
                        continue
                    for stage_dir in user_root.iterdir():
                        if not stage_dir.is_dir():
                            continue
                        meta_path = stage_dir / "meta.json"
                        created_ts = None
                        if meta_path.exists():
                            try:
                                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                            except (OSError, json.JSONDecodeError):
                                meta = {}
                            created_ts = self._parse_timestamp(meta.get("created_at"))
                        if created_ts is None:
                            created_ts = stage_dir.stat().st_mtime
                        if created_ts > expiry_cutoff:
                            continue
                        shutil.rmtree(stage_dir, ignore_errors=True)
                        deleted += 1
                    if user_root.exists() and not any(user_root.iterdir()):
                        user_root.rmdir()

            self._last_cleanup_at = time.time()
            return deleted

    def _load_index_unlocked(self) -> Dict[str, Any]:
        path = self._index_path()
        if not path.exists():
            return {"records": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_index_unlocked(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = self._index_path()
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def _load_index(self) -> Dict[str, Any]:
        with self._index_lock:
            return self._load_index_unlocked()

    def _save_index(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._index_lock:
            return self._save_index_unlocked(payload)

    @classmethod
    def _record_dir(cls, record_id: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d")
        root = cls._root_dir() / stamp / record_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _relative_media_path(path: Path) -> str:
        return path.resolve().relative_to(Path(settings.MEDIA_ROOT).resolve()).as_posix()

    def _save_image(self, path: Path, frame: np.ndarray) -> Dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        image = _image_from_bgr(frame)
        image.save(path, format="JPEG", quality=90)
        relative = self._relative_media_path(path)
        return {
            "file_name": path.name,
            "file_path": relative,
            "file_url": f"{settings.MEDIA_URL.rstrip('/')}/{relative}",
        }

    def _capture_frames(self, *, camera_indices: List[int], capture_mode: str, backend: str | None):
        preview_frames = self._capture_from_preview_snapshot(camera_indices=camera_indices, capture_mode=capture_mode)
        if preview_frames is not None:
            return preview_frames

        if capture_mode == "dual":
            left_idx, right_idx = camera_indices[:2]
            left_frame, right_frame = capture_dual_camera_frames(left_idx, right_idx, backend=backend)
            return [
                {"role": "left", "frame": left_frame},
                {"role": "right", "frame": right_frame},
            ]
        camera_index = camera_indices[0]
        frame = capture_single_camera_frame(camera_index, backend=backend)
        return [{"role": "image", "frame": frame}]

    @staticmethod
    def _build_group_name() -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S") + f"_group_{uuid.uuid4().hex[:6]}"

    def capture(self, *, user_id: int, camera_indices: List[int], capture_mode: str = "auto", persist: bool = True, left_camera_index=None, right_camera_index=None, backend: str | None = None) -> Dict[str, Any]:
        self.cleanup_expired_staged()
        registry = get_camera_registry_service().snapshot()
        backend = backend if backend is not None else registry.get("selection", {}).get("backend") or None
        if capture_mode == "auto":
            capture_mode = "dual" if len(camera_indices) == 2 else "single"

        frames = self._capture_frames(camera_indices=camera_indices, capture_mode=capture_mode, backend=backend)
        if persist:
            record_id = f"cap-{uuid.uuid4().hex[:10]}"
            record_dir = self._record_dir(record_id)
            files = []
            for index, item in enumerate(frames):
                suffix = "jpg" if item["role"] == "image" else f"{item['role']}.jpg"
                file_name = f"{index + 1}_{suffix}" if item["role"] == "image" else f"{item['role']}.jpg"
                file_info = self._save_image(record_dir / file_name, item["frame"])
                file_info["role"] = item["role"]
                files.append(file_info)
            record = {
                "id": record_id,
                "user_id": user_id,
                "capture_mode": capture_mode,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "files": files,
                "archive_name": None,
                "archive_file_path": None,
            }
            with self._index_lock:
                payload = self._load_index_unlocked()
                payload["records"].insert(0, record)
                self._save_index_unlocked(payload)
            return {"persisted": True, "records": [record], "staged_groups": []}

        stage_id = f"stage-{uuid.uuid4().hex[:10]}"
        group_name = self._build_group_name()
        stage_dir = self._stage_dir(user_id, stage_id)
        group_dir = stage_dir / group_name
        group_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for item in frames:
            file_name = f"{group_name}_{item['role']}.jpg" if item["role"] != "image" else f"{group_name}.jpg"
            file_info = self._save_image(group_dir / file_name, item["frame"])
            file_info["role"] = item["role"]
            files.append(file_info)
        meta = {
            "stage_id": stage_id,
            "group_name": group_name,
            "capture_mode": capture_mode,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "files": files,
        }
        (stage_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"persisted": False, "records": [], "staged_groups": [meta]}

    def _load_stage_meta(self, user_id: int, stage_id: str) -> Dict[str, Any] | None:
        meta_path = self._stage_dir(user_id, stage_id) / "meta.json"
        if not meta_path.exists():
            return None
        return json.loads(meta_path.read_text(encoding="utf-8"))

    def list_staged(self, *, user_id: int) -> List[Dict[str, Any]]:
        self.cleanup_expired_staged()
        stage_root = self._stage_root(user_id)
        groups = []
        if not stage_root.exists():
            return groups
        for stage_dir in stage_root.iterdir():
            if not stage_dir.is_dir():
                continue
            meta = self._load_stage_meta(user_id, stage_dir.name)
            if meta is None:
                shutil.rmtree(stage_dir, ignore_errors=True)
                continue
            groups.append(meta)
        groups.sort(key=lambda item: item.get("created_at") or "")
        return groups

    def save_staged(self, *, user_id: int, stage_ids: List[str]) -> Dict[str, Any]:
        self.cleanup_expired_staged()
        groups = []
        for stage_id in stage_ids:
            meta = self._load_stage_meta(user_id, stage_id)
            if meta:
                groups.append(meta)
        if not groups:
            raise ValueError("no staged capture groups found")

        stamp = datetime.now().strftime("%Y%m%d")
        archive_name = f"camera_capture_bundle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        bundle_dir = self._root_dir() / "bundles" / stamp
        bundle_dir.mkdir(parents=True, exist_ok=True)
        archive_path = bundle_dir / archive_name

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for group in groups:
                for file_info in group.get("files", []):
                    file_path = Path(settings.MEDIA_ROOT) / file_info["file_path"]
                    archive.write(file_path, arcname=f"{group['group_name']}/{file_info['file_name']}")

        record = {
            "id": f"bundle-{uuid.uuid4().hex[:10]}",
            "user_id": user_id,
            "capture_mode": "bundle",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "group_count": len(groups),
            "groups": groups,
            "archive_name": archive_name,
            "archive_file_path": self._relative_media_path(archive_path),
            "archive_file_url": f"{settings.MEDIA_URL.rstrip('/')}/{self._relative_media_path(archive_path)}",
            "files": [],
        }
        with self._index_lock:
            payload = self._load_index_unlocked()
            payload["records"].insert(0, record)
            self._save_index_unlocked(payload)
        self.discard_staged(user_id=user_id, stage_ids=stage_ids)
        return record

    def list_records(self, *, user_id: int) -> List[Dict[str, Any]]:
        payload = self._load_index()
        return [item for item in payload.get("records", []) if int(item.get("user_id", 0)) == int(user_id)]

    def delete_staged(self, *, user_id: int, stage_id: str) -> bool:
        return self.discard_staged(user_id=user_id, stage_ids=[stage_id]) > 0

    def delete_record(self, *, user_id: int, record_id: str) -> None:
        with self._index_lock:
            payload = self._load_index_unlocked()
            next_records = []
            target = None
            for record in payload.get("records", []):
                if record.get("id") == record_id and int(record.get("user_id", 0)) == int(user_id):
                    target = record
                else:
                    next_records.append(record)
            payload["records"] = next_records
            self._save_index_unlocked(payload)

        if target is None:
            return

        if target.get("archive_file_path"):
            delete_media_file(target["archive_file_path"])
        for group in target.get("groups", []):
            for file_info in group.get("files", []):
                if file_info.get("file_path"):
                    delete_media_file(file_info["file_path"])
        for file_info in target.get("files", []):
            if file_info.get("file_path"):
                delete_media_file(file_info["file_path"])

    def build_zip_bytes(self, *, user_id: int, record_ids: List[str]) -> Dict[str, Any]:
        records = [item for item in self.list_records(user_id=user_id) if item.get("id") in set(record_ids)]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for record in records:
                if record.get("archive_file_path"):
                    archive_path = Path(settings.MEDIA_ROOT) / record["archive_file_path"]
                    if archive_path.exists():
                        archive.write(archive_path, arcname=record.get("archive_name") or archive_path.name)
                    continue
                for file_info in record.get("files", []):
                    file_path = Path(settings.MEDIA_ROOT) / file_info["file_path"]
                    if file_path.exists():
                        archive.write(file_path, arcname=f"{record['id']}/{file_info['file_name']}")
        return {
            "file_name": f"camera_captures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            "content": buffer.getvalue(),
            "record_count": len(records),
        }

    def discard_staged(self, *, user_id: int, stage_ids: List[str] | None = None) -> int:
        stage_root = self._stage_root(user_id)
        deleted = 0
        if stage_ids is None:
            targets = [item for item in stage_root.iterdir()] if stage_root.exists() else []
        else:
            targets = [self._stage_dir(user_id, stage_id) for stage_id in stage_ids]
        for target in targets:
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
                deleted += 1
        if stage_root.exists() and not any(stage_root.iterdir()):
            stage_root.rmdir()
        return deleted


_camera_capture_service: CameraCaptureService | None = None


def get_camera_capture_service() -> CameraCaptureService:
    global _camera_capture_service
    if _camera_capture_service is None:
        _camera_capture_service = CameraCaptureService()
    return _camera_capture_service
