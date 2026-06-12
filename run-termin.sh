#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    cat <<'EOF'
Usage: ./run-termin.sh [PROJECT]

Run the Termin project launcher.

Arguments:
  PROJECT    Optional path to a .terminproj file or to a project directory.
             When provided, the launcher opens that project immediately.
             Without PROJECT, the launcher UI decides what to open.

Notes:
  All non-help arguments are forwarded to sdk/bin/termin_launcher.
  For automation/debugging, prefer direct editor launch:

      ./sdk/bin/termin_editor /path/to/Project.terminproj

  Running ./sdk/bin/termin_editor without arguments opens the last launched
  project.
EOF
    exit 0
fi

exec "$script_dir/sdk/bin/termin_launcher" "$@"
