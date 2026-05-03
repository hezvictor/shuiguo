# 水果识别、熟度判断、实时检测与双目果径测量系统

这是一个前后端分离的水果智能识别系统。项目目标包括：

- 水果目标检测
- 水果种类分类
- 芒果 / 香蕉 / 草莓熟度识别
- 实时摄像头检测
- 双目相机果径测量
- 检测历史记录与报告保存

后端使用 Django + Django REST Framework + Channels，前端使用 Vue 3 + Vite。

## 1. 仓库结构与分支说明

你的 GitHub 仓库当前有两个主要分支：

- `django`
  - 存放后端代码
  - 负责 API、WebSocket、数据库、模型加载、报告输出、双目测量、相机管理
- `vue`
  - 存放前端代码
  - 负责页面交互、表单、图片检测页、实时检测页、双目测量页、历史记录页

完整部署方式是：

1. 获取 `django` 分支作为后端工程
2. 获取 `vue` 分支作为前端工程
3. 在 `vue` 分支执行前端构建
4. 把前端构建产物复制到后端项目的 `frontend_dist/` 目录
5. 启动后端后，直接访问 `http://127.0.0.1:8000/` 即可使用完整项目

## 2. 当前代码状态说明

这份 README 以你当前本地 `django` 分支代码为准，不按论文描述做理想化扩展。

根据当前本地代码，已经可以确认：

- 后端已经集成水果分类、熟度识别、YOLO 检测、实时检测、双目相机采集和果径测量
- 双目果径测量代码已经迁移进当前 Django 项目，不再依赖外部 `E:\code\shuiguo\MonSter-main` 作为运行时项目
- 当前测量运行时代码位于：
  - `model/monster_runtime/`
  - `fruit_api/diameter_service.py`
  - `fruit_api/services/detection/diameter_app_service.py`
- 当前代码中的双目测量已经不是“推理后手动点两个点”的旧交互，而是结合 YOLO 检测结果自动测量目标

同时也需要明确一点：

- 你的论文里提到了“视频检测”
- 但按当前本地 `django` 分支的实际路由，**没有发现单独的 `/api/video/*` 上传/进度接口**
- 所以本文档严格以当前代码已经暴露出来的接口能力为准：图片检测、实时检测、相机流、双目测量、历史记录、用户认证

如果后续你把视频检测接口重新合并进 `django` 分支，可以再补充 README。

## 3. 本地目录对应关系

你当前机器上的项目目录是：

- 后端：`E:\software\PyCharm\code\shuiguo`
- 前端：`E:\code\fruit_vue\fruit_vue`
- 原始 MonSter 工程：`E:\code\shuiguo\MonSter-main`

对其他开发者来说，不需要使用和你完全一样的盘符路径，但需要保持下面的逻辑关系：

- 一个后端项目目录
- 一个前端项目目录
- 前端构建完成后，把 `dist/` 内容复制到后端的 `frontend_dist/`

## 4. 运行环境要求

### 后端

- Windows 10 / 11
- Conda
- Python 3.11.x
- MySQL 8.x
- 可选：Redis 7.x

你的后端虚拟环境使用 Conda，激活命令为：

```powershell
conda activate shuiguo
```

### 前端

根据 `vue` 分支中的 `package.json`，前端要求：

- Node.js `^20.19.0 || >=22.12.0`
- npm

前端构建脚本为：

- `npm run build`

## 5. 获取两个分支的推荐方式

推荐使用一个主仓库 + 一个 worktree，这样最清晰。

### 5.1 克隆后端分支

```powershell
git clone <你的仓库地址> shuiguo-backend
cd shuiguo-backend
git switch django
```

### 5.2 拉出前端分支到旁边目录

```powershell
git worktree add ..\shuiguo-frontend vue
```

执行完之后，目录结构类似：

```text
你的工作目录/
├─ shuiguo-backend/   # django 分支
└─ shuiguo-frontend/  # vue 分支
```

如果你不想用 `git worktree`，也可以分别克隆两次仓库，然后分别切换到 `django` 和 `vue` 分支。

## 6. 前端构建与部署方式

### 6.1 安装前端依赖

```powershell
cd ..\shuiguo-frontend
npm install
```

