#!/usr/bin/env bash
# Build QwenPaw .deb package for Ubuntu/Debian Linux.
# Run from repo root: bash scripts/pack/build_linux.sh

set -e

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
PACK_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST="${DIST:-dist}"
DEB_DIR="${DIST}/qwenpaw-desktop-${VERSION:-dev}"
APP_NAME="QwenPaw"
BIN_NAME="qwenpaw-desktop"

# Get version from __version__.py
VERSION_FILE="${REPO_ROOT}/src/qwenpaw/__version__.py"
VERSION="$(
  sed -n 's/^__version__[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' \
    "${VERSION_FILE}" 2>/dev/null || echo "0.0.0"
)"
echo "== Building QwenPaw .deb for Linux =="
echo "Version: ${VERSION}"
echo "Repository: ${REPO_ROOT}"

# 1. Build wheel if not exists
echo "== Building wheel =="
WHEELS=("${REPO_ROOT}/dist/qwenpaw-${VERSION}-"*.whl)
if [[ ${#WHEELS[@]} -eq 0 || ! -f "${WHEELS[0]}" ]]; then
  echo "No wheel found, building..."
  bash scripts/wheel_build.sh
fi

# 2. Build PyInstaller backend
echo "== Building PyInstaller backend =="
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
  if command -v uv &>/dev/null; then
    echo "Creating venv with uv..."
    uv venv "${REPO_ROOT}/.venv"
  else
    echo "ERROR: No .venv found. Run: python -m venv .venv && .venv/bin/pip install -e .[full]"
    exit 1
  fi
fi

# Install PyInstaller
if ! "$PYTHON_BIN" -c "import PyInstaller" 2>/dev/null; then
  echo "Installing PyInstaller..."
  if command -v uv &>/dev/null; then
    uv pip install --python "$PYTHON_BIN" "pyinstaller>=6.0.0"
  else
    "$PYTHON_BIN" -m pip install "pyinstaller>=6.0.0"
  fi
fi

# Install project
echo "Installing QwenPaw..."
if command -v uv &>/dev/null; then
  uv pip install --python "$PYTHON_BIN" -e "${REPO_ROOT}[full]"
else
  "$PYTHON_BIN" -m pip install -e "${REPO_ROOT}[full]"
fi

# Fix acp namespace collision
if ! "$PYTHON_BIN" -c "from acp import Agent" 2>/dev/null; then
  echo "Fixing agent-client-protocol namespace..."
  if command -v uv &>/dev/null; then
    uv pip uninstall --python "$PYTHON_BIN" -y acp 2>/dev/null || true
    uv pip install --python "$PYTHON_BIN" agent-client-protocol
  else
    "$PYTHON_BIN" -m pip uninstall -y acp 2>/dev/null || true
    "$PYTHON_BIN" -m pip install agent-client-protocol
  fi
fi

# Build with PyInstaller
echo "Running PyInstaller..."
SPEC_FILE="${REPO_ROOT}/scripts/pack-tauri/qwenpaw.spec"
BACKEND_DIR="${DIST}/pyinstaller/qwenpaw-backend"

"$PYTHON_BIN" -m PyInstaller "$SPEC_FILE" \
  --distpath "${DIST}/pyinstaller" \
  --workpath "${DIST}/pyinstaller-build" \
  --clean \
  --noconfirm

if [ ! -f "${BACKEND_DIR}/qwenpaw-backend" ]; then
  echo "ERROR: Backend build failed"
  exit 1
fi

echo "Backend built: ${BACKEND_DIR}"

# 3. Create deb package structure
echo "== Creating deb package =="
rm -rf "${DEB_DIR}"
mkdir -p "${DEB_DIR}/usr/bin"
mkdir -p "${DEB_DIR}/usr/lib/${APP_NAME}"
mkdir -p "${DEB_DIR}/usr/share/applications"
mkdir -p "${DEB_DIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${DEB_DIR}/usr/share/doc/${APP_NAME}"
mkdir -p "${DEB_DIR}/DEBIAN"

# Copy backend
cp -r "${BACKEND_DIR}/." "${DEB_DIR}/usr/lib/${APP_NAME}/"
chmod +x "${DEB_DIR}/usr/lib/${APP_NAME}/qwenpaw-backend"
chmod +x "${DEB_DIR}/usr/lib/${APP_NAME}/qwenpaw-desktop"

# Create launcher script
cat > "${DEB_DIR}/usr/bin/${BIN_NAME}" << 'LAUNCHER'
#!/bin/bash
# QwenPaw Desktop launcher

APP_DIR="/usr/lib/QwenPaw"
DESKTOP="$APP_DIR/qwenpaw-desktop"
export QWENPAW_DESKTOP_APP=1

# Set SSL certs from certifi (bundled with PyInstaller)
CERT_DIR="$APP_DIR/_internal/certifi"
if [ -f "$CERT_DIR/cacert.pem" ]; then
  export SSL_CERT_FILE="$CERT_DIR/cacert.pem"
  export REQUESTS_CA_BUNDLE="$CERT_DIR/cacert.pem"
  export CURL_CA_BUNDLE="$CERT_DIR/cacert.pem"
fi

LOG_LEVEL="${QWENPAW_LOG_LEVEL:-info}"

# Init config if needed
if [ ! -f "$HOME/.qwenpaw/config.json" ]; then
  "$APP_DIR/qwenpaw-backend" -m qwenpaw init --defaults --accept-security 2>/dev/null || true
fi

cd "$HOME" || true
exec "$DESKTOP" --log-level "$LOG_LEVEL" "$@"
LAUNCHER
chmod +x "${DEB_DIR}/usr/bin/${BIN_NAME}"

# Copy icon
if [ -f "${PACK_DIR}/assets/icon.png" ]; then
  cp "${PACK_DIR}/assets/icon.png" "${DEB_DIR}/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png"
fi

# Create .desktop file
cat > "${DEB_DIR}/usr/share/applications/${APP_NAME}.desktop" << DESKTOP
[Desktop Entry]
Version=${VERSION}
Name=${APP_NAME}
Comment=Personal AI Assistant
Exec=${BIN_NAME} %U
Icon=/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png
Type=Application
Terminal=false
Categories=Network;Chat;Assistant;
StartupWMClass=QwenPaw
DESKTOP

# Create DEBIAN/control
cat > "${DEB_DIR}/DEBIAN/control" << CONTROL
Package: qwenpaw
Version: ${VERSION}
Section: net
Priority: optional
Architecture: amd64
Depends: libwebkit2gtk-4.1-0, libgtk-3-0, libsecret-1-0, libappindicator3-1, libnotify4
Installed-Size: $(du -sk "${DEB_DIR}/usr" | cut -f1)
Maintainer: QwenPaw Contributors
Description: Personal AI Assistant with multi-channel support
 QwenPaw is a personal AI assistant that runs in your own environment.
 It talks to you over multiple channels and runs scheduled tasks.
CONTROL

# Create postinst
cat > "${DEB_DIR}/DEBIAN/postinst" << POSTINST
#!/bin/bash
# Post-installation script
if command -v update-desktop-database &>/dev/null; then
  update-desktop-database /usr/share/applications 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
  gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
fi
POSTINST
chmod +x "${DEB_DIR}/DEBIAN/postinst"

# Create prerm
cat > "${DEB_DIR}/DEBIAN/prerm" << PRERM
#!/bin/bash
# Pre-removal script
PRERM
chmod +x "${DEB_DIR}/DEBIAN/prerm"

# Create copyright (placeholder)
cat > "${DEB_DIR}/usr/share/doc/${APP_NAME}/copyright" << COPYRIGHT
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Files: *
Copyright: $(date +%Y) QwenPaw Contributors
License: Apache-2.0
 See /usr/share/licenses/${APP_NAME}/LICENSE or https://www.apache.org/licenses/LICENSE-2.0
COPYRIGHT

# 4. Build .deb
echo "== Building .deb =="
DEB_OUTPUT="${DIST}/${APP_NAME}-${VERSION}-linux-amd64.deb"

# Set ownership to root for files (required for deb)
find "${DEB_DIR}" -exec chown root:root {} \; 2>/dev/null || true

dpkg-deb --build "${DEB_DIR}" "${DEB_OUTPUT}"

echo "== Built ${DEB_OUTPUT} =="
echo "Size: $(du -h "${DEB_OUTPUT}" | cut -f1)"
echo ""
echo "To install:"
echo "  sudo dpkg -i ${DEB_OUTPUT}"
echo "  # or"
echo "  sudo apt install ./${DEB_OUTPUT}"
echo ""
echo "To uninstall:"
echo "  sudo dpkg -r qwenpaw"