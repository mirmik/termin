#!/bin/bash
# Build and install Python bindings (nanobind SDK + C++ libs with Python + pip packages)
# Assumes C++ libraries are already built and installed via build-and-install-cpp.sh
#
# Usage:
#   ./build-and-install-bindings.sh                # Release build
#   ./build-and-install-bindings.sh --debug        # Debug build
#   ./build-and-install-bindings.sh --clean        # Clean before build
#   ./build-and-install-bindings.sh --no-parallel  # Disable parallel build jobs

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

PY_EXEC="$(command -v python3 || command -v python || true)"
if [[ -z "$PY_EXEC" ]]; then
    echo "ERROR: python3 not found"
    exit 1
fi

# ── 1. nanobind SDK ──────────────────────────────────────────────
echo ""
echo "========================================"
echo "  Building termin-nanobind-sdk ($BUILD_TYPE)"
echo "========================================"
echo ""

cd "$SCRIPT_DIR/termin-nanobind-sdk"

build_dir="build/${BUILD_TYPE}"
[[ $CLEAN -eq 1 ]] && rm -rf "$build_dir"
mkdir -p "$build_dir"

"$PY_EXEC" -c "import nanobind" 2>/dev/null || pip install nanobind

cmake -S . -B "$build_dir" \
    -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
    -DCMAKE_INSTALL_PREFIX="$SDK_PREFIX" \
    -DPython_EXECUTABLE="$PY_EXEC"
cmake --build "$build_dir" --parallel "$BUILD_JOBS"
sudo cmake --install "$build_dir"

echo "termin-nanobind-sdk installed to ${SDK_PREFIX}"

# ── 2. C++ libraries with Python bindings ────────────────────────
build_with_python() {
    local name="$1"
    local dir="$2"

    echo ""
    echo "========================================"
    echo "  Building $name Python bindings ($BUILD_TYPE)"
    echo "========================================"
    echo ""

    cd "$dir"

    local build_dir="build/${BUILD_TYPE}"
    [[ $CLEAN -eq 1 ]] && rm -rf "$build_dir"
    mkdir -p "$build_dir"

    cmake -S . -B "$build_dir" \
        -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
        -DCMAKE_INSTALL_PREFIX="$SDK_PREFIX" \
        -DCMAKE_PREFIX_PATH="$SDK_PREFIX" \
        -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF \
        -DCMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON \
        -DTERMIN_BUILD_PYTHON=ON \
        -Dtermin_base_DIR="$SDK_PREFIX/lib/cmake/termin_base" \
        -Dtermin_graphics_DIR="$SDK_PREFIX/lib/cmake/termin_graphics" \
        -Dtermin_mesh_DIR="$SDK_PREFIX/lib/cmake/termin_mesh" \
        -Dtermin_inspect_DIR="$SDK_PREFIX/lib/cmake/termin_inspect" \
        -Dtermin_scene_DIR="$SDK_PREFIX/lib/cmake/termin_scene" \
        -Dtermin_render_DIR="$SDK_PREFIX/lib/cmake/termin_render" \
        -Dtermin_input_DIR="$SDK_PREFIX/lib/cmake/termin_input" \
        -Dtermin_collision_DIR="$SDK_PREFIX/lib/cmake/termin_collision" \
        -Dtermin_components_collision_DIR="$SDK_PREFIX/lib/cmake/termin_components_collision" \
        -Dtermin_components_render_DIR="$SDK_PREFIX/lib/cmake/termin_components_render" \
        -Dtermin_components_mesh_DIR="$SDK_PREFIX/lib/cmake/termin_components_mesh" \
        -Dtermin_components_kinematic_DIR="$SDK_PREFIX/lib/cmake/termin_components_kinematic" \
        -DPython_EXECUTABLE="$PY_EXEC"
    cmake --build "$build_dir" --parallel "$BUILD_JOBS"
    sudo cmake --install "$build_dir"

    echo "$name Python bindings installed to ${SDK_PREFIX}"
}

build_with_python "termin-inspect"              "$SCRIPT_DIR/termin-inspect"
build_with_python "termin-scene"                "$SCRIPT_DIR/termin-scene"
build_with_python "termin-render"               "$SCRIPT_DIR/termin-render"
build_with_python "termin-collision"            "$SCRIPT_DIR/termin-collision"
build_with_python "termin-components-collision"  "$SCRIPT_DIR/termin-components/termin-components-collision"
build_with_python "termin-components-render"     "$SCRIPT_DIR/termin-components/termin-components-render"
build_with_python "termin-components-mesh"       "$SCRIPT_DIR/termin-components/termin-components-mesh"
build_with_python "termin-components-kinematic"  "$SCRIPT_DIR/termin-components/termin-components-kinematic"

# ── 3. pip-installable Python packages ───────────────────────────
for pkg in termin-base termin-modules termin-mesh termin-graphics; do
    echo ""
    echo "========================================"
    echo "  Installing $pkg (pip)"
    echo "========================================"
    echo ""
    CMAKE_PREFIX_PATH="$SDK_PREFIX" pip install --no-build-isolation "$SCRIPT_DIR/$pkg"
done

for pkg in termin-gui termin-nodegraph; do
    echo ""
    echo "========================================"
    echo "  Installing $pkg (pip)"
    echo "========================================"
    echo ""
    pip install "$SCRIPT_DIR/$pkg"
done

# ── 4. termin ────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  Building termin ($BUILD_TYPE)"
echo "========================================"
echo ""

build_args=()
if [[ "$BUILD_TYPE" == "Debug" ]]; then
    build_args+=("--debug")
fi
if [[ $CLEAN -eq 1 ]]; then
    build_args+=("--clean")
fi

if [[ $NO_PARALLEL -eq 1 ]]; then
    CMAKE_BUILD_PARALLEL_LEVEL=1 \
    CMAKE_PREFIX_PATH="$SDK_PREFIX" \
    CMAKE_FIND_USE_PACKAGE_REGISTRY=OFF \
    CMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON \
    "$SCRIPT_DIR/termin/build.sh" "${build_args[@]}"
else
    CMAKE_PREFIX_PATH="$SDK_PREFIX" \
    CMAKE_FIND_USE_PACKAGE_REGISTRY=OFF \
    CMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON \
    "$SCRIPT_DIR/termin/build.sh" "${build_args[@]}"
fi

echo "Installing termin to ${SDK_PREFIX}..."
sudo "$SCRIPT_DIR/termin/install_system.sh"

echo "Installing termin Python package (editable)..."
CMAKE_PREFIX_PATH="$SDK_PREFIX" pip install --no-build-isolation -e "$SCRIPT_DIR/termin"

echo ""
echo "========================================"
echo "  All bindings done!"
echo "========================================"
