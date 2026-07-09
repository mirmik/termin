#!/usr/bin/env bash
# Clean build artifacts across all termin-env projects.
#
# Usage:
#   ./clean-all.sh
#   ./clean-all.sh --dry-run
#   ./clean-all.sh --include-sdk

set -euo pipefail

DRY_RUN=0
INCLUDE_SDK=0

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --include-sdk) INCLUDE_SDK=1 ;;
        --help|-h)
            echo "Usage: ./clean-all.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run      Show what would be removed without deleting"
            echo "  --include-sdk  Also remove local sdk/ and /opt/termin"
            echo "  --help, -h     Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            exit 1
            ;;
    esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TARGETS=()

PROJECT_ROOTS=("$ROOT_DIR")

while IFS= read -r -d '' pyproject; do
    project_root="$(dirname "$pyproject")"
    case "$project_root" in
        "$ROOT_DIR/termin-thirdparty/"*) continue ;;
    esac
    PROJECT_ROOTS+=("$project_root")
done < <(
    find "$ROOT_DIR" \
        -path "$ROOT_DIR/.git" -prune -o \
        -path "$ROOT_DIR/build" -prune -o \
        -path "$ROOT_DIR/sdk" -prune -o \
        -path "$ROOT_DIR/.venv" -prune -o \
        -type f -name 'pyproject.toml' -print0
)

PROJECT_ROOTS+=(
    "$ROOT_DIR/termin-app"
    "$ROOT_DIR/termin-app/cpp"
    "$ROOT_DIR/termin-csharp"
)

ARTIFACT_DIR_NAMES=(
    build
    build_standalone
    build_win
    dist
    install
    install_win
)

for project_root in "${PROJECT_ROOTS[@]}"; do
    [[ -d "$project_root" ]] || continue

    for name in "${ARTIFACT_DIR_NAMES[@]}"; do
        p="$project_root/$name"
        if [[ -e "$p" ]]; then
            TARGETS+=("$p")
        fi
    done
done

for p in \
    "$ROOT_DIR/termin-app/build_standalone" \
    "$ROOT_DIR/termin-app/install" \
    "$ROOT_DIR/termin-app/cpp/build"
do
    if [[ -e "$p" ]]; then
        TARGETS+=("$p")
    fi
done

for project_root in "${PROJECT_ROOTS[@]}"; do
    [[ -d "$project_root" ]] || continue

    while IFS= read -r -d '' d; do
        TARGETS+=("$d")
    done < <(
        find "$project_root" \
            -path "$ROOT_DIR/.git" -prune -o \
            -path "$ROOT_DIR/build" -prune -o \
            -path "$ROOT_DIR/sdk" -prune -o \
            -path "$ROOT_DIR/.venv" -prune -o \
            -path '*/.git' -prune -o \
            -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '*.egg-info' \) \
            -print0
    )

done

if [[ -d "$ROOT_DIR/termin-csharp" ]]; then
    while IFS= read -r -d '' d; do
        TARGETS+=("$d")
    done < <(
        find "$ROOT_DIR/termin-csharp" \
            -type d \( -name 'bin' -o -name 'obj' \) -print0
    )
fi

if [[ "$INCLUDE_SDK" -eq 1 ]]; then
    [[ -e "$ROOT_DIR/sdk" ]] && TARGETS+=("$ROOT_DIR/sdk")
    [[ -e "/opt/termin" ]] && TARGETS+=("/opt/termin")
fi

if [[ "${#TARGETS[@]}" -eq 0 ]]; then
    echo "Nothing to clean."
    exit 0
fi

mapfile -t FINAL_TARGETS < <(printf '%s\n' "${TARGETS[@]}" | awk '!seen[$0]++' | awk '{ print length($0) "\t" $0 }' | sort -nr | cut -f2-)

echo "Targets to clean: ${#FINAL_TARGETS[@]}"
for t in "${FINAL_TARGETS[@]}"; do
    echo "  $t"
done

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo ""
    echo "Dry run complete. Nothing was deleted."
    exit 0
fi

REMOVED=0
for t in "${FINAL_TARGETS[@]}"; do
    if [[ -e "$t" ]]; then
        rm -rf "$t"
        REMOVED=$((REMOVED + 1))
    fi
done

echo ""
echo "Clean complete. Removed: $REMOVED"
