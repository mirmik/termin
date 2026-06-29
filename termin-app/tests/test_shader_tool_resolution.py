import os
import importlib.util
from pathlib import Path
import sys
import types

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_shader_tools_module():
    termin_module = sys.modules.setdefault("termin", types.ModuleType("termin"))
    module = _load_module(
        "termin.shader_tools",
        _repo_root() / "termin-shader-runtime" / "termin" / "shader_tools.py",
    )
    termin_module.shader_tools = module
    return module


def _load_runtime_package_exporter_module():
    _load_shader_tools_module()
    return _load_module(
        "runtime_package_exporter_under_test",
        _repo_root()
        / "termin-app"
        / "termin"
        / "project_build"
        / "runtime_package_exporter.py",
    )


def _load_editor_shader_runtime_module():
    _load_shader_tools_module()
    tcbase_module = types.ModuleType("tcbase")
    tcbase_module.log = types.SimpleNamespace(error=lambda message: None, info=lambda message: None)
    sys.modules["tcbase"] = tcbase_module

    settings_module = types.ModuleType("termin.editor_core.settings")

    class _EditorSettings:
        @classmethod
        def instance(cls):
            return cls()

        def get_slang_compiler(self):
            return None

    settings_module.EditorSettings = _EditorSettings
    sys.modules["termin.editor_core.settings"] = settings_module

    return _load_module(
        "editor_shader_runtime_under_test",
        _repo_root()
        / "termin-app"
        / "termin"
        / "editor_tcgui"
        / "shader_runtime.py",
    )


def _executable_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def _write_tool(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)


def test_shader_tools_resolves_sdk_windows_exe_suffix(monkeypatch, tmp_path: Path) -> None:
    sdk = tmp_path / "sdk"
    tool = sdk / "bin" / _executable_name("termin_shaderc")
    _write_tool(tool)

    monkeypatch.setenv("TERMIN_SDK", str(sdk))

    shader_tools = _load_shader_tools_module()

    assert shader_tools.existing_executable(sdk / "bin" / "termin_shaderc") == tool
    assert shader_tools.resolve_sdk_tool("termin_shaderc", Path(__file__)) == tool


def test_runtime_package_exporter_resolves_sdk_windows_exe_suffix(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sdk = tmp_path / "sdk"
    tool = sdk / "bin" / _executable_name("termin_shaderc")
    _write_tool(tool)

    monkeypatch.setenv("TERMIN_SDK", str(sdk))
    monkeypatch.setenv("PATH", "")

    runtime_package_exporter = _load_runtime_package_exporter_module()

    assert runtime_package_exporter._resolve_shader_compiler(None) == tool.resolve()


def test_editor_shader_runtime_uses_local_app_data_cache_root_on_windows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    if os.name != "nt":
        pytest.skip("Windows LOCALAPPDATA shader cache path")

    local_app_data = tmp_path / "LocalAppData"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.delenv("TERMIN_SDK_SHADER_CACHE_ROOT", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    shader_runtime = _load_editor_shader_runtime_module()

    assert (
        shader_runtime._sdk_shader_cache_root()
        == local_app_data / "Termin" / "Cache" / "sdk-shaders"
    )
