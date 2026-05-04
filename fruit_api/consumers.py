import asyncio
import base64
import io
import json
import threading
import time

from channels.generic.websocket import AsyncWebsocketConsumer
from django.apps import apps
from django.conf import settings
from PIL import Image

from fruit_api.services.camera import (
    CameraDependencyError,
    CameraOpenError,
    CameraStateError,
    get_stereo_camera_service,
    get_stereo_preview_manager,
)
from fruit_api.services.camera.device_preview_service import DevicePreviewSession
from fruit_api.services.detection.detect_service import build_detection_target, yolo_targets


def _get_camera_service():
    return get_stereo_camera_service(default_config=getattr(settings, "CAMERA_CONFIG", {}))


def _get_yolo_model():
    app_config = apps.get_app_config("fruit_api")
    app_config.ensure_models_loaded()
    return app_config.yolo_model


def _get_preview_manager():
    return get_stereo_preview_manager(
        camera_service_getter=_get_camera_service,
        yolo_model_getter=_get_yolo_model,
    )


class FruitRecognitionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        await self.accept()
        print("WebSocket connected")

    async def disconnect(self, close_code):
        print(f"WebSocket disconnected: {close_code}")

    async def receive(self, text_data):
        try:
            image_data = text_data.strip()
            if image_data.startswith("data:image"):
                image_data = image_data.split(",", 1)[1]

            img_bytes = base64.b64decode(image_data)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            app_config = apps.get_app_config("fruit_api")
            app_config.ensure_models_loaded()
            predictions = []
            for detection in yolo_targets(img, app_config):
                target = build_detection_target(
                    img,
                    detection,
                    app_config,
                    detect_ripeness=True,
                    source_mode="single",
                )
                ripeness = target.get("ripeness")
                if ripeness:
                    ripeness = {
                        "class": ripeness["predicted_class"],
                        "predicted_class": ripeness["predicted_class"],
                        "confidence": ripeness["confidence"],
                    }
                predictions.append(
                    {
                        "bbox": target["bbox"],
                        "label": target.get("label"),
                        "confidence": target.get("confidence"),
                        "fruit_class": target.get("fruit_class"),
                        "fruit_confidence": target.get("fruit_confidence"),
                        "classification": target.get("classification"),
                        "ripeness": ripeness,
                    }
                )

            await self.send(
                text_data=json.dumps(
                    {
                        "status": "success",
                        "predictions": predictions,
                    }
                )
            )

        except Exception as exc:
            import traceback

            traceback.print_exc()
            await self.send(
                text_data=json.dumps(
                    {
                        "status": "error",
                        "error": str(exc),
                    }
                )
            )


class StereoPreviewConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.preview_manager = _get_preview_manager()
        self.preview_queue = asyncio.Queue(maxsize=1)
        self.stream_task = asyncio.create_task(self._stream_preview_events())

        await self.accept()
        await self.send_json(self.preview_manager.build_ready_payload())

    async def disconnect(self, close_code):
        if hasattr(self, "preview_manager"):
            self.preview_manager.unsubscribe(self.channel_name)
        if hasattr(self, "stream_task"):
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            await self.send_json(self.preview_manager.build_error_payload("invalid_message", "text JSON required"))
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json(self.preview_manager.build_error_payload("invalid_json", "invalid JSON payload"))
            return

        message_type = payload.get("type")
        if message_type == "preview.subscribe":
            ready_payload = self.preview_manager.subscribe(
                self.channel_name,
                loop=asyncio.get_running_loop(),
                queue=self.preview_queue,
                detect=payload.get("detect"),
                conf=payload.get("conf"),
                fps=payload.get("fps"),
            )
            await self.send_json(ready_payload)
            await self.send_json(self.preview_manager.build_status_payload())
            return

        if message_type == "preview.update":
            self.preview_manager.update_config(
                detect=payload.get("detect"),
                conf=payload.get("conf"),
                fps=payload.get("fps"),
            )
            await self.send_json(self.preview_manager.build_status_payload())
            return

        if message_type == "preview.unsubscribe":
            self.preview_manager.unsubscribe(self.channel_name)
            await self.send_json(self.preview_manager.build_status_payload())
            return

        await self.send_json(
            self.preview_manager.build_error_payload("unsupported_message", f"unsupported type: {message_type}")
        )

    async def _stream_preview_events(self):
        while True:
            item = await self.preview_queue.get()
            kind = item.get("kind")
            if kind == "frame":
                await self.send(bytes_data=item["bytes"])
                continue
            if kind == "json":
                await self.send_json(item["payload"])

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))


