# fruit_api/consumers.py
import json
import base64
import io
import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F
from channels.generic.websocket import AsyncWebsocketConsumer
from django.apps import apps
import asyncio


class FruitRecognitionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 接受连接
        await self.accept()
        print("WebSocket 连接已建立")

    async def disconnect(self, close_code):
        print(f"WebSocket 断开: {close_code}")

    async def receive(self, text_data):
        try:
            # 接收 base64 图像数据
            image_data = text_data.strip()
            if image_data.startswith('data:image'):
                # 提取 base64 部分
                image_data = image_data.split(',')[1]

            # 解码图像
            img_bytes = base64.b64decode(image_data)
            img = Image.open(io.BytesIO(img_bytes)).convert('RGB')

            # 获取 app 配置中的模型
            app_config = apps.get_app_config('fruit_api')
            yolo_model = app_config.yolo_model
            fruit_model = app_config.fruit_model
            fruit_preprocess = app_config.fruit_preprocess
            fruit_class_names = app_config.fruit_class_names
            ripeness_preprocess = app_config.ripeness_preprocess
            device = app_config.device

            # 获取熟度支持映射
            ripeness_supported = app_config.RIPENESS_SUPPORTED  # 需要从 app_config 获取

            # 运行 YOLO 检测
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

                    # 裁剪目标区域
                    cropped = img.crop((x1, y1, x2, y2))

                    # 水果分类
                    img_t = fruit_preprocess(cropped).unsqueeze(0).to(device)
                    with torch.no_grad():
                        fruit_output = fruit_model(img_t)
                    fruit_probs = F.softmax(fruit_output, dim=1)[0]
                    fruit_idx = torch.argmax(fruit_probs).item()
                    fruit_class = fruit_class_names[fruit_idx]
                    fruit_confidence = fruit_probs[fruit_idx].item()

                    # 熟度检测（仅对特定水果）
                    ripeness = None
                    if fruit_class in ripeness_supported:
                        model_name = ripeness_supported[fruit_class]['model_attr']
                        classes_attr = ripeness_supported[fruit_class]['classes_attr']
                        model = getattr(app_config, model_name)
                        classes = getattr(app_config, classes_attr)

                        img_t_ripe = ripeness_preprocess(cropped).unsqueeze(0).to(device)
                        with torch.no_grad():
                            ripe_output = model(img_t_ripe)
                        ripe_probs = F.softmax(ripe_output, dim=1)[0]
                        ripe_idx = torch.argmax(ripe_probs).item()
                        ripeness = {
                            'class': classes[ripe_idx],
                            'confidence': ripe_probs[ripe_idx].item()
                        }

                    predictions.append({
                        'bbox': [x1, y1, x2, y2],
                        'label': label,
                        'confidence': conf,
                        'fruit_class': fruit_class,
                        'fruit_confidence': fruit_confidence,
                        'ripeness': ripeness
                    })

            # 发送结果
            await self.send(text_data=json.dumps({
                'status': 'success',
                'predictions': predictions
            }))

        except Exception as e:
            import traceback
            traceback.print_exc()
            await self.send(text_data=json.dumps({
                'status': 'error',
                'error': str(e)
            }))