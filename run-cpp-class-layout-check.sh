#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL_SOURCE_DIR="$SCRIPT_DIR/tools/cpp-class-layout"
TOOL_BUILD_DIR="${CPP_CLASS_LAYOUT_TOOL_BUILD_DIR:-$SCRIPT_DIR/build/cpp-class-layout-checker}"
COMPILE_DB_DIR="${CPP_CLASS_LAYOUT_COMPILE_DB_DIR:-$SCRIPT_DIR/build/Release-lint}"
BUILD_JOBS="${BUILD_JOBS:-$(nproc)}"
CHECK_JOBS="${CPP_CLASS_LAYOUT_JOBS:-4}"

LLVM_CONFIG="${CPP_CLASS_LAYOUT_LLVM_CONFIG:-llvm-config-18}"
if ! command -v "$LLVM_CONFIG" >/dev/null 2>&1; then
    echo "ERROR: LLVM/Clang 18 is required, but $LLVM_CONFIG was not found" >&2
    echo "Set CPP_CLASS_LAYOUT_LLVM_CONFIG to the LLVM 18 llvm-config executable." >&2
    exit 2
fi

LLVM_VERSION="$($LLVM_CONFIG --version)"
if [[ "${LLVM_VERSION%%.*}" != "18" ]]; then
    echo "ERROR: $LLVM_CONFIG reports LLVM $LLVM_VERSION; LLVM 18 is required" >&2
    exit 2
fi

LLVM_CMAKE_DIR="$($LLVM_CONFIG --cmakedir)"
CLANG_CMAKE_DIR="$(dirname "$LLVM_CMAKE_DIR")/clang"
if [[ ! -f "$LLVM_CMAKE_DIR/LLVMConfig.cmake" ]]; then
    echo "ERROR: LLVM 18 CMake package was not found under $LLVM_CMAKE_DIR" >&2
    exit 2
fi
if [[ ! -f "$CLANG_CMAKE_DIR/ClangConfig.cmake" ]]; then
    echo "ERROR: Clang 18 CMake package was not found under $CLANG_CMAKE_DIR" >&2
    exit 2
fi

cmake -S "$TOOL_SOURCE_DIR" -B "$TOOL_BUILD_DIR" \
    -DBUILD_TESTING=ON \
    -DLLVM_DIR="$LLVM_CMAKE_DIR" \
    -DClang_DIR="$CLANG_CMAKE_DIR"
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
