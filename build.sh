#!/bin/bash
# Termin build script
# Usage:
#   ./build.sh          # Release build
#   ./build.sh --debug  # Debug build
#   ./build.sh --asan   # Debug build with AddressSanitizer
#   ./build.sh --clean  # Clean and rebuild
#   ./build.sh --install-only  # Only install (skip build)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build_standalone"
INSTALL_DIR="$SCRIPT_DIR/install"

BUILD_TYPE="Release"
CLEAN=0
INSTALL_ONLY=0
ASAN=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --debug|-d)
            BUILD_TYPE="Debug"
            shift
            ;;
        --asan|-a)
            BUILD_TYPE="Debug"
            ASAN=1
            shift
            ;;
        --clean|-c)
            CLEAN=1
            shift
            ;;
        --install-only|-i)
            INSTALL_ONLY=1
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --debug, -d        Build with debug symbols"
            echo "  --asan, -a         Build with AddressSanitizer (implies --debug)"
            echo "  --clean, -c        Clean build directory before building"
            echo "  --install-only, -i Skip build, only run install"
            echo "  --help, -h         Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=== Termin Build Script ==="
echo "Build type: $BUILD_TYPE"
if [[ $ASAN -eq 1 ]]; then
    echo "AddressSanitizer: ON"
fi
echo "Build dir:  $BUILD_DIR"
echo "Install dir: $INSTALL_DIR"
echo ""

# Clean if requested
if [[ $CLEAN -eq 1 ]]; then
    echo "Cleaning build directories..."
    rm -rf "$BUILD_DIR" "$INSTALL_DIR"
fi

# Create build directory
mkdir -p "$BUILD_DIR"

# Configure
if [[ ! -f "$BUILD_DIR/CMakeCache.txt" ]] || [[ $CLEAN -eq 1 ]]; then
    echo "Configuring CMake..."

    if [[ $ASAN -eq 1 ]]; then
        ASAN_FLAGS="-fsanitize=address -fno-omit-frame-pointer"
        cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" \
            -DBUILD_EDITOR_MINIMAL=ON \
            -DBUNDLE_PYTHON=ON \
            -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
            -DCMAKE_C_FLAGS="$ASAN_FLAGS" \
            -DCMAKE_CXX_FLAGS="$ASAN_FLAGS" \
            -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address" \
            -DCMAKE_SHARED_LINKER_FLAGS="-fsanitize=address"
    else
        cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" \
            -DBUILD_EDITOR_MINIMAL=ON \
            -DBUNDLE_PYTHON=ON \
            -DCMAKE_BUILD_TYPE="$BUILD_TYPE"
    fi
fi

# Build
if [[ $INSTALL_ONLY -eq 0 ]]; then
    echo "Building..."
    cmake --build "$BUILD_DIR" --parallel
fi

# Install
echo "Installing..."
rm -rf "$INSTALL_DIR"
cmake --install "$BUILD_DIR"

echo ""
echo "=== Build complete ==="
echo ""
echo "To run:"
echo "  cd $INSTALL_DIR && LD_LIBRARY_PATH=./lib ./bin/termin_editor"
echo ""
echo "Or use the run script:"
echo "  ./run.sh"
