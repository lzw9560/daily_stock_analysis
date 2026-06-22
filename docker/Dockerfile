# ============================================================
# A股自选股智能分析系统 - Dockerfile
# ============================================================
# 多阶段构建：前端打包 → 后端运行
#
# 构建上下文须为 workspace 根目录 daily-stock-analysis/
#   docker build -t stock-analysis -f daily_stock_analysis/docker/Dockerfile .
#   docker compose -f daily_stock_analysis/docker/docker-compose.yml up -d --build
#
# 运行模式（通过 CMD 覆盖）：
#   schedule  - 定时调度模式（默认），持续运行，每日定时分析
#   api       - 仅 API 服务，不执行定时分析
#   once      - 单次分析后退出
# ============================================================

# ==================== 阶段 1：前端构建 ====================
FROM node:20-slim AS web-builder

WORKDIR /app/apps/dsa-web

# 依赖安装（利用层缓存）
COPY daily_stock_analysis/apps/dsa-web/package.json daily_stock_analysis/apps/dsa-web/package-lock.json ./
RUN npm ci --prefer-offline || npm ci

# 源码 + 构建
COPY daily_stock_analysis/apps/dsa-web/ ./
RUN npm run build \
    && echo "Frontend build complete!" \
    && ls -la /app/static/ \
    && test -f /app/static/index.html || (echo "ERROR: index.html missing after build!" && exit 1)

# ==================== 阶段 2：后端运行 ====================
FROM python:3.11-slim-bullseye

WORKDIR /app

# ── 时区 ──
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# ── 系统依赖 ──
# wkhtmltopdf/wkhtmltoimage: Markdown 转图片/PDF（Issue #289）
# gosu: 安全的 non-root 用户切换（entrypoint 中使用）
# fontconfig/libjpeg/libxrender/libxext: wkhtmltoimage 渲染依赖
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    git \
    gosu \
    procps \
    wkhtmltopdf \
    fontconfig \
    libjpeg62-turbo \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# ── 创建非 root 用户（UID 1000 与常见 Linux 桌面用户对齐）──
RUN groupadd -g 1000 dsa && \
    useradd -u 1000 -g dsa -m dsa

# ── Python 依赖 ──
# 先复制 TradingAgents-astock 源码（本地路径依赖需要，与 requirements.txt 中 ../TradingAgents-astock 对应）
COPY TradingAgents-astock /TradingAgents-astock
COPY daily_stock_analysis/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/ \
    -r requirements.txt && \
    rm -rf /TradingAgents-astock

# ── 应用代码 ──
COPY daily_stock_analysis/*.py ./
COPY daily_stock_analysis/api/ ./api/
COPY daily_stock_analysis/data_provider/ ./data_provider/
COPY daily_stock_analysis/bot/ ./bot/
COPY daily_stock_analysis/patch/ ./patch/
COPY daily_stock_analysis/src/ ./src/
COPY daily_stock_analysis/strategies/ ./strategies/
COPY daily_stock_analysis/templates/ ./templates/

# ── 前端静态资源（由阶段 1 构建，输出到 /app/static）──
COPY --from=web-builder /app/static ./static/

# ── 验证前端产物完整性 ──
RUN echo "=== Frontend static files ===" \
    && ls -la /app/static/ \
    && test -f /app/static/index.html || (echo "ERROR: index.html missing!" && exit 1) \
    && echo "Frontend static files verified OK!"

# ── Entrypoint 脚本 ──
COPY daily_stock_analysis/docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# ── AlphaSift 选股适配器（可选，安装失败不影响核心功能）──
RUN ALPHASIFT_INSTALL_SPEC="$(python -c 'from src.config import DEFAULT_ALPHASIFT_INSTALL_SPEC; print(DEFAULT_ALPHASIFT_INSTALL_SPEC)')" \
    && test -n "$ALPHASIFT_INSTALL_SPEC" \
    && python -m pip install --no-cache-dir "$ALPHASIFT_INSTALL_SPEC" \
    && python -c "import alphasift.dsa_adapter" \
    || echo "WARNING: AlphaSift installation skipped. The app will still work."

# ── 运行时目录 & 权限 ──
# efinance 库会在 ../data 目录下写入缓存文件，需确保 dsa 用户可写
# 使用 chmod a+rwX（而非仅 chown）确保即使 owner 被 volume mount 覆盖也可写
RUN mkdir -p /app/data /app/logs /app/reports && \
    mkdir -p /usr/local/lib/python3.11/site-packages/efinance/data /usr/local/lib/python3.11/site-packages/efinance/config && \
    chown -R dsa:dsa /app && \
    chown -R dsa:dsa /usr/local/lib/python3.11/site-packages/efinance && \
    chmod -R a+rwX /usr/local/lib/python3.11/site-packages/efinance && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

# ── 环境变量 ──
ENV PYTHONUNBUFFERED=1
ENV LOG_DIR=/app/logs
ENV DATABASE_PATH=/app/data/stock_analysis.db
ENV WEBUI_HOST=0.0.0.0
ENV API_PORT=8000
# 禁用 LiteLLM 远程模型价格表获取（避免 GitHub raw 超时）
ENV LITELLM_LOCAL_COST_MAP=true

# ── 数据卷 ──
VOLUME ["/app/data", "/app/logs", "/app/reports"]

EXPOSE 8000

# Health check 兼容两种模式：
# - server 模式（port 8000 监听） → 检查 API health
# - schedule 模式（无端口）→ 检查 Python 主进程存活
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/api/health 2>/dev/null || pgrep -f "python main.py" >/dev/null || exit 1

# ── 入口：先修复 bind mount 目录权限，再降权为 dsa 执行 ──
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# 默认：定时调度模式
CMD ["python", "main.py", "--schedule"]
