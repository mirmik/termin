#!/bin/bash
# Compatibility entry point for the SDK-backed Python test environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "setup-test-venv.sh now creates an SDK-backed checkout overlay."
exec "$SCRIPT_DIR/setup-sdk-python-env.sh" "$@"
