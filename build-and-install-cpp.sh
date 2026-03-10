#!/bin/bash
# Build and install C/C++ parts only (no Python bindings / nanobind modules)
# Dependency order:
#   termin-base -> termin-modules -> termin-mesh -> termin-graphics -> termin-inspect -> termin-scene
#   -> termin-render -> termin-input -> termin-collision -> termin-components-collision -> termin-components-mesh
#   -> termin-components-kinematic -> termin(cpp only)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_PREFIX="/opt/termin"

BUILD_TYPE="Release"
CLEAN=0
NO_PARALLEL=0
BUILD_JOBS="$(nproc)"

for arg in "$@"; do
    case "$arg" in
        --debug|-d)    BUILD_TYPE="Debug" ;;
        --clean|-c)    CLEAN=1 ;;
        --no-parallel) NO_PARALLEL=1 ;;
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
        *)
            echo "Unknown option: $arg"
            exit 1
            ;;
    esac
done

if [[ $NO_PARALLEL -eq 1 ]]; then
    BUILD_JOBS=1
fi

build_cmake_lib_cpp() {
    local name="$1"
    local dir="$2"

    echo ""
    echo "========================================"
    echo "  Building $name ($BUILD_TYPE) [C/C++ only]"
    echo "========================================"
    echo ""

    cd "$dir"

    local build_dir="build/${BUILD_TYPE}"

    if [[ $CLEAN -eq 1 ]]; then
        echo "Cleaning $build_dir..."
        rm -rf "$build_dir"
    fi

    mkdir -p "$build_dir"

    local extra_args=()
    if [[ "$name" == "termin-modules" ]]; then
        extra_args+=(-DTERMIN_MODULES_BUILD_PYTHON=OFF)
    fi

    cmake -S . -B "$build_dir" \
        -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
        -DCMAKE_INSTALL_PREFIX="$SDK_PREFIX" \
        -DCMAKE_PREFIX_PATH="$SDK_PREFIX" \
        -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF \
        -DCMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON \
        -DTERMIN_BUILD_PYTHON=OFF \
        -Dtermin_base_DIR="$SDK_PREFIX/lib/cmake/termin_base" \
        -Dtermin_graphics_DIR="$SDK_PREFIX/lib/cmake/termin_graphics" \
        -Dtermin_mesh_DIR="$SDK_PREFIX/lib/cmake/termin_mesh" \
        -Dtermin_inspect_DIR="$SDK_PREFIX/lib/cmake/termin_inspect" \
        -Dtermin_scene_DIR="$SDK_PREFIX/lib/cmake/termin_scene" \
        -Dtermin_render_DIR="$SDK_PREFIX/lib/cmake/termin_render" \
        -Dtermin_input_DIR="$SDK_PREFIX/lib/cmake/termin_input" \
        -Dtermin_collision_DIR="$SDK_PREFIX/lib/cmake/termin_collision" \
        -Dtermin_components_collision_DIR="$SDK_PREFIX/lib/cmake/termin_components_collision" \
        -Dtermin_components_mesh_DIR="$SDK_PREFIX/lib/cmake/termin_components_mesh" \
        -Dtermin_components_kinematic_DIR="$SDK_PREFIX/lib/cmake/termin_components_kinematic" \
        "${extra_args[@]}"

    cmake --build "$build_dir" --parallel "$BUILD_JOBS"

    sudo cmake --install "$build_dir"

    echo "$name installed to ${SDK_PREFIX}"
}

build_termin_cpp_only() {
    echo ""
    echo "========================================"
    echo "  Building termin ($BUILD_TYPE) [C/C++ only, no nanobind]"
    echo "========================================"
    echo ""

    cd "$SCRIPT_DIR/termin"

    local build_dir="build_standalone_cpp/${BUILD_TYPE}"
    if [[ $CLEAN -eq 1 ]]; then
        echo "Cleaning $build_dir..."
        rm -rf "$build_dir"
    fi

    mkdir -p "$build_dir"

    cmake -S . -B "$build_dir" \
        -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
        -DCMAKE_INSTALL_PREFIX="$SDK_PREFIX" \
        -DCMAKE_PREFIX_PATH="$SDK_PREFIX" \
        -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF \
        -DCMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON \
        -DBUILD_EDITOR_MINIMAL=OFF \
        -DBUILD_EDITOR_EXE=OFF \
        -DBUILD_LAUNCHER=OFF \
        -DBUNDLE_PYTHON=OFF \
        -DBUILD_CSHARP_BINDINGS=OFF \
        -DTERMIN_BUILD_PYTHON=OFF \
        -Dtermin_base_DIR="$SDK_PREFIX/lib/cmake/termin_base" \
        -Dtermin_graphics_DIR="$SDK_PREFIX/lib/cmake/termin_graphics" \
        -Dtermin_inspect_DIR="$SDK_PREFIX/lib/cmake/termin_inspect" \
        -Dtermin_scene_DIR="$SDK_PREFIX/lib/cmake/termin_scene" \
        -Dtermin_render_DIR="$SDK_PREFIX/lib/cmake/termin_render" \
        -Dtermin_input_DIR="$SDK_PREFIX/lib/cmake/termin_input" \
        -Dtermin_collision_DIR="$SDK_PREFIX/lib/cmake/termin_collision" \
        -Dtermin_components_collision_DIR="$SDK_PREFIX/lib/cmake/termin_components_collision" \
        -Dtermin_components_mesh_DIR="$SDK_PREFIX/lib/cmake/termin_components_mesh" \
        -Dtermin_components_kinematic_DIR="$SDK_PREFIX/lib/cmake/termin_components_kinematic"

    cmake --build "$build_dir" --parallel "$BUILD_JOBS"
    sudo cmake --install "$build_dir"

    echo "termin (C/C++ only) installed to ${SDK_PREFIX}"
}

# Build chain (C/C++ only)
build_cmake_lib_cpp "termin-base" "$SCRIPT_DIR/termin-base"
build_cmake_lib_cpp "termin-modules" "$SCRIPT_DIR/termin-modules"
build_cmake_lib_cpp "termin-mesh" "$SCRIPT_DIR/termin-mesh"
build_cmake_lib_cpp "termin-graphics" "$SCRIPT_DIR/termin-graphics"
build_cmake_lib_cpp "termin-inspect" "$SCRIPT_DIR/termin-inspect"
build_cmake_lib_cpp "termin-scene" "$SCRIPT_DIR/termin-scene"
build_cmake_lib_cpp "termin-render" "$SCRIPT_DIR/termin-render"
build_cmake_lib_cpp "termin-input" "$SCRIPT_DIR/termin-input"
build_cmake_lib_cpp "termin-collision" "$SCRIPT_DIR/termin-collision"
build_cmake_lib_cpp "termin-components-collision" "$SCRIPT_DIR/termin-components/termin-components-collision"
build_cmake_lib_cpp "termin-components-mesh" "$SCRIPT_DIR/termin-components/termin-components-mesh"
build_cmake_lib_cpp "termin-components-kinematic" "$SCRIPT_DIR/termin-components/termin-components-kinematic"
build_termin_cpp_only

echo ""
echo "========================================"
echo "  All done (C/C++ only)!"
echo "========================================"
