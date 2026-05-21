# ============================================================
# A股自选股智能分析系统 - Dockerfile
# ============================================================
# 多阶段构建：前端打包 → 后端运行
#
# 运行模式（通过 RUN_MODE 环境变量或 CMD 覆盖）：
#   schedule  - 定时调度模式（默认），持续运行，每日定时分析
#   api       - 仅 API 服务，不执行定时分析
#   once      - 单次分析后退出
#
# 构建：
#   docker build -t stock-analysis .
#
# 运行示例：
#   docker run -d -p 8000:8000 --env-file .env stock-analysis              # 默认定时模式
#   docker run -d -p 8000:8000 --env-file .env stock-analysis api          # API 模式
#   docker run --rm --env-file .env stock-analysis once                    # 单次分析
# ============================================================

# ==================== 阶段 1：前端构建 ====================
FROM node:20-slim AS web-builder

WORKDIR /src/apps/dsa-web

COPY apps/dsa-web/package.json apps/dsa-web/package-lock.json ./
RUN npm ci --prefer-offline || npm ci

COPY apps/dsa-web/ ./
RUN npm run build

# ==================== 阶段 2：后端运行 ====================
# 使用 bullseye：wkhtmltopdf 在 bookworm 中被移除
FROM python:3.11-slim-bullseye

WORKDIR /app

# 时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    wkhtmltopdf \
    fontconfig \
    libjpeg62-turbo \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# --- Python 依赖（利用 Docker 层缓存） ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- 应用代码 ---
COPY *.py ./
COPY api/ ./api/
COPY data_provider/ ./data_provider/
COPY bot/ ./bot/
COPY patch/ ./patch/
COPY src/ ./src/
COPY strategies/ ./strategies/

# 前端静态资源
COPY --from=web-builder /src/apps/dsa-web/dist ./static/

# --- 运行时目录 ---
RUN mkdir -p /app/data /app/logs /app/reports

# --- 安全：切换到非 root 用户 ---
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# --- 环境变量 ---
ENV PYTHONUNBUFFERED=1
ENV LOG_DIR=/app/logs
ENV DATABASE_PATH=/app/data/stock_analysis.db
ENV WEBUI_HOST=0.0.0.0
ENV API_PORT=8000

VOLUME ["/app/data", "/app/logs", "/app/reports"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/api/health || curl -sf http://localhost:8000/health || exit 1

# 默认：定时调度模式
ENTRYPOINT ["python", "main.py"]
CMD ["--schedule"]
