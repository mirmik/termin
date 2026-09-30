#!/bin/bash
# Run repo tests: working set by default, full set on request.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FULL=0
SDK_PROFILE=""
NO_EDITOR_SMOKE=0
PYTHON_WINDOW_CAPABILITY=1
CPP_ARGS=()

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

        --full)
            FULL=1
            ;;
        --no-editor-smoke)
            NO_EDITOR_SMOKE=1
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS] [run-tests-cpp options]"
            echo ""
            echo "By default this runs the working test set: no window tests,"
            echo "no editor-process smoke tests, and no pytest tests marked full."
            echo ""
            echo "Vulkan is enabled by default for C/C++ tests."
            echo "Use --no-vulkan only for OpenGL/legacy compatibility checks."
            echo ""
            echo "Options:"
            echo "  --profile PRODUCT  Select full, graphics, or core SDK product"
            echo "  --full             Include window tests, full pytest tests, and editor smoke tests"
            echo "  --no-editor-smoke  Skip editor-process smoke tests even with --full"
            echo "  --help, -h         Show this help"
            echo ""
            echo "Other options are passed through to run-tests-cpp.sh."
            exit 0
            ;;
        *)
            if [[ "$arg" == "--no-sdl" ]]; then
                PYTHON_WINDOW_CAPABILITY=0
            elif [[ "$arg" == "--sdl" ]]; then
                PYTHON_WINDOW_CAPABILITY=1
            fi
            CPP_ARGS+=("$arg")
            ;;
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
SDK_PROFILE="$("$CONTEXT_PYTHON" -c "$CONTEXT_BOOTSTRAP" "$SCRIPT_DIR/core/termin-build-tools" "${CONTEXT_ARGS[@]}" --field profile)" || exit 1
SDK_PREFIX="$("$CONTEXT_PYTHON" -c "$CONTEXT_BOOTSTRAP" "$SCRIPT_DIR/core/termin-build-tools" "${CONTEXT_ARGS[@]}" --field sdk-prefix)" || exit 1
export SDK_PREFIX
export TERMIN_SDK="$SDK_PREFIX"
CPP_ARGS+=(--profile "$SDK_PROFILE")
failures=()

if [[ "$FULL" -eq 1 ]]; then
    CPP_ARGS=(--full "${CPP_ARGS[@]}")
fi

PYTHON_ARGS=(--profile "$SDK_PROFILE")
if [[ "$FULL" -eq 1 ]]; then
    PYTHON_ARGS+=(--full)
fi

if ! bash "$SCRIPT_DIR/scripts/test/cpp.sh" "${CPP_ARGS[@]}"; then
    failures+=("C/C++")
fi

TEST_BUILD_TYPE="Release"
for arg in "${CPP_ARGS[@]}"; do
    if [[ "$arg" == "--debug" || "$arg" == "-d" ]]; then
        TEST_BUILD_TYPE="Debug"
    fi
done
if ! bash "$SCRIPT_DIR/scripts/test/setup-python-env.sh" --profile "$SDK_PROFILE"; then
    failures+=("Python environment")
elif ! TERMIN_TEST_CAPABILITIES="$(
        if [[ "$PYTHON_WINDOW_CAPABILITY" -eq 1 ]]; then
            printf 'host,window'
        else
            printf 'host'
        fi
    )" \
    bash "$SCRIPT_DIR/scripts/test/python.sh" "${PYTHON_ARGS[@]}"; then
    failures+=("Python")
fi

if [[ "$SDK_PROFILE" == "full" && "$FULL" -eq 1 && "$NO_EDITOR_SMOKE" -eq 0 ]]; then
    echo ""
    echo "========================================"
    echo "  Editor smoke tests"
    echo "========================================"

    PROCESS_SMOKE_ROOT="$SCRIPT_DIR/build/process-smoke/editor-smoke"
    PROCESS_SMOKE_PLAN="$PROCESS_SMOKE_ROOT/expected.json"
    PROCESS_SMOKE_REPORT="$PROCESS_SMOKE_ROOT/execution-manifest.json"
    mkdir -p "$PROCESS_SMOKE_ROOT"
    PROCESS_PYTHON="$(command -v python3 || command -v python || true)"
    if [[ -z "$PROCESS_PYTHON" ]]; then
        echo "ERROR: Python is required for process-smoke repository control" >&2
        failures+=("Editor smoke")
    elif ! PYTHONPATH="$SCRIPT_DIR/core/termin-build-tools${PYTHONPATH:+:$PYTHONPATH}" \
        "$PROCESS_PYTHON" -m termin_build.repository_control \
            --repo-root "$SCRIPT_DIR" plan editor-smoke --sdk-profile "$SDK_PROFILE" --platform linux --json \
            > "$PROCESS_SMOKE_PLAN"; then
        failures+=("Editor smoke plan")
    else
        EDITOR_SMOKE_CAPABILITIES=(--capability editor)
        if command -v xvfb-run >/dev/null 2>&1 \
            && command -v Xvfb >/dev/null 2>&1 \
            && command -v xauth >/dev/null 2>&1 \
            && command -v glxinfo >/dev/null 2>&1; then
            EDITOR_SMOKE_CAPABILITIES+=(--capability virtual-display)
        else
            echo "Virtual-display editor smoke is inapplicable: xvfb-run, Xvfb, xauth, or glxinfo is missing."
        fi
        PROCESS_EXIT=0
        PYTHONPATH="$SCRIPT_DIR/core/termin-build-tools${PYTHONPATH:+:$PYTHONPATH}" \
            "$PROCESS_PYTHON" -m termin_build.repository_control \
                --repo-root "$SCRIPT_DIR" run editor-smoke --sdk-profile "$SDK_PROFILE" \
                --platform linux \
                --executor process-smoke \
                "${EDITOR_SMOKE_CAPABILITIES[@]}" \
                --configuration "$TEST_BUILD_TYPE" \
                --process-log-dir "$PROCESS_SMOKE_ROOT/logs" \
                --report-output "$PROCESS_SMOKE_REPORT" || PROCESS_EXIT=$?
        VERIFY_EXIT=0
        PYTHONPATH="$SCRIPT_DIR/core/termin-build-tools${PYTHONPATH:+:$PYTHONPATH}" \
            "$PROCESS_PYTHON" -m termin_build.repository_control \
                --repo-root "$SCRIPT_DIR" verify-suite-execution \
                --plan "$PROCESS_SMOKE_PLAN" \
                --manifest "$PROCESS_SMOKE_REPORT" \
                --executor process-smoke || VERIFY_EXIT=$?
        if [[ "$PROCESS_EXIT" -ne 0 || "$VERIFY_EXIT" -ne 0 ]]; then
            failures+=("Editor smoke")
        fi
    fi
else
    echo ""
    echo "========================================"
    echo "  Editor smoke tests skipped (use --full to include)"
    echo "========================================"
fi

if (( ${#failures[@]} > 0 )); then
    echo ""
    echo "========================================"
    echo "  Test failures"
    echo "========================================"
    printf '  - %s\n' "${failures[@]}"
    exit 1
fi

echo ""
echo "========================================"
echo "  All tests passed"
echo "========================================"
