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
SDK_DIR="${SDK_PREFIX:-$(dirname "$SCRIPT_DIR")/sdk}"

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

CMAKE_COMMON_ARGS=(
    -DBUILD_EDITOR_MINIMAL=ON
    -DBUILD_LAUNCHER=ON
    -DBUNDLE_PYTHON=ON
    -DCMAKE_BUILD_TYPE="$BUILD_TYPE"
    -DCMAKE_PREFIX_PATH="$SDK_DIR"
    -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF
    -DCMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON
    -DPython_EXECUTABLE="$(which python3)"
)

if [[ $ASAN -eq 1 ]]; then
    ASAN_FLAGS="-fsanitize=address -fno-omit-frame-pointer"
    cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" \
        "${CMAKE_COMMON_ARGS[@]}" \
        -DCMAKE_C_FLAGS="$ASAN_FLAGS" \
        -DCMAKE_CXX_FLAGS="$ASAN_FLAGS" \
        -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address" \
        -DCMAKE_SHARED_LINKER_FLAGS="-fsanitize=address"
else
    cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" \
        "${CMAKE_COMMON_ARGS[@]}"
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

# Copy shared libraries from SDK
echo "Copying shared libraries from SDK..."
if [[ -d "$SDK_DIR/lib" ]]; then
    rsync -aL \
        --include='libtermin_*.so*' \
        --include='libnanobind.so*' \
        --exclude='*' \
        "$SDK_DIR/lib/" "$INSTALL_DIR/lib/"
    echo "  Copied SDK libraries from $SDK_DIR/lib"
else
    echo "  WARNING: $SDK_DIR/lib not found — skipping SDK library copy"
fi

# Copy Python bindings (.so) and .py sources from subprojects
echo "Copying Python packages from subprojects..."
PYTHON_DEST="$INSTALL_DIR/lib/python"

# Module definitions: project_dir | python_subdir | so_pattern | py_source_dir
PYTHON_MODULES=(
    "termin-inspect       | termin/inspect    | _inspect_native*.so               | termin-inspect/python/termin/inspect"
    "termin-scene         | termin/scene      | _scene_native*.so                 | termin-scene/python/termin/scene"
    "termin-input         | termin/input      | _input_native*.so                 | termin-input/python/termin/input"
    "termin-render        | termin/render     | _render_native*.so                | termin-render/python/termin/render"
    "termin-collision     | termin/colliders  | _colliders_native*.so             | termin-collision/python/termin/colliders"
    "termin-collision     | termin/collision  | _collision_native*.so             | "
    "termin-components-collision | termin/colliders | _components_collision_native*.so | "
    "termin-components-mesh     | termin/mesh      | _components_mesh_native*.so      | termin-components/termin-components-mesh/python/termin/mesh"
    "termin-components-kinematic | termin/kinematic | _components_kinematic_native*.so | termin-components/termin-components-kinematic/python/termin/kinematic"
)

for entry in "${PYTHON_MODULES[@]}"; do
    IFS='|' read -r project_name py_subdir so_pattern py_source <<< "$entry"
    project_name=$(echo "$project_name" | xargs)
    py_subdir=$(echo "$py_subdir" | xargs)
    so_pattern=$(echo "$so_pattern" | xargs)
    py_source=$(echo "$py_source" | xargs)

    mkdir -p "$PYTHON_DEST/$py_subdir"

    # Copy .py files from source if specified
    if [[ -n "$py_source" && -d "$ENV_DIR/$py_source" ]]; then
        cp -n "$ENV_DIR/$py_source/"*.py "$PYTHON_DEST/$py_subdir/" 2>/dev/null || true
    fi

    # Find and copy .so binding
    build_dir="$ENV_DIR/$project_name/build"
    if [[ "$project_name" == termin-components-* ]]; then
        build_dir="$ENV_DIR/termin-components/$project_name/build"
    fi
    SO_FILE=$(find_artifact_in_build "$build_dir" "$so_pattern")
    if [[ -n "$SO_FILE" ]]; then
        cp "$SO_FILE" "$PYTHON_DEST/$py_subdir/"
        echo "  Copied $(basename "$SO_FILE") → $py_subdir/"
    else
        echo "  WARNING: $so_pattern not found in $build_dir"
    fi
done

echo ""
echo "=== Build complete ==="
echo ""
echo "To run:"
echo "  cd $INSTALL_DIR && LD_LIBRARY_PATH=./lib ./bin/termin_editor"
echo ""
echo "Or use the run script:"
echo "  ./run.sh"
