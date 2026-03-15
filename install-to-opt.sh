#!/bin/bash
# Copy locally built SDK to /opt/termin and create system integration.
#
# Usage:
#   sudo ./install-to-opt.sh           # Install from ./sdk to /opt/termin
#   sudo ./install-to-opt.sh --remove  # Uninstall

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_DIR="$SCRIPT_DIR/sdk"
INSTALL_PREFIX="/opt/termin"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "This script must be run as root (sudo)."
    exit 1
fi

case "${1:-}" in
    --remove|--uninstall|-r)
        echo "Removing /opt/termin..."
        rm -f /usr/local/bin/termin /usr/local/bin/termin_editor
        rm -f /usr/share/applications/termin.desktop
        rm -rf "$INSTALL_PREFIX"
        echo "Done."
        exit 0
        ;;
esac

if [[ ! -d "$SDK_DIR" ]]; then
    echo "SDK directory not found: $SDK_DIR"
    echo "Run build-and-install-cpp.sh and/or build-and-install-bindings.sh first."
    exit 1
fi

echo "Installing SDK from $SDK_DIR to $INSTALL_PREFIX..."
mkdir -p "$INSTALL_PREFIX"
rsync -a --delete "$SDK_DIR/" "$INSTALL_PREFIX/"

# Symlinks
ln -sf "$INSTALL_PREFIX/bin/termin_launcher" /usr/local/bin/termin 2>/dev/null || true
ln -sf "$INSTALL_PREFIX/bin/termin_editor" /usr/local/bin/termin_editor 2>/dev/null || true

# Desktop file
cat > /usr/share/applications/termin.desktop << DESKTOP
[Desktop Entry]
Name=Termin
Comment=3D Engine and Editor
Exec=/opt/termin/bin/termin_launcher %F
Terminal=false
Type=Application
Categories=Development;Graphics;3DGraphics;
Keywords=3d;editor;engine;cad;
DESKTOP

echo "Done. SDK installed to $INSTALL_PREFIX"
