# A股自选股智能分析系统 — 部署指南

Docker Compose 构建 + Cloudflare Tunnel 公网发布，全程免费。

---

## 前置条件

| 项目 | 状态 |
|------|------|
| Docker Desktop（已安装） | ✅ |
| cloudflared（已安装） | ✅ |
| Cloudflare 账号 + 域名托管 | ✅ |
| Tunnel `stock-analysis` 已创建 | ✅  `cb0f91b2-67fa-44a2-b2c1-f03820f8eeb8` |

---

## 一、Docker Compose 构建启动

```bash
cd /Users/lizhiwei/project/code/stock/daily-stock-analysis/daily_stock_analysis

# 构建镜像 + 后台启动 API 服务（首次约 5-10 分钟）
docker compose -f docker/docker-compose.yml up -d --build server
```

### 验证

```bash
# 查看状态
docker compose -f docker/docker-compose.yml ps

# 查看日志
docker compose -f docker/docker-compose.yml logs -f server

# 本地访问
curl http://localhost:8000/api/health
```

### 常用命令

```bash
# 重启
docker compose -f docker/docker-compose.yml restart server

# 停止
docker compose -f docker/docker-compose.yml down

# 重新构建（代码变更后）
docker compose -f docker/docker-compose.yml up -d --build server

# 同时启动定时分析 + API
docker compose -f docker/docker-compose.yml up -d --build
```

---

## 二、Cloudflare DNS 配置（手动）

> 命令行 `cloudflared tunnel route dns` 报认证错误，直接去网页操作更稳。

### 第 1 步：Cloudflare → 添加 DNS 记录

```
Cloudflare 后台 → 你的域名 → DNS → Records → Add record

类型:   CNAME
名称:   api          （将生成 api.你的域名.eu.cc）
目标:   cb0f91b2-67fa-44a2-b2c1-f03820f8eeb8.cfargotunnel.com
代理:   开启（橙色云朵）
TTL:    Auto
```

保存后等待 1-2 分钟生效。

---

## 三、启动 Cloudflare Tunnel

```bash
# 启动 tunnel（前台运行，Ctrl+C 停止）
cloudflared tunnel run stock-analysis
```

---

## 四、设为开机自启（推荐）

```bash
# 安装为系统服务，电脑开机自动启动
sudo cloudflared service install

# 安装后 Tunnel 会后台自动运行，无需手动启动
```

### 管理服务

```bash
sudo launchctl list | grep cloudflared    # 查看状态
sudo launchctl stop com.cloudflare.cloudflared    # 停止
sudo launchctl start com.cloudflare.cloudflared   # 启动
```

---

## 五、验证

| 地址 | 说明 |
|------|------|
| `http://localhost:8000` | 本地访问 |
| `https://api.你的域名.eu.cc` | 公网访问 |
| `https://api.你的域名.eu.cc/docs` | API 文档 |
| `https://api.你的域名.eu.cc/api/health` | 健康检查 |

---

## 整体架构

```
浏览器 ──HTTPS──> Cloudflare CDN ──Tunnel──> 本地 Docker 容器
               (证书/缓存/DDoS防护)              (stock-server:8000)
```
