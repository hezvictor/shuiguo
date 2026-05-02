"""
Django settings for shuiguo project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_local_env(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_local_env(BASE_DIR / ".env.local")

SECRET_KEY = "django-insecure-9mvbwht*#kz5+*ph0xyg=k5%igoqwwuoqquz8&gvy8=p+fa=o4"
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "fruit_api",
    "rest_framework",
    "channels",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "shuiguo.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "shuiguo.wsgi.application"
ASGI_APPLICATION = "shuiguo.asgi.application"

# Database
DB_NAME = os.environ.get("DB_NAME", "").strip()
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "3306")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": DB_NAME or "shuiguo_db",
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "public",
]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Model files and inference configuration
MODEL_CONFIG = {
    "BASE_DIR": BASE_DIR / "model",
    "FRUIT_MODEL": "best_model_finetuned.pth",
    "MANGO_MODEL": "mango_mobilevit_plus.pth",
    "BANANA_MODEL": "banana_mobilevit_plus.pth",
    "STRAWBERRY_MODEL": "strawberry_3class_mobilevit.pth",
    "YOLO_MODEL": "epoch90.pt",
    "FRUIT_CLASS_NAMES": [
        "apple", "apricot", "banana", "beetroot", "blackberry", "blueberry", "broccoli", "cabbage",
        "capsicum", "carrot", "cauliflower", "chili", "corn", "cucumber", "dates", "dragonfruit",
        "eggplant", "fig", "garlic", "ginger", "grape", "guava", "jalapeno", "kiwi",
        "lemon", "lettuce", "mango", "mushroom", "onion", "orange", "papaya", "pea",
        "pear", "pineapple", "pomegranate", "potato", "pumpkin", "radish", "raspberry", "soybean",
        "spinach", "strawberry", "sweetcorn", "sweetpotato", "tomato", "turnip", "watermelon", "zucchini",
        "plum", "coconut",
    ],
    "PREPROCESS": {
        "FRUIT": {
            "RESIZE": 256,
            "CROP": 224,
            "MEAN": [0.485, 0.456, 0.406],
            "STD": [0.229, 0.224, 0.225],
        },
        "RIPENESS": {
            "RESIZE": (256, 256),
            "MEAN": [0.485, 0.456, 0.406],
            "STD": [0.229, 0.224, 0.225],
        },
    },
    "RIPENESS_SUPPORTED": {
        "mango": {"model_attr": "mango_model", "classes_attr": "mango_classes"},
        "banana": {"model_attr": "banana_model", "classes_attr": "banana_classes"},
        "strawberry": {"model_attr": "strawberry_model", "classes_attr": "strawberry_classes"},
    },
}

MEASURE_CONFIG = {
    "MONSTER_DIR": str(BASE_DIR / "model" / "monster_runtime"),
    "CALIB_NPZ": str(BASE_DIR / "model" / "monster_runtime" / "calibration" / "calib_stereo.npz"),
    "RESTORE_CKPT": str(BASE_DIR / "model" / "monster_runtime" / "pretrained" / "mix_all.pth"),
    "OUTPUT_DIR": str(MEDIA_ROOT / "diameter_tmp"),
    "PATCH_SIZE": 5,
    "YOLO_CONF": 0.25,
    "INFER_VALID_ITERS": 16,
    "INFER_TIMEOUT_SECONDS": 300,
    "DEVICE": os.environ.get("MEASURE_DEVICE", "auto"),
    "ALLOW_CPU_FALLBACK": True,
}

CAMERA_CONFIG = {
    "source_mode": os.environ.get("STEREO_CAMERA_SOURCE_MODE", "single"),
    "camera_index": int(os.environ.get("STEREO_CAMERA_INDEX", "0")),
    "left_camera_index": int(os.environ.get("STEREO_LEFT_CAMERA_INDEX", "0")),
    "right_camera_index": int(os.environ.get("STEREO_RIGHT_CAMERA_INDEX", "1")),
    "frame_width": int(os.environ["STEREO_CAMERA_WIDTH"]) if os.environ.get("STEREO_CAMERA_WIDTH") else None,
    "frame_height": int(os.environ["STEREO_CAMERA_HEIGHT"]) if os.environ.get("STEREO_CAMERA_HEIGHT") else None,
    "fps": int(os.environ["STEREO_CAMERA_FPS"]) if os.environ.get("STEREO_CAMERA_FPS") else None,
    "split_mode": os.environ.get("STEREO_CAMERA_SPLIT_MODE", "left_right"),
    "backend": os.environ.get("STEREO_CAMERA_BACKEND", ""),
}

CSRF_TRUSTED_ORIGINS = [
    os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173"),
]

# Channel layer: InMemory in dev, Redis in production
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
USE_REDIS_CHANNEL = os.environ.get("USE_REDIS_CHANNEL", "0") == "1"

if USE_REDIS_CHANNEL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "PAGE_SIZE_QUERY_PARAM": "page_size",
    "MAX_PAGE_SIZE": 100,
}

TEST_RUNNER = "fruit_api.test_runner.CompatibleDiscoverRunner"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
