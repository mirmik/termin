#!/bin/bash
# Run bundled SDK Python with the checkout source overlay.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if (( $# == 1 )) && [[ "$1" == "--help" || "$1" == "-h" ]]; then
    cat <<'EOF'
Usage: ./run-python.sh [python arguments ...]

Runs bundled SDK Python with the checkout source overlay.

Examples:
  ./run-python.sh tcplot/examples/demo_sin.py
  ./run-python.sh -m pytest tcplot/tests/python
  ./run-python.sh -c "import tcplot; print(tcplot.__file__)"
EOF
    exit 0
fi

SDK_ROOT="${TERMIN_SDK:-$SCRIPT_DIR/sdk}"
PYTHON_BIN="${PYTHON_BIN:-$SDK_ROOT/bin/termin_python}"
OVERLAY_MANIFEST="${TERMIN_PYTHON_OVERLAY:-$SCRIPT_DIR/build/python-envs/test/overlay.json}"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "ERROR: SDK Python launcher is missing: $PYTHON_BIN" >&2
    echo "Run ./build-sdk.sh first." >&2
    exit 1
fi
if [[ ! -f "$OVERLAY_MANIFEST" ]]; then
    echo "ERROR: checkout Python overlay is missing: $OVERLAY_MANIFEST" >&2
    echo "Run ./setup-sdk-python-env.sh first." >&2
    exit 1
fi

export PATH="$SDK_ROOT/bin:$SDK_ROOT/lib:$PATH"
export LD_LIBRARY_PATH="$SDK_ROOT/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
unset PYTHONHOME PYTHONPATH PYTHONUSERBASE

exec "$PYTHON_BIN" --termin-overlay "$OVERLAY_MANIFEST" "$@"
