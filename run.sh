#!/bin/bash
# Termin run script
# Usage:
#   ./run.sh                # Run editor
#   ./run.sh --launcher     # Run launcher (UIRenderer test)
#   ./run.sh --gdb          # Run editor under gdb
#   ./run.sh --valgrind     # Run under valgrind

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/install"

# Select executable
EXE="$INSTALL_DIR/bin/termin_editor"
if [[ "${1:-}" == "--launcher" || "${1:-}" == "-l" ]]; then
    EXE="$INSTALL_DIR/bin/termin_launcher"
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
