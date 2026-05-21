#!/bin/bash
# ===================================
# Docker 运行环境脚本
# ===================================

set -e

# Docker 应用路径
DOCKER_BIN="/Applications/Docker.app/Contents/Resources/bin"
export PATH="$DOCKER_BIN:$PATH"

# 项目目录
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 检查 Docker 是否运行
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Docker 未运行，正在启动..."
        open -a Docker
        echo "⏳ 等待 Docker 启动..."
        for i in {1..30}; do
            sleep 2
            if docker info > /dev/null 2>&1; then
                echo "✅ Docker 已启动"
                return 0
            fi
            echo "⏳ 等待中... ($i/30)"
        done
        echo "❌ Docker 启动超时"
        exit 1
    fi
    echo "✅ Docker 已运行"
}

# 显示菜单
show_menu() {
    echo ""
    echo "=========================================="
    echo "  A股智能分析系统 - Docker 管理"
    echo "=========================================="
    echo "1. 构建镜像"
    echo "2. 启动服务"
    echo "3. 停止服务"
    echo "4. 查看日志"
    echo "5. 进入容器 shell"
    echo "6. 清理镜像"
    echo "0. 退出"
    echo "=========================================="
    echo -n "请选择: "
}

# 主菜单
case "${1:-menu}" in
    "build")
        check_docker
        echo "🔨 构建 Docker 镜像..."
        docker compose build --no-cache
        echo "✅ 镜像构建完成"
        ;;
    "start")
        check_docker
        echo "🚀 启动服务..."
        docker compose up -d
        echo "✅ 服务已启动"
        docker compose ps
        ;;
    "stop")
        echo "🛑 停止服务..."
        docker compose down
        echo "✅ 服务已停止"
        ;;
    "logs")
        docker compose logs -f "${2:-stock-analysis}"
        ;;
    "shell")
        docker compose exec stock-analysis /bin/bash
        ;;
    "clean")
        echo "🧹 清理 Docker 资源..."
        docker compose down --rmi all -v
        echo "✅ 清理完成"
        ;;
    "restart")
        docker compose restart
        ;;
    *)
        show_menu
        read choice
        case $choice in
            1) $0 build ;;
            2) $0 start ;;
            3) $0 stop ;;
            4) $0 logs ;;
            5) $0 shell ;;
            6) $0 clean ;;
            0) exit 0 ;;
            *) echo "无效选择" ;;
        esac
        ;;
esac
