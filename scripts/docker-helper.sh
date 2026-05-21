#!/bin/bash
# Docker 快捷命令

DOCKER_BIN="/Applications/Docker.app/Contents/Resources/bin"

export PATH="$DOCKER_BIN:$PATH"

case "$1" in
    "ps")
        docker ps
        ;;
    "images")
        docker images
        ;;
    "up")
        shift
        docker compose up "$@"
        ;;
    "down")
        shift
        docker compose down "$@"
        ;;
    "build")
        shift
        docker compose build "$@"
        ;;
    "logs")
        shift
        docker compose logs "$@"
        ;;
    "restart")
        shift
        docker compose restart "$@"
        ;;
    *)
        docker "$@"
        ;;
esac
