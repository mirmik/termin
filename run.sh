#!/bin/bash
# Termin run script
# Usage:
#   ./run.sh           # Run editor
#   ./run.sh --gdb     # Run under gdb
#   ./run.sh --valgrind # Run under valgrind

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/install"
EDITOR="$INSTALL_DIR/bin/termin_editor"

if [[ ! -f "$EDITOR" ]]; then
    echo "Editor not found at $EDITOR"
    echo "Run ./build.sh first"
    exit 1
fi

cd "$INSTALL_DIR"
export LD_LIBRARY_PATH="./lib/python/termin:./lib:$LD_LIBRARY_PATH"

case "${1:-}" in
    --gdb|-g)
        shift
        exec gdb --args ./bin/termin_editor "$@"
        ;;
    --valgrind|-v)
        shift
        exec valgrind --leak-check=full ./bin/termin_editor "$@"
        ;;
    *)
        exec ./bin/termin_editor "$@"
        ;;
esac
