#!/bin/bash
# Create checkout-local test tooling and a source overlay over bundled SDK Python.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SDK_PROFILE=""
TOOLS_REQUIREMENTS="$SCRIPT_DIR/build-system/python-test-requirements.txt"
BUILD_TOOLS_ROOT="$SCRIPT_DIR/core/termin-build-tools"
PYTHON_BUILD_ENV="${TERMIN_PYTHON_BUILD_ENV:-$SCRIPT_DIR/build/python-runtime/build-env}"
TEST_TOOLS_PYTHON="${TERMIN_TEST_TOOLS_PYTHON:-$PYTHON_BUILD_ENV/bin/python}"
FORCE=0

while (( $# > 0 )); do
    arg="$1"; shift
    case "$arg" in
        --profile)
            if (( $# == 0 )); then
                echo "ERROR: --profile requires full, graphics, or core." >&2
                exit 1
            fi
            SDK_PROFILE="$1"; shift
            if [[ -z "$SDK_PROFILE" ]]; then echo "ERROR: --profile cannot be empty." >&2; exit 1; fi ;;
        --profile=*) SDK_PROFILE="${arg#--profile=}"
            if [[ -z "$SDK_PROFILE" ]]; then echo "ERROR: --profile cannot be empty." >&2; exit 1; fi ;;

        --force|-f) FORCE=1 ;;
        --help|-h)
            echo "Usage: $0 [--profile full|graphics|core] [--force]"
            echo "Creates build/python-envs/test using bundled SDK Python."
            exit 0
            ;;
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

CONTEXT_BOOTSTRAP='import sys; sys.path.insert(0, sys.argv.pop(1)); from termin_build.sdk_test_context import main; raise SystemExit(main())'
CONTEXT_PYTHON="${TERMIN_TEST_TOOLS_PYTHON:-$(command -v python3 || command -v python || true)}"
if [[ -z "$CONTEXT_PYTHON" ]]; then
    echo "ERROR: Python is required to resolve the SDK test context." >&2
    exit 1
fi
CONTEXT_ARGS=(--repo-root "$SCRIPT_DIR")
if [[ -n "$SDK_PROFILE" ]]; then
    CONTEXT_ARGS+=(--profile "$SDK_PROFILE")
fi
CONTEXT_ARGS+=(--installed)
SDK_PROFILE="$("$CONTEXT_PYTHON" -c "$CONTEXT_BOOTSTRAP" "$SCRIPT_DIR/core/termin-build-tools" "${CONTEXT_ARGS[@]}" --field profile)" || exit 1
SDK_PREFIX="$("$CONTEXT_PYTHON" -c "$CONTEXT_BOOTSTRAP" "$SCRIPT_DIR/core/termin-build-tools" "${CONTEXT_ARGS[@]}" --field sdk-prefix)" || exit 1
SDK_ROOT="$SDK_PREFIX"
SDK_PYTHON="$SDK_ROOT/bin/termin_python"
ENV_ROOT="$("$CONTEXT_PYTHON" -c "$CONTEXT_BOOTSTRAP" "$BUILD_TOOLS_ROOT" "${CONTEXT_ARGS[@]}" --field environment-root)" || exit 1
if [[ -n "${TERMIN_PYTHON_OVERLAY:-}" ]]; then
    OVERLAY_MANIFEST="$TERMIN_PYTHON_OVERLAY"
    ENV_ROOT="$(dirname "$OVERLAY_MANIFEST")"
else
    OVERLAY_MANIFEST="$ENV_ROOT/overlay.json"
fi
TOOLS_SITE="$ENV_ROOT/site-packages"

if [[ ! -x "$SDK_PYTHON" ]]; then
    echo "ERROR: isolated SDK Python launcher is missing: $SDK_PYTHON" >&2
    echo "Run task build first." >&2
    exit 1
fi

if [[ ! -x "$TEST_TOOLS_PYTHON" ]]; then
    echo "ERROR: pinned SDK Python build frontend is missing: $TEST_TOOLS_PYTHON" >&2
    echo "Run task build first." >&2
    exit 1
fi

ENVIRONMENT_BOOTSTRAP='import sys; sys.path.insert(0, sys.argv.pop(1)); from termin_build.python_test_environment import main; raise SystemExit(main())'
PREPARE_ARGS=(
    prepare
    --environment-root "$ENV_ROOT"
    --requirements "$TOOLS_REQUIREMENTS"
    --installer-python "$TEST_TOOLS_PYTHON"
)
if [[ $FORCE -eq 1 ]]; then
    PREPARE_ARGS+=(--force)
fi
"$SDK_PYTHON" -c "$ENVIRONMENT_BOOTSTRAP" "$BUILD_TOOLS_ROOT" \
    "${PREPARE_ARGS[@]}"

echo "Generating checkout overlay: $OVERLAY_MANIFEST"
OVERLAY_BOOTSTRAP='import sys; sys.path.insert(0, sys.argv.pop(1)); from termin_build.python_overlay import main; raise SystemExit(main())'
"$SDK_PYTHON" -c "$OVERLAY_BOOTSTRAP" "$BUILD_TOOLS_ROOT" \
    --repo-root "$SCRIPT_DIR" \
    --sdk-root "$SDK_ROOT" \
    --output "$OVERLAY_MANIFEST" \
    --extra-site "$TOOLS_SITE"

echo "SDK-backed Python test environment is ready."
echo "Run: task test:python -- --profile=$SDK_PROFILE"
