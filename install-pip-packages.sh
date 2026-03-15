#!/bin/bash
# Install termin Python packages into the current pip environment.
# Assumes SDK is already built via build-sdk-cpp.sh + build-sdk-bindings.sh.
#
# Usage:
#   ./install-pip-packages.sh              # Install all packages
#   ./install-pip-packages.sh --editable   # Install termin in editable mode

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_PREFIX="${SDK_PREFIX:-$SCRIPT_DIR/sdk}"
EDITABLE=0

for arg in "$@"; do
    case "$arg" in
        --editable|-e) EDITABLE=1 ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --editable, -e  Install termin in editable mode"
            echo "  --help, -h      Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            exit 1
            ;;
    esac
done

install_pkg() {
    local pkg="$1"
    echo ""
    echo "========================================"
    echo "  Installing $pkg"
    echo "========================================"
    echo ""
    CMAKE_PREFIX_PATH="$SDK_PREFIX" pip install --no-build-isolation "$SCRIPT_DIR/$pkg"
}

# Build tools (needed by termin-base, termin-mesh, termin-graphics, termin-modules)
install_pkg "termin-build-tools"

# C++ packages with native bindings
for pkg in termin-base termin-modules termin-mesh termin-graphics; do
    install_pkg "$pkg"
done

# Pure Python packages
for pkg in termin-gui termin-nodegraph; do
    install_pkg "$pkg"
done

# Main termin package
echo ""
echo "========================================"
echo "  Installing termin"
echo "========================================"
echo ""
if [[ $EDITABLE -eq 1 ]]; then
    CMAKE_PREFIX_PATH="$SDK_PREFIX" pip install --no-build-isolation -e "$SCRIPT_DIR/termin"
else
    CMAKE_PREFIX_PATH="$SDK_PREFIX" pip install --no-build-isolation "$SCRIPT_DIR/termin"
fi

echo ""
echo "========================================"
echo "  All pip packages installed!"
echo "========================================"
