#!/bin/bash
# Build and install all termin libraries in dependency order:
#   termin-nanobind-sdk -> termin-base -> termin-mesh -> termin-graphics -> termin-inspect -> termin-scene -> termin-collision -> termin-components-collision -> termin-components-mesh -> termin-components-kinematic -> termin-gui -> termin
#
# Usage:
#   ./make-termin.sh              # Release build
#   ./make-termin.sh --debug      # Debug build
#   ./make-termin.sh --clean      # Clean before build
#   ./make-termin.sh --no-parallel  # Disable parallel build jobs

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

build_cmake_lib() {
    local name="$1"
    local dir="$2"

    echo ""
    echo "========================================"
    echo "  Building $name ($BUILD_TYPE)"
    echo "========================================"
    echo ""

    cd "$dir"

    local build_dir="build/${BUILD_TYPE}"

    if [[ $CLEAN -eq 1 ]]; then
        echo "Cleaning $build_dir..."
        rm -rf "$build_dir"
    fi

    mkdir -p "$build_dir"

    local py_exec
    py_exec="$(command -v python3 || true)"
    if [[ -z "$py_exec" ]]; then
        py_exec="$(command -v python || true)"
    fi

    local extra_args=()
    if [[ "$name" == "termin-scene" ]]; then
        extra_args+=(-DTERMIN_BUILD_PYTHON=ON)
    elif [[ "$name" == "termin-collision" ]]; then
        extra_args+=(-DTERMIN_BUILD_PYTHON=ON)
    elif [[ "$name" == "termin-components-collision" ]]; then
        extra_args+=(-DTERMIN_BUILD_PYTHON=ON)
    elif [[ "$name" == "termin-components-mesh" ]]; then
        extra_args+=(-DTERMIN_BUILD_PYTHON=ON)
    elif [[ "$name" == "termin-components-kinematic" ]]; then
        extra_args+=(-DTERMIN_BUILD_PYTHON=ON)
    fi

    cmake -S . -B "$build_dir" \
        -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
        -DCMAKE_INSTALL_PREFIX="$SDK_PREFIX" \
        -DCMAKE_PREFIX_PATH="$SDK_PREFIX" \
        -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF \
        -DCMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON \
        -Dtermin_base_DIR="$SDK_PREFIX/lib/cmake/termin_base" \
        -Dtermin_graphics_DIR="$SDK_PREFIX/lib/cmake/termin_graphics" \
        -Dtermin_mesh_DIR="$SDK_PREFIX/lib/cmake/termin_mesh" \
        -Dtermin_inspect_DIR="$SDK_PREFIX/lib/cmake/termin_inspect" \
        -Dtermin_scene_DIR="$SDK_PREFIX/lib/cmake/termin_scene" \
        -Dtermin_collision_DIR="$SDK_PREFIX/lib/cmake/termin_collision" \
        -Dtermin_components_collision_DIR="$SDK_PREFIX/lib/cmake/termin_components_collision" \
        -Dtermin_components_mesh_DIR="$SDK_PREFIX/lib/cmake/termin_components_mesh" \
        -Dtermin_components_kinematic_DIR="$SDK_PREFIX/lib/cmake/termin_components_kinematic" \
        -DPython_EXECUTABLE="$py_exec" \
        "${extra_args[@]}"

    cmake --build "$build_dir" --parallel "$BUILD_JOBS"
    sudo cmake --install "$build_dir"

    if [[ "$name" == "termin-scene" || "$name" == "termin-collision" || "$name" == "termin-components-collision" || "$name" == "termin-components-mesh" || "$name" == "termin-components-kinematic" ]]; then
        echo "Skipping Python package install for $name"
    else
        echo "Installing $name Python package..."
        CMAKE_PREFIX_PATH="$SDK_PREFIX" pip install --no-build-isolation .
    fi

    echo "$name installed to ${SDK_PREFIX}"
}

build_nanobind_sdk() {
    echo ""
    echo "========================================"
    echo "  Building termin-nanobind-sdk ($BUILD_TYPE)"
    echo "========================================"
    echo ""

    cd "$SCRIPT_DIR/termin-nanobind-sdk"

    local build_dir="build/${BUILD_TYPE}"
    if [[ $CLEAN -eq 1 ]]; then
        echo "Cleaning $build_dir..."
        rm -rf "$build_dir"
    fi

    mkdir -p "$build_dir"

    local py_exec
    py_exec="$(command -v python3 || true)"
    if [[ -z "$py_exec" ]]; then
        py_exec="$(command -v python || true)"
    fi

    if ! "$py_exec" -c "import nanobind" >/dev/null 2>&1; then
        echo "Installing nanobind Python package for SDK bootstrap..."
        pip install nanobind
    fi

    cmake -S . -B "$build_dir" \
        -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
        -DCMAKE_INSTALL_PREFIX="$SDK_PREFIX" \
        -DPython_EXECUTABLE="$py_exec"

    cmake --build "$build_dir" --parallel "$BUILD_JOBS"
    sudo cmake --install "$build_dir"

    echo "termin-nanobind-sdk installed to ${SDK_PREFIX}"
}

