# Ubuntu 22.04 云服务器部署步骤

目标：在全新的 Ubuntu Server 22.04 LTS 64bit 云服务器上部署当前项目，并最终通过 `http://110.42.223.232` 直接访问项目首页。

部署架构：

- Nginx 监听 `80` 端口
- Daphne 监听 `127.0.0.1:8000`
- Nginx 反向代理到 Daphne

## 1. 部署前准备

服务器上必须具备以下内容：

- 当前项目代码
- `frontend_dist/` 前端静态产物
- `.env.local`
- 模型文件
- MySQL
- Conda 环境 `shuiguo`

需要确认这些文件已经上传到服务器：

- `frontend_dist/index.html`
- `frontend_dist/assets/`
- `model/epoch90.pt`
- `model/best_model_finetuned.pth`
- `model/Mango_50_ultimate_model.pth`
- `model/Banana_50_ultimate_model.pth`
- `model/strawberry_ultimate_model.pth`
- `model/monster_runtime/pretrained/mix_all.pth`
- `model/monster_runtime/pretrained/depth_anything_v2_vitl.pth`
- `model/monster_runtime/calibration/calib_stereo.npz`

云服务器安全组必须放行：

- `22/tcp`
- `80/tcp`

## 2. 连接服务器

本地执行：

```bash
ssh root@110.42.223.232
```

## 3. 安装系统依赖

服务器执行：

```bash
apt update
apt install -y build-essential pkg-config python3-dev default-libmysqlclient-dev mysql-server nginx libgl1 libglib2.0-0 ffmpeg curl unzip git
```

启动并设置开机自启：

```bash
systemctl enable mysql nginx
systemctl start mysql nginx
systemctl status mysql --no-pager
systemctl status nginx --no-pager
```

## 4. 安装 Miniconda

```bash
cd /opt
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p /opt/miniconda3
source /opt/miniconda3/etc/profile.d/conda.sh
conda create -n shuiguo python=3.12 -y
conda activate shuiguo
python --version
```

## 5. 上传项目

服务器目录统一使用：

```bash
mkdir -p /opt/shuiguo
```

建议把当前整个项目上传到：

```text
/opt/shuiguo
```

上传完成后检查：

```bash
cd /opt/shuiguo
ls
ls frontend_dist
ls model
```

重点确认：

```bash
ls /opt/shuiguo/frontend_dist/index.html
ls /opt/shuiguo/frontend_dist/assets
ls /opt/shuiguo/model/epoch90.pt
ls /opt/shuiguo/model/monster_runtime/pretrained/mix_all.pth
ls /opt/shuiguo/model/monster_runtime/calibration/calib_stereo.npz
```

## 6. 安装 Python 依赖

```bash
cd /opt/shuiguo
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate shuiguo
pip install -r requirements.txt
```

## 7. 配置 MySQL

当前项目本地 `.env.local` 中的数据库配置是：

```env
DB_NAME=shuiguo_db
DB_USER=root
DB_PASSWORD=105474
DB_HOST=127.0.0.1
DB_PORT=3306
```

因此服务器按这个密码准备数据库。执行：

```bash
mysql
```

在 MySQL 中执行：

```sql
CREATE DATABASE shuiguo_db DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci;
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '105474';
FLUSH PRIVILEGES;
EXIT;
```

如果你的服务器 root 用户不能直接这样改，也可以改成新建用户，但那样就必须同步修改 `.env.local` 里的 `DB_USER`。

## 8. 配置 `.env.local`

服务器上的 `/opt/shuiguo/.env.local` 建议至少为：

