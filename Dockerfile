# ============================================================
# A股自选股智能分析系统 - Dockerfile（根目录快捷入口）
# ============================================================
# 本文件为 docker/Dockerfile 的快捷入口，内容完全一致。
# 推荐使用 docker/docker-compose.yml 管理服务编排。
#
# 快速启动:
#   docker compose -f docker/docker-compose.yml up -d --build
#
# 手动构建:
#   docker build -t stock-analysis -f docker/Dockerfile .
# ============================================================

# ==================== 阶段 1：前端构建 ====================
FROM node:20-slim AS web-builder

WORKDIR /app/apps/dsa-web

COPY apps/dsa-web/package.json apps/dsa-web/package-lock.json ./
RUN npm ci --prefer-offline || npm ci

COPY apps/dsa-web/ ./
RUN npm run build \
    && echo "Frontend build complete!" \
    && test -f /app/static/index.html || (echo "ERROR: index.html missing after build!" && exit 1)

# ==================== 阶段 2：后端运行 ====================
FROM python:3.11-slim-bullseye

WORKDIR /app

ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    git \
    gosu \
    wkhtmltopdf \
    fontconfig \
    libjpeg62-turbo \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 dsa && \
    useradd -u 1000 -g dsa -m dsa

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY api/ ./api/
COPY data_provider/ ./data_provider/
COPY bot/ ./bot/
COPY patch/ ./patch/
COPY src/ ./src/
COPY strategies/ ./strategies/
COPY templates/ ./templates/

COPY --from=web-builder /app/static ./static/
RUN test -f /app/static/index.html || (echo "ERROR: index.html missing!" && exit 1)

COPY docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN ALPHASIFT_INSTALL_SPEC="$(python -c 'from src.config import DEFAULT_ALPHASIFT_INSTALL_SPEC; print(DEFAULT_ALPHASIFT_INSTALL_SPEC)')" \
    && test -n "$ALPHASIFT_INSTALL_SPEC" \
    && python -m pip install --no-cache-dir "$ALPHASIFT_INSTALL_SPEC" \
    && python -c "import alphasift.dsa_adapter" \
    || echo "WARNING: AlphaSift installation skipped."

RUN mkdir -p /app/data /app/logs /app/reports && \
    chown -R dsa:dsa /app && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV LOG_DIR=/app/logs
ENV DATABASE_PATH=/app/data/stock_analysis.db
ENV WEBUI_HOST=0.0.0.0
ENV API_PORT=8000

VOLUME ["/app/data", "/app/logs", "/app/reports"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/api/health || curl -sf http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "main.py", "--schedule"]
