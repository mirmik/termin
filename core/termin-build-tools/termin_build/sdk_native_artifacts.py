"""Native SDK artifact discovery and binary inspection helpers."""

from __future__ import annotations

import os
import re
import struct
import subprocess
from pathlib import Path

from .python_abi import PythonAbiIdentity


def artifact_roots(build_dir: Path) -> list[Path]:
    roots = []
    for config in ("Release", "Debug", "RelWithDebInfo", "MinSizeRel"):
        roots.append(build_dir / "bin" / config)
    roots.append(build_dir / "bin")
    return roots


def find_native_artifact(
    build_dir: Path,
    target: str,
    *,
    python_abi: PythonAbiIdentity,
) -> Path | None:
    patterns = (
        f"{target}.{python_abi.soabi}.so",
        f"{target}.{python_abi.soabi}.pyd",
        f"{target}.pyd",
        f"{target}.so",
    )
    for root in artifact_roots(build_dir):
        if not root.is_dir():
            continue
        for pattern in patterns:
            matches = sorted(root.glob(pattern))
            if matches:
                return matches[0]
    return None


def elf_dynamic_entries(binary: Path) -> dict[str, list[str]]:
    env = dict(os.environ, LC_ALL="C", LANGUAGE="C")
    try:
        result = subprocess.run(
            ["readelf", "-d", str(binary)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except OSError as error:
        raise RuntimeError(f"failed to execute readelf for {binary}: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"readelf failed for {binary}: {detail}")
    entries: dict[str, list[str]] = {}
    for line in result.stdout.splitlines():
        tag = re.search(r"\((NEEDED|SONAME|RPATH|RUNPATH)\)", line)
        if tag is None:
            continue
        opening = line.rfind("[")
        closing = line.find("]", opening + 1)
        if opening < 0 or closing < 0:
            raise RuntimeError(
                f"readelf returned an unrecognized {tag[1]} entry for {binary}: {line.strip()}"
            )
        entries.setdefault(tag[1], []).append(line[opening + 1 : closing])
    return entries


def pe_import_dependencies(binary: Path, *, require_x64_dll: bool = False) -> list[str]:
    try:
        image = binary.read_bytes()
        if len(image) < 0x40 or image[:2] != b"MZ":
            raise ValueError("missing DOS header")
        pe_offset = struct.unpack_from("<I", image, 0x3C)[0]
        if pe_offset + 24 > len(image) or image[pe_offset : pe_offset + 4] != b"PE\0\0":
            raise ValueError("missing PE header")

        file_header = pe_offset + 4
        machine = struct.unpack_from("<H", image, file_header)[0]
        section_count = struct.unpack_from("<H", image, file_header + 2)[0]
        optional_size = struct.unpack_from("<H", image, file_header + 16)[0]
        characteristics = struct.unpack_from("<H", image, file_header + 18)[0]
        optional = file_header + 20
        if optional + optional_size > len(image):
            raise ValueError("truncated optional header")
        magic = struct.unpack_from("<H", image, optional)[0]
        if require_x64_dll and (machine != 0x8664 or not characteristics & 0x2000 or magic != 0x20B):
            raise ValueError("expected an AMD64 DLL")
        if magic == 0x10B:
            data_directories = optional + 96
            image_base = struct.unpack_from("<I", image, optional + 28)[0]
        elif magic == 0x20B:
            data_directories = optional + 112
            image_base = struct.unpack_from("<Q", image, optional + 24)[0]
        else:
            raise ValueError(f"unsupported optional-header magic 0x{magic:04x}")
        if data_directories + 16 > optional + optional_size:
            raise ValueError("missing import directory")
        directory_count = struct.unpack_from("<I", image, data_directories - 4)[0]

        sections = []
        section_offset = optional + optional_size
        for index in range(section_count):
            entry = section_offset + index * 40
            if entry + 40 > len(image):
                raise ValueError("truncated section table")
            virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
                "<IIII", image, entry + 8
            )
            sections.append(
                (virtual_address, max(virtual_size, raw_size), raw_offset, raw_size)
            )

        def file_offset(rva: int) -> int:
            for virtual_address, span, raw_offset, raw_size in sections:
                delta = rva - virtual_address
                if 0 <= delta < span and delta < raw_size:
                    offset = raw_offset + delta
                    if offset < len(image):
                        return offset
            raise ValueError(f"RVA 0x{rva:x} is outside file-backed sections")

        def import_name(name_rva: int) -> str:
            name_offset = file_offset(name_rva)
            name_end = image.find(b"\0", name_offset)
            if name_end < 0:
                raise ValueError("unterminated import name")
            return image[name_offset:name_end].decode("ascii")

        def import_descriptors(directory: int, width: int):
            directory_offset = data_directories + 8 * directory
            if directory_offset + 8 > optional + optional_size:
                raise ValueError("truncated import data directory")
            start_rva, size = struct.unpack_from("<II", image, directory_offset)
            if not start_rva or not size:
                return
            descriptor = file_offset(start_rva)
            end = min(descriptor + size, len(image))
            stride = 4 * width
            while descriptor + stride <= end:
                fields = struct.unpack_from(f"<{width}I", image, descriptor)
                if not any(fields):
                    return
                yield fields
                descriptor += stride
            raise ValueError("truncated import descriptor table")

        dependencies = [import_name(fields[3]) for fields in import_descriptors(1, 5)]
        if directory_count > 13:
            for fields in import_descriptors(13, 8):
                name_rva = fields[1] if fields[0] & 1 else fields[1] - image_base
                dependencies.append(import_name(name_rva))
        return dependencies
    except (OSError, UnicodeDecodeError, ValueError, struct.error) as error:
        raise RuntimeError(f"failed to inspect PE imports for {binary}: {error}") from error


def find_installed_artifact(
    install_dir: Path,
    extension_name: str,
    target: str,
    *,
    python_abi: PythonAbiIdentity,
) -> Path | None:
    package_path = extension_name.rsplit(".", 1)[0].replace(".", "/")
    patterns = (
        f"{target}.{python_abi.soabi}.so",
        f"{target}.{python_abi.soabi}.pyd",
    )
    candidate_dirs = [
        install_dir / "lib" / "python" / package_path,
        install_dir / "python" / "Lib" / "site-packages" / package_path,
    ]
    lib_dir = install_dir / "lib"
    if lib_dir.is_dir():
        candidate_dirs.extend(
            python_dir / "site-packages" / package_path
            for python_dir in sorted(lib_dir.glob("python*"))
            if python_dir.is_dir()
        )
    for candidate_dir in candidate_dirs:
        if not candidate_dir.is_dir():
            continue
        for pattern in patterns:
            matches = sorted(candidate_dir.glob(pattern))
            if matches:
                return matches[0]
    if install_dir.is_dir():
        for pattern in patterns:
            matches = sorted(install_dir.rglob(pattern))
            if matches:
                return matches[0]
    return None
