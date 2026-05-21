#!/bin/bash
# 使用 nvm Node.js 20 运行前端测试

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# 使用 nvm 的 Node 20
NODE_PATH="$NVM_DIR/versions/node/v20.20.2/bin"
export PATH="$NODE_PATH:$PATH"

# 验证版本
echo "Node version: $(node -v)"
echo "npm version: $(npm -v)"

# 运行测试
npm run test