### 6.2 构建前端

```powershell
npm run build
```

构建完成后，`vue` 分支会生成 `dist/` 目录。

### 6.3 将前端构建产物复制到后端

切回后端目录并创建 `frontend_dist/`：

```powershell
cd ..\shuiguo-backend
New-Item -ItemType Directory -Force frontend_dist | Out-Null
```

然后把前端 `dist/` 的内容复制进去：

```powershell
xcopy /E /I /Y ..\shuiguo-frontend\dist\* .\frontend_dist\
```

### 6.4 前端构建产物至少应包含什么

根据当前 `django` 分支的静态资源服务逻辑，后端会从 `frontend_dist/` 中读取这些内容：

- `frontend_dist/index.html`
- `frontend_dist/assets/` 下的所有构建资源
- `frontend_dist/favicon.ico`
- `frontend_dist/config.json`
- `frontend_dist/fonts/` 下的字体资源

其中，`vue` 分支当前已经包含：

- `public/config.json`
- `public/favicon.ico`
- `public/fonts/simhei.ttf`

因此正常执行 `npm run build` 后，再把整个 `dist/` 复制到 `frontend_dist/`，这些文件应当自动到位。

## 7. 后端依赖安装

进入后端目录：

```powershell
cd shuiguo-backend
conda activate shuiguo
```

安装 Python 依赖：

```powershell
pip install -r requirements.txt
```

如果你只想测试双目测量实验依赖，可以使用：

```powershell
pip install -r requirements_monster.txt
```

但要启动完整后端服务，应该安装 `requirements.txt`。

## 8. 必须准备的非 Git 文件

下面这些文件**不会上传到 Git 仓库**。其他用户要复现完整项目，必须在拿到这些文件后，按下面的文件名和目录放好。

### 8.1 水果识别与熟度识别模型

放到后端项目的 `model/` 目录下：

- `model/epoch90.pt`
- `model/best_model_finetuned.pth`
- `model/mango_mobilevit_plus.pth`
- `model/banana_mobilevit_plus.pth`
- `model/strawberry_3class_mobilevit.pth`

### 8.2 双目果径测量模型

放到后端项目的 `model/monster_runtime/pretrained/` 目录下：

- `model/monster_runtime/pretrained/mix_all.pth`
- `model/monster_runtime/pretrained/depth_anything_v2_vitl.pth`

### 8.3 双目标定结果文件

放到后端项目的 `model/monster_runtime/calibration/` 目录下：

- `model/monster_runtime/calibration/calib_stereo.npz`

### 8.4 环境变量文件

需要在后端项目根目录创建：

- `.env.local`

你可以直接从仓库中的模板复制：

```powershell
Copy-Item .env.local.example .env.local
```

### 8.5 构建后前端文件

需要放到后端项目根目录下的：

- `frontend_dist/`

里面应至少包含：

- `frontend_dist/index.html`
- `frontend_dist/assets/...`
- `frontend_dist/favicon.ico`
- `frontend_dist/config.json`
- `frontend_dist/fonts/...`

## 9. 当前项目不再依赖外部 MonSter-main 目录

你的原始果径测量工程来自：

- `E:\code\shuiguo\MonSter-main`

但根据当前本地 Django 代码，部署完整项目时：

- **不需要把 `MonSter-main` 单独克隆到服务器**
- **不需要在运行时引用那个目录里的 Python 包**

因为你已经把需要的运行时代码迁移进当前项目：

- `model/monster_runtime/`
- `fruit_api/diameter_service.py`

也就是说，部署时只需要：

- `django` 分支代码
- `vue` 分支构建产物
- 模型文件
- 双目标定结果文件

## 10. MySQL 数据库准备

当前 `django` 分支的数据库后端固定为 MySQL。

请先在 MySQL 中创建数据库：

```sql
CREATE DATABASE shuiguo_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;
```

## 11. 后端环境变量配置

项目启动时会自动读取根目录 `.env.local`。

推荐最小配置如下：

