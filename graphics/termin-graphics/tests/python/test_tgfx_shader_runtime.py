import importlib.util
import os
from pathlib import Path
import sys
import types

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_shader_runtime_module(monkeypatch, settings_values=None):
    class FakeSettings:
        def __init__(self, app_name):
            assert app_name == "termin"

        def get(self, key, default=None):
            return (settings_values or {}).get(key, default)

    monkeypatch.setitem(sys.modules, "termin.base", types.SimpleNamespace(
        Settings=FakeSettings,
        log=types.SimpleNamespace(error=lambda message: None, info=lambda message: None)
    ))
    path = _repo_root() / "termin-graphics" / "python" / "termin" / "graphics" / "shader_runtime.py"
    spec = importlib.util.spec_from_file_location("tgfx_shader_runtime_under_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _executable_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def test_tgfx_shader_runtime_resolves_sdk_windows_exe_suffix(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sdk = tmp_path / "sdk"
    tool = sdk / "bin" / _executable_name("termin_shaderc")
    tool.parent.mkdir(parents=True)
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    tool.chmod(0o755)

    monkeypatch.setenv("TERMIN_SDK", str(sdk))
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("TERMIN_SHADERC", raising=False)

    shader_runtime = _load_shader_runtime_module(monkeypatch)

    assert shader_runtime._resolve_tool(
        "termin_shaderc", "TERMIN_SHADERC", "Build/shaderCompiler"
    ) == tool


def test_tgfx_shader_runtime_reads_common_slang_setting(
    monkeypatch,
    tmp_path: Path,
) -> None:
    slangc = tmp_path / _executable_name("slangc")
    slangc.write_text("#!/bin/sh\n", encoding="utf-8")
    slangc.chmod(0o755)
    monkeypatch.delenv("TERMIN_SLANGC", raising=False)

    shader_runtime = _load_shader_runtime_module(
        monkeypatch,
        {"Shader/slangCompiler": str(slangc)},
    )

    assert shader_runtime._resolve_tool(
        "slangc", "TERMIN_SLANGC", "Shader/slangCompiler"
    ) == slangc


def test_tgfx_shader_runtime_activates_installed_graphics_profile(monkeypatch) -> None:
    activated = []
    monkeypatch.setitem(
        sys.modules,
        "termin_graphics_profile",
        types.SimpleNamespace(activate=lambda: activated.append(True)),
    )
    shader_runtime = _load_shader_runtime_module(monkeypatch)

    shader_runtime._activate_graphics_profile_resources()

    assert activated == [True]


def test_tgfx_shader_runtime_prefers_product_precompiled_artifacts(
    monkeypatch, tmp_path: Path
) -> None:
    configured = []
    profile = types.SimpleNamespace(
        activate=lambda: monkeypatch.setenv("TERMIN_SHADER_DEV_COMPILE", "0"),
        shader_artifact_root=lambda: tmp_path / "share" / "termin",
    )
    fake_tgfx = types.SimpleNamespace(
        configure_shader_runtime=lambda **kwargs: configured.append(kwargs),
    )
    import termin

    monkeypatch.setitem(sys.modules, "termin_graphics_profile", profile)
    monkeypatch.setitem(sys.modules, "termin.graphics", fake_tgfx)
    monkeypatch.setattr(termin, "graphics", fake_tgfx)
    monkeypatch.delenv("TERMIN_SHADERC", raising=False)
    monkeypatch.delenv("TERMIN_SLANGC", raising=False)
    shader_runtime = _load_shader_runtime_module(monkeypatch)

    assert shader_runtime.configure_default_shader_runtime("wheel")
    assert configured == [
        {
            "artifact_root": str(tmp_path / "share" / "termin"),
            "cache_root": "",
            "shader_compiler": "",
            "dev_compile": False,
        }
    ]
    assert "TERMIN_SHADERC" not in os.environ
    assert "TERMIN_SLANGC" not in os.environ


@pytest.mark.skipif(os.name != "nt", reason="Windows cache root uses LOCALAPPDATA")
def test_tgfx_shader_runtime_uses_local_app_data_cache_root_on_windows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    local_app_data = tmp_path / "LocalAppData"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.delenv("TERMIN_SDK_SHADER_CACHE_ROOT", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    shader_runtime = _load_shader_runtime_module(monkeypatch)

    assert (
        shader_runtime._cache_root("python")
        == local_app_data / "Termin" / "Cache" / "python-shaders"
    )