class CameraDevicePreviewConsumer(AsyncWebsocketConsumer):
    STATUS_INTERVAL_SECONDS = 2.0

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.preview_session = DevicePreviewSession(yolo_model_getter=_get_yolo_model)
        self.preview_queue = asyncio.Queue(maxsize=1)
        self.preview_loop = asyncio.get_running_loop()
        self.preview_stop_event = threading.Event()
        self.preview_worker = None
        self.preview_manual_close = False
        self.last_status_sent_at = 0.0
        self.stream_task = asyncio.create_task(self._stream_preview_events())

        await self.accept()
        await self.send_json(self._build_ready_payload())

    async def disconnect(self, close_code):
        self.preview_manual_close = True
        self.preview_stop_event.set()
        self.preview_session.close()
        worker = getattr(self, "preview_worker", None)
        if worker and worker.is_alive():
            worker.join(timeout=1.0)
        if hasattr(self, "stream_task"):
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass

    def _build_ready_payload(self):
        status_payload = self.preview_session.status_payload()
        return {
            "type": "preview.ready",
            "camera_active": status_payload.get("camera_active", False),
            "config": status_payload.get("config", {}),
        }

    @staticmethod
    def _build_error_payload(code: str, message: str):
        return {
            "type": "preview.error",
            "code": code,
            "message": message,
        }

    def _offer_queue_item(self, item):
        try:
            self.preview_queue.put_nowait(item)
            return
        except asyncio.QueueFull:
            pass

        try:
            self.preview_queue.get_nowait()
        except asyncio.QueueEmpty:
            return

        try:
            self.preview_queue.put_nowait(item)
        except asyncio.QueueFull:
            return

    def _dispatch(self, item):
        self.preview_loop.call_soon_threadsafe(self._offer_queue_item, item)

    def _ensure_worker(self):
        worker = getattr(self, "preview_worker", None)
        if worker is not None and worker.is_alive():
            return
        self.preview_stop_event.clear()
        self.preview_worker = threading.Thread(target=self._preview_loop, name=f"camera-device-preview-{self.channel_name}", daemon=True)
        self.preview_worker.start()

    def _preview_loop(self):
        while not self.preview_stop_event.is_set():
            try:
                frame_bytes = self.preview_session.encode_preview_frame()
                self.preview_session.record_success()
                self._dispatch({"kind": "frame", "bytes": frame_bytes})
            except (CameraDependencyError, CameraOpenError, CameraStateError, RuntimeError, ValueError) as exc:
                self.preview_session.record_failure(str(exc))
                self._dispatch({"kind": "json", "payload": self._build_error_payload("preview_failed", str(exc))})

            now = time.monotonic()
            if now - self.last_status_sent_at >= self.STATUS_INTERVAL_SECONDS:
                self.last_status_sent_at = now
                self._dispatch({"kind": "json", "payload": self.preview_session.status_payload()})

            config = self.preview_session.status_payload().get("config", {})
            fps = int(config.get("stream_fps") or 6)
            self.preview_stop_event.wait(max(0.05, 1.0 / max(1, fps)))

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            await self.send_json(self._build_error_payload("invalid_message", "text JSON required"))
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json(self._build_error_payload("invalid_json", "invalid JSON payload"))
            return

        message_type = payload.get("type")
        if message_type in {"preview.subscribe", "preview.update"}:
            try:
                status_payload = self.preview_session.update_config(payload)
            except ValueError as exc:
                await self.send_json(self._build_error_payload("invalid_config", str(exc)))
                return
            self._ensure_worker()
            await self.send_json(status_payload if message_type == "preview.update" else self._build_ready_payload())
            await self.send_json(self.preview_session.status_payload())
            return

        if message_type == "preview.unsubscribe":
            self.preview_stop_event.set()
            self.preview_session.close()
            worker = getattr(self, "preview_worker", None)
            if worker and worker.is_alive():
                worker.join(timeout=1.0)
            self.preview_worker = None
            await self.send_json(self.preview_session.status_payload())
            return

        await self.send_json(self._build_error_payload("unsupported_message", f"unsupported type: {message_type}"))

    async def _stream_preview_events(self):
        while True:
            item = await self.preview_queue.get()
            if item.get("kind") == "frame":
                await self.send(bytes_data=item["bytes"])
                continue
            if item.get("kind") == "json":
                await self.send_json(item["payload"])

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))
