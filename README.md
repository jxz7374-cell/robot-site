# Robot组招生训练平台

这是一个基于 `Flask + SQLite` 的网站，支持：

- 学生注册、登录
- 报名信息采集
- 学习资料发布与下载
- 学习时长记录
- 在线考试
- 管理员查看、导出、剔除学生和管理员

## 本地启动

```powershell
cd "C:\Users\Thinkbook\Desktop\new student"
.\start-local.ps1
```

浏览器访问：

```text
http://127.0.0.1:8000/
```

## 生产启动

Windows 下如果你只是想用更接近生产环境的方式启动：

```powershell
cd "C:\Users\Thinkbook\Desktop\new student"
.\start-prod.ps1
```

这个脚本使用的是 `waitress`。

## 环境变量

项目已经支持用环境变量控制数据库、上传目录和密钥。示例见 [.env.example](<C:\Users\Thinkbook\Desktop\new student\.env.example:1>)。

常用变量：

- `SECRET_KEY`
- `PORT`
- `DATABASE_PATH`
- `UPLOAD_FOLDER`
- `DEFAULT_ADMIN_USERNAME`
- `DEFAULT_ADMIN_PASSWORD`
- `DEFAULT_ADMIN_NAME`

## Linux 服务器部署

如果你准备的是一台 Ubuntu 或 Debian 服务器，可以按这个流程部署。

### 1. 准备服务器

- 一台有公网 IP 的 Linux 服务器
- 已开放 `80` 端口
- 如果后面要 HTTPS，再开放 `443` 端口

### 2. 安装依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
```

### 3. 上传项目

把整个项目上传到服务器，例如：

```text
/opt/robot-site
```

### 4. 创建虚拟环境并安装依赖

```bash
cd /opt/robot-site
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. 配置环境变量

复制一份环境变量文件：

```bash
cp .env.example .env
```

然后至少改这几项：

- `SECRET_KEY`
- `DATABASE_PATH=/opt/robot-site/instance/robot_recruit.db`
- `UPLOAD_FOLDER=/opt/robot-site/uploads/materials`
- `DEFAULT_ADMIN_PASSWORD`

### 6. 先手动测试启动

```bash
cd /opt/robot-site
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
gunicorn -w 1 --threads 4 --timeout 120 -b 127.0.0.1:8000 wsgi:application
```

如果没有报错，说明服务本身没问题。

### 7. 配置 systemd

项目里已经给你准备好了 systemd 模板：

- [deploy/robot-site.service](<C:\Users\Thinkbook\Desktop\new student\deploy\robot-site.service:1>)

复制到服务器：

```bash
sudo cp deploy/robot-site.service /etc/systemd/system/robot-site.service
```

如果你的项目目录不是 `/opt/robot-site`，记得先改文件里的路径。

然后启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable robot-site
sudo systemctl start robot-site
sudo systemctl status robot-site
```

### 8. 配置 Nginx

项目里已经给你准备好了 Nginx 模板：

- [deploy/nginx-robot-site.conf](<C:\Users\Thinkbook\Desktop\new student\deploy\nginx-robot-site.conf:1>)

复制到服务器：

```bash
sudo cp deploy/nginx-robot-site.conf /etc/nginx/sites-available/robot-site
```

修改里面的：

- `server_name your-domain.com;`
- 项目实际目录

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/robot-site /etc/nginx/sites-enabled/robot-site
sudo nginx -t
sudo systemctl reload nginx
```

### 9. 配置 HTTPS

如果你已经有域名，推荐用 `certbot`：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Docker 部署

项目已经带了：

- [Dockerfile](<C:\Users\Thinkbook\Desktop\new student\Dockerfile:1>)
- [.dockerignore](<C:\Users\Thinkbook\Desktop\new student\.dockerignore:1>)

构建镜像：

```bash
docker build -t robot-site .
```

运行容器：

```bash
docker run -d \
  --name robot-site \
  -p 8000:8000 \
  -e SECRET_KEY='replace-with-a-long-random-secret' \
  -e DATABASE_PATH='/data/robot_recruit.db' \
  -e UPLOAD_FOLDER='/data/uploads/materials' \
  -v /opt/robot-site-data:/data \
  robot-site
```

这样数据库和上传文件会保存在宿主机 `/opt/robot-site-data`。

## 默认管理员

首次启动且数据库里没有管理员时，系统会自动创建默认管理员：

- 用户名：`admin`
- 密码：`Admin123456`

上线前建议马上修改，或者在第一次启动前通过环境变量覆盖。

## 你现在离真正上线还差什么

我已经把项目整理到“可部署”状态了，但我现在还不能替你直接发到公网，因为还缺这些外部条件：

- 你的服务器或云平台账号
- 公网 IP 或域名
- 服务器登录权限

如果你接下来告诉我你准备用哪一种方式，我可以继续按那条路给你细化到几乎照抄命令就能上线：

1. `Linux 云服务器`
2. `Docker 服务器`
3. `Windows 电脑临时公网演示`

