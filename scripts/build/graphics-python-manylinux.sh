#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHONPATH="$REPO_ROOT/core/termin-build-tools${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m termin_build.graphics_python_manylinux --repo-root "$REPO_ROOT" -- "$@"
