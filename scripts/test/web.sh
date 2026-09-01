#!/bin/bash
# Run an explicit smoke gate against an already configured Termin Web build.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${TERMIN_WEB_BUILD_DIR:-$SCRIPT_DIR/build/web-core}"
HOST_BUILD_DIR="${TERMIN_WEB_HOST_BUILD_DIR:-$BUILD_DIR-host-tools}"
MODE="node"

usage() {
    echo "Usage: $0 [--browser] [--build-dir PATH]"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --browser)
            MODE="browser"
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

if [[ ! -f "$BUILD_DIR/CMakeCache.txt" ]]; then
    echo "ERROR: Termin Web build is not configured at $BUILD_DIR" >&2
    echo "Run: task build:web -- --setup" >&2
    exit 1
fi

if [[ "$(uname -s)" == Darwin ]]; then
    export DYLD_LIBRARY_PATH="$HOST_BUILD_DIR/bin:$HOST_BUILD_DIR/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
else
    export LD_LIBRARY_PATH="$HOST_BUILD_DIR/bin:$HOST_BUILD_DIR/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

if [[ "$MODE" == "browser" ]]; then
    TARGET="termin_web_core_browser_smoke"
else
    TARGET="termin_web_core_node_smoke"
fi

cmake --build "$BUILD_DIR" --target "$TARGET"
