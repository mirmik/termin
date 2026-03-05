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
ENV_DIR="$(dirname "$SCRIPT_DIR")"
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
            -DBUILD_LAUNCHER=ON \
            -DBUNDLE_PYTHON=ON \
            -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
            -DCMAKE_C_FLAGS="$ASAN_FLAGS" \
            -DCMAKE_CXX_FLAGS="$ASAN_FLAGS" \
            -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address" \
            -DCMAKE_SHARED_LINKER_FLAGS="-fsanitize=address"
    else
        cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" \
            -DBUILD_EDITOR_MINIMAL=ON \
            -DBUILD_LAUNCHER=ON \
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

# Copy shared libraries from termin-base, termin-scene, termin-graphics and termin-inspect
echo "Copying shared libraries from termin-base, termin-scene, termin-graphics and termin-inspect..."
TERMIN_BASE_LIBDIR="$ENV_DIR/termin-base/python/tcbase/lib"
TERMIN_SCENE_LIBDIR="/usr/local/lib"
TERMIN_GFX_LIBDIR="$ENV_DIR/termin-graphics/python/tgfx/lib"
TERMIN_INSPECT_LIBDIR="/usr/local/lib"

if [[ -d "$TERMIN_BASE_LIBDIR" ]]; then
    cp -P "$TERMIN_BASE_LIBDIR"/libtermin_base.so* "$INSTALL_DIR/lib/"
    echo "  Copied libtermin_base from $TERMIN_BASE_LIBDIR"
else
    echo "  WARNING: $TERMIN_BASE_LIBDIR not found — skipping libtermin_base"
fi

if [[ -d "$TERMIN_SCENE_LIBDIR" ]] && compgen -G "$TERMIN_SCENE_LIBDIR/libtermin_scene.so*" > /dev/null; then
    cp -P "$TERMIN_SCENE_LIBDIR"/libtermin_scene.so* "$INSTALL_DIR/lib/"
    echo "  Copied libtermin_scene from $TERMIN_SCENE_LIBDIR"
else
    echo "  WARNING: libtermin_scene not found in $TERMIN_SCENE_LIBDIR — skipping libtermin_scene"
fi

if [[ -d "$TERMIN_GFX_LIBDIR" ]]; then
    cp -P "$TERMIN_GFX_LIBDIR"/libtermin_graphics.so* "$INSTALL_DIR/lib/"
    echo "  Copied libtermin_graphics from $TERMIN_GFX_LIBDIR"
else
    echo "  WARNING: $TERMIN_GFX_LIBDIR not found — skipping libtermin_graphics"
fi

if [[ -d "$TERMIN_INSPECT_LIBDIR" ]] && compgen -G "$TERMIN_INSPECT_LIBDIR/libtermin_inspect.so*" > /dev/null; then
    cp -P "$TERMIN_INSPECT_LIBDIR"/libtermin_inspect.so* "$INSTALL_DIR/lib/"
    echo "  Copied libtermin_inspect from $TERMIN_INSPECT_LIBDIR"
else
    echo "  WARNING: libtermin_inspect not found in $TERMIN_INSPECT_LIBDIR — skipping libtermin_inspect"
fi

# Copy Python packages from termin-inspect and termin-scene
echo "Copying Python packages from termin-inspect and termin-scene..."
PYTHON_DEST="$INSTALL_DIR/lib/python"

TERMIN_INSPECT_PY="$ENV_DIR/termin-inspect/python"
TERMIN_INSPECT_BUILD="$ENV_DIR/termin-inspect/build"
if [[ -d "$TERMIN_INSPECT_PY/termin/inspect" ]]; then
    mkdir -p "$PYTHON_DEST/termin/inspect"
    cp -r "$TERMIN_INSPECT_PY/termin/inspect/"*.py "$PYTHON_DEST/termin/inspect/"
    # Copy _inspect_native shared module
    INSPECT_SO=$(find "$TERMIN_INSPECT_BUILD" -maxdepth 2 -name "_inspect_native*.so" -not -path "*/CMakeFiles/*" | head -1)
    if [[ -n "$INSPECT_SO" ]]; then
        cp "$INSPECT_SO" "$PYTHON_DEST/termin/inspect/"
        echo "  Copied termin.inspect + _inspect_native from $TERMIN_INSPECT_PY"
    else
        echo "  Copied termin.inspect (WARNING: _inspect_native.so not found)"
    fi
else
    echo "  WARNING: $TERMIN_INSPECT_PY/termin/inspect not found — skipping termin.inspect"
fi

TERMIN_SCENE_PY="$ENV_DIR/termin-scene/python"
TERMIN_SCENE_BUILD="$ENV_DIR/termin-scene/build"
if [[ -d "$TERMIN_SCENE_PY/termin/scene" ]]; then
    mkdir -p "$PYTHON_DEST/termin/scene"
    cp -r "$TERMIN_SCENE_PY/termin/scene/"*.py "$PYTHON_DEST/termin/scene/"
    # Copy _scene_native shared module
    SCENE_SO=$(find "$TERMIN_SCENE_BUILD" -maxdepth 2 -name "_scene_native*.so" -not -path "*/CMakeFiles/*" | head -1)
    if [[ -n "$SCENE_SO" ]]; then
        cp "$SCENE_SO" "$PYTHON_DEST/termin/scene/"
        echo "  Copied termin.scene + _scene_native from $TERMIN_SCENE_PY"
    else
        echo "  Copied termin.scene (WARNING: _scene_native.so not found)"
    fi
else
    echo "  WARNING: $TERMIN_SCENE_PY/termin/scene not found — skipping termin.scene"
fi

echo ""
echo "=== Build complete ==="
echo ""
echo "To run:"
echo "  cd $INSTALL_DIR && LD_LIBRARY_PATH=./lib ./bin/termin_editor"
echo ""
echo "Or use the run script:"
echo "  ./run.sh"
