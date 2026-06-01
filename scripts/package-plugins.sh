#!/usr/bin/env bash
# -*- coding: utf-8 -*-
#
# package-plugins.sh — 打包 plugins/tool/ 和 plugins/bundle/ 下所有插件为 zip
#
# 用法:
#   bash scripts/package-plugins.sh                    # 输出到 dist/plugins/
#   bash scripts/package-plugins.sh -o /tmp/plugins     # 指定输出目录
#   bash scripts/package-plugins.sh -s github-trending  # 只打包指定插件
#
# 做了什么:
#   1. 检查前端是否需要构建 (package.json 存在就 npm install + vite build)
#   2. 清理 __pycache__ / *.pyc / node_modules / .venv / .git / *.db
#   3. 以插件目录名为根打包为 <plugin_id>.zip

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGINS_DIR="$REPO_ROOT/plugins"
OUTPUT_DIR="$REPO_ROOT/dist/plugins"
SINGLE_PLUGIN=""         # 如果指定了 -s，只打包这一个
NO_BUILD=false           # -n 跳过前端构建

# ── 解析参数 ──────────────────────────────────────────────────────────

while getopts "o:s:nh" opt; do
  case $opt in
    o) OUTPUT_DIR="$OPTARG" ;;
    s) SINGLE_PLUGIN="$OPTARG" ;;
    n) NO_BUILD=true ;;
    h)
      echo "用法: bash scripts/package-plugins.sh [-o 输出目录] [-s 插件名] [-n]"
      echo "  -o  输出目录（默认 dist/plugins/）"
      echo "  -s  只打包指定插件（按目录名匹配，如 github-trending）"
      echo "  -n  跳过前端构建（npm install && build）"
      exit 0
      ;;
    *) echo "未知参数: -$OPTARG" >&2; exit 1 ;;
  esac
done

mkdir -p "$OUTPUT_DIR"

# ── 工具函数 ──────────────────────────────────────────────────────────

# 清理目录中的脏文件（原地）
clean_dir() {
  local dir="$1"
  find "$dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
  find "$dir" -type f -name "*.pyc" -delete 2>/dev/null || true
  find "$dir" -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
  find "$dir" -type d -name ".venv" -exec rm -rf {} + 2>/dev/null || true
  find "$dir" -type d -name ".git" -exec rm -rf {} + 2>/dev/null || true
  find "$dir" -type f -name "*.db" -delete 2>/dev/null || true
  find "$dir" -type f -name ".DS_Store" -delete 2>/dev/null || true
  # 清理可能残留的 lock 文件、uv 缓存
  find "$dir" -type f -name "uv.lock" -delete 2>/dev/null || true
  find "$dir" -type f -name "CACHEDIR.TAG" -delete 2>/dev/null || true
  find "$dir" -type f -name ".gitignore" -delete 2>/dev/null || true
}

# 构建插件前端（如果有 frontend/ 目录）
build_frontend() {
  local plugin_dir="$1"
  local frontend_dir="$plugin_dir/frontend"

  if [[ ! -d "$frontend_dir" ]] || [[ ! -f "$frontend_dir/package.json" ]]; then
    return 0   # 无前端，跳过
  fi

  echo "  📦 构建前端..."

  pushd "$frontend_dir" > /dev/null

  # 安装依赖
  if [[ -f "package-lock.json" ]]; then
    npm ci --silent 2>&1 | tail -1 || npm install --silent 2>&1 | tail -1
  else
    npm install --silent 2>&1 | tail -1
  fi

  # 执行构建
  if npm run build --if-present 2>&1; then
    echo "  ✅ 前端构建完成"
  else
    # 回退: 直接调 vite（某些插件的 package.json 没定义 build 脚本）
    echo "  ⚠️  npm run build 未定义，直接用 npx vite build"
    npx vite build 2>&1 || {
      echo "  ❌ 前端构建失败" >&2
      popd > /dev/null
      return 1
    }
    echo "  ✅ vite build 完成"
  fi

  popd > /dev/null
}