build_termin() {
    echo ""
    echo "========================================"
    echo "  Building termin ($BUILD_TYPE)"
    echo "========================================"
    echo ""

    cd "$SCRIPT_DIR/termin"

    local build_args=""
    [[ "$BUILD_TYPE" == "Debug" ]] && build_args="--debug"
    [[ $CLEAN -eq 1 ]] && build_args="$build_args --clean"

    # Ensure extracted modules are discoverable for find_package(...)
    local cmake_prefix="$SDK_PREFIX"

    if [[ $NO_PARALLEL -eq 1 ]]; then
        CMAKE_BUILD_PARALLEL_LEVEL=1 CMAKE_PREFIX_PATH="$cmake_prefix" \
        CMAKE_FIND_USE_PACKAGE_REGISTRY=OFF \
        CMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON \
        "$SCRIPT_DIR/termin/build.sh" $build_args
    else
        CMAKE_PREFIX_PATH="$cmake_prefix" \
        CMAKE_FIND_USE_PACKAGE_REGISTRY=OFF \
        CMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON \
        "$SCRIPT_DIR/termin/build.sh" $build_args
    fi

    echo "Installing termin to ${SDK_PREFIX}..."
    sudo "$SCRIPT_DIR/termin/install_system.sh"

    echo "Installing termin Python package (editable)..."
    CMAKE_PREFIX_PATH="$SDK_PREFIX" pip install --no-build-isolation -e "$SCRIPT_DIR/termin"
}

build_termin_inspect() {
    echo ""
    echo "========================================"
    echo "  Building termin-inspect ($BUILD_TYPE)"
    echo "========================================"
    echo ""

    cd "$SCRIPT_DIR/termin-inspect"

    local build_dir="build/${BUILD_TYPE}"
    if [[ $CLEAN -eq 1 ]]; then
        echo "Cleaning $build_dir..."
        rm -rf "$build_dir"
    fi

    mkdir -p "$build_dir"

    local py_exec
    py_exec="$(command -v python3 || true)"
    if [[ -z "$py_exec" ]]; then
        py_exec="$(command -v python || true)"
    fi

    cmake -S . -B "$build_dir" \
        -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
        -DCMAKE_INSTALL_PREFIX="$SDK_PREFIX" \
        -DCMAKE_PREFIX_PATH="$SDK_PREFIX" \
        -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF \
        -DCMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON \
        -Dtermin_base_DIR="$SDK_PREFIX/lib/cmake/termin_base" \
        -DPython_EXECUTABLE="$py_exec" \
        -DTERMIN_BUILD_PYTHON=ON

    cmake --build "$build_dir" --parallel "$BUILD_JOBS"
    sudo cmake --install "$build_dir"

    echo "termin-inspect installed to ${SDK_PREFIX}"
}

# Build chain
build_nanobind_sdk
build_cmake_lib "termin-base" "$SCRIPT_DIR/termin-base"
build_cmake_lib "termin-mesh" "$SCRIPT_DIR/termin-mesh"
build_cmake_lib "termin-graphics" "$SCRIPT_DIR/termin-graphics"
build_termin_inspect
build_cmake_lib "termin-scene" "$SCRIPT_DIR/termin-scene"
build_cmake_lib "termin-collision" "$SCRIPT_DIR/termin-collision"
build_cmake_lib "termin-components-collision" "$SCRIPT_DIR/termin-components/termin-components-collision"
build_cmake_lib "termin-components-mesh" "$SCRIPT_DIR/termin-components/termin-components-mesh"
build_cmake_lib "termin-components-kinematic" "$SCRIPT_DIR/termin-components/termin-components-kinematic"

echo ""
echo "========================================"
echo "  Installing termin-gui (pip)"
echo "========================================"
echo ""
pip install "$SCRIPT_DIR/termin-gui"

echo ""
echo "========================================"
echo "  Installing termin-nodegraph (pip)"
echo "========================================"
echo ""
pip install "$SCRIPT_DIR/termin-nodegraph"

build_termin

echo ""
echo "========================================"
echo "  All done!"
echo "========================================"