```env
DEBUG=1
SECRET_KEY=replace-this-with-a-local-dev-secret
ALLOWED_HOSTS=127.0.0.1,localhost,0.0.0.0

DB_NAME=shuiguo_db
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306

FRONTEND_ORIGIN=http://localhost:5173
FRONTEND_DIST_DIR=frontend_dist

USE_REDIS_CHANNEL=0
REDIS_URL=redis://127.0.0.1:6379/0

MEASURE_DEVICE=auto

STEREO_CAMERA_SOURCE_MODE=single
STEREO_CAMERA_INDEX=0
STEREO_LEFT_CAMERA_INDEX=0
STEREO_RIGHT_CAMERA_INDEX=1
STEREO_CAMERA_WIDTH=
STEREO_CAMERA_HEIGHT=
STEREO_CAMERA_FPS=
STEREO_CAMERA_SPLIT_MODE=left_right
STEREO_CAMERA_BACKEND=
```

### 关键变量说明

- `SECRET_KEY`
  - Django 密钥，生产环境必须改成你自己的值
- `DB_*`
  - MySQL 连接信息
- `FRONTEND_DIST_DIR`
  - 前端构建产物目录，默认就是 `frontend_dist`
- `USE_REDIS_CHANNEL`
  - `0` 表示开发期使用内存通道层
  - `1` 表示启用 Redis，适合多进程 / 生产环境
- `MEASURE_DEVICE`
  - 双目测量使用的设备，默认 `auto`

## 12. 初始化数据库

在后端目录下执行：

```powershell
conda activate shuiguo
python manage.py migrate
python manage.py createsuperuser
```

说明：

- `migrate`
- `createsuperuser`
- `test`

这些命令不会强制加载模型文件，因此即使你还没放模型，也能先完成数据库初始化。

## 13. 启动完整项目

### 13.1 本地开发方式

先确保：

- `.env.local` 已配置
- MySQL 已启动
- 前端 `dist/` 已复制到 `frontend_dist/`
- 所需模型文件和 `calib_stereo.npz` 已放到正确目录

然后启动后端：

```powershell
conda activate shuiguo
python manage.py runserver 0.0.0.0:8000
```

启动后访问：

- 首页：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/health/`
- 管理后台：`http://127.0.0.1:8000/admin/`

### 13.2 Daphne / ASGI 启动方式

如果你要用更接近生产环境的方式启动：

```powershell
conda activate shuiguo
daphne -b 0.0.0.0 -p 8000 shuiguo.asgi:application
```

## 14. 当前代码中可直接使用的核心接口

### 14.1 用户认证

- `GET /api/csrf/`
- `POST /api/register/`
- `POST /api/login/`
- `POST /api/logout/`
- `GET /api/user_info/`
- `POST /api/update_profile/`
- `POST /api/change_password/`

### 14.2 图片检测

- `POST /api/predict/`
- `POST /api/predict_with_ripeness/`
- `POST /api/predict_ripeness_by_type/`
- `POST /api/yolo_detect_info/`
- `POST /api/yolo_detect_with_boxes/`
- `POST /api/yolo_report/`
- `POST /api/image-detection/tasks/`

### 14.3 双目测量

- `POST /api/measure/infer/`
- `POST /api/measure/distance/`
- `POST /api/measure/diameter/`
- `GET /api/measure/runtime-status/`

### 14.4 相机与双目采集

- `GET /api/camera/status/`
- `GET /api/camera/registry/`
- `POST /api/camera/registry/scan/`
- `POST /api/camera/registry/select/`
- `GET /api/camera/probe/`
- `POST /api/camera/start/`
- `POST /api/camera/stop/`
- `GET /api/camera/stream/`
- `POST /api/camera/capture/`
- `POST /api/camera/capture/save/`
- `GET /api/camera/captures/`
- `GET /api/camera/captures/download/`
- `DELETE /api/camera/captures/<record_id>/`
- `POST /api/camera/measure/`

### 14.5 实时检测

- `POST /api/realtime/detect/current-frame/`
- `POST /api/realtime/save_report/`

### 14.6 历史记录

- `GET /api/detection/history/`
- `GET /api/detection/history/<id>/`

## 15. WebSocket 路径

当前后端代码中启用了以下 WebSocket：

- `/ws/fruit-recognition/`
- `/ws/camera/preview/`
- `/ws/camera/device-preview/`

说明：

