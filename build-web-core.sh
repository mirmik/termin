#!/bin/bash
# Configure, build, and smoke-test the portable Termin WebAssembly core.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EMSDK_VERSION="$(tr -d '[:space:]' < "$SCRIPT_DIR/build-system/emscripten-version.txt")"
EMSDK_DIR="${TERMIN_EMSDK_DIR:-$SCRIPT_DIR/build/toolchains/emsdk}"
BUILD_DIR="${TERMIN_WEB_BUILD_DIR:-$SCRIPT_DIR/build/web-core}"
RUN_BROWSER_SMOKE=0

usage() {
    echo "Usage: $0 [--setup] [--browser-smoke] [--build-dir PATH]"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --setup)
            "$SCRIPT_DIR/setup-web-toolchain.sh"
            shift
            ;;
        --browser-smoke)
            RUN_BROWSER_SMOKE=1
            shift
            ;;
        --build-dir)
            if [[ $# -lt 2 ]]; then
                usage >&2
                exit 2
            fi
            BUILD_DIR="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            usage >&2
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

if [[ -x "$EMSDK_DIR/upstream/emscripten/emcmake" ]]; then
    EMcmake="$EMSDK_DIR/upstream/emscripten/emcmake"
    EMcc="$EMSDK_DIR/upstream/emscripten/emcc"
else
    EMcmake="$(command -v emcmake || true)"
    EMcc="$(command -v emcc || true)"
fi

if [[ -z "$EMcmake" || -z "$EMcc" ]]; then
    echo "ERROR: Emscripten is not installed. Run: $0 --setup" >&2
    exit 1
fi

EMCC_VERSION_OUTPUT="$($EMcc --version | head -n 1)"
if [[ "$EMCC_VERSION_OUTPUT" != *" $EMSDK_VERSION "* && "$EMCC_VERSION_OUTPUT" != *" $EMSDK_VERSION" ]]; then
    echo "ERROR: expected Emscripten $EMSDK_VERSION, got: $EMCC_VERSION_OUTPUT" >&2
    exit 1
fi

"$EMcmake" cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" -G "Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=Release \
    -DTERMIN_PLATFORM_WEB=ON
cmake --build "$BUILD_DIR" --target termin_web_core_node_smoke

if [[ "$RUN_BROWSER_SMOKE" -eq 1 ]]; then
    cmake --build "$BUILD_DIR" --target termin_web_core_browser_smoke
fi

echo "Termin Web core: $BUILD_DIR/bin/termin_web_core.mjs"
