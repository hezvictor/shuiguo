# 水果识别、熟度判断、实时检测与双目果径测量系统

本文档基于当前实际代码整理，主要参考：

- 后端：`E:\software\PyCharm\code\shuiguo`
- 前端：`E:\code\fruit_vue\fruit_vue`

这不是按论文或理想设计写的说明，而是按当前本地代码、真实路由、真实配置和真实依赖写的复现文档。

## 1. 项目简介

这是一个前后端分离的水果视觉识别系统，已经把以下能力接入同一套业务流程：

- 水果目标检测：YOLO 检测图片或实时画面中的目标。
- 水果种类识别：对检测框目标做二次分类。
- 熟度判断：当前实际支持 `mango`、`banana`、`strawberry` 三类水果熟度分类。
- 实时检测：摄像头预览 + 定时检测 + 会话保存。
- 双目果径测量：基于双目图像、标定结果和 MonSter 运行时做果径测量。
- 历史记录与报告管理：图片检测、实时检测、果径测量统一落库并生成文件产物。

后端使用 Django、Django REST Framework、Channels；前端使用 Vue 3、Vite、Element Plus。

## 2. 仓库与分支说明

GitHub 仓库有两个主要分支：

- `django`
  - 存放后端代码。
- `vue`
  - 存放前端代码。

完整部署方式不是把两个分支分别跑在两个端口长期联调，而是：

1. 获取 `django` 分支作为后端项目。
2. 获取 `vue` 分支作为前端项目。
3. 在 `vue` 分支执行构建。
4. 把前端构建产物复制到后端根目录的 `frontend_dist/`。
5. 启动后端后，直接访问 `http://127.0.0.1:8000/` 即可使用完整项目。

也就是说，部署态下由 Django 直接托管前端构建结果。

## 3. 本地目录对应关系

当前开发机目录如下：

- 后端：`E:\software\PyCharm\code\shuiguo`
- 前端：`E:\code\fruit_vue\fruit_vue`

其他开发者不需要使用相同盘符路径，但需要保持下面这层关系：

- 一个后端目录，内容来自 `django` 分支。
- 一个前端目录，内容来自 `vue` 分支。
- 前端构建完成后，把 `dist/` 里的内容复制到后端 `frontend_dist/`。

## 4. 当前实际技术栈

### 4.1 后端

根据 `requirements.txt`、`shuiguo/settings.py`、`fruit_api/apps.py`、`shuiguo/asgi.py`，后端当前实际使用：

- Python 3.11.x
- Conda 虚拟环境
- Django 6.0.3
- Django REST Framework
- Channels
- Daphne
- MySQL
- Redis / channels_redis
  - 开发态可不启用 Redis，默认可退回 InMemory channel layer。
- PyTorch
- torchvision
- timm
- ultralytics
- OpenCV
- Pillow
- NumPy
- SciPy
- matplotlib
- openpyxl
- opt-einsum

### 4.2 前端

根据 `E:\code\fruit_vue\fruit_vue\package.json`、`vite.config.ts` 和源码，前端当前实际使用：

- Vue 3
- Vue Router 4
- Vite
- Element Plus
- Axios
- TypeScript 工程配置

前端 `package.json` 当前声明的 Node 版本要求是：

- `^20.19.0 || >=22.12.0`

## 5. 后端实际目录结构

- `manage.py`
  - Django 管理入口。
- `shuiguo/`
  - Django 项目配置，包含 `settings.py`、`urls.py`、`asgi.py`、`views.py`。
- `fruit_api/`
  - 主业务 app。
- `fruit_api/views_modules/`
  - 按业务拆分的 API 视图层。
- `fruit_api/services/`
  - 服务层，拆分为认证、检测、摄像头、存储、控制台等模块。
- `model/`
  - 模型文件和 MonSter 双目运行时代码。
- `media/`
  - 运行期输出目录，保存报告、标注图、会话产物、拍照 ZIP 等。
- `frontend_dist/`
  - 前端构建产物目录，Django 从这里返回 `index.html` 和静态资源。

## 6. 前端实际页面与路由

根据 `E:\code\fruit_vue\fruit_vue\src\router\index.js`，当前真正挂载的主页面有：

- `/login`
- `/register`
- `/console`
- `/detection/image`
- `/detection/realtime`
- `/camera/config`
- `/history`
- `/profile`
- `/about`

同时，前端源码里还存在但当前路由未挂载的页面：

