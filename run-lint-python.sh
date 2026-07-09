#!/bin/bash
# Run Python static checks.
#
# This is intentionally separate from run-tests.sh for now: the lint baseline is
# new, so it should be easy to run during cleanup without changing test semantics.
#
# Usage:
#   ./run-lint-python.sh                 # check the repository Python tree
#   ./run-lint-python.sh termin-csg ...  # check selected paths
#   ./run-lint-python.sh --system-python # use PYTHON_BIN / system Python

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEM_PYTHON=0
TARGETS=()

print_usage() {
    printf '%s\n' \
        "Usage: $0 [--system-python] [path ...]" \
        "" \
        "  (no paths)  Check the repository Python tree" \
        "  path        Check selected paths, e.g. termin-csg termin-app/tests" \
        "  --system-python  Bypass the SDK-backed environment"
}

for arg in "$@"; do
    case "$arg" in
        --system-python|--no-venv) SYSTEM_PYTHON=1 ;;
        --help|-h)
            print_usage
            exit 0
            ;;
        --*) echo "Unknown option: $arg" >&2; exit 1 ;;
        *) TARGETS+=("$arg") ;;
    esac
done

if [[ $SYSTEM_PYTHON -eq 0 ]]; then
    SDK_PYTHON="${TERMIN_SDK:-$SCRIPT_DIR/sdk}/bin/termin_python"
    OVERLAY="$SCRIPT_DIR/build/python-envs/test/overlay.json"
    if [[ ! -x "$SDK_PYTHON" || ! -f "$OVERLAY" ]]; then
        echo "SDK-backed Python test environment is not ready." >&2
        echo "Run ./setup-sdk-python-env.sh first." >&2
        exit 1
    fi
    PYTHON_COMMAND=("$SDK_PYTHON" --termin-overlay "$OVERLAY")
else
    if [[ -z "${PYTHON_BIN:-}" ]]; then
        PYTHON_BIN="$(command -v python3 || command -v python || true)"
    fi
    if [[ -z "${PYTHON_BIN:-}" ]]; then
        echo "python3 not found" >&2
        exit 1
    fi
    PYTHON_COMMAND=("$PYTHON_BIN")
fi

if ! "${PYTHON_COMMAND[@]}" -m ruff --version >/dev/null 2>&1; then
    echo "ruff is not installed for: ${PYTHON_COMMAND[*]}" >&2
    echo "Run ./setup-sdk-python-env.sh to install test and lint dependencies." >&2
    exit 1
fi

if (( ${#TARGETS[@]} == 0 )); then
    TARGETS=("$SCRIPT_DIR")
fi

echo "Python: ${PYTHON_COMMAND[*]}"
echo ""
echo "========================================"
echo "  Python lint"
echo "========================================"

"${PYTHON_COMMAND[@]}" -m ruff check "${TARGETS[@]}"