- `vue` 分支的 Vite 开发配置已经把 `/api/`、`/media/`、`/ws/`、`/static/` 代理到 `http://localhost:8000`
- 但如果你已经把前端构建结果放入 `frontend_dist/`，那么直接访问 `8000` 端口即可，不再需要 Vite 开发服务器

## 16. 复现成功的最小检查清单

其他用户拿到代码、模型文件和标定文件后，至少要确认以下项目全部完成：

1. `django` 分支代码已获取
2. `vue` 分支代码已获取
3. 前端已成功执行 `npm install`
4. 前端已成功执行 `npm run build`
5. 前端 `dist/` 已复制到后端 `frontend_dist/`
6. 后端已安装 `requirements.txt`
7. `.env.local` 已创建并填写 MySQL 配置
8. MySQL 数据库 `shuiguo_db` 已创建
9. `python manage.py migrate` 已成功执行
10. 模型文件已放入 `model/` 和 `model/monster_runtime/pretrained/`
11. 双目标定文件 `calib_stereo.npz` 已放入 `model/monster_runtime/calibration/`
12. `python manage.py runserver 0.0.0.0:8000` 能正常启动
13. `http://127.0.0.1:8000/api/health/` 返回 `status=ok`
14. `http://127.0.0.1:8000/` 可以正常打开前端页面

## 17. 常见问题

### 17.1 启动后首页返回 `Frontend build not found`

原因：

- 你没有把 `vue` 分支构建后的 `dist/` 内容复制到 `frontend_dist/`

处理：

```powershell
xcopy /E /I /Y ..\shuiguo-frontend\dist\* .\frontend_dist\
```

### 17.2 图片检测 / 双目测量时报模型加载失败

原因：

- 模型文件没有放在代码约定目录

请重点检查这些文件是否存在：

- `model/epoch90.pt`
- `model/best_model_finetuned.pth`
- `model/mango_mobilevit_plus.pth`
- `model/banana_mobilevit_plus.pth`
- `model/strawberry_3class_mobilevit.pth`
- `model/monster_runtime/pretrained/mix_all.pth`
- `model/monster_runtime/pretrained/depth_anything_v2_vitl.pth`
- `model/monster_runtime/calibration/calib_stereo.npz`

### 17.3 双目测量报依赖缺失

请检查：

- `model/monster_runtime/pretrained/mix_all.pth`
- `model/monster_runtime/pretrained/depth_anything_v2_vitl.pth`
- `model/monster_runtime/calibration/calib_stereo.npz`

这三个文件缺一不可。

### 17.4 WebSocket 在多进程下不稳定

开发环境默认：

- `USE_REDIS_CHANNEL=0`

如果你要多进程部署，请切换为：

```env
USE_REDIS_CHANNEL=1
REDIS_URL=redis://127.0.0.1:6379/0
```

并确保 Redis 正常运行。

### 17.5 `mysqlclient` 安装失败

Windows 下这是常见问题。建议检查：

- Python 版本是否与依赖兼容
- 是否安装了 Visual C++ Build Tools
- 是否具备 MySQL 客户端开发环境

## 18. 与论文描述的对应关系

你的论文里描述的总体技术路线，与当前仓库代码基本一致：

- Django + DRF 负责 API
- Vue 负责前端页面
- Channels + WebSocket 负责实时能力
- YOLOv8 负责目标检测
- EfficientNet-B3 负责水果分类
- MobileViT + CBAM 负责熟度识别
- MySQL 保存结构化摘要
- 本地文件系统 `media/` 保存报告和媒体文件

但在部署与复现时，**请一律以当前代码和本 README 为准**，不要只根据论文文字自行推断目录和文件名。

## 19. 一句话部署总结

只要其他用户拿到以下四部分内容，就可以按本 README 复现你的完整项目：

1. `django` 分支代码
2. `vue` 分支代码
3. 所有模型文件
4. 双目标定结果文件 `calib_stereo.npz`

然后执行：

- 构建 `vue` 分支前端
- 把 `dist/` 复制到 `django/frontend_dist/`
- 配置 `.env.local`
- 准备 MySQL
- 启动 Django 8000 端口

即可在本地通过 `http://127.0.0.1:8000/` 使用完整服务。
