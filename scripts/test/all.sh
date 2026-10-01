#!/bin/bash
# Run repo tests: working set by default, full set on request.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FULL=0
SDK_PROFILE=""
NO_PROCESS_SMOKE=0
PROCESS_SMOKE_ONLY=0
PROCESS_SMOKE_PROFILE="${TERMIN_PROCESS_SMOKE_PROFILE:-}"
PYTHON_MODE="auto"
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
        --python|--no-python)
            if [[ "$arg" == "--python" ]]; then PYTHON_MODE=on; else PYTHON_MODE=off; fi
            CPP_ARGS+=("$arg")
            ;;
        --process-smoke-only)
            PROCESS_SMOKE_ONLY=1
            ;;
        --process-smoke-profile)
            if (( $# == 0 )) || [[ -z "$1" ]]; then
                echo "ERROR: --process-smoke-profile requires a manifest profile." >&2
                exit 1
            fi
            PROCESS_SMOKE_PROFILE="$1"; shift
            ;;
        --process-smoke-profile=*)
            PROCESS_SMOKE_PROFILE="${arg#--process-smoke-profile=}"
            if [[ -z "$PROCESS_SMOKE_PROFILE" ]]; then
                echo "ERROR: --process-smoke-profile cannot be empty." >&2
                exit 1
            fi
            ;;
        --no-editor-smoke|--no-process-smoke)
            NO_PROCESS_SMOKE=1
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
            echo "  --python           Enable Python bindings and Python test phases"
            echo "  --no-python        Disable Python bindings and skip Python test phases"
            echo "  --process-smoke-only Run only the selected installed process-smoke profile"
            echo "  --process-smoke-profile PROFILE Select a manifest profile (default with --full: editor-smoke)"
            echo "  --no-process-smoke Skip process smoke (--no-editor-smoke is an alias)"
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

if [[ "$PROCESS_SMOKE_ONLY" -eq 1 && ( "$NO_PROCESS_SMOKE" -eq 1 || "$PYTHON_MODE" == "off" ) ]]; then
    echo "ERROR: --process-smoke-only cannot be combined with --no-process-smoke or --no-python." >&2
    exit 1
fi

TEST_BUILD_TYPE="Release"
for arg in "${CPP_ARGS[@]}"; do
    if [[ "$arg" == "--debug" || "$arg" == "-d" ]]; then TEST_BUILD_TYPE="Debug"; fi
done

CONTEXT_BOOTSTRAP='import sys; sys.path.insert(0, sys.argv.pop(1)); from termin_build.sdk_test_context import main; raise SystemExit(main())'
CONTEXT_PYTHON="${TERMIN_TEST_TOOLS_PYTHON:-$(command -v python3 || command -v python || true)}"
if [[ -z "$CONTEXT_PYTHON" ]]; then
    echo "ERROR: Python is required to resolve the SDK test context." >&2
    exit 1
fi
CONTEXT_ARGS=(--repo-root "$SCRIPT_DIR" --build-type "$TEST_BUILD_TYPE")
if [[ "$PROCESS_SMOKE_ONLY" -eq 1 ]]; then
    # Installed process checks have no configured test graph. Do not let an
    # unrelated BUILD_DIR influence the selected SDK product.
    CONTEXT_BOOTSTRAP='import os, sys; os.environ.pop("BUILD_DIR", None); sys.path.insert(0, sys.argv.pop(1)); from termin_build.sdk_test_context import main; raise SystemExit(main())'
    CONTEXT_ARGS+=(--installed)
fi
if [[ -n "$SDK_PROFILE" ]]; then
    CONTEXT_ARGS+=(--profile "$SDK_PROFILE")
fi
SDK_PROFILE="$("$CONTEXT_PYTHON" -c "$CONTEXT_BOOTSTRAP" "$SCRIPT_DIR/core/termin-build-tools" "${CONTEXT_ARGS[@]}" --field profile)" || exit 1
SDK_PREFIX="$("$CONTEXT_PYTHON" -c "$CONTEXT_BOOTSTRAP" "$SCRIPT_DIR/core/termin-build-tools" "${CONTEXT_ARGS[@]}" --field sdk-prefix)" || exit 1
BUILD_DIR="$("$CONTEXT_PYTHON" -c "$CONTEXT_BOOTSTRAP" "$SCRIPT_DIR/core/termin-build-tools" "${CONTEXT_ARGS[@]}" --field build-dir)" || exit 1
export SDK_PREFIX BUILD_DIR
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

PYTHON_ENABLED=OFF
if [[ "$PROCESS_SMOKE_ONLY" -eq 1 ]]; then
    PYTHON_ENABLED=ON
    echo "Native/Python suite phases skipped (--process-smoke-only); using installed SDK context."
