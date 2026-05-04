import os
import sys
import threading
from pathlib import Path

import timm
import torch
import torch.nn as nn
from django.apps import AppConfig
from django.conf import settings
from torchvision import transforms


MANAGEMENT_COMMANDS_WITHOUT_MODEL_LOADING = {
    "check",
    "collectstatic",
    "createsuperuser",
    "dbshell",
    "makemigrations",
    "migrate",
    "shell",
    "showmigrations",
    "test",
}


def should_skip_model_loading():
    if os.environ.get("SKIP_MODEL_LOADING") == "1":
        return True
    if len(sys.argv) < 2:
        return False
    return sys.argv[1] in MANAGEMENT_COMMANDS_WITHOUT_MODEL_LOADING


class HSigmoid(nn.Module):
    def __init__(self, inplace: bool = True):
        super().__init__()
        self.relu = nn.ReLU6(inplace=inplace)

    def forward(self, x):
        return self.relu(x + 3) / 6


class HSwish(nn.Module):
    def __init__(self, inplace: bool = True):
        super().__init__()
        self.sigmoid = HSigmoid(inplace=inplace)

    def forward(self, x):
        return x * self.sigmoid(x)


class CoordAttention(nn.Module):
    def __init__(self, inp: int, oup: int, reduction: int = 32):
        super().__init__()
        self.pool_h = nn.AdaptiveAvgPool2d((None, 1))
        self.pool_w = nn.AdaptiveAvgPool2d((1, None))

        mip = max(8, inp // reduction)
        self.conv1 = nn.Conv2d(inp, mip, kernel_size=1, stride=1, padding=0)
        self.bn1 = nn.BatchNorm2d(mip)
        self.act = HSwish()
        self.conv_h = nn.Conv2d(mip, oup, kernel_size=1, stride=1, padding=0)
        self.conv_w = nn.Conv2d(mip, oup, kernel_size=1, stride=1, padding=0)

    def forward(self, x):
        identity = x
        _, _, height, width = x.size()

        x_h = self.pool_h(x)
        x_w = self.pool_w(x).permute(0, 1, 3, 2)

        y = torch.cat([x_h, x_w], dim=2)
        y = self.conv1(y)
        y = self.bn1(y)
        y = self.act(y)

        x_h, x_w = torch.split(y, [height, width], dim=2)
        x_w = x_w.permute(0, 1, 3, 2)

        a_h = torch.sigmoid(self.conv_h(x_h))
        a_w = torch.sigmoid(self.conv_w(x_w))
        return identity * a_h * a_w


class MobileViT_Plus(nn.Module):
    def __init__(self, num_classes=2):
        super().__init__()
        self.backbone = timm.create_model("mobilevit_xs", pretrained=False, features_only=True)
        with torch.no_grad():
            dummy = torch.randn(1, 3, 256, 256)
            features = self.backbone(dummy)
            self.in_channels = features[-1].shape[1]
        self.ca = CoordAttention(self.in_channels, self.in_channels)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(self.in_channels, 512),
            nn.Hardswish(),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes),
        )

    def forward(self, x):
        features = self.backbone(x)
        x = features[-1]
        x = self.ca(x)
        x = self.pool(x)
        x = self.head(x)
        return x


class LoginAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "fruit_api"

    def _reset_runtime_state(self):
        self.mango_model = None
        self.banana_model = None
        self.strawberry_model = None
        self.mango_classes = []
        self.banana_classes = []
        self.strawberry_classes = []
        self.yolo_model = None
        self.ripeness_preprocess = None
        self.RIPENESS_SUPPORTED = {}
        self.device = torch.device("cpu")
        self._models_loaded = False
        self._model_loading_error = None
        self._model_lock = threading.Lock()

    def _prepare_runtime_dirs(self):
        yolo_config_dir = Path(settings.BASE_DIR) / ".yolo"
        yolo_config_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("YOLO_CONFIG_DIR", str(yolo_config_dir))

    @staticmethod
    def _extract_state_dict(checkpoint):
        if isinstance(checkpoint, dict):
            for candidate_key in ("state_dict", "model_state_dict", "model"):
                candidate = checkpoint.get(candidate_key)
                if isinstance(candidate, dict):
                    checkpoint = candidate
                    break

        if not isinstance(checkpoint, dict):
            raise RuntimeError("熟度模型权重格式无效，未找到 state_dict。")

        normalized_state_dict = {}
        for key, value in checkpoint.items():
            normalized_key = key[7:] if key.startswith("module.") else key
            normalized_state_dict[normalized_key] = value
        return normalized_state_dict

    @staticmethod
    def _infer_ripeness_checkpoint_classes(state_dict):
        for key in ("head.4.weight", "head.4.bias"):
            tensor = state_dict.get(key)
            if tensor is None:
                continue
            return int(tensor.shape[0])
        raise RuntimeError("熟度模型权重缺少分类头，无法推断类别数。")

    def _load_ripeness_model(self, model_path: Path, class_names: list[str]):
        state_dict = self._extract_state_dict(torch.load(model_path, map_location="cpu"))
        checkpoint_class_count = self._infer_ripeness_checkpoint_classes(state_dict)
        expected_class_count = len(class_names)
        if checkpoint_class_count != expected_class_count:
            raise RuntimeError(
                f"熟度模型类别数不匹配: {model_path.name} 输出 {checkpoint_class_count} 类，但配置要求 {expected_class_count} 类。"
            )

        model = MobileViT_Plus(num_classes=expected_class_count)
        model.load_state_dict(state_dict)
        model.eval()
        return model

    def _load_models(self):
        from ultralytics import YOLO

        model_base = settings.MODEL_CONFIG["BASE_DIR"]
        mango_path = model_base / settings.MODEL_CONFIG["MANGO_MODEL"]
        banana_path = model_base / settings.MODEL_CONFIG["BANANA_MODEL"]
        strawberry_path = model_base / settings.MODEL_CONFIG["STRAWBERRY_MODEL"]
        yolo_path = model_base / settings.MODEL_CONFIG["YOLO_MODEL"]

        ripeness_class_names = settings.MODEL_CONFIG["RIPENESS_CLASS_NAMES"]

        self.mango_model = self._load_ripeness_model(mango_path, ripeness_class_names["mango"])
        self.mango_classes = ripeness_class_names["mango"]

        self.banana_model = self._load_ripeness_model(banana_path, ripeness_class_names["banana"])
        self.banana_classes = ripeness_class_names["banana"]

        self.strawberry_model = self._load_ripeness_model(strawberry_path, ripeness_class_names["strawberry"])
        self.strawberry_classes = ripeness_class_names["strawberry"]

        ripe_prep = settings.MODEL_CONFIG["PREPROCESS"]["RIPENESS"]
        self.ripeness_preprocess = transforms.Compose(
            [
                transforms.Resize(ripe_prep["RESIZE"]),
                transforms.ToTensor(),
                transforms.Normalize(mean=ripe_prep["MEAN"], std=ripe_prep["STD"]),
            ]
        )

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.mango_model.to(self.device)
        self.banana_model.to(self.device)
        self.strawberry_model.to(self.device)

        self.yolo_model = YOLO(yolo_path)
        self.RIPENESS_SUPPORTED = settings.MODEL_CONFIG["RIPENESS_SUPPORTED"]
        self._models_loaded = True
        self._model_loading_error = None

    def ensure_models_loaded(self):
        if self._models_loaded:
            return

        with self._model_lock:
            if self._models_loaded:
                return
            try:
                self._load_models()
            except Exception as exc:
                self._model_loading_error = exc
                raise RuntimeError(f"模型加载失败: {exc}") from exc

    def ready(self):
        self._reset_runtime_state()
        self._prepare_runtime_dirs()

        if should_skip_model_loading():
            return

    def get_ripeness_info(self, fruit_name):
        supported = settings.MODEL_CONFIG["RIPENESS_SUPPORTED"]
        if fruit_name in supported:
            info = supported[fruit_name]
            model = getattr(self, info["model_attr"])
            classes = getattr(self, info["classes_attr"])
            return model, classes
        return None, None
