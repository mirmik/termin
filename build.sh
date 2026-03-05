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
SDK_DIR="/opt/termin"

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

find_artifact_in_build() {
    local base_dir="$1"
    local pattern="$2"
    local config_dir="$base_dir/$BUILD_TYPE"
    local result=""

    if [[ -d "$config_dir" ]]; then
        result=$(find "$config_dir" -maxdepth 3 -name "$pattern" -not -path "*/CMakeFiles/*" | head -1)
    fi

    if [[ -z "$result" ]]; then
        result=$(find "$base_dir" -maxdepth 3 -name "$pattern" -not -path "*/CMakeFiles/*" | head -1)
    fi

    echo "$result"
}

# Configure
echo "Configuring CMake..."

if [[ $ASAN -eq 1 ]]; then
    ASAN_FLAGS="-fsanitize=address -fno-omit-frame-pointer"
    cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" \
        -DBUILD_EDITOR_MINIMAL=ON \
        -DBUILD_LAUNCHER=ON \
        -DBUNDLE_PYTHON=ON \
        -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
        -DCMAKE_PREFIX_PATH="$SDK_DIR" \
        -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF \
        -DCMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON \
        -DPython_EXECUTABLE="$(which python3)" \
        -Dtermin_base_DIR="$SDK_DIR/lib/cmake/termin_base" \
        -Dtermin_graphics_DIR="$SDK_DIR/lib/cmake/termin_graphics" \
        -Dtermin_inspect_DIR="$SDK_DIR/lib/cmake/termin_inspect" \
        -Dtermin_scene_DIR="$SDK_DIR/lib/cmake/termin_scene" \
        -Dtermin_collision_DIR="$SDK_DIR/lib/cmake/termin_collision" \
        -Dtermin_components_collision_DIR="$SDK_DIR/lib/cmake/termin_components_collision" \
        -Dtermin_components_mesh_DIR="$SDK_DIR/lib/cmake/termin_components_mesh" \
        -DCMAKE_C_FLAGS="$ASAN_FLAGS" \
        -DCMAKE_CXX_FLAGS="$ASAN_FLAGS" \
        -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address" \
        -DCMAKE_SHARED_LINKER_FLAGS="-fsanitize=address"
else
    cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" \
        -DBUILD_EDITOR_MINIMAL=ON \
        -DBUILD_LAUNCHER=ON \
        -DBUNDLE_PYTHON=ON \
        -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
        -DCMAKE_PREFIX_PATH="$SDK_DIR" \
        -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF \
        -DCMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON \
        -DPython_EXECUTABLE="$(which python3)" \
        -Dtermin_base_DIR="$SDK_DIR/lib/cmake/termin_base" \
        -Dtermin_graphics_DIR="$SDK_DIR/lib/cmake/termin_graphics" \
        -Dtermin_inspect_DIR="$SDK_DIR/lib/cmake/termin_inspect" \
        -Dtermin_scene_DIR="$SDK_DIR/lib/cmake/termin_scene" \
        -Dtermin_collision_DIR="$SDK_DIR/lib/cmake/termin_collision" \
        -Dtermin_components_collision_DIR="$SDK_DIR/lib/cmake/termin_components_collision" \
        -Dtermin_components_mesh_DIR="$SDK_DIR/lib/cmake/termin_components_mesh"
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

# Copy shared libraries from extracted modules
echo "Copying shared libraries from termin-base, termin-scene, termin-graphics, termin-inspect, termin-collision, termin-components-collision and termin-components-mesh..."
TERMIN_BASE_LIBDIR="$SDK_DIR/lib"
TERMIN_SCENE_LIBDIR="$SDK_DIR/lib"
TERMIN_GFX_LIBDIR="$SDK_DIR/lib"
TERMIN_INSPECT_LIBDIR="$SDK_DIR/lib"
TERMIN_COLLISION_LIBDIR="$SDK_DIR/lib"
TERMIN_COMPONENTS_COLLISION_LIBDIR="$SDK_DIR/lib"
TERMIN_COMPONENTS_MESH_LIBDIR="$SDK_DIR/lib"

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

if [[ -d "$TERMIN_COLLISION_LIBDIR" ]] && compgen -G "$TERMIN_COLLISION_LIBDIR/libtermin_collision.so*" > /dev/null; then
    cp -P "$TERMIN_COLLISION_LIBDIR"/libtermin_collision.so* "$INSTALL_DIR/lib/"
    echo "  Copied libtermin_collision from $TERMIN_COLLISION_LIBDIR"
else
    echo "  WARNING: libtermin_collision not found in $TERMIN_COLLISION_LIBDIR — skipping libtermin_collision"
fi

if [[ -d "$TERMIN_COMPONENTS_COLLISION_LIBDIR" ]] && compgen -G "$TERMIN_COMPONENTS_COLLISION_LIBDIR/libtermin_components_collision.so*" > /dev/null; then
    cp -P "$TERMIN_COMPONENTS_COLLISION_LIBDIR"/libtermin_components_collision.so* "$INSTALL_DIR/lib/"
    echo "  Copied libtermin_components_collision from $TERMIN_COMPONENTS_COLLISION_LIBDIR"