else
    CPP_SUCCEEDED=0
    if bash "$SCRIPT_DIR/scripts/test/cpp.sh" "${CPP_ARGS[@]}"; then
        CPP_SUCCEEDED=1
    else
        failures+=("C/C++")
    fi
    if [[ "$CPP_SUCCEEDED" -eq 1 ]]; then
        PYTHON_CAPABILITY_BOOTSTRAP='import sys; from pathlib import Path; sys.path.insert(0, sys.argv.pop(1)); from termin_build.sdk_test_context import load_configured_test_python_bindings; print("ON" if load_configured_test_python_bindings(Path(sys.argv[1])) else "OFF")'
        if ! PYTHON_ENABLED="$("$CONTEXT_PYTHON" -c "$PYTHON_CAPABILITY_BOOTSTRAP" "$SCRIPT_DIR/core/termin-build-tools" "$BUILD_DIR")"; then
            failures+=("Python bindings context")
            PYTHON_ENABLED=OFF
        fi
    fi
    if [[ "$PYTHON_ENABLED" == "ON" ]]; then
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
    else
        echo "Python test phases skipped: configured Python bindings are disabled or C/C++ validation failed."
    fi
fi

if [[ -z "$PROCESS_SMOKE_PROFILE" ]]; then
    if [[ "$SDK_PROFILE" == "full" && ( "$FULL" -eq 1 || "$PROCESS_SMOKE_ONLY" -eq 1 ) ]]; then
        PROCESS_SMOKE_PROFILE=editor-smoke
    elif [[ "$PROCESS_SMOKE_ONLY" -eq 1 ]]; then
        PROCESS_SMOKE_PROFILE=sdk-installed
    fi
fi
if [[ "$PYTHON_ENABLED" == "ON" && -n "$PROCESS_SMOKE_PROFILE" && "$NO_PROCESS_SMOKE" -eq 0 ]]; then
    echo ""
    echo "========================================"
    echo "  Process smoke tests ($PROCESS_SMOKE_PROFILE)"
    echo "========================================"

    PROCESS_SMOKE_ROOT="$SCRIPT_DIR/build/process-smoke/$SDK_PROFILE/$PROCESS_SMOKE_PROFILE"
    PROCESS_SMOKE_PLAN="$PROCESS_SMOKE_ROOT/expected.json"
    PROCESS_SMOKE_REPORT="$PROCESS_SMOKE_ROOT/execution-manifest.json"
    export PYTHONPATH="$SCRIPT_DIR/core/termin-build-tools${PYTHONPATH:+:$PYTHONPATH}"
    PROCESS_CONTROL=("$CONTEXT_PYTHON" -m termin_build.repository_control --repo-root "$SCRIPT_DIR")
    if ! PROCESS_PLAN_JSON="$("${PROCESS_CONTROL[@]}" plan "$PROCESS_SMOKE_PROFILE" --sdk-profile "$SDK_PROFILE" --platform linux --json)"; then
        failures+=("Process smoke plan")
    elif ! mkdir -p "$PROCESS_SMOKE_ROOT" || ! printf '%s\n' "$PROCESS_PLAN_JSON" > "$PROCESS_SMOKE_PLAN"; then
        failures+=("Process smoke plan output")
    else
        PROCESS_CAPABILITIES=()
        if [[ -n "${TERMIN_PROCESS_SMOKE_CAPABILITIES:-}" ]]; then
            IFS=',; ' read -r -a CAPABILITY_NAMES <<< "$TERMIN_PROCESS_SMOKE_CAPABILITIES"
            for capability in "${CAPABILITY_NAMES[@]}"; do
                if [[ -n "$capability" ]]; then PROCESS_CAPABILITIES+=(--capability "$capability"); fi
            done
        else
            if [[ "$PROCESS_SMOKE_PROFILE" == "sdk-installed" ]]; then
                PROCESS_CAPABILITIES+=(--capability installed-sdk --capability sdk-relocation)
            elif [[ "$PROCESS_SMOKE_PROFILE" == "editor-smoke" ]]; then
                PROCESS_CAPABILITIES+=(--capability editor)
            fi
            if command -v xvfb-run >/dev/null 2>&1 \
                && command -v Xvfb >/dev/null 2>&1 \
                && command -v xauth >/dev/null 2>&1 \
                && command -v glxinfo >/dev/null 2>&1; then
                PROCESS_CAPABILITIES+=(--capability virtual-display)
            else
                echo "Virtual-display smoke is inapplicable: xvfb-run, Xvfb, xauth, or glxinfo is missing."
            fi
        fi
        PROCESS_EXIT=0
        "${PROCESS_CONTROL[@]}" run "$PROCESS_SMOKE_PROFILE" --sdk-profile "$SDK_PROFILE" \
                --platform linux \
                --executor process-smoke \
                "${PROCESS_CAPABILITIES[@]}" \
                --configuration "$TEST_BUILD_TYPE" \
                --process-timeout "${TERMIN_PROCESS_SMOKE_TIMEOUT:-900}" \
                --process-log-dir "$PROCESS_SMOKE_ROOT/logs" \
                --report-output "$PROCESS_SMOKE_REPORT" || PROCESS_EXIT=$?
        VERIFY_EXIT=0
        "${PROCESS_CONTROL[@]}" verify-suite-execution \
                --plan "$PROCESS_SMOKE_PLAN" \
                --manifest "$PROCESS_SMOKE_REPORT" \
                --executor process-smoke || VERIFY_EXIT=$?
        if [[ "$PROCESS_EXIT" -ne 0 || "$VERIFY_EXIT" -ne 0 ]]; then
            failures+=("Process smoke")
        fi
    fi
else
    echo ""
    echo "========================================"
    echo "  Process smoke tests skipped (use --full or --process-smoke-profile)"
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
