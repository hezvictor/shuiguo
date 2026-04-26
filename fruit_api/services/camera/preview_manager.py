from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Optional

from fruit_api.services.camera.stereo_camera_service import (
    CameraDependencyError,
    CameraOpenError,
    CameraStateError,
)


@dataclass
class PreviewStreamConfig:
    detect: bool = True
    conf: float = 0.25
    fps: int = 8

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PreviewSubscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue


class StereoPreviewManager:
    DEFAULT_FPS = 8
    MAX_FPS = 12
    STATUS_INTERVAL = 2.0

    def __init__(
        self,
        *,
        camera_service_getter: Callable[[], Any],
        yolo_model_getter: Callable[[], Any],
    ) -> None:
        self._camera_service_getter = camera_service_getter
        self._yolo_model_getter = yolo_model_getter
        self._lock = threading.RLock()
        self._stream_config = PreviewStreamConfig()
        self._subscribers: Dict[str, PreviewSubscriber] = {}
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @staticmethod
    def _coerce_bool(value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return bool(value)

    @classmethod
    def _sanitize_fps(cls, value: Any) -> int:
        if value is None:
            return cls.DEFAULT_FPS
        fps = int(value)
        if fps < 1:
            return 1
        return min(cls.MAX_FPS, fps)

    @staticmethod
    def _sanitize_conf(value: Any) -> float:
        if value is None:
            return 0.25
        conf = float(value)
        if conf < 0.01:
            return 0.01
        if conf > 1.0:
            return 1.0
        return conf

    @staticmethod
    def _offer_queue_item(queue: asyncio.Queue, item: Dict[str, Any]) -> None:
        try:
            queue.put_nowait(item)
            return
        except asyncio.QueueFull:
            pass

        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return

        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            return

    def _dispatch(self, item: Dict[str, Any], subscriber_id: Optional[str] = None) -> None:
        with self._lock:
            if subscriber_id is None:
                subscribers = list(self._subscribers.values())
            else:
                subscriber = self._subscribers.get(subscriber_id)
                subscribers = [subscriber] if subscriber else []

        for subscriber in subscribers:
            if subscriber is None:
                continue
            subscriber.loop.call_soon_threadsafe(self._offer_queue_item, subscriber.queue, item)

    def _build_ready_payload(self) -> Dict[str, Any]:
        camera_status = self._camera_service_getter().status()
        return {
            "type": "preview.ready",
            "camera_active": bool(camera_status.get("active")),
            "config": camera_status.get("config", {}),
            "preview": self._stream_config.to_payload(),
        }

    def build_ready_payload(self) -> Dict[str, Any]:
        with self._lock:
            return self._build_ready_payload()

    def build_status_payload(self) -> Dict[str, Any]:
        camera_status = self._camera_service_getter().status()
        with self._lock:
            preview = self._stream_config.to_payload()
        return {
            "type": "preview.status",
            "camera_active": bool(camera_status.get("active")),
            "last_frame_ts": camera_status.get("last_frame_ts"),
            "consecutive_failures": int(camera_status.get("consecutive_failures") or 0),
            "preview": preview,
        }

    @staticmethod
    def build_error_payload(code: str, message: str) -> Dict[str, Any]:
        return {
            "type": "preview.error",
            "code": code,
            "message": message,
        }

    def update_config(self, *, detect: Any = None, conf: Any = None, fps: Any = None) -> Dict[str, Any]:
        with self._lock:
            if detect is not None:
                self._stream_config.detect = bool(self._coerce_bool(detect))
            if conf is not None:
                self._stream_config.conf = self._sanitize_conf(conf)
            if fps is not None:
                self._stream_config.fps = self._sanitize_fps(fps)
            return self._stream_config.to_payload()

    def subscribe(
        self,
        subscriber_id: str,
        *,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue,
        detect: Any = None,
        conf: Any = None,
        fps: Any = None,
    ) -> Dict[str, Any]:
        ready_payload = {}
        with self._lock:
            if detect is not None:
                self._stream_config.detect = bool(self._coerce_bool(detect))
            if conf is not None:
                self._stream_config.conf = self._sanitize_conf(conf)
            if fps is not None:
                self._stream_config.fps = self._sanitize_fps(fps)
            self._subscribers[subscriber_id] = PreviewSubscriber(loop=loop, queue=queue)
            self._ensure_worker_locked()
            ready_payload = self._build_ready_payload()
        return ready_payload

    def unsubscribe(self, subscriber_id: str) -> None:
        with self._lock:
            self._subscribers.pop(subscriber_id, None)
            if not self._subscribers:
                self._stop_event.set()

    def notify_camera_started(self) -> None:
        self._dispatch({"kind": "json", "payload": self._build_ready_payload()})
        self._dispatch({"kind": "json", "payload": self.build_status_payload()})

    def notify_camera_stopped(self) -> None:
        self._dispatch(
            {
                "kind": "json",
                "payload": self.build_error_payload("camera_stopped", "camera stopped"),
            }
        )
        self._dispatch({"kind": "json", "payload": self.build_status_payload()})

    def _ensure_worker_locked(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="stereo-preview-stream",
            daemon=True,
        )
        self._worker_thread.start()

    def _worker_loop(self) -> None:
        cached_yolo_model = None
        last_status_sent_at = 0.0

        while not self._stop_event.is_set():
            with self._lock:
                has_subscribers = bool(self._subscribers)
                stream_config = PreviewStreamConfig(**self._stream_config.to_payload())
            if not has_subscribers:
                break

            frame_started_at = time.monotonic()
            try:
                yolo_model = None
                if stream_config.detect:
                    if cached_yolo_model is None:
                        cached_yolo_model = self._yolo_model_getter()
                    yolo_model = cached_yolo_model
                frame_bytes = self._camera_service_getter().encode_preview_jpeg(
                    detect=stream_config.detect,
                    yolo_model=yolo_model,
                    conf=stream_config.conf,
                )
                self._camera_service_getter().record_preview_success()
                self._dispatch({"kind": "frame", "bytes": frame_bytes})
            except (CameraDependencyError, CameraOpenError, CameraStateError, RuntimeError) as exc:
                self._camera_service_getter().record_preview_failure(str(exc))
                error_code = "camera_not_active" if "not active" in str(exc).lower() else "preview_failed"
                self._dispatch(
                    {
                        "kind": "json",
                        "payload": self.build_error_payload(error_code, str(exc)),
                    }
                )

            now = time.monotonic()
            if now - last_status_sent_at >= self.STATUS_INTERVAL:
                self._dispatch({"kind": "json", "payload": self.build_status_payload()})
                last_status_sent_at = now

            frame_interval = 1.0 / max(1, stream_config.fps)
            sleep_for = max(0.0, frame_interval - (time.monotonic() - frame_started_at))
            self._stop_event.wait(sleep_for)

        with self._lock:
            self._worker_thread = None


_preview_manager: Optional[StereoPreviewManager] = None


def get_stereo_preview_manager(
    *,
    camera_service_getter: Callable[[], Any],
    yolo_model_getter: Callable[[], Any],
) -> StereoPreviewManager:
    global _preview_manager
    if _preview_manager is None:
        _preview_manager = StereoPreviewManager(
            camera_service_getter=camera_service_getter,
            yolo_model_getter=yolo_model_getter,
        )
    return _preview_manager
