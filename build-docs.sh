#!/bin/bash
# Validate and build every public documentation site from the repository plan.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_ROOT="${TERMIN_DOCS_ENV:-$SCRIPT_DIR/build/python-envs/docs}"
DOCS_PYTHON="$ENV_ROOT/bin/python"
SITE_ROOT="${TERMIN_DOCS_SITE:-$SCRIPT_DIR/_site}"
PLAN_FILE="$SCRIPT_DIR/build/docs-plan.tsv"

"$SCRIPT_DIR/setup-docs-env.sh"

export PYTHONPATH="$SCRIPT_DIR/termin-build-tools${PYTHONPATH:+:$PYTHONPATH}"
"$DOCS_PYTHON" -m termin_build.repository_control --repo-root "$SCRIPT_DIR" check
mkdir -p "$(dirname "$PLAN_FILE")"
"$DOCS_PYTHON" -m termin_build.repository_control \
    --repo-root "$SCRIPT_DIR" docs-plan > "$PLAN_FILE"

rm -rf "$SITE_ROOT"
mkdir -p "$SITE_ROOT"
while IFS=$'\t' read -r module config site_path; do
    if [[ -z "$module" || -z "$config" || -z "$site_path" ]]; then
        echo "ERROR: invalid documentation plan entry" >&2
        exit 1
    fi
    echo "=== Building $module docs ==="
    "$DOCS_PYTHON" -I -m mkdocs build \
        --strict \
        --config-file "$SCRIPT_DIR/$config" \
        --site-dir "$SITE_ROOT/$site_path"
done < "$PLAN_FILE"

echo "Documentation site built at: $SITE_ROOT"
