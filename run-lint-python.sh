#!/bin/bash
# Run Python static checks.
#
# This is intentionally separate from run-tests.sh for now: the lint baseline is
# new, so it should be easy to run during cleanup without changing test semantics.
#
# Usage:
#   ./run-lint-python.sh                 # check the repository Python tree
#   ./run-lint-python.sh termin-csg ...  # check selected paths
#   ./run-lint-python.sh --no-venv ...   # use PYTHON_BIN / system Python

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NO_VENV=0
TARGETS=()

print_usage() {
    printf '%s\n' \
        "Usage: $0 [--no-venv] [path ...]" \
        "" \
        "  (no paths)  Check the repository Python tree" \
        "  path        Check selected paths, e.g. termin-csg termin-app/tests" \
        "  --no-venv   Skip auto-activation; use PYTHON_BIN or system Python"
}

for arg in "$@"; do
    case "$arg" in
        --no-venv) NO_VENV=1 ;;
        --help|-h)
            print_usage
            exit 0
            ;;
        --*) echo "Unknown option: $arg" >&2; exit 1 ;;
        *) TARGETS+=("$arg") ;;
    esac
done

if [[ $NO_VENV -eq 0 && -f "$SCRIPT_DIR/.venv/bin/activate" ]]; then
    echo "Activating venv: $SCRIPT_DIR/.venv"
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
    PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi
if [[ -z "${PYTHON_BIN:-}" ]]; then
    echo "python3 not found" >&2
    exit 1
fi

if ! "$PYTHON_BIN" -m ruff --version >/dev/null 2>&1; then
    echo "ruff is not installed for Python: $PYTHON_BIN" >&2
    echo "Run ./setup-test-venv.sh to install test and lint dependencies." >&2
    exit 1
fi

if (( ${#TARGETS[@]} == 0 )); then
    TARGETS=("$SCRIPT_DIR")
fi

echo "Python: $PYTHON_BIN"
echo ""
echo "========================================"
echo "  Python lint"
echo "========================================"

"$PYTHON_BIN" -m ruff check "${TARGETS[@]}"
