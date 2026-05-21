#!/bin/bash
# 前端开发环境设置脚本

set -e

PROJECT_DIR="/Users/lizhiwei/project/code/stock/daily-stock-analysis/daily_stock_analysis/apps/dsa-web"

echo "=== 前端开发环境设置 ==="

# 1. 加载 nvm 并切换到 Node 20
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    echo "Loading nvm..."
    . "$NVM_DIR/nvm.sh"
    nvm use 20
else
    echo "Error: nvm not found at $NVM_DIR"
    exit 1
fi

# 2. 验证 Node 版本
NODE_VERSION=$(node -v)
echo "Node version: $NODE_VERSION"

if [[ ! "$NODE_VERSION" =~ ^v20 ]]; then
    echo "Error: Expected Node.js v20.x, but got $NODE_VERSION"
    echo "Please run: source ~/.zshrc && nvm use 20"
    exit 1
fi

# 3. 进入项目目录
cd "$PROJECT_DIR"

# 4. 检查并安装依赖
if [ ! -d "node_modules" ]; then
    echo "node_modules not found, installing dependencies..."
    npm install
else
    echo "node_modules exists, checking for required packages..."
fi

# 5. 检查关键包
for pkg in "vitest" "@vitejs/plugin-react"; do
    if [ ! -d "node_modules/$pkg" ]; then
        echo "Package $pkg not found, reinstalling..."
        npm install
        break
    fi
done

# 6. 运行类型检查
echo ""
echo "=== Running TypeScript type check ==="
npx tsc --noEmit

echo ""
echo "=== Running tests ==="
npm run test

echo ""
echo "=== Build check ==="
npm run build

echo ""
echo "=== All checks passed! ==="