# 打包单个插件
package_plugin() {
  local plugin_dir="$1"
  local plugin_name
  plugin_name="$(basename "$plugin_dir")"

  # 检查 plugin.json
  if [[ ! -f "$plugin_dir/plugin.json" ]]; then
    echo "  ⚠️  跳过: 没有 plugin.json"
    return 0
  fi

  local plugin_id
  plugin_id="$(python3 -c "import json; print(json.load(open('$plugin_dir/plugin.json'))['id'])" 2>/dev/null || echo "$plugin_name")"

  echo ""
  echo "═══════════════════════════════════════════════════"
  echo "📦 打包: $plugin_name  (id=$plugin_id)"
  echo "═══════════════════════════════════════════════════"

  # 1. 构建前端（如果需要且未跳过）
  if [[ "$NO_BUILD" != "true" ]]; then
    build_frontend "$plugin_dir" || return 1
  fi

  # 2. 清理脏文件
  echo "  🧹 清理脏文件..."
  clean_dir "$plugin_dir"

  # 3. 创建 zip（从插件父目录打包，保持插件目录名作为根）
  local parent_dir
  parent_dir="$(dirname "$plugin_dir")"
  local zip_path="$OUTPUT_DIR/${plugin_id}.zip"

  echo "  📦 压缩为 $zip_path"

  # 使用 Python 的 zipfile 获得跨平台一致性和更好的排除控制
  python3 -c "
import zipfile, os, sys
from pathlib import Path

plugin_dir = Path('$plugin_dir')
zip_path = Path('$zip_path')
zip_path.parent.mkdir(parents=True, exist_ok=True)

# 需要排除的模式
exclude_patterns = {'.venv', '__pycache__', 'node_modules', '.git'}

file_count = 0
with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(plugin_dir.rglob('*')):
        if f.is_dir():
            continue
        # 检查是否有需要排除的父目录
        parts = set(f.relative_to(plugin_dir.parent).parts)
        if parts & exclude_patterns:
            continue
        # 单独排除 .pyc 文件
        if f.suffix == '.pyc':
            continue
        # 单独排除 .db 文件
        if f.suffix == '.db':
            continue
        # 排除 .DS_Store
        if f.name == '.DS_Store':
            continue
        # arcname = 相对于插件父目录的路径 → zip 内为 plugin_name/xxx
        arcname = str(f.relative_to(plugin_dir.parent))
        zf.write(str(f), arcname)
        file_count += 1

# 验证 zip 内 plugin.json 可访问
with zipfile.ZipFile(str(zip_path), 'r') as zf:
    names = zf.namelist()
    has_manifest = any('plugin.json' in n for n in names)

if not has_manifest:
    print(f'❌ 错误: zip 内未找到 plugin.json！', file=sys.stderr)
    sys.exit(1)

size_mb = zip_path.stat().st_size / (1024*1024)
print(f'  ✅ 完成: {file_count} 个文件, {size_mb:.1f} MB')
" 2>&1 || {
    echo "  ❌ 打包失败" >&2
    return 1
  }
}

# ── 主流程 ────────────────────────────────────────────────────────────

echo "╔══════════════════════════════════════════════════╗"
echo "║     QwenPaw 插件打包脚本                          ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  输出目录: $OUTPUT_DIR"
echo "╚══════════════════════════════════════════════════╝"

# 收集所有插件目录
PLUGIN_DIRS=()

if [[ -n "$SINGLE_PLUGIN" ]]; then
  # 在 tool/ 和 bundle/ 下查找
  for category in tool bundle; do
    dir="$PLUGINS_DIR/$category/$SINGLE_PLUGIN"
    if [[ -d "$dir" ]] && [[ -f "$dir/plugin.json" ]]; then
      PLUGIN_DIRS+=("$dir")
      break
    fi
  done
  if [[ ${#PLUGIN_DIRS[@]} -eq 0 ]]; then
    echo "❌ 未找到插件: $SINGLE_PLUGIN" >&2
    echo "   已检查: plugins/tool/$SINGLE_PLUGIN, plugins/bundle/$SINGLE_PLUGIN"
    exit 1
  fi
else
  for category in tool bundle; do
    if [[ -d "$PLUGINS_DIR/$category" ]]; then
      for dir in "$PLUGINS_DIR/$category"/*/; do
        PLUGIN_DIRS+=("${dir%/}")
      done
    fi
  done
fi

echo "找到 ${#PLUGIN_DIRS[@]} 个插件"
echo ""

FAILED=()
SUCCESS=()

for plugin_dir in "${PLUGIN_DIRS[@]}"; do
  if package_plugin "$plugin_dir"; then
    SUCCESS+=("$(basename "$plugin_dir")")
  else
    FAILED+=("$(basename "$plugin_dir")")
  fi
done

# ── 汇总 ──────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  打包完成                                        ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  成功: ${#SUCCESS[@]} 个"
echo "║  失败: ${#FAILED[@]} 个"
echo "║  输出: $OUTPUT_DIR"
echo "╚══════════════════════════════════════════════════╝"

if [[ ${#SUCCESS[@]} -gt 0 ]]; then
  echo ""
  echo "✅ 打包成功的插件:"
  for p in "${SUCCESS[@]}"; do
    zip_file="$OUTPUT_DIR/${p}.zip"
    size="$(du -h "$zip_file" 2>/dev/null | cut -f1 || echo '?')"
    echo "   $p.zip  ($size)"
  done
fi

if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo ""
  echo "❌ 打包失败的插件:"
  for p in "${FAILED[@]}"; do
    echo "   $p"
  done
  exit 1
fi
