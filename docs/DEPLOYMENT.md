# 部署完整指南

> 本项目支持多种部署方式，按用户需求与平台特性选择最合适的方案。
> 当前主推：**Hugging Face Spaces**（国内可访问、无需信用卡、单容器一键部署）。
>
> 部署后端前请先完整阅读 [`PROJECT_ANALYSIS.md`](PROJECT_ANALYSIS.md) 与 [`backend/core.md`](backend/core.md) 了解架构。

## 0. 方案对比

| 方案 | 后端 | 前端 | 数据库 | 费用 | 国内访问 | 适用场景 |
|------|------|------|--------|------|----------|----------|
| **Hugging Face Spaces** | 单容器（gunicorn + nginx） | 内置（nginx 静态服务） | SQLite + Persistent Storage | 免费 / 持久化 $5/月 | ✅ 优秀 | **当前主推**、演示、毕业设计 |
| Render + Vercel | Render Docker | Vercel 静态 | Neon PostgreSQL | 免费（需 Visa 验证） | 一般 | 海外团队演示 |
| Oracle Cloud ARM | Docker Compose | Nginx | SQLite + Volume | 永久免费 | 一般 | 重度使用 |
| 雨云/腾讯云 | Docker Compose | Nginx | SQLite + Volume | ¥10-30/月 | ✅ 优秀 | 长期运营 |

**为什么最终选择 Hugging Face Spaces**：

1. **零门槛注册**：GitHub 登录即可，国内可访问
2. **免费 Stockfish**：16GB 内存 + 2 CPU 跑得动
3. **国内访问快**：huggingface.co 在国内有 CDN
4. **数据库持久化**：升级 Persistent Storage 即可（$5/月）
5. **单仓库单容器**：维护简单，CI/CD 友好

---

## 1. Hugging Face Spaces 部署（推荐）

### 1.1 前置准备

- Hugging Face 账号（https://huggingface.co，建议用 GitHub 登录）
- 项目已推送到 GitHub（见 1.2 节）
- 本地已通过 `start.bat` 验证后端能跑起来

### 1.2 GitHub 仓库准备

项目根目录已包含完整的 HF 部署相关文件：

| 文件 | 作用 |
|------|------|
| `Dockerfile.hf` | HF Spaces 单容器构建（前端+后端+Nginx+Stockfish） |
| `README_HF.md` | HF Spaces 部署说明 |
| `deploy-hf.sh` | 一键部署脚本（推送 + 配置 Space） |
| `start-hf.sh` | 容器启动入口（supervisord 拉起 nginx+gunicorn） |
| `hf/supervisord.conf` | 进程管理配置 |
| `hf/nginx.conf` | 反向代理配置 |
| `render.yaml` | Render 部署（备用） |

#### 推送项目到 GitHub

```bash
cd d:\Users\pc\AppData\Local\Programs\trae_projects\ces

# 1. 初始化（首次）
git init
git add .
git commit -m "feat: ChessDB v1.0"

# 2. 关联远程仓库（在 GitHub 新建仓库后）
git remote add origin https://github.com/<your-username>/chessdb.git

# 3. 推送
git branch -M main
git push -u origin main
```

**注意**：`.gitignore` 已排除：
- `backend/chessdb.db`（本地数据库，HF 上自动生成）
- `backend/.env`（本地环境变量）
- `backend/uploads/`（用户上传文件）
- `frontend/node_modules/`
- `__pycache__/`
- `.venv/`

### 1.3 创建 Hugging Face Space

1. 访问 https://huggingface.co/new-space
2. 填写信息：
   - **Space name**：`chessdb`（或自定义）
   - **License**：MIT
   - **SDK**：**Docker**（必须）
   - **Space hardware**：CPU basic（免费）/ CPU upgrade（$5/月含持久化）
   - **Visibility**：Public（公开）/ Private（私有）
3. 点击 **Create Space**

### 1.4 推送代码到 Space

#### 方式 A：使用 deploy-hf.sh（一键）

```bash
# 在项目根目录执行
chmod +x deploy-hf.sh
./deploy-hf.sh
```

脚本会自动：
1. 校验环境
2. 添加 HF 远程仓库
3. 推送到 Space
4. 触发 Docker 构建

#### 方式 B：手动推送

```bash
# 添加 HF 远程
git remote add hf https://<your-username>:<your-hf-token>@huggingface.co/spaces/<your-username>/chessdb

# 推送
git push hf main
```

> Token 在 https://huggingface.co/settings/tokens 生成，需勾选 `write` 权限。

### 1.5 配置 Space 密钥（可选）

在 Space 页面 **Settings → Repository secrets** 添加：

