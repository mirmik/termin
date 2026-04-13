#!/bin/bash
# Termin run script
# Usage:
#   ./run.sh                # Run launcher
#   ./run.sh --editor       # Run editor directly
#   ./run.sh --gdb          # Run launcher under gdb
#   ./run.sh --valgrind     # Run under valgrind

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/install"
export LD_LIBRARY_PATH="$INSTALL_DIR/lib:${LD_LIBRARY_PATH:-}"

# Select executable
EXE="$INSTALL_DIR/bin/termin_launcher"
if [[ "${1:-}" == "--editor" || "${1:-}" == "-e" ]]; then
    EXE="$INSTALL_DIR/bin/termin_editor"
    shift
fi

if [[ ! -f "$EXE" ]]; then
    echo "Not found: $EXE"
    echo "Run ./build.sh first"
    exit 1
fi

case "${1:-}" in
    --gdb|-g)
        shift
        exec gdb --args "$EXE" "$@"
        ;;
    --valgrind|-v)
        shift
        exec valgrind --leak-check=full "$EXE" "$@"
        ;;
    *)
        exec "$EXE" "$@"
        ;;
esac
