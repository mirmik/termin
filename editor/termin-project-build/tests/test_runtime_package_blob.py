from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest

from termin.project_build.runtime_package_blob import (
    MAGIC,
    build_runtime_package_blob,
    write_runtime_package_blob,
)


def parse_blob(blob: bytes) -> tuple[dict, bytes]:
    assert blob.startswith(MAGIC)
    header_size = struct.unpack_from("<I", blob, len(MAGIC))[0]
    header_start = len(MAGIC) + 4
    header = json.loads(blob[header_start:header_start + header_size])
    return header, blob[header_start + header_size:]


def test_runtime_package_blob_is_deterministic_and_hash_indexed(tmp_path: Path) -> None:
    package = tmp_path / "package"
    (package / "scenes").mkdir(parents=True)
    (package / "manifest.json").write_text(
        '{"version":3,"world_controller":null}', encoding="utf-8"
    )
    (package / "scenes" / "Main.scene.json").write_bytes(b"scene")

    first = build_runtime_package_blob(package)
    second = build_runtime_package_blob(package)
    assert first == second
    header, payload = parse_blob(first)
    assert header["version"] == 1
    assert [entry["path"] for entry in header["entries"]] == [
        "manifest.json",
        "scenes/Main.scene.json",
    ]
    for entry in header["entries"]:
        content = payload[entry["offset"]:entry["offset"] + entry["size"]]
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]


def test_runtime_package_blob_does_not_include_previous_output(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "manifest.json").write_text("{}", encoding="utf-8")
    output = package / "package.trpkg"
    write_runtime_package_blob(package, output)
    first = output.read_bytes()
    write_runtime_package_blob(package, output)
    assert output.read_bytes() == first


def test_runtime_package_blob_rejects_non_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a directory"):
        build_runtime_package_blob(tmp_path / "missing")


def test_runtime_package_blob_rejects_symlink_escape(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    (package / "escaped.bin").symlink_to(outside)

    with pytest.raises(ValueError, match="escapes bundle root"):
        build_runtime_package_blob(package)
