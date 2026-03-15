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

PROJECT_ROOTS=(
    "$ROOT_DIR/termin-base"
    "$ROOT_DIR/termin-mesh"
    "$ROOT_DIR/termin-graphics"
    "$ROOT_DIR/termin-inspect"
    "$ROOT_DIR/termin-scene"
    "$ROOT_DIR/termin-collision"
    "$ROOT_DIR/termin-components/termin-components-collision"
    "$ROOT_DIR/termin-components/termin-components-mesh"
    "$ROOT_DIR/termin-components/termin-components-kinematic"
    "$ROOT_DIR/termin-gui"
    "$ROOT_DIR/termin-nodegraph"
    "$ROOT_DIR/termin"
)

EXPLICIT_DIRS=(
    "termin-base/build" "termin-base/dist" "termin-base/install" "termin-base/install_win"
    "termin-mesh/build" "termin-mesh/dist" "termin-mesh/install" "termin-mesh/install_win"
    "termin-graphics/build" "termin-graphics/dist" "termin-graphics/install" "termin-graphics/install_win"
    "termin-inspect/build" "termin-inspect/dist" "termin-inspect/install" "termin-inspect/install_win"
    "termin-scene/build" "termin-scene/dist" "termin-scene/install" "termin-scene/install_win"
    "termin-collision/build" "termin-collision/dist" "termin-collision/install" "termin-collision/install_win"
    "termin-components/termin-components-collision/build" "termin-components/termin-components-collision/dist" "termin-components/termin-components-collision/install"
    "termin-components/termin-components-mesh/build" "termin-components/termin-components-mesh/dist" "termin-components/termin-components-mesh/install"
    "termin-components/termin-components-kinematic/build" "termin-components/termin-components-kinematic/dist" "termin-components/termin-components-kinematic/install"
    "termin-gui/build" "termin-gui/dist"
    "termin-nodegraph/build" "termin-nodegraph/dist"
    "termin/build_win" "termin/build_standalone" "termin/install" "termin/install_win" "termin/cpp/build"
)

TARGETS=()

for rel in "${EXPLICIT_DIRS[@]}"; do
    p="$ROOT_DIR/$rel"
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
            -path '*/.git' -prune -o \
            -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '*.egg-info' \) \
            -print0
    )

    if [[ -d "$project_root/termin/csharp" ]]; then
        while IFS= read -r -d '' d; do
            TARGETS+=("$d")
        done < <(
            find "$project_root/termin/csharp" \
                -type d \( -name 'bin' -o -name 'obj' \) -print0
        )
    fi
done

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
