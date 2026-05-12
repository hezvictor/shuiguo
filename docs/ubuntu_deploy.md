# Ubuntu 22.04 部署说明

目标：通过 `http://110.42.223.232` 直接访问项目首页，效果与本地访问 `http://localhost:8000` 一致。

本文按以下固定路径编写：

- 项目目录：`/opt/shuiguo`
- Conda 安装目录：`/opt/miniconda3`
- Conda 环境名：`shuiguo`

如果你使用别的目录，需要同步修改：

- `deploy/ubuntu/shuiguo.service`
- `deploy/ubuntu/nginx-shuiguo.conf`

## 1. 需要先准备好的文件

代码仓库之外，这些文件也要放到服务器上：

- `.env.local`
- `frontend_dist/` 前端构建产物
- `frontend_dist/config.json` 里的 `serverUrl` 不能再指向 `localhost`
- `model/epoch90.pt`
- `model/best_model_finetuned.pth`
- `model/Mango_50_ultimate_model.pth`
- `model/Banana_50_ultimate_model.pth`
- `model/strawberry_ultimate_model.pth`
- `model/monster_runtime/pretrained/mix_all.pth`
- `model/monster_runtime/pretrained/depth_anything_v2_vitl.pth`
- `model/monster_runtime/calibration/calib_stereo.npz`

## 2. 安装系统依赖

```bash
sudo apt update
sudo apt install -y build-essential pkg-config python3-dev default-libmysqlclient-dev mysql-server nginx libgl1 libglib2.0-0 ffmpeg
```

说明：

- `default-libmysqlclient-dev` 和 `pkg-config` 用于安装 `mysqlclient`
- `libgl1`、`libglib2.0-0` 常用于 `opencv-python` 运行
- 当前单进程部署不强制要求 Redis

## 3. 安装 Conda 并创建环境

先在服务器安装 Miniconda 或 Anaconda，然后创建与本地一致的环境名 `shuiguo`。

创建环境后执行：

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda create -n shuiguo python=3.12 -y
conda activate shuiguo
```

## 4. 上传项目并安装 Python 依赖

将项目放到 `/opt/shuiguo` 后执行：

```bash
cd /opt/shuiguo
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate shuiguo
pip install -r requirements.txt
```

## 5. 配置 MySQL

登录 MySQL：

```bash
sudo mysql
```

在 MySQL 中执行：

```sql
CREATE DATABASE shuiguo_db DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci;
CREATE USER 'shuiguo_user'@'127.0.0.1' IDENTIFIED BY 'replace_with_strong_password';
GRANT ALL PRIVILEGES ON shuiguo_db.* TO 'shuiguo_user'@'127.0.0.1';
FLUSH PRIVILEGES;
```

## 6. 生产环境 `.env.local`

可以从 `.env.local.example` 复制：

```bash
cp .env.local.example .env.local
```

建议至少改成：

```env
DEBUG=0
SECRET_KEY=replace-with-a-long-random-secret
ALLOWED_HOSTS=110.42.223.232,127.0.0.1,localhost

DB_NAME=shuiguo_db
DB_USER=shuiguo_user
DB_PASSWORD=replace_with_strong_password
DB_HOST=127.0.0.1
DB_PORT=3306

FRONTEND_ORIGIN=http://110.42.223.232
CSRF_TRUSTED_ORIGINS=http://110.42.223.232
FRONTEND_DIST_DIR=frontend_dist

USE_REDIS_CHANNEL=0
REDIS_URL=redis://127.0.0.1:6379/0

MEASURE_DEVICE=auto

STEREO_CAMERA_SOURCE_MODE=single
STEREO_CAMERA_INDEX=0
STEREO_LEFT_CAMERA_INDEX=0
STEREO_RIGHT_CAMERA_INDEX=1
STEREO_CAMERA_SPLIT_MODE=left_right
```

如果未来切 HTTPS，再额外打开这些变量：

```env
USE_X_FORWARDED_HOST=1
USE_X_FORWARDED_PROTO=1
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
```

## 7. 初始化数据库和静态文件

```bash
cd /opt/shuiguo
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate shuiguo
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 8. 先手工验证 Daphne

先确认应用本身可启动：

```bash
cd /opt/shuiguo
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate shuiguo
daphne -b 0.0.0.0 -p 8000 shuiguo.asgi:application
```

此时在服务器上执行：

```bash
curl http://127.0.0.1:8000/api/health/
```

预期返回包含 `"status":"ok"`。

## 9. 配置 systemd

复制服务文件：

```bash
sudo cp deploy/ubuntu/shuiguo.service /etc/systemd/system/shuiguo.service
```

如果你的项目目录或 Conda 目录不是本文默认值，先编辑：

```bash
sudo nano /etc/systemd/system/shuiguo.service
```

然后启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable shuiguo
sudo systemctl restart shuiguo
sudo systemctl status shuiguo --no-pager
```

查看日志：

```bash
sudo journalctl -u shuiguo -f
```

## 10. 配置 Nginx

复制站点配置：

```bash
sudo cp deploy/ubuntu/nginx-shuiguo.conf /etc/nginx/sites-available/shuiguo
sudo ln -sf /etc/nginx/sites-available/shuiguo /etc/nginx/sites-enabled/shuiguo
sudo rm -f /etc/nginx/sites-enabled/default
```

检查并重载：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 11. 放行端口

如果启用了 UFW：

```bash
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw reload
```

如果你使用云厂商安全组，也要同步放行 `80` 端口。

## 12. 最终验证

依次检查：

```bash
curl http://127.0.0.1:8000/api/health/
curl http://110.42.223.232/api/health/
```

然后浏览器访问：

- `http://110.42.223.232`
- `http://110.42.223.232/admin/`

## 13. 已知限制

- 当前摄像头相关能力读取的是服务器本机摄像头，不是你自己电脑浏览器的摄像头
- 如果服务器没有接摄像头，首页和图片检测类功能可以正常访问，但摄像头预览、实时检测、标定等能力不会可用
- 当前单进程部署下 `USE_REDIS_CHANNEL=0` 没问题；如果后续改成多进程或多实例，再启用 Redis channel layer
