#!/bin/bash
# Create the checkout-local, exactly pinned documentation tool environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_ROOT="${TERMIN_DOCS_ENV:-$SCRIPT_DIR/build/python-envs/docs}"
LOCK_FILE="$SCRIPT_DIR/build-system/python-docs-lock.txt"
STAMP_FILE="$ENV_ROOT/python-docs-lock.txt"
FORCE=0

for arg in "$@"; do
    case "$arg" in
        --force|-f) FORCE=1 ;;
        --help|-h)
            echo "Usage: $0 [--force]"
            echo "Creates build/python-envs/docs from the exact docs lock."
            exit 0
            ;;
        *) echo "ERROR: unknown argument: $arg" >&2; exit 1 ;;
    esac
done

BOOTSTRAP_PYTHON="${PYTHON_BOOTSTRAP:-$(command -v python3 || command -v python || true)}"
if [[ -z "$BOOTSTRAP_PYTHON" ]]; then
    echo "ERROR: bootstrap Python was not found." >&2
    exit 1
fi

DOCS_PYTHON="$ENV_ROOT/bin/python"
if [[ $FORCE -eq 0 && -x "$DOCS_PYTHON" && -f "$STAMP_FILE" ]] \
    && cmp -s "$LOCK_FILE" "$STAMP_FILE"; then
    echo "Documentation environment is up to date: $ENV_ROOT"
    exit 0
fi

echo "Creating documentation environment: $ENV_ROOT"
rm -rf "$ENV_ROOT"
mkdir -p "$(dirname "$ENV_ROOT")"
"$BOOTSTRAP_PYTHON" -I -m venv "$ENV_ROOT"
if ! "$DOCS_PYTHON" -I -m pip install \
    --no-deps \
    --requirement "$LOCK_FILE"; then
    echo "ERROR: documentation tool installation failed" >&2
    rm -rf "$ENV_ROOT"
    exit 1
fi
cp "$LOCK_FILE" "$STAMP_FILE"
"$DOCS_PYTHON" -I -m mkdocs --version
echo "Documentation environment is ready."
