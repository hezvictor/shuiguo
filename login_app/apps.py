from django.apps import AppConfig
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms   # 新增导入
import os
from pathlib import Path

class LoginAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'login_app'

    def ready(self):
        # 获取模型文件的绝对路径（模型放在项目根目录下的 model 文件夹）
        base_dir = Path(__file__).resolve().parent.parent
        model_path = base_dir / 'model' / 'best_model_finetuned.pth'

        # 加载模型架构
        self.model = models.efficientnet_b3(weights=models.EfficientNet_B3_Weights.DEFAULT)
        num_ftrs = self.model.classifier[1].in_features
        self.model.classifier = nn.Sequential(
            nn.Dropout(p=0.5, inplace=True),
            nn.Linear(num_ftrs, 50)  # 50个类别
        )

        # 加载权重
        self.model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
        self.model.eval()  # 设置为评估模式

        # 类别列表（与训练时保持一致）
        self.class_names = [
            '苹果', '鳄梨', '香蕉', '甜菜根', '黑莓', '蓝莓', '西兰花', '卷心菜',
            '辣椒', '胡萝卜', '花椰菜', '辣椒', '玉米', '黄瓜', '枣',
            '火龙果', '茄子', '无花果', '大蒜', '生姜', '葡萄', '番石榴', '墨西哥辣椒',
            '猕猴桃', '柠檬', '生菜', '芒果', '蘑菇', '秋葵', '橄榄', '洋葱', '橙子',
            '辣椒粉', '花生', '梨', '豌豆', '菠萝', '石榴', '土豆', '南瓜',
            '萝卜', '红毛丹', '大豆', '菠菜', '草莓', '甜玉米', '红薯',
            '番茄', '芜菁', '西瓜'
        ]

        # 图像预处理（与训练时相同）
        self.preprocess = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])