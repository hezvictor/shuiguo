import torch
import torch.nn as nn
import timm
from PIL import Image
from torchvision import transforms
import os
from pathlib import Path
from django.apps import AppConfig
from ultralytics import YOLO
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
    name = 'login_app'

    def ready(self):
        base_dir = Path(__file__).resolve().parent.parent

        # ---------- 水果分类模型（EfficientNet） ----------
        fruit_model_path = base_dir / 'model' / 'best_model_finetuned.pth'
        # 加载模型架构
        import torchvision.models as models
        self.fruit_model = models.efficientnet_b3(weights=models.EfficientNet_B3_Weights.DEFAULT)
        num_ftrs = self.fruit_model.classifier[1].in_features
        self.fruit_model.classifier = nn.Sequential(
            nn.Dropout(p=0.5, inplace=True),
            nn.Linear(num_ftrs, 50)
        )
        self.fruit_model.load_state_dict(torch.load(fruit_model_path, map_location=torch.device('cpu')))
        self.fruit_model.eval()

        # 水果类别列表
        self.fruit_class_names = [
            '苹果', '鳄梨', '香蕉', '甜菜根', '黑莓', '蓝莓', '西兰花', '卷心菜',
            '辣椒', '胡萝卜', '花椰菜', '辣椒', '玉米', '黄瓜', '枣',
            '火龙果', '茄子', '无花果', '大蒜', '生姜', '葡萄', '番石榴', '墨西哥辣椒',
            '猕猴桃', '柠檬', '生菜', '芒果', '蘑菇', '秋葵', '橄榄', '洋葱', '橙子',
            '辣椒粉', '花生', '梨', '豌豆', '菠萝', '石榴', '土豆', '南瓜',
            '萝卜', '红毛丹', '大豆', '菠菜', '草莓', '甜玉米', '红薯',
            '番茄', '芜菁', '西瓜'
        ]

        # 水果分类预处理
        self.fruit_preprocess = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        # ---------- 芒果熟度模型 ----------
        mango_path = base_dir / 'model' / 'mango_mobilevit_plus.pth'
        self.mango_model = MobileViT_Plus(num_classes=2)
        self.mango_model.load_state_dict(torch.load(mango_path, map_location='cpu'))
        self.mango_model.eval()
        self.mango_classes = ['Ripe (熟芒果 🥭)', 'Unripe (生芒果 🍏)']  # 索引0=熟,1=生

        # ---------- 香蕉熟度模型 ----------
        banana_path = base_dir / 'model' / 'banana_mobilevit_plus.pth'
        self.banana_model = MobileViT_Plus(num_classes=2)
        self.banana_model.load_state_dict(torch.load(banana_path, map_location='cpu'))
        self.banana_model.eval()
        self.banana_classes = ['Ripe (熟香蕉)', 'Unripe (生香蕉)']

        # ---------- 草莓熟度模型 ----------
        strawberry_path = base_dir / 'model' / 'strawberry_3class_mobilevit.pth'
        self.strawberry_model = MobileViT_Plus(num_classes=3)
        self.strawberry_model.load_state_dict(torch.load(strawberry_path, map_location='cpu'))
        self.strawberry_model.eval()
        self.strawberry_classes = ['Half Ripe (半熟 🍓偏白/粉)', 'Ripe (全熟 🍓红透)', 'Unripe (生果 🍏纯青)']

        # 通用预处理（熟度模型共用）
        self.ripeness_preprocess = transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

        # 将模型移动到设备（可自行添加GPU支持）
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.fruit_model.to(self.device)
        self.mango_model.to(self.device)
        self.banana_model.to(self.device)
        self.strawberry_model.to(self.device)
        yolo_path = base_dir / 'model' / 'epoch90.pt'
        self.yolo_model = YOLO(yolo_path)