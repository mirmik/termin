import os
import sys
import types
from pathlib import Path

from termin.player import runtime as player_runtime
from termin.player.runtime import PlayerRuntime
from termin import shader_runtime


def _fake_executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_project_shader_runtime_configures_project_cache(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    compiler = _fake_executable(tmp_path / "termin_shaderc")
    slangc = _fake_executable(tmp_path / "slangc")
    calls: list[dict] = []

    fake_tgfx = types.ModuleType("tgfx")
    fake_tgfx.configure_shader_runtime = lambda **kwargs: calls.append(kwargs)
    monkeypatch.setitem(sys.modules, "tgfx", fake_tgfx)
    monkeypatch.setattr(shader_runtime, "resolve_termin_shaderc", lambda _anchor=None: compiler)
    monkeypatch.setattr(shader_runtime, "resolve_slangc", lambda _anchor=None: slangc)
    monkeypatch.delenv("TERMIN_SLANGC", raising=False)

    assert shader_runtime.configure_project_shader_runtime(project_root, label="test player")

    assert calls == [
        {
            "artifact_root": str(project_root / ".termin" / "shader-artifacts"),
            "cache_root": str(project_root / ".termin" / "shader-cache"),
            "shader_compiler": str(compiler),
            "dev_compile": True,
        }
    ]
    assert Path(os.environ["TERMIN_SLANGC"]) == slangc
    assert (project_root / ".termin" / "shader-artifacts").is_dir()
    assert (project_root / ".termin" / "shader-cache").is_dir()


def test_player_source_runtime_requires_project_shader_runtime(monkeypatch, tmp_path: Path):
    calls: list[Path] = []

    def fake_configure(project_root: Path, *, label: str) -> bool:
        assert label == "source player"
        calls.append(project_root)
        return True

    monkeypatch.setattr("termin.shader_runtime.configure_project_shader_runtime", fake_configure)

    runtime = PlayerRuntime(project_path=tmp_path, scene_name="scene.scene")

    assert runtime._configure_shader_runtime()
    assert calls == [tmp_path]


def test_player_packaged_runtime_uses_prebuilt_shader_artifacts(monkeypatch, tmp_path: Path):
    calls: list[Path] = []
    monkeypatch.setattr(
        "termin.shader_runtime.configure_project_shader_runtime",
        lambda project_root, *, label: calls.append(project_root) or True,
    )

    runtime = PlayerRuntime(
        project_path=tmp_path,
        scene_name="scene.json",
        asset_manifest_path=tmp_path / "manifest.json",
        build_json_path=tmp_path / "app.json",
    )
    monkeypatch.setattr(runtime, "_configure_build_shader_runtime", lambda: calls.append(Path("build")))

    assert runtime._configure_shader_runtime()
    assert calls == [Path("build")]


def test_player_backend_default_uses_d3d11_on_windows(monkeypatch, tmp_path: Path):
    logs: list[str] = []
    fake_tcbase = types.ModuleType("tcbase")
    fake_tcbase.log = types.SimpleNamespace(info=logs.append)
    monkeypatch.setitem(sys.modules, "tcbase", fake_tcbase)
    monkeypatch.delenv("TERMIN_BACKEND", raising=False)
    monkeypatch.setattr(player_runtime.sys, "platform", "win32")

    runtime = PlayerRuntime(project_path=tmp_path, scene_name="scene.scene")
    runtime._configure_backend_default()

    assert os.environ["TERMIN_BACKEND"] == "d3d11"
    assert logs == ["[PlayerRuntime] TERMIN_BACKEND not set; using d3d11 for standalone player"]


def test_player_backend_default_uses_vulkan_off_windows(monkeypatch, tmp_path: Path):
    logs: list[str] = []
    fake_tcbase = types.ModuleType("tcbase")
    fake_tcbase.log = types.SimpleNamespace(info=logs.append)
    monkeypatch.setitem(sys.modules, "tcbase", fake_tcbase)
    monkeypatch.delenv("TERMIN_BACKEND", raising=False)
    monkeypatch.setattr(player_runtime.sys, "platform", "linux")

    runtime = PlayerRuntime(project_path=tmp_path, scene_name="scene.scene")
    runtime._configure_backend_default()

    assert os.environ["TERMIN_BACKEND"] == "vulkan"
    assert logs == ["[PlayerRuntime] TERMIN_BACKEND not set; using vulkan for standalone player"]


def test_player_backend_default_keeps_explicit_backend(monkeypatch, tmp_path: Path):
    logs: list[str] = []
    fake_tcbase = types.ModuleType("tcbase")
    fake_tcbase.log = types.SimpleNamespace(info=logs.append)
    monkeypatch.setitem(sys.modules, "tcbase", fake_tcbase)
    monkeypatch.setenv("TERMIN_BACKEND", "opengl")
    monkeypatch.setattr(player_runtime.sys, "platform", "win32")

    runtime = PlayerRuntime(project_path=tmp_path, scene_name="scene.scene")
    runtime._configure_backend_default()

    assert os.environ["TERMIN_BACKEND"] == "opengl"
    assert logs == ["[PlayerRuntime] Using TERMIN_BACKEND=opengl"]
