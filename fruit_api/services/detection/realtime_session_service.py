from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

from django.conf import settings


def _image_from_bytes(content: bytes) -> Image.Image:
    from io import BytesIO

    return Image.open(BytesIO(content)).convert("RGB")


class RealtimeSessionService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._last_cleanup_at = 0.0

    @staticmethod
    def _root_dir() -> Path:
        root = Path(settings.MEDIA_ROOT) / "realtime_sessions"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _user_root(self, user_id: int) -> Path:
        root = self._root_dir() / str(user_id)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _session_dir(self, user_id: int, session_id: str) -> Path:
        return self._user_root(user_id) / session_id

    def _samples_dir(self, user_id: int, session_id: str) -> Path:
        root = self._session_dir(user_id, session_id) / "samples"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _meta_path(self, user_id: int, session_id: str) -> Path:
        return self._session_dir(user_id, session_id) / "meta.json"

    @staticmethod
    def _retention_seconds() -> int:
        return int(getattr(settings, "REALTIME_SESSION_RETENTION_SECONDS", 6 * 60 * 60))

    @staticmethod
    def _cleanup_interval_seconds() -> int:
        return int(getattr(settings, "REALTIME_SESSION_CLEANUP_INTERVAL_SECONDS", 10 * 60))

    def _should_cleanup(self, *, force: bool = False) -> bool:
        if force:
            return True
        interval = max(0, self._cleanup_interval_seconds())
        if interval == 0:
            return True
        return (time.time() - self._last_cleanup_at) >= interval

    @staticmethod
    def _relative_media_path(path: Path) -> str:
        return path.resolve().relative_to(Path(settings.MEDIA_ROOT).resolve()).as_posix()

    @staticmethod
    def _parse_timestamp(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None

    def cleanup_expired_sessions(self, *, force: bool = False) -> int:
        if not self._should_cleanup(force=force):
            return 0

        with self._lock:
            if not self._should_cleanup(force=force):
                return 0

            deleted = 0
            expiry_cutoff = time.time() - max(0, self._retention_seconds())
            root = self._root_dir()
            for user_root in root.iterdir():
                if not user_root.is_dir():
                    continue
                for session_dir in user_root.iterdir():
                    if not session_dir.is_dir():
                        continue
                    meta_path = session_dir / "meta.json"
                    created_ts = None
                    if meta_path.exists():
                        try:
                            meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        except (OSError, json.JSONDecodeError):
                            meta = {}
                        created_ts = self._parse_timestamp(meta.get("created_at")) or self._parse_timestamp(meta.get("updated_at"))
                    if created_ts is None:
                        created_ts = session_dir.stat().st_mtime
                    if created_ts > expiry_cutoff:
                        continue
                    shutil.rmtree(session_dir, ignore_errors=True)
                    deleted += 1
                if user_root.exists() and not any(user_root.iterdir()):
                    user_root.rmdir()

            self._last_cleanup_at = time.time()
            return deleted

    def _default_meta(self, *, session_id: str, mode: str, target_group_count: int, metadata: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat() + "Z"
        return {
            "session_id": session_id,
            "mode": mode,
            "target_group_count": int(target_group_count or 10),
            "captured_group_count": 0,
            "created_at": now,
            "updated_at": now,
            "meta": dict(metadata or {}),
            "samples": [],
        }

    def _load_meta_unlocked(self, *, user_id: int, session_id: str) -> Dict[str, Any] | None:
        path = self._meta_path(user_id, session_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_meta_unlocked(self, *, user_id: int, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        session_dir = self._session_dir(user_id, session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        path = self._meta_path(user_id, session_id)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    @staticmethod
    def _write_bytes(path: Path, content: bytes) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path.name

    def record_sample(
        self,
        *,
        user_id: int,
        session_id: str | None,
        mode: str,
        target_group_count: int,
        sample_payload: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        self.cleanup_expired_sessions()
        with self._lock:
            current_session_id = session_id or f"realtime-session-{uuid.uuid4().hex[:12]}"
            meta = self._load_meta_unlocked(user_id=user_id, session_id=current_session_id)
            if meta is None:
                meta = self._default_meta(
                    session_id=current_session_id,
                    mode=mode,
                    target_group_count=target_group_count,
                    metadata=metadata,
                )
            else:
                meta["mode"] = mode
                meta["target_group_count"] = int(target_group_count or meta.get("target_group_count") or 10)
                meta["meta"] = {
                    **(meta.get("meta") or {}),
                    **dict(metadata or {}),
                }

            if int(meta.get("captured_group_count") or 0) < int(meta.get("target_group_count") or 0):
                group_index = int(meta.get("captured_group_count") or 0) + 1
                samples_dir = self._samples_dir(user_id, current_session_id)
                sample_record = {
                    "group_index": group_index,
                    "mode": mode,
                    "created_at": datetime.utcnow().isoformat() + "Z",
                }

                if mode == "single":
                    file_name = f"sample_{group_index:03d}.jpg"
                    self._write_bytes(samples_dir / file_name, sample_payload["image_bytes"])
                    sample_record["image_name"] = file_name
                    sample_record["image_path"] = self._relative_media_path(samples_dir / file_name)
                else:
                    left_name = f"sample_{group_index:03d}_left.jpg"
                    right_name = f"sample_{group_index:03d}_right.jpg"
                    self._write_bytes(samples_dir / left_name, sample_payload["left_bytes"])
                    self._write_bytes(samples_dir / right_name, sample_payload["right_bytes"])
                    sample_record["left_name"] = left_name
                    sample_record["right_name"] = right_name
                    sample_record["left_path"] = self._relative_media_path(samples_dir / left_name)
                    sample_record["right_path"] = self._relative_media_path(samples_dir / right_name)

                meta.setdefault("samples", []).append(sample_record)
                meta["captured_group_count"] = group_index

            meta["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._save_meta_unlocked(user_id=user_id, session_id=current_session_id, payload=meta)
            return {
                "session_id": current_session_id,
                "captured_group_count": int(meta.get("captured_group_count") or 0),
                "target_group_count": int(meta.get("target_group_count") or 0),
                "completed": int(meta.get("captured_group_count") or 0) >= int(meta.get("target_group_count") or 0),
            }

    def get_session_meta(self, *, user_id: int, session_id: str) -> Dict[str, Any] | None:
        self.cleanup_expired_sessions()
        with self._lock:
            return self._load_meta_unlocked(user_id=user_id, session_id=session_id)

    def build_batch_inputs(self, *, user_id: int, session_id: str) -> Dict[str, Any]:
        self.cleanup_expired_sessions()
        with self._lock:
            meta = self._load_meta_unlocked(user_id=user_id, session_id=session_id)
            if meta is None:
                raise ValueError("realtime session not found")

            mode = meta.get("mode") or "single"
            standard_images: List[Dict[str, Any]] = []
            diameter_groups: List[Dict[str, Any]] = []
            mixed_groups: List[Dict[str, Any]] = []

            for sample in meta.get("samples") or []:
                if mode == "single":
                    image_path = Path(settings.MEDIA_ROOT) / sample["image_path"]
                    standard_images.append(
                        {
                            "file_name": sample["image_name"],
                            "display_name": Path(sample["image_name"]).stem,
                            "content": image_path.read_bytes(),
                            "input_source": "realtime_session",
                            "archive_name": None,
                            "archive_path": None,
                        }
                    )
                    continue

                left_path = Path(settings.MEDIA_ROOT) / sample["left_path"]
                right_path = Path(settings.MEDIA_ROOT) / sample["right_path"]
                group_payload = {
                    "label": f"sample_{int(sample['group_index']):03d}",
                    "left_name": sample["left_name"],
                    "right_name": sample["right_name"],
                    "left_content": left_path.read_bytes(),
                    "right_content": right_path.read_bytes(),
                    "input_source": "realtime_session",
                    "archive_name": None,
                    "archive_path": None,
                }
                if mode == "dual":
                    diameter_groups.append(group_payload)
                else:
                    mixed_groups.append(group_payload)

            return {
                "mode": mode,
                "meta": meta.get("meta") or {},
                "sample_count": int(meta.get("captured_group_count") or 0),
                "standard_images": standard_images,
                "diameter_groups": diameter_groups,
                "mixed_groups": mixed_groups,
            }

    def delete_session(self, *, user_id: int, session_id: str) -> bool:
        with self._lock:
            session_dir = self._session_dir(user_id, session_id)
            if not session_dir.exists():
                return False
            shutil.rmtree(session_dir, ignore_errors=True)
            user_root = self._root_dir() / str(user_id)
            if user_root.exists() and not any(user_root.iterdir()):
                user_root.rmdir()
            return True


_realtime_session_service: RealtimeSessionService | None = None


def get_realtime_session_service() -> RealtimeSessionService:
    global _realtime_session_service
    if _realtime_session_service is None:
        _realtime_session_service = RealtimeSessionService()
    return _realtime_session_service
