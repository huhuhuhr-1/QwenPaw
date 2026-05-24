#!/usr/bin/env bash
# QwenPaw Ubuntu/Debian 系统依赖安装脚本
# 运行前请使用 sudo 或以 root 身份运行
set -e

echo "[qwenpaw] 安装系统依赖..."

apt-get update

# QwenPaw 运行基础依赖
BASE_PKGS=(
    curl
    python3
    python3-pip
    python3-venv
    build-essential
    libssl-dev
    git
    supervisor
    vim
    gettext-base
    xvfb
    dbus-x11
    fonts-wqy-zenhei
    fonts-wqy-microhei
)

# Chromium 浏览器（browser skill 和桌面自动化需要）
CHROMIUM_PKGS=(
    chromium
    chromium-sandbox
    libx11-xcb1
    libxcomposite1
    libxdamage1
    libxext6
    libxfixes3
    libxi6
    libxtst6
    libnss3
    libglib2.0-0
    libdrm2
    libgbm1
    libasound2
    fonts-liberation
    libu2f-udev
)

echo "[qwenpaw] 安装基础依赖..."
apt-get install -y --fix-missing "${BASE_PKGS[@]}"

echo "[qwenpaw] 安装 Chromium 及相关库..."
apt-get install -y --fix-missing "${CHROMIUM_PKGS[@]}"

# Chromium --no-sandbox（容器内运行需要）
if command -v chromium &>/dev/null; then
    sed -i 's/^CHROMIUM_FLAGS=""/CHROMIUM_FLAGS="--no-sandbox"/' /usr/bin/chromium
    echo "[qwenpaw] Chromium 已配置 --no-sandbox"
fi

echo "[qwenpaw] 系统依赖安装完成"
echo ""
echo "后续步骤："
echo "  1. 克隆仓库: git clone https://github.com/agentscope-ai/QwenPaw.git"
echo "  2. 进入目录: cd QwenPaw"
echo "  3. 安装前端: cd console && npm ci && npm run build && cd .."
echo "  4. 复制前端: mkdir -p src/qwenpaw/console && cp -R console/dist/. src/qwenpaw/console/"
echo "  5. 安装 Python 包: pip install -e \".[dev,full]\""
echo "  6. 初始化: qwenpaw init --defaults"
echo "  7. 启动: qwenpaw app"