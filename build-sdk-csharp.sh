#!/bin/bash
# Build and install C# bindings/runtime from termin-csharp.
# Assumes the SDK is already built via build-sdk-cpp.sh + build-sdk-bindings.sh.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_PREFIX="${SDK_PREFIX:-$SCRIPT_DIR/sdk}"

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

cmake -S . -B "$build_dir" \
    -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
    -DCMAKE_PREFIX_PATH="$SDK_PREFIX" \
    -DTERMIN_CSHARP_BUILD_NATIVE=ON \
    -DTERMIN_CSHARP_BUILD_MANAGED=ON \
    -DTERMIN_CSHARP_BUILD_TESTS=ON

cmake --build "$build_dir" --parallel "$BUILD_JOBS"

# Install C# artifacts to SDK
CSHARP_SDK="$SDK_PREFIX/csharp"
echo "Installing C# artifacts to $CSHARP_SDK..."
mkdir -p "$CSHARP_SDK/runtimes/linux-x64/native"
mkdir -p "$CSHARP_SDK/lib"

# Native bridge and runtime dependencies
cp -P "$SCRIPT_DIR/termin-csharp/Termin.Native/runtimes/linux-x64/native/"*.so* "$CSHARP_SDK/runtimes/linux-x64/native/" 2>/dev/null || true

# Managed assembly — find the built DLL
MANAGED_DLL=$(find "$SCRIPT_DIR/termin-csharp/Termin.Native/bin" -name "Termin.Native.dll" -path "*/$BUILD_TYPE/*" 2>/dev/null | head -1)
if [[ -n "$MANAGED_DLL" ]]; then
    cp "$MANAGED_DLL" "$CSHARP_SDK/lib/"
    echo "  Copied $(basename "$MANAGED_DLL") to $CSHARP_SDK/lib/"
fi

echo ""
echo "========================================"
echo "  termin-csharp build complete"
echo "========================================"