```env
DEBUG=0
SECRET_KEY=dev-secret-key-not-for-production
ALLOWED_HOSTS=110.42.223.232,127.0.0.1,localhost

DB_NAME=shuiguo_db
DB_USER=root
DB_PASSWORD=105474
DB_HOST=127.0.0.1
DB_PORT=3306

FRONTEND_ORIGIN=http://110.42.223.232
CSRF_TRUSTED_ORIGINS=http://110.42.223.232
FRONTEND_DIST_DIR=frontend_dist

USE_X_FORWARDED_HOST=0
USE_X_FORWARDED_PROTO=0
SESSION_COOKIE_SECURE=0
CSRF_COOKIE_SECURE=0

USE_REDIS_CHANNEL=0
REDIS_URL=redis://127.0.0.1:6379/0

MEASURE_DEVICE=auto

STEREO_CAMERA_SOURCE_MODE=single
STEREO_CAMERA_INDEX=0
STEREO_LEFT_CAMERA_INDEX=0
STEREO_RIGHT_CAMERA_INDEX=1
STEREO_CAMERA_SPLIT_MODE=left_right
```

如果没有这个文件，可以先复制模板：

```bash
cd /opt/shuiguo
cp .env.local.example .env.local
nano .env.local
```

## 9. 检查前端配置

确认前端配置不是本地地址：

```bash
cat /opt/shuiguo/frontend_dist/config.json
```

应为：

```json
{
    "serverUrl": "http://110.42.223.232"
}
```

## 10. 初始化 Django

```bash
cd /opt/shuiguo
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate shuiguo
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 11. 手工启动验证

先手工确认项目能跑起来：

```bash
cd /opt/shuiguo
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate shuiguo
daphne -b 0.0.0.0 -p 8000 shuiguo.asgi:application
```

另开一个 SSH 窗口测试：

```bash
curl http://127.0.0.1:8000/api/health/
curl http://127.0.0.1:8000/
```

要求：

- `/api/health/` 返回 `status: ok`
- `/` 返回 HTML 页面，不是 `Frontend build not found`

## 12. 配置 systemd

项目里已经准备了服务文件：

- `deploy/ubuntu/shuiguo.service`

执行：

```bash
cp /opt/shuiguo/deploy/ubuntu/shuiguo.service /etc/systemd/system/shuiguo.service
systemctl daemon-reload
systemctl enable shuiguo
systemctl restart shuiguo
systemctl status shuiguo --no-pager
```

查看日志：

```bash
journalctl -u shuiguo -f
```

## 13. 配置 Nginx

项目里已经准备了 Nginx 配置：

- `deploy/ubuntu/nginx-shuiguo.conf`

执行：

```bash
cp /opt/shuiguo/deploy/ubuntu/nginx-shuiguo.conf /etc/nginx/sites-available/shuiguo
ln -sf /etc/nginx/sites-available/shuiguo /etc/nginx/sites-enabled/shuiguo
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

## 14. 最终验证

先验证本机：

```bash
curl http://127.0.0.1:8000/api/health/
curl http://127.0.0.1/api/health/
```

再验证公网：

```bash
curl http://110.42.223.232/api/health/
```

浏览器访问：

- `http://110.42.223.232`
- `http://110.42.223.232/admin/`

如果首页和你本地 `http://localhost:8000` 打开的一样，说明部署完成。

## 15. 常见问题

### 15.1 访问公网超时

检查：

- 云安全组是否放行 `80`
- `systemctl status nginx`
- `systemctl status shuiguo`

### 15.2 返回 502

说明 Nginx 找不到后端，检查：

```bash
systemctl status shuiguo --no-pager
journalctl -u shuiguo -f
```

### 15.3 首页提示 `Frontend build not found`

说明 `frontend_dist/` 没上传完整，重点检查：

```bash
ls /opt/shuiguo/frontend_dist/index.html
ls /opt/shuiguo/frontend_dist/assets
```

### 15.4 数据库连接失败

检查：

- `.env.local` 中 `DB_USER=root`
- `.env.local` 中 `DB_PASSWORD=105474`
- MySQL root 密码是否已设置为 `105474`

### 15.5 模型加载失败

说明模型文件不全或路径不对，按第 1 节重新核对。

## 16. 已知限制

- 摄像头相关能力使用的是服务器本机摄像头，不是你自己电脑浏览器的摄像头
- 如果服务器没有接摄像头，图片检测和普通页面可以用，但实时检测、摄像头预览、标定等能力不可用
