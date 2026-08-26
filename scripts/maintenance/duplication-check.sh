#!/bin/bash
# Run jscpd copy/paste detection for the Termin monorepo.
#
# The default mode is exploratory: it writes console/json/html reports and does
# not fail the shell command when existing duplications are found. Pass
# --threshold to turn it into a quality gate.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

JSCPD_BIN="${JSCPD_BIN:-jscpd}"
MIN_LINES="${JSCPD_MIN_LINES:-8}"
MIN_TOKENS="${JSCPD_MIN_TOKENS:-80}"
REPORTERS="${JSCPD_REPORTERS:-console,json,html}"
OUTPUT_DIR="${JSCPD_OUTPUT_DIR:-/tmp/jscpd-termin-report-own}"
THRESHOLD=""
INCLUDE_THIRDPARTY=0
SILENT=0

TARGETS=()
EXTRA_IGNORES=()

mapfile -t DEFAULT_TARGETS < <(
    python3 - "$SCRIPT_DIR/build-system/districts.json" <<'PY'
import json
import pathlib
import sys

manifest_path = pathlib.Path(sys.argv[1])
repo_root = manifest_path.parents[1]
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
targets = [
    pathlib.PurePosixPath(district["root"], package).as_posix()
    for district in manifest["districts"]
    for package in district["packages"]
]
missing = [target for target in targets if not (repo_root / target).is_dir()]
if missing:
    raise SystemExit("district manifest contains missing packages: " + ", ".join(missing))
print(*targets, sep="\n")
PY
)
if (( ${#DEFAULT_TARGETS[@]} == 0 )); then
    echo "Failed to load default targets from build-system/districts.json" >&2
    exit 1
fi
DEFAULT_TARGETS+=(termin-csharp)

print_usage() {
    printf '%s\n' \
        "Usage: $0 [OPTIONS] [path ...]" \
        "" \
        "  (no paths)              Check first-party repository modules" \
        "  path                    Check selected paths" \
        "  --output DIR            Report output directory (default: $OUTPUT_DIR)" \
        "  --min-lines N           Minimum duplicate length in lines (default: $MIN_LINES)" \
        "  --min-tokens N          Minimum duplicate length in tokens (default: $MIN_TOKENS)" \
        "  --reporters LIST        jscpd reporters (default: $REPORTERS)" \
        "  --threshold PERCENT     Fail when duplicated lines reach the threshold" \
        "  --silent                Suppress detailed jscpd console output" \
        "  --include-thirdparty    Include termin-app/third and termin-thirdparty" \
        "  --list-default-targets  Print manifest-derived default paths and exit" \
        "  --ignore GLOB           Add an ignore glob; can be passed multiple times" \
        "  --help, -h              Show this help" \
        "" \
        "Environment:" \
        "  JSCPD_BIN               jscpd executable (default: jscpd)" \
        "  JSCPD_OUTPUT_DIR        Default report directory" \
        "  JSCPD_MIN_LINES         Default --min-lines value" \
        "  JSCPD_MIN_TOKENS        Default --min-tokens value" \
        "  JSCPD_REPORTERS         Default reporter list"
}

require_value() {
    local option="$1"
    local value="${2:-}"
    if [[ -z "$value" ]]; then
        echo "Missing value for $option" >&2
        exit 1
    fi
}

while (($# > 0)); do
    case "$1" in
        --output)
            require_value "$1" "${2:-}"
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --output=*)
            OUTPUT_DIR="${1#*=}"
            shift
            ;;
        --min-lines)
            require_value "$1" "${2:-}"
            MIN_LINES="$2"
            shift 2
            ;;
        --min-lines=*)
            MIN_LINES="${1#*=}"
            shift
            ;;
        --min-tokens)
            require_value "$1" "${2:-}"
            MIN_TOKENS="$2"
            shift 2
            ;;
        --min-tokens=*)
            MIN_TOKENS="${1#*=}"
            shift
            ;;
        --reporters)
            require_value "$1" "${2:-}"
            REPORTERS="$2"
            shift 2
            ;;
        --reporters=*)
            REPORTERS="${1#*=}"
            shift
            ;;
        --threshold)
            require_value "$1" "${2:-}"
            THRESHOLD="$2"
            shift 2
            ;;
        --threshold=*)
            THRESHOLD="${1#*=}"
            shift
            ;;
        --include-thirdparty)
            INCLUDE_THIRDPARTY=1
            shift
            ;;
        --silent)
            SILENT=1
            shift
            ;;
        --list-default-targets)
            printf '%s\n' "${DEFAULT_TARGETS[@]}"
            exit 0
            ;;
        --ignore)
            require_value "$1" "${2:-}"
            EXTRA_IGNORES+=("$2")
            shift 2
            ;;
        --ignore=*)
            EXTRA_IGNORES+=("${1#*=}")
            shift
            ;;
        --help|-h)
            print_usage
            exit 0
            ;;
        --)
            shift
            TARGETS+=("$@")
            break
            ;;
        --*)
            echo "Unknown option: $1" >&2
            print_usage >&2
            exit 1
            ;;
        *)
            TARGETS+=("$1")
            shift
            ;;
    esac
done

if ! command -v "$JSCPD_BIN" >/dev/null 2>&1; then
    echo "jscpd is not installed or not found: $JSCPD_BIN" >&2
    echo "Install it with: npm install --global jscpd" >&2
    exit 1
fi

if (( ${#TARGETS[@]} == 0 )); then
    TARGETS=("${DEFAULT_TARGETS[@]}")
fi

IGNORES=(
    "**/build/**"
    "**/.venv/**"
    "**/__pycache__/**"
    "**/node_modules/**"
    "**/.gradle/**"
)

if [[ "$INCLUDE_THIRDPARTY" -eq 0 ]]; then
    IGNORES+=(
        "editor/termin-app/third/**"
        "termin-thirdparty/**"
    )
fi

IGNORES+=("${EXTRA_IGNORES[@]}")

ARGS=(
    "${TARGETS[@]}"
    --min-lines "$MIN_LINES"
    --min-tokens "$MIN_TOKENS"
    --reporters "$REPORTERS"
    --output "$OUTPUT_DIR"
    --no-tips
)

IGNORE_PATTERN="${IGNORES[0]}"
for ignore in "${IGNORES[@]:1}"; do
    IGNORE_PATTERN+=",$ignore"
done
ARGS+=(--ignore "$IGNORE_PATTERN")

if [[ -n "$THRESHOLD" ]]; then
    ARGS+=(--threshold "$THRESHOLD")
else
    ARGS+=(--exit-code 0)
fi
if [[ "$SILENT" -eq 1 ]]; then
    ARGS+=(--silent)
fi

cd "$SCRIPT_DIR" || exit 1

echo "jscpd:        $("$JSCPD_BIN" --version)"
echo "output:       $OUTPUT_DIR"
echo "min lines:    $MIN_LINES"
echo "min tokens:   $MIN_TOKENS"
echo "reporters:    $REPORTERS"
if [[ -n "$THRESHOLD" ]]; then
    echo "threshold:    $THRESHOLD"
else
    echo "threshold:    disabled"
fi
if [[ "$INCLUDE_THIRDPARTY" -eq 1 ]]; then
    echo "third-party:  included"
else
    echo "third-party:  excluded"
fi
if [[ "$SILENT" -eq 1 ]]; then
    echo "jscpd output: silent"
fi
echo ""
echo "========================================"
echo "  Code duplication check"
echo "========================================"
echo ""

"$JSCPD_BIN" "${ARGS[@]}"
