#!/bin/bash
# Build the SDK into ./sdk/ using the dedicated stage scripts:
#   1. build-and-install-cpp.sh    — C/C++ libraries
#   2. build-and-install-bindings.sh — Python bindings (nanobind)
#   3. build-and-install-csharp.sh  — C# bindings
#
# To install pip packages into your Python environment, run separately:
#   ./install-pip-packages.sh

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
echo "  Stage 2/3: Python bindings (nanobind)"
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
