#!/bin/bash
# Compile and independently validate the built-in Slang shader catalog as WGSL.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
TOOLCHAIN_ROOT="${TERMIN_WEB_SHADER_TOOLCHAIN_DIR:-$SCRIPT_DIR/build/toolchains}"

if [[ "$SETUP" -eq 1 ]]; then
    "$SCRIPT_DIR/setup-web-shader-toolchain.sh"
fi

SLANGC_PATH="$("$SCRIPT_DIR/setup-slang-toolchain.sh" --require-installed --print-path)"

exec python3 "$SCRIPT_DIR/scripts/audit_webgpu_shaders.py" \
    --slangc "$SLANGC_PATH" \
    --naga "$TOOLCHAIN_ROOT/naga-$NAGA_VERSION/bin/naga" \
    "$@"