| 密钥名 | 值 | 说明 |
|--------|-----|------|
| `SECRET_KEY` | 随机字符串 | Flask Session 加密 |
| `JWT_SECRET_KEY` | 随机字符串 | JWT 签名 |
| `CORS_ORIGINS` | `*` | CORS 白名单 |

> 如不配置，将使用默认值（仅适合演示）。**生产环境务必修改**。

### 1.6 数据库持久化（重要！）

**免费层**：数据存储在临时文件系统，**重启容器会丢失**。
**付费层（$5/月）**：升级到 CPU upgrade，HF 自动挂载 `/data` 持久卷。

#### 启用持久化

1. 进入 Space → **Settings → Persistent Storage**
2. 点击 **Enable persistent storage**
3. 等待 5 分钟生效

#### 数据库自动迁移到 /data

启动脚本 `start-hf.sh` 会：

```bash
# 创建 /data 目录
mkdir -p /data

# 如果 /data/chessdb.db 不存在，从代码中复制
if [ ! -f /data/chessdb.db ]; then
    cp /app/backend/chessdb.db /data/chessdb.db
fi

# 软链接
ln -sf /data/chessdb.db /app/backend/chessdb.db
```

### 1.7 访问应用

部署成功后（约 5-10 分钟首次构建），访问：

```
https://<your-username>-chessdb.hf.space
```

**默认管理员账号**：
- 用户名：`admin`
- 密码：`admin123`（由 `init_db.py` 创建，**部署后请立即修改**）

### 1.8 常见问题

#### Q1: Stockfish 启动失败，引擎不可用？

**A**：检查 Space 日志（**Logs** 标签）。常见原因：
- 多架构二进制不兼容：HF 默认 x86_64，如果使用 ARM 镜像需要 `stockfish-arm64`
- 权限不足：`chmod +x stockfish` 必须在 Dockerfile 中执行

**Dockerfile.hf** 已包含：
```dockerfile
RUN apt-get update && apt-get install -y stockfish wget curl
# 自动下载适配架构的 Stockfish 二进制
RUN wget -O /usr/bin/stockfish ... && chmod +x /usr/bin/stockfish
```

#### Q2: 部署成功但访问 500 错误？

**A**：检查 `/api/health` 端点：
```
curl https://<your-username>-chessdb.hf.space/api/health
```

返回 `{"status":"ok","games":N}` 表示后端正常。失败的话：
- 查看 Logs 标签
- 确认 `SECRET_KEY` / `JWT_SECRET_KEY` 已设置
- 确认数据库迁移成功

#### Q3: 数据库每次重启都被清空？

**A**：需要：
1. 升级到 CPU upgrade（$5/月）
2. 启用 Persistent Storage
3. 重启 Space 让 `/data` 卷挂载

#### Q4: 注册新用户报 418 错误？

**A**：Hugging Face 的安全策略，可能因 IP 被风控。解决方案：
- 使用 VPN 切换到美国节点
- 等待 24 小时后重试
- 用 GitHub 账号注册

---

## 2. Render + Vercel 部署（备选）

### 2.1 Render 部署后端

1. 访问 https://render.com（需要 Visa 卡验证，但不扣费）
2. **New → Web Service** → 连接 GitHub 仓库
3. 配置：
   - **Environment**：Docker
   - **Dockerfile Path**：`Dockerfile`
   - **Region**：Oregon
   - **Instance Type**：Free
4. 添加环境变量：
   - `SECRET_KEY`：随机字符串
   - `JWT_SECRET_KEY`：随机字符串
   - `DATABASE_URL`：Neon PostgreSQL 连接串
5. 点击 **Create Web Service**

### 2.2 Vercel 部署前端

1. 访问 https://vercel.com → **New Project** → 导入 GitHub 仓库
2. **Root Directory** 设为 `frontend`
3. 框架：**Vite**
4. 添加环境变量：
   - `VITE_API_BASE_URL`：`/api`（由 vercel.json 反代）
5. 部署

### 2.3 vercel.json 反向代理

项目根目录 `vercel.json`：

```json
{
  "rewrites": [
    { "source": "/api/(.*)", "destination": "https://<your-render-app>.onrender.com/api/$1" }
  ]
}
```

---

## 3. Oracle Cloud ARM 部署

适合**重度使用**且需要**永久免费**的场景。

### 3.1 创建实例

1. 注册 Oracle Cloud（信用卡验证，永久免费层）
2. 创建 ARM 实例（4 CPU + 24GB 内存，免费）
3. 开放端口：22（SSH）、80（HTTP）、443（HTTPS）

### 3.2 部署

```bash
# SSH 登录
ssh ubuntu@<your-instance-ip>

# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 克隆项目
git clone https://github.com/<your-username>/chessdb.git
cd chessdb

# 启动
docker compose up -d --build

# 初始化数据库
docker compose exec backend flask init-db

# 访问
http://<your-instance-ip>
```

