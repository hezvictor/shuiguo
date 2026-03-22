import torch
import torch.nn as nn
import timm
from PIL import Image
from torchvision import transforms
import os
from pathlib import Path
from django.apps import AppConfig
from ultralytics import YOLO
from django.conf import settings

# ==========================================
# 模型结构定义（必须与训练时完全一致）
# ==========================================
class ChannelAttention(nn.Module):
    def __init__(self, in_planes, ratio=16):
        super(ChannelAttention, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.fc1 = nn.Conv2d(in_planes, in_planes // ratio, 1, bias=False)
        self.relu1 = nn.ReLU()
        self.fc2 = nn.Conv2d(in_planes // ratio, in_planes, 1, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        avg_out = self.fc2(self.relu1(self.fc1(self.avg_pool(x))))
        max_out = self.fc2(self.relu1(self.fc1(self.max_pool(x))))
        out = avg_out + max_out
        return self.sigmoid(out)

class SpatialAttention(nn.Module):
    def __init__(self, kernel_size=7):
        super(SpatialAttention, self).__init__()
        padding = 3 if kernel_size == 7 else 1
        self.conv1 = nn.Conv2d(2, 1, kernel_size, padding=padding, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        avg_out = torch.mean(x, dim=1, keepdim=True)
        max_out, _ = torch.max(x, dim=1, keepdim=True)
        x_cat = torch.cat([avg_out, max_out], dim=1)
        out = self.conv1(x_cat)
        return self.sigmoid(out)

class CBAM(nn.Module):
    def __init__(self, planes):
        super(CBAM, self).__init__()
        self.ca = ChannelAttention(planes)
        self.sa = SpatialAttention()

    def forward(self, x):
        x = self.ca(x) * x
        x = self.sa(x) * x
        return x

class MobileViT_Plus(nn.Module):
    def __init__(self, num_classes=2):
        super(MobileViT_Plus, self).__init__()
        self.backbone = timm.create_model('mobilevit_xs', pretrained=False, features_only=True)
        with torch.no_grad():
            dummy = torch.randn(1, 3, 256, 256)
            features = self.backbone(dummy)
            self.in_channels = features[-1].shape[1]
        self.cbam = CBAM(self.in_channels)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(self.in_channels, 512),
            nn.Hardswish(),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes)
        )

    def forward(self, x):
        features = self.backbone(x)
        x = features[-1]
        x = self.cbam(x)
        x = self.pool(x)
        x = self.head(x)
        return x

class LoginAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fruit_api'

    def ready(self):
        # 从配置中获取模型路径
        model_base = settings.MODEL_CONFIG['BASE_DIR']
        fruit_model_path = model_base / settings.MODEL_CONFIG['FRUIT_MODEL']
        mango_path = model_base / settings.MODEL_CONFIG['MANGO_MODEL']
        banana_path = model_base / settings.MODEL_CONFIG['BANANA_MODEL']
        strawberry_path = model_base / settings.MODEL_CONFIG['STRAWBERRY_MODEL']
        yolo_path = model_base / settings.MODEL_CONFIG['YOLO_MODEL']

        # 水果类别列表
        self.fruit_class_names = settings.MODEL_CONFIG['FRUIT_CLASS_NAMES']

        # ---------- 水果分类模型（EfficientNet） ----------
        import torchvision.models as models
        self.fruit_model = models.efficientnet_b3(weights=models.EfficientNet_B3_Weights.DEFAULT)
        num_ftrs = self.fruit_model.classifier[1].in_features
        self.fruit_model.classifier = nn.Sequential(
            nn.Dropout(p=0.5, inplace=True),
            nn.Linear(num_ftrs, len(self.fruit_class_names))  # 输出类别数等于列表长度
        )
        self.fruit_model.load_state_dict(torch.load(fruit_model_path, map_location=torch.device('cpu')))
        self.fruit_model.eval()

        # 水果分类预处理
        fruit_prep = settings.MODEL_CONFIG['PREPROCESS']['FRUIT']
        self.fruit_preprocess = transforms.Compose([
            transforms.Resize(fruit_prep['RESIZE']),
            transforms.CenterCrop(fruit_prep['CROP']),
            transforms.ToTensor(),
            transforms.Normalize(mean=fruit_prep['MEAN'], std=fruit_prep['STD']),
        ])

        # ---------- 芒果熟度模型 ----------
        self.mango_model = MobileViT_Plus(num_classes=2)
        self.mango_model.load_state_dict(torch.load(mango_path, map_location='cpu'))
        self.mango_model.eval()
        self.mango_classes = ['Ripe (熟芒果 🥭)', 'Unripe (生芒果 🍏)']

        # ---------- 香蕉熟度模型 ----------
        self.banana_model = MobileViT_Plus(num_classes=2)
        self.banana_model.load_state_dict(torch.load(banana_path, map_location='cpu'))
        self.banana_model.eval()
        self.banana_classes = ['Ripe (熟香蕉)', 'Unripe (生香蕉)']

        # ---------- 草莓熟度模型 ----------
        self.strawberry_model = MobileViT_Plus(num_classes=3)
        self.strawberry_model.load_state_dict(torch.load(strawberry_path, map_location='cpu'))
        self.strawberry_model.eval()
        self.strawberry_classes = ['Half Ripe (半熟 🍓偏白/粉)', 'Ripe (全熟 🍓红透)', 'Unripe (生果 🍏纯青)']

        # 通用预处理（熟度模型共用）
        ripe_prep = settings.MODEL_CONFIG['PREPROCESS']['RIPENESS']
        self.ripeness_preprocess = transforms.Compose([
            transforms.Resize(ripe_prep['RESIZE']),
            transforms.ToTensor(),
            transforms.Normalize(mean=ripe_prep['MEAN'], std=ripe_prep['STD'])
        ])

        # 设备
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.fruit_model.to(self.device)
        self.mango_model.to(self.device)
        self.banana_model.to(self.device)
        self.strawberry_model.to(self.device)

        # YOLO模型
        self.yolo_model = YOLO(yolo_path)

    def get_ripeness_info(self, fruit_name):
        """
        根据水果名称返回对应的熟度模型和类别列表。
        参数 fruit_name: 水果名称（中文，如'芒果'）
        返回: (model, classes) 或 (None, None) 如果不支持
        """
        supported = settings.MODEL_CONFIG['RIPENESS_SUPPORTED']
        if fruit_name in supported:
            info = supported[fruit_name]
            model = getattr(self, info['model_attr'])
            classes = getattr(self, info['classes_attr'])
            return model, classes
        return None, None