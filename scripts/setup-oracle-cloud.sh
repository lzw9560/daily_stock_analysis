#!/usr/bin/env bash
# ============================================================
# Oracle Cloud 部署脚本
# 适用于：Ubuntu 22.04 / 24.04 (ARM Ampere A1)
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[x]${NC} $1"; exit 1; }

# === 配置变量（请按需修改） ===
APP_DIR="${APP_DIR:-$HOME/daily-stock-analysis}"
GIT_REPO="${GIT_REPO:-git@github.com:lzw9560/daily_stock_analysis.git}"
GIT_BRANCH="${GIT_BRANCH:-develop}"

info "============================================"
info " Oracle Cloud 免费实例部署脚本"
info "============================================"

# === 1. 系统更新 ===
info "更新系统软件包..."
sudo apt-get update -y && sudo apt-get upgrade -y

# === 2. 安装 Docker ===
if ! command -v docker &>/dev/null; then
    info "安装 Docker..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
    warn "已添加到 docker 组，脚本结束后请重新登录使其生效"
else
    info "Docker 已安装，跳过"
fi

# === 3. 安装 Docker Compose ===
if ! docker compose version &>/dev/null; then
    info "安装 Docker Compose 插件..."
    sudo apt-get install -y docker-compose-plugin
else
    info "Docker Compose 已安装，跳过"
fi

# === 4. 启动 Docker ===
sudo systemctl enable docker
sudo systemctl start docker

# === 5. 克隆代码 ===
if [ -d "$APP_DIR" ]; then
    info "代码目录已存在，执行 git pull..."
    cd "$APP_DIR"
    git checkout "$GIT_BRANCH"
    git pull origin "$GIT_BRANCH"
else
    info "克隆代码仓库..."
    git clone -b "$GIT_BRANCH" "$GIT_REPO" "$APP_DIR"
fi

cd "$APP_DIR"

# === 6. 配置 .env 文件 ===
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        info "从 .env.example 创建 .env 文件..."
        cp .env.example .env
        warn "请编辑 $APP_DIR/.env 填入你的 API Key！"
        warn "至少需要：GEMINI_API_KEY、FEISHU_WEBHOOK_URL"
    else
        info "创建空白 .env 文件..."
        cat > .env << 'EOF'
# === 必需配置 ===
GEMINI_API_KEY=your_gemini_api_key_here
FEISHU_WEBHOOK_URL=your_feishu_webhook_url_here

# === 可选配置 ===
TUSHARE_TOKEN=
DISCORD_BOT_TOKEN=
API_PORT=8000
EOF
        warn "请编辑 $APP_DIR/.env 填入实际值！"
    fi
else
    info ".env 文件已存在，跳过"
fi

# === 7. 创建数据目录 ===
mkdir -p data logs reports

# === 8. 防火墙放行端口 ===
info "配置防火墙（放行 8000 端口）..."
sudo apt-get install -y ufw
sudo ufw allow 8000/tcp comment 'stock-analysis API'
sudo ufw --force enable 2>/dev/null || true

# === 9. 创建 systemd 服务 ===
SERVICE_FILE="/etc/systemd/system/stock-analysis.service"
if [ ! -f "$SERVICE_FILE" ]; then
    info "创建 systemd 服务..."
    sudo tee "$SERVICE_FILE" > /dev/null << SYSTEMD
[Unit]
Description=Daily Stock Analysis (Docker Compose)
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose -f docker/docker-compose.yml up -d server
ExecStop=/usr/bin/docker compose -f docker/docker-compose.yml down
ExecStartPost=/bin/sleep 5
User=$USER
Group=docker

[Install]
WantedBy=multi-user.target
SYSTEMD
    sudo systemctl daemon-reload
    sudo systemctl enable stock-analysis.service
    info "systemd 服务已创建并启用"
else
    warn "systemd 服务已存在，跳过"
fi

# === 10. 构建并启动 ===
info "构建 Docker 镜像（首次约 5-10 分钟）..."
sudo systemctl start stock-analysis.service

info ""
info "============================================"
info "  部署完成！"
info "============================================"
info ""
info "  检查服务状态："
info "    sudo systemctl status stock-analysis"
info "    docker compose -f docker/docker-compose.yml logs -f"
info ""
info "  服务地址："
info "    http://<你的公网IP>:8000"
info "    http://<你的公网IP>:8000/docs"
info "    http://<你的公网IP>:8000/api/health"
info ""
warn "  别忘了编辑 .env："
warn "    vim $APP_DIR/.env"
info ""
