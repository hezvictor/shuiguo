import asyncio
import base64
import io
import json

import torch
import torch.nn.functional as F
from channels.generic.websocket import AsyncWebsocketConsumer
from django.apps import apps
from django.conf import settings
from PIL import Image

from fruit_api.services.camera import get_stereo_camera_service, get_stereo_preview_manager


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
            yolo_model = app_config.yolo_model
            fruit_model = app_config.fruit_model
            fruit_preprocess = app_config.fruit_preprocess
            fruit_class_names = app_config.fruit_class_names
            ripeness_preprocess = app_config.ripeness_preprocess
            device = app_config.device
            ripeness_supported = app_config.RIPENESS_SUPPORTED

            results = yolo_model.predict(source=img, conf=0.25, save=False)
            result = results[0]
            boxes = result.boxes

            predictions = []
            if boxes is not None and len(boxes) > 0:
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = box.conf[0].item()
                    cls = int(box.cls[0].item())
                    label = result.names[cls]

                    cropped = img.crop((x1, y1, x2, y2))

                    img_t = fruit_preprocess(cropped).unsqueeze(0).to(device)
                    with torch.no_grad():
                        fruit_output = fruit_model(img_t)
                    fruit_probs = F.softmax(fruit_output, dim=1)[0]
                    fruit_idx = torch.argmax(fruit_probs).item()
                    fruit_class = fruit_class_names[fruit_idx]
                    fruit_confidence = fruit_probs[fruit_idx].item()

                    ripeness = None
                    if fruit_class in ripeness_supported:
                        model_name = ripeness_supported[fruit_class]["model_attr"]
                        classes_attr = ripeness_supported[fruit_class]["classes_attr"]
                        model = getattr(app_config, model_name)
                        classes = getattr(app_config, classes_attr)

                        img_t_ripe = ripeness_preprocess(cropped).unsqueeze(0).to(device)
                        with torch.no_grad():
                            ripe_output = model(img_t_ripe)
                        ripe_probs = F.softmax(ripe_output, dim=1)[0]
                        ripe_idx = torch.argmax(ripe_probs).item()
                        ripeness = {
                            "class": classes[ripe_idx],
                            "confidence": ripe_probs[ripe_idx].item(),
                        }

                    predictions.append(
                        {
                            "bbox": [x1, y1, x2, y2],
                            "label": label,
                            "confidence": conf,
                            "fruit_class": fruit_class,
                            "fruit_confidence": fruit_confidence,
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
        self.preview_queue = asyncio.Queue(maxsize=2)
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
