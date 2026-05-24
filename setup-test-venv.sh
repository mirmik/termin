#!/bin/bash
# Setup a Python virtual environment for running termin tests.
#
# Creates a venv at .venv/ (or the path given as the first argument), installs
# build and test dependencies, then installs all termin packages in editable
# mode so Python source changes take effect immediately without reinstallation.
#
# Usage:
#   ./setup-test-venv.sh              # creates .venv/
#   ./setup-test-venv.sh /path/venv   # custom path
#   ./setup-test-venv.sh --force      # force-reinstall .so bindings from SDK

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR=""
FORCE=0

for arg in "$@"; do
    case "$arg" in
        --force|-f) FORCE=1 ;;
        --help|-h)
            echo "Usage: $0 [PATH] [--force]"
            echo ""
            echo "Options:"
            echo "  PATH          Venv directory (default: .venv/)"
            echo "  --force, -f   Force-reinstall to pick up rebuilt .so bindings"
            echo "  --help, -h    Show this help"
            exit 0
            ;;
        *) VENV_DIR="$arg" ;;
    esac
done

VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv}"

echo "=== setting up test venv: $VENV_DIR ==="

# 1. Create venv
if [[ -d "$VENV_DIR" ]]; then
    echo "venv already exists, reusing: $VENV_DIR"
else
    python3 -m venv "$VENV_DIR"
    echo "venv created: $VENV_DIR"
fi

# 2. Activate
source "$VENV_DIR/bin/activate"

# 3. Build-time dependencies (needed by --no-build-isolation)
echo ""
echo "--- installing build dependencies ---"
pip install --upgrade pip setuptools wheel nanobind

# 4. Runtime and test dependencies
echo ""
echo "--- installing runtime and test dependencies ---"
pip install numpy scipy Pillow pytest PyYAML pysdl2 pysdl2-dll

# 5. Locate and export TERMIN_SDK
_sdk_valid() { [[ -d "$1/lib" ]]; }

if [[ -n "$TERMIN_SDK" ]]; then
    if ! _sdk_valid "$TERMIN_SDK"; then
        echo "WARNING: TERMIN_SDK=$TERMIN_SDK does not contain lib/" >&2
    fi
elif _sdk_valid "$SCRIPT_DIR/sdk"; then
    export TERMIN_SDK="$SCRIPT_DIR/sdk"
elif _sdk_valid "/opt/termin"; then
    export TERMIN_SDK="/opt/termin"
else
    echo "ERROR: termin SDK not found." >&2
    echo "  Run build-sdk-cpp.sh and build-sdk-bindings.sh first." >&2
    exit 1
fi
echo "TERMIN_SDK=$TERMIN_SDK"

# 6. Install termin packages in editable mode
echo ""
echo "--- installing termin packages (editable) ---"
FORCE_FLAG=()
if [[ $FORCE -eq 1 ]]; then
    FORCE_FLAG=(--force)
fi
bash "$SCRIPT_DIR/install-pip-packages.sh" --editable "${FORCE_FLAG[@]}"

echo ""
echo "=== test venv ready: $VENV_DIR ==="
echo ""
echo "To use it:"
echo "  source $VENV_DIR/bin/activate"
echo "  TERMIN_SDK=$TERMIN_SDK bash run-tests-python.sh"
