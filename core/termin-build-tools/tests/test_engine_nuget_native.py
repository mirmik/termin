"""Native libraries in a Termin Engine package must load outside the SDK."""

from pathlib import Path
import os
import shutil
import struct
import subprocess
import sys

import pytest

from termin_build import engine_nuget_native as native


@pytest.fixture()
def sdk(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "_PINVOKE_ROOTS", ())
    root = tmp_path / "sdk"
    for name in ("lib", "bin", "csharp/runtimes/linux-x64/native", "csharp/runtimes/win-x64/native"):
        (root / name).mkdir(parents=True)
    return root


def _projection(sdk: Path, rid: str) -> Path:
    return sdk / "csharp" / "runtimes" / rid / "native"


def _compile_shared(path, source, *flags):
    subprocess.run(
        ["cc", "-shared", "-fPIC", "-x", "c", "-", *flags, "-o", str(path)],
        input=source,
        text=True,
        check=True,
    )


@pytest.mark.skipif(
    not sys.platform.startswith("linux") or not all(shutil.which(tool) for tool in ("cc", "readelf", "patchelf")),
    reason="requires the Linux packaging toolchain",
)
def test_linux_soname_and_transitive_library_load_without_sdk(sdk, tmp_path):
    projection = _projection(sdk, "linux-x64")
    installed = sdk / "lib"
    leaf = installed / "libleaf.so.1"
    middle = installed / "libmiddle.so.2.3"
    root = projection / "termin.so"
    _compile_shared(leaf, "int leaf(void) { return 42; }", "-Wl,-soname,libleaf.so.1")
    _compile_shared(
        middle,
        "extern int leaf(void); int middle(void) { return leaf(); }",
        "-Wl,-soname,libmiddle.so.2",
        f"-L{installed}",
        "-l:libleaf.so.1",
    )
    _compile_shared(
        root,
        "extern int middle(void); int answer(void) { return middle(); }",
        f"-L{installed}",
        "-l:libmiddle.so.2.3",
        f"-Wl,-rpath,{installed}",
    )
    (projection / "libmiddle.so").symlink_to(middle)
    original = root.read_bytes()

    payloads, system = native.collect_native(sdk, "linux-x64")

    assert set(payloads) == {"termin.so", "libmiddle.so", "libmiddle.so.2", "libleaf.so.1"}
    assert payloads["libmiddle.so"] == payloads["libmiddle.so.2"]
    assert "libleaf.so.1" not in system
    assert root.read_bytes() == original
    app = tmp_path / "app"
    app.mkdir()
    for name, content in payloads.items():
        (app / name).write_bytes(content)
    sdk.rename(tmp_path / "old-sdk")
    command = "import ctypes, sys; assert ctypes.CDLL(sys.argv[1]).answer() == 42"
    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)
    subprocess.run([sys.executable, "-I", "-c", command, str(app / "termin.so")], env=env, check=True)


def _write_pe(path: Path, *, regular: str = "", delayed: str = "", machine: int = 0x8664):
    """Write the PE headers and import tables exercised by the dependency parser."""
    binary = bytearray(0x600)
    binary[:2] = b"MZ"
    struct.pack_into("<I", binary, 0x3C, 0x80)
    binary[0x80:0x84] = b"PE\0\0"
    file_header = 0x84
    struct.pack_into("<HH", binary, file_header, machine, 1)
    struct.pack_into("<HH", binary, file_header + 16, 240, 0x2000)
    optional = file_header + 20
    struct.pack_into("<H", binary, optional, 0x20B)
    struct.pack_into("<I", binary, optional + 108, 16)
    directories = optional + 112
    section_table = optional + 240
    struct.pack_into("<IIII", binary, section_table + 8, 0x400, 0x1000, 0x400, 0x200)
    if regular:
        struct.pack_into("<II", binary, directories + 8, 0x1000, 40)
        struct.pack_into("<IIIII", binary, 0x200, 0, 0, 0, 0x1080, 0)
        value = regular.encode("ascii") + b"\0"
        binary[0x280 : 0x280 + len(value)] = value
    if delayed:
        struct.pack_into("<II", binary, directories + 13 * 8, 0x1100, 64)
        struct.pack_into("<II", binary, 0x300, 1, 0x1180)
        value = delayed.encode("ascii") + b"\0"
        binary[0x380 : 0x380 + len(value)] = value
    path.write_bytes(binary)


def test_windows_normal_and_delay_load_imports(sdk):
    projection = _projection(sdk, "win-x64")
    _write_pe(projection / "termin.dll", regular="Middle.DLL", delayed="Delayed.DLL")
    _write_pe(sdk / "bin" / "middle.dll", regular="Kernel32.dll")
    _write_pe(sdk / "bin" / "delayed.dll", regular="VCRUNTIME140.dll")

    payloads, system = native.collect_native(sdk, "win-x64")

    assert set(payloads) == {"termin.dll", "middle.dll", "delayed.dll"}
    assert system == ("kernel32.dll", "vcruntime140.dll")


def test_missing_windows_dependency_names_consumer(sdk):
    projection = _projection(sdk, "win-x64")
    _write_pe(projection / "termin.dll", delayed="Termin_Missing.dll")
    with pytest.raises(native.EngineNugetNativeError, match=r"termin_missing\.dll needed by termin\.dll"):
        native.collect_native(sdk, "win-x64")


def test_wrong_native_machine_is_rejected(sdk):
    _write_pe(_projection(sdk, "win-x64") / "termin.dll", machine=0x14C)
    with pytest.raises(RuntimeError, match="expected an AMD64 DLL"):
        native.collect_native(sdk, "win-x64")


def test_conflicting_csharp_projection_and_installed_binary(sdk):
    projection = _projection(sdk, "win-x64")
    _write_pe(projection / "termin.dll", regular="engine.dll")
    _write_pe(projection / "engine.dll", regular="kernel32.dll")
    _write_pe(sdk / "bin" / "engine.dll", regular="bcrypt.dll")
    with pytest.raises(native.EngineNugetNativeError, match="conflicting native libraries for engine.dll"):
        native.collect_native(sdk, "win-x64")


@pytest.mark.skipif(os.name == "nt", reason="Windows native SDKs do not require symlink support")
def test_project_files_cannot_point_outside_sdk(sdk, tmp_path):
    path = tmp_path / "outside.dll"
    _write_pe(path)
    (_projection(sdk, "win-x64") / "termin.dll").symlink_to(path)
    with pytest.raises(native.EngineNugetNativeError, match="inside the SDK"):
        native.collect_native(sdk, "win-x64")