- `E:\code\fruit_vue\fruit_vue\src\views\DiameterMeasurementView.vue`
- `E:\code\fruit_vue\fruit_vue\src\views\DashboardView.vue`
- `E:\code\fruit_vue\fruit_vue\src\views\HomeView.vue`

因此，当前用户主流程实际集中在控制台、图片检测、实时检测、摄像头配置、历史记录和个人中心。

## 7. 当前主要接口与通信方式

### 7.1 认证接口

- `GET /api/csrf/`
- `POST /api/register/`
- `POST /api/login/`
- `POST /api/logout/`
- `GET /api/user_info/`
- `POST /api/update_profile/`
- `POST /api/change_password/`

前端当前是 `Django Session + CSRF + localStorage 登录标记` 的组合方式，不是纯 JWT。

### 7.2 图片检测相关接口

- `POST /api/predict/`
- `POST /api/predict_with_ripeness/`
- `POST /api/predict_ripeness_by_type/`
- `POST /api/yolo_detect_info/`
- `POST /api/yolo_detect_with_boxes/`
- `POST /api/yolo_report/`
- `POST /api/image-detection/tasks/`

### 7.3 果径测量相关接口

- `POST /api/measure/infer/`
- `POST /api/measure/distance/`
- `POST /api/measure/diameter/`
- `GET /api/measure/runtime-status/`
- `POST /api/camera/measure/`

### 7.4 摄像头相关接口

- `GET /api/camera/status/`
- `GET /api/camera/registry/`
- `POST /api/camera/registry/scan/`
- `POST /api/camera/registry/select/`
- `GET /api/camera/probe/`
- `GET /api/camera/device-frame/<camera_index>/`
- `GET /api/camera/calibration/status/`
- `POST /api/camera/calibration/capture/`
- `POST /api/camera/calibration/run/`
- `POST /api/camera/start/`
- `POST /api/camera/stop/`
- `GET /api/camera/stream/`
- `POST /api/camera/capture/`
- `POST /api/camera/capture/save/`
- `DELETE /api/camera/capture/stages/<stage_id>/`
- `GET /api/camera/captures/`
- `POST /api/camera/captures/download/`
- `DELETE /api/camera/captures/<record_id>/`

### 7.5 控制台与历史记录

- `GET /api/console/overview/`
- `GET /api/console/recent/`
- `GET /api/console/system-status/`
- `GET /api/detection/history/`
- `GET /api/detection/history/<id>/`

### 7.6 实时检测

- `POST /api/realtime/detect/current-frame/`
- `POST /api/realtime/save_report/`

### 7.7 WebSocket

根据 `fruit_api/routing.py`，当前已注册的 WebSocket 路由为：

- `/ws/fruit-recognition/`
- `/ws/camera/preview/`
- `/ws/camera/device-preview/`

前端当前实际主要使用 `/ws/camera/device-preview/` 做摄像头预览。

## 8. 运行环境要求

### 8.1 后端

- Windows 10 / 11
- Conda
- Python 3.11.x
- MySQL 8.x
- 可选：Redis 7.x

你的虚拟环境激活命令为：

```powershell
conda activate shuiguo
```

### 8.2 前端

- Node.js `^20.19.0 || >=22.12.0`
- npm

## 9. 获取两个分支

推荐方式一：分别克隆两个目录。

```powershell
git clone <你的仓库地址> shuiguo-backend
cd shuiguo-backend
git switch django
```

```powershell
git clone <你的仓库地址> shuiguo-frontend
cd shuiguo-frontend
git switch vue
```

推荐方式二：使用 `git worktree`。

```powershell
git clone <你的仓库地址> shuiguo-backend
cd shuiguo-backend
git switch django
git worktree add ..\shuiguo-frontend vue
```

## 10. 安装依赖

### 10.1 后端依赖

在后端目录执行：

```powershell
conda activate shuiguo
pip install -r requirements.txt
```

说明：

- `requirements.txt` 是完整后端依赖。
- `requirements_monster.txt` 只是双目果径实验依赖子集，不足以启动完整系统。

### 10.2 前端依赖

在前端目录执行：

```powershell
npm install
```

## 11. 前端构建与部署到后端

### 11.1 构建前端

在前端目录执行：

```powershell
npm run build
```

构建完成后会生成 `dist/`。

### 11.2 复制到后端 `frontend_dist/`

切回后端目录：