### 3.3 配置 HTTPS

使用 Let's Encrypt + Nginx：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## 4. 国内 VPS 部署（雨云/腾讯云）

适合**长期运营**且需要**国内访问速度**的场景。

### 4.1 服务器准备

1. 购买 VPS（2C2G 起步，约 ¥10-30/月）
2. 安装 Ubuntu 22.04
3. 开放端口：22、80、443

### 4.2 一键部署

```bash
# 克隆项目
git clone https://github.com/<your-username>/chessdb.git
cd chessdb

# 给脚本加权限
chmod +x deploy-cn.sh

# 执行一键部署
./deploy-cn.sh
```

脚本自动完成：
1. 安装 Docker
2. 构建镜像
3. 启动容器
4. 初始化数据库
5. 配置 Nginx
6. 申请 SSL 证书

---

## 5. 本地开发部署

### 5.1 Windows 本地启动

```bat
# 双击或在 cmd 中执行
start.bat
```

自动启动：
- 后端：Flask dev server，端口 5000
- 前端：Vite dev server，端口 3000

### 5.2 Docker 本地启动

```bash
docker compose up -d --build
docker compose exec backend flask init-db
```

访问：
- 前端：http://localhost
- 后端：http://localhost:5000

### 5.3 手动启动

```bash
# 终端 1：后端
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
flask init-db
flask run

# 终端 2：前端
cd frontend
npm install
npm run dev
```

---

## 6. 部署后必做清单

- [ ] 修改默认管理员密码（`admin / admin123`）
- [ ] 配置 `SECRET_KEY` 和 `JWT_SECRET_KEY` 为强随机字符串
- [ ] 配置 `CORS_ORIGINS` 为实际域名（不要用 `*`）
- [ ] 启用 HTTPS（Let's Encrypt）
- [ ] 配置数据库自动备份（cron 定时任务）
- [ ] 配置日志收集（Hugging Face Logs / CloudWatch）
- [ ] 注册时如果遇到 418 错误，切换 IP 重试

---

## 7. 部署故障排查

| 现象 | 可能原因 | 解决方案 |
|------|----------|----------|
| Docker 构建失败 | 网络问题导致依赖下载失败 | 重新构建 `docker compose build --no-cache` |
| Stockfish 不可用 | 引擎二进制与架构不匹配 | 重新下载正确架构的 Stockfish |
| 数据库表不存在 | 未执行 `flask init-db` | 进入容器执行初始化命令 |
| 端口被占用 | 5000/7860 端口已被其他程序占用 | 修改 `docker-compose.yml` 端口映射 |
| 静态资源 404 | 前端未构建 | `cd frontend && npm run build` |
| CORS 错误 | 跨域白名单未配置 | 设置 `CORS_ORIGINS` 环境变量 |
| Token 过期频繁 | JWT 密钥不一致 | 确保 `JWT_SECRET_KEY` 一致 |

---

## 8. 性能优化建议

- **分析任务**：开启异步分析，避免阻塞请求
- **数据库**：SQLite 适合 < 1 万棋谱，超过后建议迁移到 PostgreSQL
- **缓存**：分析结果已自动缓存到 `analyses` 表，重复查询不会重复分析
- **CDN**：HF Spaces 静态资源已自动 CDN 加速
- **限流**：`flask-limiter` 默认 2000/天，500/小时，多用户场景建议调整

---

## 9. 监控与运维

### 9.1 HF Spaces 监控

- **Logs** 标签：查看实时日志
- **Community** 标签：用户反馈
- **Settings → Usage**：CPU/内存使用率

### 9.2 自建监控

- 使用管理 API `/api/admin/stats` 获取流量统计
- 使用 `/api/admin/analytics/heatmap` 端点热度分析
- 配合 Prometheus + Grafana（可选）

### 9.3 数据备份

```bash
# 进入容器
docker compose exec backend bash

# 备份
flask backup-db
# 生成 backups/chessdb_YYYYMMDD_HHMMSS.db
```

或手动备份：
```bash
docker cp chessdb-backend:/app/backend/chessdb.db ./backup_$(date +%Y%m%d).db
```

---

## 10. 升级与回滚

### 10.1 代码升级

```bash
git pull origin main
docker compose up -d --build
```

HF Spaces：直接 push 到 HF 远程，Space 自动重新构建。

### 10.2 数据库迁移

```bash
docker compose exec backend flask db migrate -m "description"
docker compose exec backend flask db upgrade
```

### 10.3 回滚

```bash
# 1. 回滚代码
git checkout <previous-tag>
docker compose up -d --build

# 2. 回滚数据库（如需）
docker compose exec backend flask db downgrade -1
```
