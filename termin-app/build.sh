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
SDK_DIR="${SDK_PREFIX:-$(dirname "$SCRIPT_DIR")/sdk}"
PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

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
echo "Python:     $PYTHON_VERSION"
echo ""

# Clean if requested
if [[ $CLEAN -eq 1 ]]; then
    echo "Cleaning build directories..."
    rm -rf "$BUILD_DIR" "$INSTALL_DIR"
fi

# Create build directory
mkdir -p "$BUILD_DIR"

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
    echo "ERROR: SDK library directory not found: $SDK_DIR/lib" >&2
    exit 1
fi

# Runtime assets (fonts, built-in shader sources, and catalogs) follow the same
# verified SDK provenance as the shared libraries and Python packages.
echo "Synchronizing runtime assets from SDK..."
if [[ ! -d "$SDK_DIR/share" ]]; then
    echo "ERROR: SDK runtime asset directory not found: $SDK_DIR/share" >&2
    exit 1
fi
mkdir -p "$INSTALL_DIR/share"
rsync -aL --delete "$SDK_DIR/share/" "$INSTALL_DIR/share/"
echo "  Synchronized verified SDK assets from $SDK_DIR/share"

# Synchronize the exact SDK runtime into the standalone bundle. The editor
# binding itself is built by this standalone graph and must remain in place;
# every other Python module and native binding comes from the verified SDK.
echo "Synchronizing Python runtime from SDK..."
PYTHON_DEST="$INSTALL_DIR/lib/python$PYTHON_VERSION/site-packages"
SDK_SITE_PACKAGES="$SDK_DIR/lib/python$PYTHON_VERSION/site-packages"
if [[ ! -d "$SDK_SITE_PACKAGES" ]]; then
    echo "ERROR: SDK Python $PYTHON_VERSION site-packages not found: $SDK_SITE_PACKAGES" >&2
    exit 1
fi
rsync -aL --delete \
    --exclude='termin/editor/_editor_native*.so' \
    "$SDK_SITE_PACKAGES/" "$PYTHON_DEST/"
echo "  Synchronized verified SDK site-packages from $SDK_SITE_PACKAGES"

echo ""
echo "=== Build complete ==="
echo ""
echo "To run:"
echo "  cd $INSTALL_DIR && LD_LIBRARY_PATH=./lib ./bin/termin_editor"
echo ""
echo "Or use the run script:"
echo "  ./run.sh"
