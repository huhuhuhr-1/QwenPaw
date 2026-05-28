#!/usr/bin/env bash
# Build QwenPaw Ubuntu/Debian desktop client (deb package)
# Combines frontend + PyInstaller + Tauri build
#
# Usage:
#   ./scripts/pack-tauri/build-deb.sh
#
# Prerequisites:
#   - Node.js 18+
#   - Python 3.10+ with virtual environment
#   - Rust toolchain
#   - System deps: libdbus-1-dev, libglib2.0-dev, libgtk-3-dev, libwebkit2gtk-4.1-dev

set -e

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

echo "========================================="
echo "QwenPaw Ubuntu Desktop Build"
echo "========================================="
echo "Repository: ${REPO_ROOT}"
echo ""

# Check and install system dependencies
check_system_deps() {
    echo "== Checking system dependencies =="

    local deps=(
        "libdbus-1-dev"
        "libglib2.0-dev"
        "libgtk-3-dev"
        "libwebkit2gtk-4.1-dev"
        "pkg-config"
    )

    local missing=()
    for dep in "${deps[@]}"; do
        if ! dpkg -l "$dep" &>/dev/null; then
            missing+=("$dep")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        echo "Missing dependencies: ${missing[*]}"
        echo "Installing..."
        sudo apt update
        sudo apt install -y "${missing[@]}"
    else
        echo "All system dependencies installed"
    fi
    echo ""
}

# Build frontend
build_frontend() {
    echo "== Building frontend =="
    cd "${REPO_ROOT}/console"
    npm run build:tauri-bootstrap
    echo "Frontend built: console/dist-tauri/"
    echo ""
}

# Build PyInstaller backend
build_backend() {
    echo "== Building PyInstaller backend =="
    bash "${REPO_ROOT}/scripts/pack-tauri/build_pyinstaller.sh"
    echo ""
}

# Build Tauri app
build_tauri() {
    echo "== Building Tauri app =="
    cd "${REPO_ROOT}/console/src-tauri"
    npx @tauri-apps/cli build
    echo ""
}

# Main
check_system_deps
build_frontend
build_backend
build_tauri

echo "========================================="
echo "Build Complete!"
echo "========================================="
echo "deb package: console/src-tauri/target/release/bundle/deb/"
ls -lh "${REPO_ROOT}/console/src-tauri/target/release/bundle/deb/"*.deb 2>/dev/null || echo "No deb found"
echo ""
echo "To install:"
echo "  sudo dpkg -i /opt/github/QwenPaw/console/src-tauri/target/release/bundle/deb/QwenPaw\\ Desktop_*.deb"
