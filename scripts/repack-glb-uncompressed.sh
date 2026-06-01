#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  scripts/repack-glb-uncompressed.sh INPUT.glb OUTPUT.glb [--dequantize] [--validate]

Rewrites a GLB with glTF-Transform so meshopt-compressed buffers are decoded
and the output no longer requires EXT_meshopt_compression.

Options:
  --dequantize  Also remove KHR_mesh_quantization by expanding quantized
                attributes to regular component types. This increases size,
                but helps older importers.
  --validate    Run gltf-transform validate on the result.

Install dependency:
  npm install --global @gltf-transform/cli
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ $# -lt 2 ]]; then
    usage
    exit 2
fi

input=$1
output=$2
shift 2

dequantize=0
validate=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dequantize)
            dequantize=1
            ;;
        --validate)
            validate=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

if [[ ! -f "$input" ]]; then
    echo "Input file does not exist: $input" >&2
    exit 1
fi

if ! command -v gltf-transform >/dev/null 2>&1; then
    cat >&2 <<'ERROR'
Missing command: gltf-transform

Install it with:
  npm install --global @gltf-transform/cli

Then rerun this script.
ERROR
    exit 127
fi

mkdir -p "$(dirname "$output")"

tmp_output=$(mktemp --suffix=.glb)
trap 'rm -f "$tmp_output"' EXIT

echo "Repacking without EXT_meshopt_compression..."
gltf-transform copy "$input" "$tmp_output"

if [[ "$dequantize" -eq 1 ]]; then
    dequantized_output=$(mktemp --suffix=.glb)
    trap 'rm -f "$tmp_output" "$dequantized_output"' EXIT
    echo "Dequantizing geometry attributes..."
    gltf-transform dequantize "$tmp_output" "$dequantized_output"
    mv "$dequantized_output" "$tmp_output"
fi

mv "$tmp_output" "$output"
trap - EXIT

python3 - "$output" <<'PY'
import json
import struct
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = path.read_bytes()

if len(data) < 20:
    print(f"Invalid GLB, file is too small: {path}", file=sys.stderr)
    sys.exit(1)

magic, version, declared_length = struct.unpack_from("<4sII", data, 0)
if magic != b"glTF" or version != 2:
    print(f"Invalid GLB header: magic={magic!r}, version={version}", file=sys.stderr)
    sys.exit(1)

if declared_length != len(data):
    print(
        f"Invalid GLB length: header={declared_length}, actual={len(data)}",
        file=sys.stderr,
    )
    sys.exit(1)

offset = 12
document = None
while offset + 8 <= len(data):
    chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
    offset += 8
    chunk_name = chunk_type.to_bytes(4, "little")
    chunk = data[offset : offset + chunk_length]
    offset += chunk_length
    if chunk_name == b"JSON":
        document = json.loads(chunk.rstrip(b" \t\r\n\0"))
        break

if document is None:
    print(f"GLB has no JSON chunk: {path}", file=sys.stderr)
    sys.exit(1)

required_extensions = document.get("extensionsRequired", [])
used_extensions = document.get("extensionsUsed", [])

if "EXT_meshopt_compression" in required_extensions:
    print(
        "Repack failed: EXT_meshopt_compression is still required.",
        file=sys.stderr,
    )
    sys.exit(1)

print(f"Wrote: {path}")
print(f"extensionsUsed: {used_extensions}")
print(f"extensionsRequired: {required_extensions}")
PY

if [[ "$validate" -eq 1 ]]; then
    gltf-transform validate "$output"
fi
