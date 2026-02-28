#!/bin/bash
# Install termin to /opt/termin and create system integration.
#
# Usage:
#   sudo ./install_system.sh            # Install
#   sudo ./install_system.sh --remove   # Uninstall
#
# What it does:
#   - Copies install/ contents to /opt/termin/
#   - Creates symlink /usr/local/bin/termin -> /opt/termin/bin/termin_editor
#   - Installs .desktop file for the application menu

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/install"
INSTALL_PREFIX="/opt/termin"
SYMLINK="/usr/local/bin/termin"
SYMLINK_EDITOR="/usr/local/bin/termin_editor"
DESKTOP_FILE="/usr/share/applications/termin.desktop"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "This script must be run as root (sudo)."
    exit 1
fi

remove() {
    echo "Removing termin system installation..."
    rm -f "$SYMLINK" "$SYMLINK_EDITOR"
    rm -f "$DESKTOP_FILE"
    rm -rf "$INSTALL_PREFIX"
    echo "Done."
}

install() {
    if [[ ! -d "$SOURCE_DIR" ]]; then
        echo "Not found: $SOURCE_DIR"
        echo "Run ./build.sh first."
        exit 1
    fi

    echo "Installing termin to $INSTALL_PREFIX..."

    # Do not wipe existing install to preserve extra bundled libs
    mkdir -p "$INSTALL_PREFIX"

    # Copy files (overwrite existing)
    cp -a "$SOURCE_DIR/." "$INSTALL_PREFIX/"

    # Create symlink
    ln -sf "$INSTALL_PREFIX/bin/termin_launcher" "$SYMLINK"
    echo "  Symlink: $SYMLINK -> $INSTALL_PREFIX/bin/termin_launcher"
    ln -sf "$INSTALL_PREFIX/bin/termin_editor" "$SYMLINK_EDITOR"
    echo "  Symlink: $SYMLINK_EDITOR -> $INSTALL_PREFIX/bin/termin_editor"

    # Install .desktop file
    cat > "$DESKTOP_FILE" << 'DESKTOP'
[Desktop Entry]
Name=Termin
Comment=3D Engine and Editor
Exec=/opt/termin/bin/termin_launcher %F
Terminal=false
Type=Application
Categories=Development;Graphics;3DGraphics;
Keywords=3d;editor;engine;cad;
DESKTOP
    echo "  Desktop file: $DESKTOP_FILE"

    echo ""
    echo "Installation complete."
    echo "  Run: termin               (launcher)"
    echo "  Run: termin_editor        (editor directly)"
    echo "  Run: termin_editor --ui=tcgui  (new UI)"
}

case "${1:-}" in
    --remove|--uninstall|-r)
        remove
        ;;
    *)
        install
        ;;
esac
