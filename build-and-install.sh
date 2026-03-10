#!/bin/bash
# Build and install the full environment using the dedicated stage scripts:
#   1. build-and-install-cpp.sh
#   2. build-and-install-bindings.sh
#   3. build-and-install-csharp.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for arg in "$@"; do
    case "$arg" in
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --debug, -d       Debug build"
            echo "  --clean, -c       Clean build directories first"
            echo "  --no-parallel     Disable parallel compilation (equivalent to -j1)"
            echo "  --help, -h        Show this help"
            exit 0
            ;;
    esac
done

echo ""
echo "========================================"
echo "  Stage 1/2: C/C++ libraries"
echo "========================================"
echo ""
"$SCRIPT_DIR/build-and-install-cpp.sh" "$@"

echo ""
echo "========================================"
echo "  Stage 2/3: Python bindings and packages"
echo "========================================"
echo ""
"$SCRIPT_DIR/build-and-install-bindings.sh" "$@"

echo ""
echo "========================================"
echo "  Stage 3/3: C# bindings"
echo "========================================"
echo ""
bash "$SCRIPT_DIR/build-and-install-csharp.sh" "$@"

echo ""
echo "========================================"
echo "  All done!"
echo "========================================"
