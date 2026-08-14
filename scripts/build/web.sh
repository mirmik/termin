#!/bin/bash
# Configure, build, and smoke-test the portable Termin WebAssembly core.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EMSDK_VERSION="$(tr -d '[:space:]' < "$SCRIPT_DIR/build-system/emscripten-version.txt")"
SLANG_VERSION="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "$SCRIPT_DIR/build-system/slang-toolchain-lock.json")"
NAGA_VERSION="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["naga_cli"]["version"])' "$SCRIPT_DIR/build-system/web-shader-toolchain-lock.json")"
EMSDK_DIR="$("$SCRIPT_DIR/scripts/build/setup-web-toolchain.sh" --print-path)"
BUILD_DIR="${TERMIN_WEB_BUILD_DIR:-$SCRIPT_DIR/build/web-core}"
HOST_BUILD_DIR="${TERMIN_WEB_HOST_BUILD_DIR:-$BUILD_DIR-host-tools}"
RUN_BROWSER_SMOKE=0
TARGET_CORE_SDK="${TERMIN_WEB_CORE_SDK:-${TERMIN_CORE_SDK:-}}"
TARGET_CORE_BUILD_ID="${TERMIN_WEB_CORE_BUILD_ID:-${TERMIN_CORE_BUILD_ID:-}}"
HOST_CORE_SDK="${TERMIN_HOST_CORE_SDK:-}"
HOST_CORE_BUILD_ID="${TERMIN_HOST_CORE_BUILD_ID:-}"

usage() {
    echo "Usage: $0 [--setup] [--browser-smoke] [--build-dir PATH] [CORE INPUTS]"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --setup)
            "$SCRIPT_DIR/scripts/build/setup-web-toolchain.sh"
            "$SCRIPT_DIR/scripts/build/setup-web-shader-toolchain.sh"
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
        --core-sdk) TARGET_CORE_SDK="$2"; shift 2 ;;
        --core-build-id) TARGET_CORE_BUILD_ID="$2"; shift 2 ;;
        --host-core-sdk) HOST_CORE_SDK="$2"; shift 2 ;;
        --host-core-build-id) HOST_CORE_BUILD_ID="$2"; shift 2 ;;
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

if [[ -z "$TARGET_CORE_SDK" ]]; then
    echo "ERROR: --core-sdk is required for Web Core" >&2
    exit 1
fi
if [[ -z "$HOST_CORE_SDK" ]]; then
    echo "ERROR: --host-core-sdk is required for host shader tools" >&2
    exit 1
fi
TARGET_CORE_SDK="$(cd "$TARGET_CORE_SDK" && pwd)"
HOST_CORE_SDK="$(cd "$HOST_CORE_SDK" && pwd)"
TARGET_CORE_MANIFEST="$TARGET_CORE_SDK/termin-core-platform.json"
if [[ ! -f "$TARGET_CORE_MANIFEST" ]]; then
    echo "ERROR: Web Core platform manifest is missing: $TARGET_CORE_MANIFEST" >&2
    exit 1
fi
HOST_CORE_MANIFEST="$HOST_CORE_SDK/termin-artifacts.json"
if [[ ! -f "$HOST_CORE_MANIFEST" ]]; then
    echo "ERROR: host Core artifact manifest is missing: $HOST_CORE_MANIFEST" >&2
    exit 1
fi
if [[ -z "$TARGET_CORE_BUILD_ID" ]]; then
    TARGET_CORE_BUILD_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["native_build_id"])' "$TARGET_CORE_MANIFEST")"
fi
if [[ -z "$HOST_CORE_BUILD_ID" ]]; then
    HOST_CORE_BUILD_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["native_build_id"])' "$HOST_CORE_MANIFEST")"
fi
TARGET_CORE_TOOLCHAIN_VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["target"]["toolchain_version"])' "$TARGET_CORE_MANIFEST")"

emcmake="$EMSDK_DIR/upstream/emscripten/emcmake"
emcc="$EMSDK_DIR/upstream/emscripten/emcc"
if [[ ! -x "$emcmake" || ! -x "$emcc" ]]; then
    echo "ERROR: Emscripten is not installed. Run: $0 --setup" >&2
    exit 1
fi

EMCC_VERSION_OUTPUT="$($emcc --version | head -n 1)"
if [[ "$EMCC_VERSION_OUTPUT" != *" $EMSDK_VERSION "* && "$EMCC_VERSION_OUTPUT" != *" $EMSDK_VERSION" ]]; then
    echo "ERROR: expected Emscripten $EMSDK_VERSION, got: $EMCC_VERSION_OUTPUT" >&2
    exit 1
fi

