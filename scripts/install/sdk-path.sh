#!/usr/bin/env bash
# Install an idempotent Termin SDK PATH block in the user's Bash configuration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SDK_BIN="$SCRIPT_DIR/sdk/bin"
BEGIN_MARKER="# >>> Termin SDK PATH >>>"
END_MARKER="# <<< Termin SDK PATH <<<"
BASHRC_PATH="${TERMIN_BASHRC:-${HOME:?HOME is not set}/.bashrc}"

if [[ $# -ne 0 ]]; then
    echo "Usage: $0" >&2
    exit 2
fi

mkdir -p "$(dirname "$BASHRC_PATH")"
touch "$BASHRC_PATH"

escaped_sdk_bin="${SDK_BIN//\\/\\\\}"
escaped_sdk_bin="${escaped_sdk_bin//\"/\\\"}"
escaped_sdk_bin="${escaped_sdk_bin//\$/\\\$}"
escaped_sdk_bin="${escaped_sdk_bin//\`/\\\`}"

temporary_file="$(mktemp "${BASHRC_PATH}.termin.XXXXXX")"
trap 'rm -f "$temporary_file"' EXIT

if ! awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
    $0 == begin {
        if (inside) exit 2
        inside = 1
        next
    }
    $0 == end {
        if (!inside) exit 2
        inside = 0
        next
    }
    !inside { print }
    END { if (inside) exit 2 }
' "$BASHRC_PATH" > "$temporary_file"; then
    echo "ERROR: malformed Termin SDK PATH block in $BASHRC_PATH" >&2
    exit 1
fi

if [[ -s "$temporary_file" ]] && [[ "$(tail -c 1 "$temporary_file")" != "" ]]; then
    printf '\n' >> "$temporary_file"
fi

{
    printf '%s\n' "$BEGIN_MARKER"
    printf 'case ":${PATH}:" in\n'
    printf '    *":%s:"*) ;;\n' "$escaped_sdk_bin"
    printf '    *) export PATH="%s:${PATH}" ;;\n' "$escaped_sdk_bin"
    printf 'esac\n'
    printf '%s\n' "$END_MARKER"
} >> "$temporary_file"

chmod --reference="$BASHRC_PATH" "$temporary_file"
mv "$temporary_file" "$BASHRC_PATH"
trap - EXIT

echo "Termin SDK path installed in $BASHRC_PATH"
echo "Open a new Bash shell or run: source \"$BASHRC_PATH\""
