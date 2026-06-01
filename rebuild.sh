#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

echo "=== 1/2: 编译 Python Backend ==="
bash scripts/pack-tauri/build_pyinstaller.sh

echo ""
echo "=== 2/2: 打包 Tauri ==="
cd console/src-tauri
npx @tauri-apps/cli build

echo ""
echo "=== 完成 ==="
ls -lh target/release/bundle/deb/QwenPaw\ Desktop_*.deb
