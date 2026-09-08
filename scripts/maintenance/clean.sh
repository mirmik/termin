#!/usr/bin/env bash
# Cross-platform clean inventory is owned by clean_inventory.py.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INVENTORY="$ROOT_DIR/scripts/maintenance/clean_inventory.py"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_COMMAND=(python3)
elif command -v python >/dev/null 2>&1; then
    PYTHON_COMMAND=(python)
elif [[ " ${*} " != *" --include-sdk "* && -x "$ROOT_DIR/sdk/bin/termin_python" ]]; then
    PYTHON_COMMAND=("$ROOT_DIR/sdk/bin/termin_python")
else
    echo "ERROR: Python 3 is required to compute the clean inventory." >&2
    exit 1
fi

exec "${PYTHON_COMMAND[@]}" "$INVENTORY" "$@"
