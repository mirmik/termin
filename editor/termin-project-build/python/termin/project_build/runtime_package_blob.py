"""Deterministic indexed blob container for browser runtime packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


MAGIC = b"TRPKG01\n"
BLOB_VERSION = 1


def _validate_relative_path(path: str) -> None:
    if not path or path.startswith("/") or "\\" in path or ":" in path:
        raise ValueError(f"runtime package path must be portable and relative: {path}")
    if any(part in {"", ".", ".."} for part in path.split("/")):
        raise ValueError(
            f"runtime package path must not contain empty or dot segments: {path}"
        )


def build_runtime_package_blob(package_root: str | Path) -> bytes:
    root = Path(package_root).resolve()
    if not root.is_dir():
        raise ValueError(f"runtime package root is not a directory: {root}")
    files = sorted(path for path in root.rglob("*") if path.is_file())
    entries: list[dict[str, int | str]] = []
    payload = bytearray()
    for file_path in files:
        relative = file_path.relative_to(root).as_posix()
        if relative == "package.trpkg":
            continue
        _validate_relative_path(relative)
        if not file_path.resolve().is_relative_to(root):
            raise ValueError(
                f"runtime package path escapes bundle root: {relative}"
            )
        content = file_path.read_bytes()
        entries.append({
            "path": relative,
            "offset": len(payload),
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
        payload.extend(content)
    header = json.dumps(
        {"version": BLOB_VERSION, "entries": entries},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return MAGIC + struct.pack("<I", len(header)) + header + payload


def write_runtime_package_blob(
    package_root: str | Path,
    output_path: str | Path,
) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(build_runtime_package_blob(package_root))
    temporary.replace(destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root")
    parser.add_argument("output_path")
    args = parser.parse_args()
    write_runtime_package_blob(args.package_root, args.output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
