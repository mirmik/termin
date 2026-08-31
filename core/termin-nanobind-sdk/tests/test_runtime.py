from __future__ import annotations

import os
from pathlib import Path
import types

from termin_nanobind import runtime


class _DllDirectoryHandle:
    def __init__(self, path: str) -> None:
        self.path = path
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_logical_nanobind_name_selects_interpreter_abi_runtime(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime.sysconfig,
        "get_config_var",
        lambda name: 1 if name == "Py_GIL_DISABLED" else None,
    )
    assert runtime._abi_runtime_library_name("nanobind") == "nanobind-ft"
    assert runtime._abi_runtime_library_name("termin_base") == "termin_base"

    monkeypatch.setattr(runtime.sysconfig, "get_config_var", lambda _name: 0)
    assert runtime._abi_runtime_library_name("nanobind") == "nanobind"


def test_find_library_prefers_elf_soname_over_flattened_linker_name(tmp_path) -> None:
    linker_name = tmp_path / "libtermin_graphics2.so"
    soname = tmp_path / "libtermin_graphics2.so.0"
    linker_name.write_bytes(b"independent artifact copy")
    soname.write_bytes(b"runtime SONAME copy")

    assert runtime._find_library("termin_graphics2", [tmp_path]) == soname


def test_find_library_falls_back_to_unversioned_shared_library(tmp_path) -> None:
    library = tmp_path / "libnanobind-ft.so"
    library.write_bytes(b"unversioned runtime")

    assert runtime._find_library("nanobind-ft", [tmp_path]) == library


def test_installed_graphics_product_exposes_one_shared_library_root(
    tmp_path: Path, monkeypatch
) -> None:
    package_root = tmp_path / "termin_graphics_profile"
    lib_dir = package_root / "lib"
    lib_dir.mkdir(parents=True)
    spec = types.SimpleNamespace(submodule_search_locations=[str(package_root)])
    monkeypatch.setattr(runtime.importlib.util, "find_spec", lambda name: spec)

    assert runtime._installed_product_lib_dirs() == [lib_dir]


def test_installed_graphics_product_declares_exact_runtime_paths(
    tmp_path: Path, monkeypatch
) -> None:
    package_root = tmp_path / "termin_graphics_profile"
    library = package_root / "lib" / "libtermin_graphics2.so.0"
    library.parent.mkdir(parents=True)
    library.write_bytes(b"runtime")
    (package_root / "native-libraries.json").write_text(
        '["libtermin_graphics2.so.0"]', encoding="utf-8"
    )
    spec = types.SimpleNamespace(submodule_search_locations=[str(package_root)])
    monkeypatch.setattr(runtime.importlib.util, "find_spec", lambda name: spec)

    assert runtime._installed_product_library_paths() == [library]


def test_windows_dll_directory_handles_are_retained_idempotently_and_can_close(tmp_path, monkeypatch) -> None:
    local_dir = tmp_path / "package" / "lib"
    sdk_bin = tmp_path / "sdk" / "bin"
    sdk_lib = tmp_path / "sdk" / "lib"
    for directory in (local_dir, sdk_bin, sdk_lib):
        directory.mkdir(parents=True)

    calls: list[str] = []
    handles: list[_DllDirectoryHandle] = []

    def add_dll_directory(path: str) -> _DllDirectoryHandle:
        calls.append(path)
        handle = _DllDirectoryHandle(path)
        handles.append(handle)
        return handle

    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setattr(runtime, "_caller_lib_dirs", lambda: [local_dir, local_dir])
    monkeypatch.setattr(runtime, "find_sdk", lambda: tmp_path / "sdk")
    monkeypatch.setattr(runtime.os, "add_dll_directory", add_dll_directory, raising=False)
    monkeypatch.setattr(runtime, "_windows_dll_directory_handles", {})

    runtime.preload_sdk_libs("termin_base")
    runtime.preload_sdk_libs("termin_base")

    expected = [
        os.path.normcase(os.path.normpath(os.path.abspath(directory)))
        for directory in (local_dir, sdk_bin, sdk_lib)
    ]
    assert calls == expected
    assert set(runtime._windows_dll_directory_handles) == set(expected)
    assert all(not handle.closed for handle in handles)

    runtime.close_windows_dll_directories()

    assert runtime._windows_dll_directory_handles == {}
    assert all(handle.closed for handle in handles)
