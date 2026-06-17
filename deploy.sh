#!/bin/bash
# ChessDB Oracle Cloud 部署脚本
# 适用于 Ubuntu 22.04/24.04 ARM64 (Ampere A1)
# 使用方法: bash deploy.sh

set -e

echo "============================================"
echo "  ChessDB 一键部署脚本 (Oracle Cloud ARM64)"
echo "============================================"

# ---- 1. 系统依赖 ----
echo ""
echo "[1/6] 安装系统依赖..."
sudo apt-get update
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw

# ---- 2. 安装 Docker ----
if command -v docker &> /dev/null; then
    echo "Docker 已安装，跳过..."
else
    echo ""
    echo "[2/6] 安装 Docker..."
    # 添加 Docker 官方 GPG key
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    # 添加 Docker 仓库
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # 允许当前用户使用 docker
    sudo usermod -aG docker $USER
    echo "Docker 安装完成! (可能需要重新登录以生效用户组)"
fi

# ---- 3. 克隆项目 ----
REPO_DIR="$HOME/ces"
if [ -d "$REPO_DIR" ]; then
    echo ""
    echo "[3/6] 项目目录已存在，拉取最新代码..."
    cd "$REPO_DIR"
    git pull || true
else
    echo ""
    echo "[3/6] 克隆项目..."
    read -p "请输入 GitHub 仓库地址 (例: https://github.com/user/ces.git): " REPO_URL
    git clone "${REPO_URL:-https://github.com/user/ces.git}" "$REPO_DIR"
    cd "$REPO_DIR"
fi

# ---- 4. 配置环境变量 ----
ENV_FILE="$REPO_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    echo ""
    echo "[4/6] .env 文件已存在，跳过..."
else
    echo ""
    echo "[4/6] 生成 .env 配置文件..."
    SECRET_KEY=$(openssl rand -hex 32)
    JWT_SECRET=$(openssl rand -hex 32)

    cat > "$ENV_FILE" << EOF
# 生产环境密钥 - 请勿泄露
SECRET_KEY=${SECRET_KEY}
JWT_SECRET_KEY=${JWT_SECRET}

# 数据库 (SQLite, 数据持久化在 Docker Volume 中)
DATABASE_URI=sqlite:////app/backend/data/chessdb.db

# Stockfish 配置 (Oracle Cloud 12GB RAM)
ANALYSIS_DEPTH=20
ANALYSIS_THREADS=2
ANALYSIS_HASH=256
EOF
    echo ".env 文件已生成: $ENV_FILE"
fi

# ---- 5. 防火墙配置 ----
echo ""
echo "[5/6] 配置防火墙..."
sudo ufw --force enable
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
echo "防火墙规则: SSH(22) + HTTP(80) + HTTPS(443)"

# ---- 6. 构建并启动 ----
echo ""
echo "[6/6] 构建 Docker 镜像并启动服务..."
cd "$REPO_DIR"
sudo docker compose up -d --build

echo ""
echo "等待服务启动..."
sleep 15

# 初始化数据库
echo "初始化数据库..."
sudo docker compose exec backend flask init-db 2>/dev/null || \
    echo "数据库可能已初始化，跳过..."

# 灌入种子数据
echo "灌入种子数据 (棋手、开局、示例棋谱)..."
sudo docker compose exec backend flask seed-data 2>/dev/null || \
    echo "种子数据可能已存在，跳过..."

# ---- 完成 ----
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")

echo ""
echo "============================================"
echo "  部署完成!"
echo "============================================"
echo ""
echo "  访问地址: http://${PUBLIC_IP}"
echo "  后端 API: http://${PUBLIC_IP}/api/"
echo ""
echo "  创建管理员账户:"
echo "    sudo docker compose exec backend flask create-admin"
echo ""
echo "  常用命令:"
echo "    查看日志:   sudo docker compose logs -f"
echo "    重启服务:   sudo docker compose restart"
echo "    停止服务:   sudo docker compose down"
echo "    更新部署:   git pull && sudo docker compose up -d --build"
echo ""
echo "  数据库位置: Docker Volume (chessdb_backend-db)"
echo "  上传文件位置: Docker Volume (chessdb_backend-uploads)"
echo "  数据不会因容器重启而丢失"
echo ""
echo "  如需绑定域名，请配置 DNS A 记录指向: ${PUBLIC_IP}"
echo "============================================"