HOST_SLANGC=""
if [[ -n "${TERMIN_SLANGC:-}" ]]; then
    HOST_SLANGC="$TERMIN_SLANGC"
elif [[ -x "$SCRIPT_DIR/build/toolchains/slang-$SLANG_VERSION/bin/slangc" ]]; then
    HOST_SLANGC="$SCRIPT_DIR/build/toolchains/slang-$SLANG_VERSION/bin/slangc"
elif [[ -x "$SCRIPT_DIR/sdk/bin/termin_python" ]]; then
    HOST_SLANGC="$("$SCRIPT_DIR/scripts/build/setup-slang-toolchain.sh" \
        --require-installed --print-path 2>/dev/null || true)"
fi
if [[ -z "$HOST_SLANGC" ]]; then
    HOST_SLANGC="$(command -v slangc || true)"
fi
if [[ -z "$HOST_SLANGC" || ! -x "$HOST_SLANGC" ]]; then
    echo "ERROR: native slangc is required for offline WebGPU/WebGL2 artifacts; run $0 --setup" >&2
    exit 1
fi

if [[ -n "${TERMIN_WGSL_VALIDATOR:-}" ]]; then
    HOST_WGSL_VALIDATOR="$TERMIN_WGSL_VALIDATOR"
elif [[ -x "$SCRIPT_DIR/build/toolchains/naga-$NAGA_VERSION/bin/naga" ]]; then
    HOST_WGSL_VALIDATOR="$SCRIPT_DIR/build/toolchains/naga-$NAGA_VERSION/bin/naga"
else
    HOST_WGSL_VALIDATOR="$(command -v naga || true)"
fi
if [[ -z "$HOST_WGSL_VALIDATOR" || ! -x "$HOST_WGSL_VALIDATOR" ]]; then
    echo "ERROR: native Naga is required for offline WebGPU artifacts; run 'task toolchain:web-shaders'" >&2
    exit 1
fi

cmake -S "$SCRIPT_DIR" -B "$HOST_BUILD_DIR" -G "Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=Release \
    -DTERMIN_SDK_PROFILE=graphics \
    -DTERMIN_ENABLE_OPENGL=OFF \
    -DTERMIN_ENABLE_WEBGL2=OFF \
    -DTERMIN_ENABLE_VULKAN=OFF \
    -DTERMIN_ENABLE_SDL=OFF \
    -DTERMIN_BUILD_PYTHON=OFF \
    -DTERMIN_BUILD_TESTS=OFF \
    -DTERMIN_BUILD_TGFX2_TESTS=OFF \
    -DTERMIN_BUILD_WINDOW_TESTS=OFF \
    -DTERMIN_CORE_SDK="$HOST_CORE_SDK" \
    -DTERMIN_CORE_BUILD_ID="$HOST_CORE_BUILD_ID"
cmake --build "$HOST_BUILD_DIR" --target termin_shaderc
HOST_SHADERC="$HOST_BUILD_DIR/bin/termin_shaderc"
if [[ ! -x "$HOST_SHADERC" ]]; then
    echo "ERROR: native termin_shaderc was not produced at $HOST_SHADERC" >&2
    exit 1
fi

# Host tools link against the immutable desktop Core SDK, which is deliberately
# outside their build tree. Keep that runtime input explicit while CMake custom
# commands execute termin_shaderc during the cross build.
if [[ "$(uname -s)" == Darwin ]]; then
    export DYLD_LIBRARY_PATH="$HOST_CORE_SDK/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
else
    export LD_LIBRARY_PATH="$HOST_CORE_SDK/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

"$emcmake" cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" -G "Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=Release \
    -DTERMIN_PLATFORM_WEB=ON \
    -DTERMIN_CORE_SDK="$TARGET_CORE_SDK" \
    -DTERMIN_CORE_BUILD_ID="$TARGET_CORE_BUILD_ID" \
    -DTERMIN_CORE_TOOLCHAIN_VERSION="$TARGET_CORE_TOOLCHAIN_VERSION" \
    -DTERMIN_WEB_HOST_SHADERC="$HOST_SHADERC" \
    -DTERMIN_WEB_HOST_SLANGC="$HOST_SLANGC" \
    -DTERMIN_WEB_HOST_WGSL_VALIDATOR="$HOST_WGSL_VALIDATOR"
cmake --build "$BUILD_DIR" --target termin_web_core_node_smoke

if [[ "$RUN_BROWSER_SMOKE" -eq 1 ]]; then
    cmake --build "$BUILD_DIR" --target termin_web_core_browser_smoke
fi

echo "Termin Web core: $BUILD_DIR/bin/termin_web_core.mjs"
