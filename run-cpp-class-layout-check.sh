#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL_SOURCE_DIR="$SCRIPT_DIR/tools/cpp-class-layout"
TOOL_BUILD_DIR="${CPP_CLASS_LAYOUT_TOOL_BUILD_DIR:-$SCRIPT_DIR/build/cpp-class-layout-checker}"
COMPILE_DB_DIR="${CPP_CLASS_LAYOUT_COMPILE_DB_DIR:-$SCRIPT_DIR/build/Release-lint}"
BUILD_JOBS="${BUILD_JOBS:-$(nproc)}"
CHECK_JOBS="${CPP_CLASS_LAYOUT_JOBS:-4}"

cmake -S "$TOOL_SOURCE_DIR" -B "$TOOL_BUILD_DIR" -DBUILD_TESTING=ON
cmake --build "$TOOL_BUILD_DIR" --parallel "$BUILD_JOBS"

CHECKER="$TOOL_BUILD_DIR/termin-cpp-class-layout"

if [[ "${1:-}" == "--self-test" ]]; then
    shift
    ctest --test-dir "$TOOL_BUILD_DIR" --output-on-failure "$@"
    exit 0
fi

if [[ "${1:-}" == "--python-bindings" ]]; then
    shift
    if [[ -z "${CPP_CLASS_LAYOUT_COMPILE_DB_DIR:-}" ]]; then
        COMPILE_DB_DIR="$SCRIPT_DIR/build/Release-lint-python"
    fi
fi

if [[ ! -f "$COMPILE_DB_DIR/compile_commands.json" ]]; then
    echo "ERROR: compilation database not found: $COMPILE_DB_DIR/compile_commands.json" >&2
    echo "Generate it with ./run-lint-cpp.sh --configure-only" >&2
    echo "or ./run-lint-cpp.sh --python-bindings --configure-only." >&2
    exit 2
fi

exec "$CHECKER" \
    -p "$COMPILE_DB_DIR" \
    --repo-root "$SCRIPT_DIR" \
    --jobs "$CHECK_JOBS" \
    "$@"
