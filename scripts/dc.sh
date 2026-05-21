#!/bin/bash
# Docker Compose 快捷命令 (V2)

export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
export COMPOSE_FILE="/Users/lizhiwei/project/code/stock/daily-stock-analysis/daily_stock_analysis/docker/docker-compose.yml"

cd /Users/lizhiwei/project/code/stock/daily-stock-analysis/daily_stock_analysis

case "$1" in
  build)   docker compose -f "$COMPOSE_FILE" build ;;
  start)   docker compose -f "$COMPOSE_FILE" up -d ;;
  stop)    docker compose -f "$COMPOSE_FILE" down ;;
  restart) docker compose -f "$COMPOSE_FILE" restart ;;
  logs)    docker compose -f "$COMPOSE_FILE" logs -f ;;
  ps)      docker compose -f "$COMPOSE_FILE" ps ;;
  rebuild) docker compose -f "$COMPOSE_FILE" build --no-cache && docker compose -f "$COMPOSE_FILE" up -d ;;
  *)       echo "Usage: $0 {build|start|stop|restart|logs|ps|rebuild}" ;;
esac
