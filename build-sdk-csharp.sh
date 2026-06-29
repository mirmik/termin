#!/bin/bash
# Build and install C# bindings/runtime from termin-csharp.
# Assumes the SDK is already built via build-sdk-cpp.sh + build-sdk-bindings.sh.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_PREFIX="${SDK_PREFIX:-$SCRIPT_DIR/sdk}"

BUILD_TYPE="Release"
CLEAN=0
NO_PARALLEL=0
TERMIN_CSHARP_ENABLE_OPENGL=""
BUILD_JOBS="${BUILD_JOBS:-$(nproc)}"

for arg in "$@"; do
    case "$arg" in
        --debug|-d)    BUILD_TYPE="Debug" ;;
        --clean|-c)    CLEAN=1 ;;
        --no-parallel) NO_PARALLEL=1 ;;
        --ccache|--no-ccache) ;;
        --ninja) ;;
        --unity|--no-unity) ;;
        --pch|--no-pch) ;;
        --no-vulkan|--vulkan) ;;
        --no-sdl|--sdl) ;;
        --no-opengl) TERMIN_CSHARP_ENABLE_OPENGL="OFF" ;;
        --opengl) TERMIN_CSHARP_ENABLE_OPENGL="ON" ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --debug, -d       Debug build"
            echo "  --clean, -c       Clean build directories first"
            echo "  --no-parallel     Disable parallel compilation (equivalent to -j1)"
            echo "  --ccache          Accepted for top-level SDK builds; ignored by C# stage"
            echo "  --no-ccache       Accepted for top-level SDK builds; ignored by C# stage"
            echo "  --ninja           Accepted for top-level SDK builds; ignored by C# stage"
            echo "  --unity           Accepted for top-level SDK builds; ignored by C# stage"
            echo "  --no-unity        Accepted for top-level SDK builds; ignored by C# stage"
            echo "  --pch             Accepted for top-level SDK builds; ignored by C# stage"
            echo "  --no-pch          Accepted for top-level SDK builds; ignored by C# stage"
            echo "  --no-vulkan       Accepted for top-level SDK builds; ignored by C# stage"
            echo "  --vulkan          Accepted for top-level SDK builds; ignored by C# stage"
            echo "  --no-sdl          Accepted for top-level SDK builds; ignored by C# stage"
            echo "  --sdl             Accepted for top-level SDK builds; ignored by C# stage"
            echo "  --no-opengl       Build C# bindings without legacy OpenGL entrypoints"
            echo "  --opengl          Build C# bindings with legacy OpenGL entrypoints"
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

if ! command -v swig >/dev/null 2>&1; then
    echo "ERROR: swig not found"
    exit 1
fi

if ! command -v dotnet >/dev/null 2>&1; then
    echo "ERROR: dotnet not found"
    exit 1
fi

echo ""
echo "========================================"
echo "  Building termin-csharp ($BUILD_TYPE)"
echo "========================================"
echo ""

cd "$SCRIPT_DIR/termin-csharp"

build_dir="build/${BUILD_TYPE}"
if [[ $CLEAN -eq 1 ]]; then
    rm -rf "$build_dir"
fi
mkdir -p "$build_dir"

cmake_args=(
    -S .
    -B "$build_dir"
    -DCMAKE_BUILD_TYPE="$BUILD_TYPE"
    -DCMAKE_PREFIX_PATH="$SDK_PREFIX"
    -DTERMIN_CSHARP_BUILD_NATIVE=ON
    -DTERMIN_CSHARP_BUILD_MANAGED=ON
    -DTERMIN_CSHARP_BUILD_TESTS=ON
    -DTERMIN_CSHARP_SDK_SHARE_DIR="$SDK_PREFIX/share/termin"
)
if [[ -n "$TERMIN_CSHARP_ENABLE_OPENGL" ]]; then
    cmake_args+=("-DTERMIN_CSHARP_ENABLE_OPENGL=$TERMIN_CSHARP_ENABLE_OPENGL")
fi
cmake "${cmake_args[@]}"

cmake --build "$build_dir" --parallel "$BUILD_JOBS"

# Install C# artifacts to SDK
CSHARP_SDK="$SDK_PREFIX/csharp"
echo "Installing C# artifacts to $CSHARP_SDK..."
mkdir -p "$CSHARP_SDK/runtimes/linux-x64/native"
mkdir -p "$CSHARP_SDK/lib"
SDK_SHARE_SOURCE="$SDK_PREFIX/share/termin"
CSHARP_SHARE_DEST="$CSHARP_SDK/share/termin"

# Native bridge and runtime dependencies
cp -P "$SCRIPT_DIR/termin-csharp/Termin.Native/runtimes/linux-x64/native/"*.so* "$CSHARP_SDK/runtimes/linux-x64/native/" 2>/dev/null || true

# Managed assembly — find the built DLL
MANAGED_DLL=$(find "$SCRIPT_DIR/termin-csharp/Termin.Native/bin" -name "Termin.Native.dll" -path "*/$BUILD_TYPE/*" 2>/dev/null | head -1)
if [[ -n "$MANAGED_DLL" ]]; then
    cp "$MANAGED_DLL" "$CSHARP_SDK/lib/"
    echo "  Copied $(basename "$MANAGED_DLL") to $CSHARP_SDK/lib/"
fi

# Shader sources and backend artifacts used by tgfx2 renderers and tcplot.
required_share_files=(
    "$SDK_SHARE_SOURCE/builtin_shaders/engine-shader-catalog.json"
)
for required in "${required_share_files[@]}"; do
    if [[ ! -e "$required" ]]; then
        echo "ERROR: SDK shader resource missing: $required" >&2
        echo "Build/install termin-graphics before build-sdk-csharp." >&2
        exit 1
    fi
done
rm -rf "$CSHARP_SHARE_DEST"
mkdir -p "$CSHARP_SHARE_DEST"
cp -R "$SDK_SHARE_SOURCE"/. "$CSHARP_SHARE_DEST/"
echo "  Copied Termin shader resources to $CSHARP_SHARE_DEST"

echo ""
echo "========================================"
echo "  termin-csharp build complete"
echo "========================================"
