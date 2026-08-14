#!/bin/bash
# Compile and independently validate the built-in Slang shader catalog as WGSL.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOCK_FILE="$SCRIPT_DIR/build-system/web-shader-toolchain-lock.json"
SETUP=0

if [[ "${1:-}" == "--setup" ]]; then
    SETUP=1
    shift
fi

read_lock() {
    python3 - "$LOCK_FILE" "$1" <<'PY'
import json
import pathlib
import sys

value = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
for component in sys.argv[2].split("."):
    value = value[component]
print(value)
PY
}

NAGA_VERSION="$(read_lock naga_cli.version)"
SLANG_VERSION="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "$SCRIPT_DIR/build-system/slang-toolchain-lock.json")"
TOOLCHAIN_ROOT="${TERMIN_WEB_SHADER_TOOLCHAIN_DIR:-$SCRIPT_DIR/build/toolchains}"

if [[ "$SETUP" -eq 1 ]]; then
    "$SCRIPT_DIR/scripts/build/setup-web-shader-toolchain.sh"
fi

SLANGC_PATH="${TERMIN_SLANGC:-$TOOLCHAIN_ROOT/slang-$SLANG_VERSION/bin/slangc}"
if [[ ! -x "$SLANGC_PATH" ]]; then
    echo "ERROR: pinned Slang compiler is missing; run $0 --setup" >&2
    exit 1
fi

exec python3 "$SCRIPT_DIR/scripts/audit_webgpu_shaders.py" \
    --slangc "$SLANGC_PATH" \
    --naga "$TOOLCHAIN_ROOT/naga-$NAGA_VERSION/bin/naga" \
    "$@"
