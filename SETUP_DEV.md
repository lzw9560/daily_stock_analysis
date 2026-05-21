# A股自选股智能分析系统 - 开发环境配置指南

## 📋 目录

1. [Python 后端环境](#1-python-后端环境)
2. [Node.js 前端环境](#2-nodejs-前端环境)
3. [数据库初始化](#3-数据库初始化)
4. [启动服务](#4-启动服务)
5. [验证运行](#5-验证运行)

---

## 1. Python 后端环境

### 1.1 检查 Python 版本

```bash
python3 --version
# 要求：Python 3.10+

# 如果版本过低，使用 pyenv 或 conda 升级
# macOS: brew install pyenv && pyenv install 3.11.8
# Linux: pyenv install 3.11.8
```

### 1.2 创建虚拟环境（推荐）

```bash
cd daily_stock_analysis

# 使用 venv
python3 -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate

# Windows:
# venv\Scripts\activate
```

### 1.3 安装后端依赖

```bash
pip install -r requirements.txt
```

### 1.4 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，配置必要的 API Key
vim .env
```

**必填配置：**
```env
# 自选股列表（至少配置一个）
STOCK_LIST=600519,300750,002594

# AI 模型（至少配置一个）
# 推荐 AIHubMix（国内可用）：
AIHUBMIX_KEY=your_key_here

# 或使用 DeepSeek：
# DEEPSEEK_API_KEY=your_key_here
```

**可选配置（推荐配置以获得完整功能）：**
```env
# 新闻搜索（至少配置一个）
TAVILY_API_KEYS=your_tavily_key
ANSPIRE_API_KEYS=your_anspire_key

# 通知渠道（根据需要配置）
# WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
# TELEGRAM_BOT_TOKEN=xxx
# TELEGRAM_CHAT_ID=xxx
```

---

## 2. Node.js 前端环境

### 2.1 检查 Node.js 版本

```bash
node --version
# 要求：Node.js 18+

# 如果版本过低，使用 nvm 升级
# nvm install 20 && nvm use 20
```

### 2.2 安装前端依赖

```bash
cd apps/dsa-web

# 安装依赖
npm install

# 如果网络慢，可使用淘宝镜像
# npm install --registry=https://registry.npmmirror.com
```

### 2.3 构建前端（可选，手动构建）

```bash
npm run build
```

---

## 3. 数据库初始化

数据库使用 SQLite，会在首次运行时自动创建。

数据目录：
```bash
# 默认数据库位置
ls -la data/stock_analysis.db
```

---

## 4. 启动服务

### 4.1 方式一：启动完整服务（推荐）

```bash
# 返回项目根目录
cd ../..

# 启动 WebUI + 自动构建前端
python main.py --webui

# 或使用简写
python main.py --serve
```

**启动时自动执行：**
1. 检查前端是否已构建
2. 如未构建，自动执行 `npm install && npm run build`
3. 启动 FastAPI 后端服务
4. 打开浏览器访问 http://127.0.0.1:8000

### 4.2 方式二：仅启动 Web 界面

```bash
# 仅启动 Web，不执行定时分析
python main.py --webui-only
```

### 4.3 方式三：开发模式

分别启动前后端：

```bash
# 终端 1: 启动后端
python main.py --webui-only

# 终端 2: 启动前端开发服务器（热更新）
cd apps/dsa-web
npm run dev
```

---

## 5. 验证运行

### 5.1 检查服务状态

启动后，终端显示：
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 5.2 访问 Web 界面

打开浏览器访问：
- **Web UI**: http://127.0.0.1:8000
- **API 文档**: http://127.0.0.1:8000/docs

### 5.3 常见问题排查

**问题 1：端口被占用**
```bash
# 查找占用端口的进程
lsof -i :8000

# 或修改端口
# 在 .env 中设置：WEBUI_PORT=8001
```

**问题 2：前端构建失败**
```bash
cd apps/dsa-web
npm install
npm run build
```

**问题 3：Python 依赖安装失败**
```bash
# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**问题 4：数据库锁定**
```bash
# 在 .env 中配置
SQLITE_BUSY_TIMEOUT_MS=10000
```

---

## 📚 常用命令

| 命令 | 说明 |
|------|------|
| `python main.py --webui` | 启动完整服务（含分析） |
| `python main.py --webui-only` | 仅启动 Web 界面 |
| `python main.py --debug` | 调试模式启动 |
| `python main.py --dry-run` | 仅获取数据不分析 |
| `npm run dev` | 前端开发服务器 |
| `npm run build` | 构建前端生产版本 |

---

## 🔧 进阶配置

### 配置定时任务

```env
SCHEDULE_ENABLED=true
SCHEDULE_TIME=18:00
```

### 配置 Agent 模式

```env
AGENT_MODE=true
```

### 配置 Web 登录认证

```env
ADMIN_AUTH_ENABLED=true
```

---

## 📞 获取帮助

- 完整文档：[docs/full-guide.md](docs/full-guide.md)
- 常见问题：[docs/FAQ.md](docs/FAQ.md)
- API 规范：[docs/architecture/api_spec.json](docs/architecture/api_spec.json)
