"""Collect an app-local native closure for the Termin Engine NuGet package."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import filecmp
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

from .sdk_native_artifacts import elf_dynamic_entries, pe_import_dependencies


class EngineNugetNativeError(RuntimeError):
    """An installed SDK does not contain a relocatable native runtime."""


# The C# projection also has P/Invoke roots that aren't linked into termin.
# Require these entry points explicitly to catch incomplete or plot-only inputs.
_PINVOKE_ROOTS = (
    "tcplot",
    "termin_base",
    "termin_bootstrap",
    "termin_collision",
    "termin_display",
    "termin_graphics",
    "termin_graphics2",
    "termin_gui_native",
    "termin_gui_native_document_renderer",
    "termin_inspect",
    "termin_mesh",
    "termin_nodegraph_ui",
    "termin_render",
    "termin_scene",
    "termin_visual_scene",
)

_WINDOWS_SYSTEM = frozenset(
    """
    advapi32.dll bcrypt.dll bcryptprimitives.dll combase.dll comdlg32.dll
    crypt32.dll d3d9.dll d3d11.dll d3dcompiler_47.dll dbghelp.dll dwmapi.dll dxgi.dll
    gdi32.dll imm32.dll iphlpapi.dll kernel32.dll kernelbase.dll msvcrt.dll
    ntdll.dll ole32.dll oleaut32.dll opengl32.dll propsys.dll psapi.dll
    rpcrt4.dll setupapi.dll shcore.dll shell32.dll shlwapi.dll ucrtbase.dll
    user32.dll userenv.dll usp10.dll uxtheme.dll version.dll winhttp.dll
    winmm.dll windowscodecs.dll ws2_32.dll
    msvcp140.dll msvcp140_1.dll msvcp140_2.dll vcruntime140.dll
    vcruntime140_1.dll
    """.split()
)
_LINUX_SYSTEM = frozenset(
    """
    ld-linux-x86-64.so.2 libc.so.6 libdl.so.2 libgcc_s.so.1 libm.so.6
    libpthread.so.0 librt.so.1 libstdc++.so.6 libvulkan.so.1
    libGL.so.1 libSDL2-2.0.so.0 libshaderc.so.1
    """.split()
)


def _system_library(name: str, windows: bool) -> bool:
    if windows:
        return name in _WINDOWS_SYSTEM or name.startswith(("api-ms-win-", "ext-ms-win-"))
    return name in _LINUX_SYSTEM


def _library_name(name: str, windows: bool) -> bool:
    pattern = r"[a-z0-9_+.-]+\.dll" if windows else r"[A-Za-z0-9_+.-]+\.so(?:\.[A-Za-z0-9_+.-]+)?"
    return re.fullmatch(pattern, name) is not None


@dataclass(frozen=True)
class _Library:
    dependencies: tuple[str, ...]
    soname: str | None = None
    runpath: tuple[str, ...] = ()


def _inspect(path: Path, windows: bool) -> _Library:
    if windows:
        return _Library(tuple(name.lower() for name in pe_import_dependencies(path, require_x64_dll=True)))

    with path.open("rb") as stream:
        header = stream.read(20)
    if (
        len(header) != 20
        or not header.startswith(b"\x7fELF\x02\x01")
        or struct.unpack_from("<HH", header, 16) != (3, 62)
    ):
        raise EngineNugetNativeError(f"expected an x86-64 shared ELF object: {path}")
    entries = elf_dynamic_entries(path)
    sonames = entries.get("SONAME", [])
    if len(sonames) > 1:
        raise EngineNugetNativeError(f"multiple SONAME entries for {path}: {sonames}")
    return _Library(
        tuple(entries.get("NEEDED", [])),
        sonames[0] if sonames else None,
        tuple(entries.get("RUNPATH", []) + entries.get("RPATH", [])),
    )


def _check_source(path: Path, sdk_prefix: Path) -> Path:
    try:
        source = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise EngineNugetNativeError(f"invalid native SDK input {path}: {error}") from error
    if not source.is_relative_to(sdk_prefix) or not source.is_file():
        raise EngineNugetNativeError(f"native library is not a regular file inside the SDK: {path}")
    return source


def _same_library(first: Path, second: Path) -> bool:
    return first == second or filecmp.cmp(first, second, shallow=False)


def _relocated_payloads(
    sources: dict[str, Path], libraries: dict[Path, _Library], *, windows: bool
) -> dict[str, bytes]:
    if windows:
        return {name: source.read_bytes() for name, source in sorted(sources.items())}

    payloads: dict[Path, bytes] = {}
    with tempfile.TemporaryDirectory(prefix="termin-engine-native-") as work:
        for source in sorted(set(sources.values())):
            library = libraries[source]
            if library.runpath == ("$ORIGIN",):
                payloads[source] = source.read_bytes()
                continue
            if not library.runpath and all(dep not in sources for dep in library.dependencies):
                payloads[source] = source.read_bytes()
                continue
            # Each ELF must find its own direct dependencies beside it. RUNPATH
            # on termin.so alone doesn't apply to its dependencies' children.
            tool = shutil.which("patchelf")
            if tool is None:
                raise EngineNugetNativeError("patchelf is required to relocate the Linux SDK libraries")
            copy = Path(work) / source.name
            shutil.copyfile(source, copy)
            result = subprocess.run(
                [tool, "--set-rpath", "$ORIGIN", str(copy)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode:
                raise EngineNugetNativeError(f"patchelf failed for {source}: {result.stderr.strip()}")
            if _inspect(copy, windows=False).runpath != ("$ORIGIN",):
                raise EngineNugetNativeError(f"failed to make Linux runpath app-local: {source}")
            payloads[source] = copy.read_bytes()
    return {name: payloads[source] for name, source in sorted(sources.items())}


def collect_native(sdk_prefix: Path, rid: str) -> tuple[dict[str, bytes], tuple[str, ...]]:
    """Return native package members and SDK-independent loader dependencies."""
    if rid not in ("win-x64", "linux-x64"):
        raise EngineNugetNativeError(f"unsupported Termin Engine runtime identifier: {rid}")
    sdk_prefix = sdk_prefix.resolve()
    windows = rid == "win-x64"
    projection = sdk_prefix / "csharp" / "runtimes" / rid / "native"
    if not projection.is_dir():
        raise EngineNugetNativeError(f"installed C# runtime directory does not exist: {projection}")

    entries: dict[str, list[Path]] = {}
    roots = []
    for directory in (projection, sdk_prefix / "bin", sdk_prefix / "lib"):
        if not directory.is_dir():
            continue
        if not directory.resolve().is_relative_to(sdk_prefix):
            raise EngineNugetNativeError(f"runtime directory escapes SDK: {directory}")
        for path in sorted(directory.iterdir()):
            name = path.name.lower() if windows else path.name
            if _library_name(name, windows) and not _system_library(name, windows):
                entries.setdefault(name, []).append(path)
                if directory == projection:
                    roots.append(name)

    required = {"termin.dll" if windows else "termin.so"}
    required.update(f"{name}.dll" if windows else f"lib{name}.so" for name in _PINVOKE_ROOTS)
    if missing := required.difference(roots):
        raise EngineNugetNativeError(f"full C# SDK is missing native roots for {rid}: {', '.join(sorted(missing))}")

    sources: dict[str, Path] = {}
    libraries: dict[Path, _Library] = {}
    external = set()
    pending = deque((name, "C# runtime projection") for name in roots)
    while pending:
        name, consumer = pending.popleft()
        if name in sources:
            continue
        if not _library_name(name, windows):
            raise EngineNugetNativeError(f"invalid native dependency {name!r} of {consumer}")
        if _system_library(name, windows):
            external.add(name)
            continue

        candidates = entries.get(name, [])
        if not candidates:
            raise EngineNugetNativeError(f"missing SDK dependency {name} needed by {consumer} ({rid})")
        source, *others = (_check_source(path, sdk_prefix) for path in candidates)
        for other in others:
            if not _same_library(source, other):
                raise EngineNugetNativeError(f"conflicting native libraries for {name}: {source} and {other}")
        sources[name] = source
        if source in libraries:
            continue

        library = _inspect(source, windows)
        libraries[source] = library
        if library.soname:
            if not _library_name(library.soname, windows) or _system_library(library.soname, windows):
                raise EngineNugetNativeError(f"invalid app-local SONAME {library.soname!r} in {source}")
            # Include the SONAME even when it was a symlink in the SDK.
            known = sources.get(library.soname)
            if known is not None and not _same_library(source, known):
                raise EngineNugetNativeError(f"conflicting SONAME {library.soname}: {source} and {known}")
            entries.setdefault(library.soname, []).append(source)
            pending.append((library.soname, name))
        pending.extend((dependency, name) for dependency in library.dependencies)

    return _relocated_payloads(sources, libraries, windows=windows), tuple(sorted(external))
