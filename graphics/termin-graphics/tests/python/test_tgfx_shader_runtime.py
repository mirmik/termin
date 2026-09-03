import importlib.util
import os
from pathlib import Path
import sys
import types

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_shader_runtime_module(monkeypatch, settings_values=None, log_messages=None):
    messages = log_messages if log_messages is not None else {
        "error": [],
        "info": [],
        "warning": [],
    }

    class FakeSettings:
        def __init__(self, app_name):
            assert app_name == "termin"

        def get(self, key, default=None):
            return (settings_values or {}).get(key, default)

    monkeypatch.setitem(sys.modules, "termin.base", types.SimpleNamespace(
        Settings=FakeSettings,
        log=types.SimpleNamespace(
            error=messages["error"].append,
            info=messages["info"].append,
            warning=messages["warning"].append,
        ),
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
        get_shader_dev_compile_enabled=lambda: False,
        get_shader_artifact_root=lambda: "",
        get_shader_cache_root=lambda: "",
        get_shader_compiler_path=lambda: "",
    )
    import termin

    monkeypatch.setitem(sys.modules, "termin_graphics_profile", profile)
    monkeypatch.setitem(sys.modules, "termin.graphics", fake_tgfx)
    monkeypatch.setattr(termin, "graphics", fake_tgfx, raising=False)
    monkeypatch.setenv("TERMIN_SHADER_DEV_COMPILE", "0")
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


def test_tgfx_shader_runtime_uses_bundled_shaderc_with_external_slangc_and_writable_cache(
    monkeypatch, tmp_path: Path
) -> None:
    configured = []
    compiler = tmp_path / _executable_name("termin_shaderc")
    slangc = tmp_path / _executable_name("slangc")
    for tool in (compiler, slangc):
        tool.write_text("#!/bin/sh\n", encoding="utf-8")
        tool.chmod(0o755)
    installed_root = tmp_path / "profile" / "share" / "termin"

    def activate_profile() -> None:
        monkeypatch.setenv("TERMIN_SHADER_ARTIFACT_ROOT", str(installed_root))
        monkeypatch.setenv("TERMIN_SHADERC", str(compiler))

    profile = types.SimpleNamespace(
        activate=activate_profile,
        shader_artifact_root=lambda: installed_root,
    )
    fake_tgfx = types.SimpleNamespace(
        configure_shader_runtime=lambda **kwargs: configured.append(kwargs),
        # The legacy resolver reflects the environment populated by profile
        # activation.  This is not a complete runtime configuration: it still
        # has no writable cache root and must not short-circuit setup.
        get_shader_dev_compile_enabled=lambda: os.environ.get("TERMIN_SHADER_DEV_COMPILE") == "1",
        get_shader_artifact_root=lambda: os.environ.get("TERMIN_SHADER_ARTIFACT_ROOT", ""),
        get_shader_cache_root=lambda: os.environ.get("TERMIN_SHADER_CACHE_ROOT", ""),
        get_shader_compiler_path=lambda: os.environ.get("TERMIN_SHADERC", ""),
    )
    import termin

    monkeypatch.setitem(sys.modules, "termin_graphics_profile", profile)
    monkeypatch.setitem(sys.modules, "termin.graphics", fake_tgfx)
    monkeypatch.setattr(termin, "graphics", fake_tgfx, raising=False)
    monkeypatch.setenv("TERMIN_SHADER_DEV_COMPILE", "1")
    monkeypatch.setenv("TERMIN_SLANGC", str(slangc))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    shader_runtime = _load_shader_runtime_module(monkeypatch)

    assert shader_runtime.configure_default_shader_runtime("product")
    runtime_root = tmp_path / "xdg-cache" / "termin" / "product-shaders"
    assert configured == [
        {
            "artifact_root": str(runtime_root / "artifacts"),
            "cache_root": str(runtime_root / "cache"),
            "shader_compiler": str(compiler),
            "dev_compile": True,
            "fallback_artifact_roots": [str(installed_root)],
        }
    ]
    assert (runtime_root / "artifacts").is_dir()
    assert (runtime_root / "cache").is_dir()


def test_tgfx_shader_runtime_preserves_complete_explicit_configuration(
    monkeypatch, tmp_path: Path
) -> None:
    configured = []
    activated = []
    profile = types.SimpleNamespace(
        activate=lambda: activated.append(True),
        shader_artifact_root=lambda: tmp_path / "profile" / "share" / "termin",
    )
    fake_tgfx = types.SimpleNamespace(
        configure_shader_runtime=lambda **kwargs: configured.append(kwargs),
        get_shader_dev_compile_enabled=lambda: True,
        get_shader_artifact_root=lambda: str(tmp_path / "explicit" / "artifacts"),
        get_shader_cache_root=lambda: str(tmp_path / "explicit" / "cache"),
        get_shader_compiler_path=lambda: str(tmp_path / "explicit" / "termin_shaderc"),
    )
    import termin

    monkeypatch.setitem(sys.modules, "termin_graphics_profile", profile)
    monkeypatch.setitem(sys.modules, "termin.graphics", fake_tgfx)
    monkeypatch.setattr(termin, "graphics", fake_tgfx, raising=False)
    monkeypatch.setenv("TERMIN_SHADER_DEV_COMPILE", "1")
    shader_runtime = _load_shader_runtime_module(monkeypatch)

    assert shader_runtime.configure_default_shader_runtime("explicit")
    assert configured == []
    assert activated == [True]


def test_tgfx_shader_runtime_reports_missing_explicit_slangc(
    monkeypatch, tmp_path: Path
) -> None:
    configured = []
    messages = {"error": [], "info": [], "warning": []}
    compiler = tmp_path / _executable_name("termin_shaderc")
    compiler.write_text("#!/bin/sh\n", encoding="utf-8")
    compiler.chmod(0o755)
    installed_root = tmp_path / "profile" / "share" / "termin"

    def activate_profile() -> None:
        monkeypatch.setenv("TERMIN_SHADER_ARTIFACT_ROOT", str(installed_root))
        monkeypatch.setenv("TERMIN_SHADERC", str(compiler))

    profile = types.SimpleNamespace(
        activate=activate_profile,
        shader_artifact_root=lambda: installed_root,
    )
    fake_tgfx = types.SimpleNamespace(
        configure_shader_runtime=lambda **kwargs: configured.append(kwargs),
        get_shader_dev_compile_enabled=lambda: os.environ.get("TERMIN_SHADER_DEV_COMPILE") == "1",
        get_shader_artifact_root=lambda: os.environ.get("TERMIN_SHADER_ARTIFACT_ROOT", ""),
        get_shader_cache_root=lambda: os.environ.get("TERMIN_SHADER_CACHE_ROOT", ""),
        get_shader_compiler_path=lambda: os.environ.get("TERMIN_SHADERC", ""),
    )
    import termin

    monkeypatch.setitem(sys.modules, "termin_graphics_profile", profile)
    monkeypatch.setitem(sys.modules, "termin.graphics", fake_tgfx)
    monkeypatch.setitem(
        sys.modules,
        "termin.shader_runtime",
        types.SimpleNamespace(
            slangc_unavailable_message=lambda label: f"{label}: external slangc is unavailable"
        ),
    )
    monkeypatch.setattr(termin, "graphics", fake_tgfx, raising=False)
    monkeypatch.setenv("TERMIN_SHADER_DEV_COMPILE", "1")
    monkeypatch.setenv("TERMIN_SLANGC", str(tmp_path / "missing-slangc"))
    shader_runtime = _load_shader_runtime_module(
        monkeypatch,
        log_messages=messages,
    )

    assert not shader_runtime.configure_default_shader_runtime("product")
    assert configured == []
    assert any("TERMIN_SLANGC points to missing file" in message for message in messages["error"])
    assert messages["warning"] == ["[ShaderRuntime] product: external slangc is unavailable"]


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