```powershell
New-Item -ItemType Directory -Force frontend_dist | Out-Null
xcopy /E /I /Y ..\shuiguo-frontend\dist\* .\frontend_dist\
```

如果你是按当前本地目录组织的，也可以把 `E:\code\fruit_vue\fruit_vue\dist\` 的内容复制到 `E:\software\PyCharm\code\shuiguo\frontend_dist\`。

### 11.3 `frontend_dist/` 至少应包含

根据 `shuiguo/urls.py` 和 `shuiguo/views.py`，部署态下 Django 会直接读取这些前端构建文件：

- `frontend_dist/index.html`
- `frontend_dist/assets/`
- `frontend_dist/favicon.ico`
- `frontend_dist/config.json`
- `frontend_dist/fonts/`

按当前前端源码，下面这些文件会从 `vue` 分支构建进入 `frontend_dist/`：

- `frontend_dist/index.html`
- `frontend_dist/config.json`
- `frontend_dist/favicon.ico`
- `frontend_dist/fonts/simhei.ttf`
- `frontend_dist/assets/*`

如果没有把前端构建结果复制到 `frontend_dist/`，访问首页时后端会返回 `Frontend build not found`。

## 12. 必须手动提供的非 Git 文件

这一节是给其他开发者复现项目时最关键的部分。

当前仓库 `.gitignore` 明确忽略了：

- `.env.local`
- `*.pt`
- `*.pth`
- `*.npz`
- `media/` 运行期产物

因此，其他用户拿到代码后，还必须额外拿到下面这些文件，并且放到指定目录。

### 12.1 后端根目录环境变量文件

需要手动创建：

- `.env.local`

放置位置：

- 后端根目录：`./.env.local`

可以先用模板复制：

```powershell
Copy-Item .env.local.example .env.local
```

### 12.2 水果分类、熟度分类、YOLO 模型文件

需要手动提供并放到后端 `model/` 目录：

- `model/epoch90.pt`
- `model/best_model_finetuned.pth`
- `model/mango_mobilevit_plus.pth`
- `model/banana_mobilevit_plus.pth`
- `model/strawberry_3class_mobilevit.pth`

这些文件由 `fruit_api/apps.py` 和 `shuiguo/settings.py` 直接引用，文件名必须一致。

### 12.3 双目果径测量模型文件

需要手动提供并放到：

- `model/monster_runtime/pretrained/`

具体文件名：

- `model/monster_runtime/pretrained/mix_all.pth`
- `model/monster_runtime/pretrained/depth_anything_v2_vitl.pth`

说明：

- `mix_all.pth` 由 `shuiguo/settings.py -> MEASURE_CONFIG["RESTORE_CKPT"]` 直接引用。
- `depth_anything_v2_vitl.pth` 由 `model/monster_runtime/core/monster.py` 在运行时直接引用。

### 12.4 双目标定结果文件

需要手动提供并放到：

- `model/monster_runtime/calibration/`

具体文件名：

- `model/monster_runtime/calibration/calib_stereo.npz`

说明：

- 当前默认标定文件路径由 `shuiguo/settings.py -> MEASURE_CONFIG["CALIB_NPZ"]` 指定。
- 文件名必须是 `calib_stereo.npz`，否则默认配置下无法直接运行。

### 12.5 前端构建产物

需要手动构建并放到：

- `frontend_dist/`

至少应包含：

- `frontend_dist/index.html`
- `frontend_dist/config.json`
- `frontend_dist/favicon.ico`
- `frontend_dist/fonts/simhei.ttf`
- `frontend_dist/assets/*`

说明：

- 这些文件来自 `vue` 分支构建结果，不会自动出现在 `django` 分支仓库里。

## 13. 不需要额外提供的内容

下面这些内容已经在当前 `django` 分支代码中，不需要再单独从别的目录复制：

- `model/monster_runtime/` 下的 MonSter 运行时代码
- `Depth-Anything-V2-list3/` 源码
- `requirements.txt`
- `requirements_monster.txt`
- `.env.local.example`

因此，复现当前项目时不需要再额外依赖外部 `MonSter-main` 目录。只要代码、模型权重和标定文件齐全即可。

## 14. `.env.local` 最小配置示例

当前后端会自动读取根目录 `.env.local`。可先使用下面这份最小配置：

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

说明：

- `USE_REDIS_CHANNEL=0` 时，本地开发可不启动 Redis。
- `FRONTEND_DIST_DIR=frontend_dist` 表示 Django 从后端根目录 `frontend_dist/` 读取构建产物。
- `MEASURE_DEVICE=auto` 表示果径测量自动选择 GPU 或 CPU。

## 15. 数据库准备

当前默认数据库后端是 MySQL。

先创建数据库：

```sql
CREATE DATABASE shuiguo_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;
```

然后在后端目录执行：

```powershell
conda activate shuiguo
python manage.py migrate
python manage.py createsuperuser
```

说明：

- 当前代码对 `migrate`、`createsuperuser`、`test` 这类管理命令做了跳过模型加载处理。
- 因此数据库初始化阶段不要求先成功加载 AI 模型。

## 16. 启动项目

### 16.1 本地开发方式

确认以下内容已经完成：

- 已安装后端依赖。
- 已安装前端依赖并完成构建。
- 已把前端构建产物复制到 `frontend_dist/`。
- 已创建 `.env.local`。
- 已准备 MySQL 并完成 `migrate`。
- 已把模型文件和 `calib_stereo.npz` 放到指定目录。

然后启动后端：

```powershell
conda activate shuiguo
python manage.py runserver 0.0.0.0:8000
```

访问地址：

- 首页：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/health/`
- Django Admin：`http://127.0.0.1:8000/admin/`

### 16.2 ASGI / Daphne 启动方式

```powershell
conda activate shuiguo
daphne -b 0.0.0.0 -p 8000 shuiguo.asgi:application
```

## 17. 复现成功的最小清单

其他开发者拿到代码、模型文件和双目标定结果文件后，只要按下面清单完成，就可以根据本 README 在本地复现：

1. 获取 `django` 分支代码。
2. 获取 `vue` 分支代码。
3. 后端执行 `pip install -r requirements.txt`。
4. 前端执行 `npm install`。
5. 前端执行 `npm run build`。
6. 把前端 `dist/` 内容复制到后端 `frontend_dist/`。
7. 在后端根目录创建 `.env.local`。
8. 创建 MySQL 数据库 `shuiguo_db` 并完成 `python manage.py migrate`。
9. 把以下文件放到 `model/`：
   `epoch90.pt`、`best_model_finetuned.pth`、`mango_mobilevit_plus.pth`、`banana_mobilevit_plus.pth`、`strawberry_3class_mobilevit.pth`
10. 把以下文件放到 `model/monster_runtime/pretrained/`：
    `mix_all.pth`、`depth_anything_v2_vitl.pth`
11. 把 `calib_stereo.npz` 放到 `model/monster_runtime/calibration/`。
12. 启动 `python manage.py runserver 0.0.0.0:8000`。
13. 访问 `http://127.0.0.1:8000/api/health/`，确认返回健康状态。
14. 访问 `http://127.0.0.1:8000/`，确认前端页面可正常打开。

## 18. 常见问题

### 18.1 首页返回 `Frontend build not found`

原因通常是：

- 没有执行前端构建。
- 构建后没有把 `dist/` 内容复制到后端 `frontend_dist/`。

### 18.2 分类、熟度或 YOLO 接口报模型加载失败

优先检查这些文件是否存在于 `model/`：

- `epoch90.pt`
- `best_model_finetuned.pth`
- `mango_mobilevit_plus.pth`
- `banana_mobilevit_plus.pth`
- `strawberry_3class_mobilevit.pth`

### 18.3 双目果径测量报依赖缺失

优先检查这些文件是否存在：

- `model/monster_runtime/pretrained/mix_all.pth`
- `model/monster_runtime/pretrained/depth_anything_v2_vitl.pth`
- `model/monster_runtime/calibration/calib_stereo.npz`

### 18.4 WebSocket 在多进程部署下不稳定

开发环境默认可用：

```env
USE_REDIS_CHANNEL=0
```

如果要多进程部署，建议改为：

```env
USE_REDIS_CHANNEL=1
REDIS_URL=redis://127.0.0.1:6379/0
```

并确保 Redis 正常运行。

## 19. 一句话总结

要复现当前项目，其他开发者只需要拿到四部分内容：

1. `django` 分支代码
2. `vue` 分支代码
3. 所有模型权重文件
4. 双目标定结果文件 `calib_stereo.npz`

然后构建前端、复制到 `frontend_dist/`、配置 `.env.local`、准备 MySQL、启动后端 8000 端口，即可在本地运行完整系统。