else
    echo "  WARNING: libtermin_components_collision not found in $TERMIN_COMPONENTS_COLLISION_LIBDIR — skipping libtermin_components_collision"
fi

if [[ -d "$TERMIN_COMPONENTS_MESH_LIBDIR" ]] && compgen -G "$TERMIN_COMPONENTS_MESH_LIBDIR/libtermin_components_mesh.so*" > /dev/null; then
    cp -P "$TERMIN_COMPONENTS_MESH_LIBDIR"/libtermin_components_mesh.so* "$INSTALL_DIR/lib/"
    echo "  Copied libtermin_components_mesh from $TERMIN_COMPONENTS_MESH_LIBDIR"
else
    echo "  WARNING: libtermin_components_mesh not found in $TERMIN_COMPONENTS_MESH_LIBDIR — skipping libtermin_components_mesh"
fi

# Copy Python packages from extracted modules
echo "Copying Python packages from termin-inspect, termin-scene, termin-collision, termin-components-collision and termin-components-mesh..."
PYTHON_DEST="$INSTALL_DIR/lib/python"

TERMIN_INSPECT_PY="$ENV_DIR/termin-inspect/python"
TERMIN_INSPECT_BUILD="$ENV_DIR/termin-inspect/build"
if [[ -d "$TERMIN_INSPECT_PY/termin/inspect" ]]; then
    mkdir -p "$PYTHON_DEST/termin/inspect"
    cp -r "$TERMIN_INSPECT_PY/termin/inspect/"*.py "$PYTHON_DEST/termin/inspect/"
    # Copy _inspect_native shared module
    INSPECT_SO=$(find_artifact_in_build "$TERMIN_INSPECT_BUILD" "_inspect_native*.so")
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
    SCENE_SO=$(find_artifact_in_build "$TERMIN_SCENE_BUILD" "_scene_native*.so")
    if [[ -n "$SCENE_SO" ]]; then
        cp "$SCENE_SO" "$PYTHON_DEST/termin/scene/"
        echo "  Copied termin.scene + _scene_native from $TERMIN_SCENE_PY"
    else
        echo "  Copied termin.scene (WARNING: _scene_native.so not found)"
    fi
else
    echo "  WARNING: $TERMIN_SCENE_PY/termin/scene not found — skipping termin.scene"
fi

TERMIN_COLLISION_BUILD="$ENV_DIR/termin-collision/build"
mkdir -p "$PYTHON_DEST/termin/colliders" "$PYTHON_DEST/termin/collision"
COLLIDERS_SO=$(find_artifact_in_build "$TERMIN_COLLISION_BUILD" "_colliders_native*.so")
COLLISION_SO=$(find_artifact_in_build "$TERMIN_COLLISION_BUILD" "_collision_native*.so")
if [[ -n "$COLLIDERS_SO" ]]; then
    cp "$COLLIDERS_SO" "$PYTHON_DEST/termin/colliders/"
    echo "  Copied _colliders_native from $TERMIN_COLLISION_BUILD"
else
    echo "  WARNING: _colliders_native.so not found in $TERMIN_COLLISION_BUILD"
fi
if [[ -n "$COLLISION_SO" ]]; then
    cp "$COLLISION_SO" "$PYTHON_DEST/termin/collision/"
    echo "  Copied _collision_native from $TERMIN_COLLISION_BUILD"
else
    echo "  WARNING: _collision_native.so not found in $TERMIN_COLLISION_BUILD"
fi

TERMIN_COMPONENTS_COLLISION_BUILD="$ENV_DIR/termin-components-collision/build"
COMPONENTS_COLLISION_SO=$(find_artifact_in_build "$TERMIN_COMPONENTS_COLLISION_BUILD" "_components_collision_native*.so")
if [[ -n "$COMPONENTS_COLLISION_SO" ]]; then
    cp "$COMPONENTS_COLLISION_SO" "$PYTHON_DEST/termin/colliders/"
    echo "  Copied _components_collision_native from $TERMIN_COMPONENTS_COLLISION_BUILD"
else
    echo "  WARNING: _components_collision_native.so not found in $TERMIN_COMPONENTS_COLLISION_BUILD"
fi

TERMIN_COMPONENTS_MESH_BUILD="$ENV_DIR/termin-components-mesh/build"
COMPONENTS_MESH_SO=$(find_artifact_in_build "$TERMIN_COMPONENTS_MESH_BUILD" "_components_mesh_native*.so")
if [[ -n "$COMPONENTS_MESH_SO" ]]; then
    mkdir -p "$PYTHON_DEST/termin/mesh"
    cp "$COMPONENTS_MESH_SO" "$PYTHON_DEST/termin/mesh/"
    echo "  Copied _components_mesh_native from $TERMIN_COMPONENTS_MESH_BUILD"
else
    echo "  WARNING: _components_mesh_native.so not found in $TERMIN_COMPONENTS_MESH_BUILD"
fi

echo ""
echo "=== Build complete ==="
echo ""
echo "To run:"
echo "  cd $INSTALL_DIR && LD_LIBRARY_PATH=./lib ./bin/termin_editor"
echo ""
echo "Or use the run script:"
echo "  ./run.sh"
