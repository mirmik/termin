import os
import sys
import types
from pathlib import Path

import pytest

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

    render_engine = types.SimpleNamespace(
        configure_shader_artifacts=lambda **kwargs: calls.append(kwargs)
    )
    monkeypatch.setattr(shader_runtime, "resolve_termin_shaderc", lambda _anchor=None: compiler)
    monkeypatch.setattr(shader_runtime, "resolve_slangc", lambda _anchor=None: slangc)
    monkeypatch.delenv("TERMIN_SLANGC", raising=False)

    assert shader_runtime.configure_project_shader_runtime(
        project_root,
        label="test player",
        render_engine=render_engine,
    )

    assert calls == [
        {
            "artifact_root": str(project_root / ".termin" / "shader-artifacts"),
            "cache_root": str(project_root / ".termin" / "shader-cache"),
            "compiler_path": str(compiler),
            "dev_compile_enabled": True,
        }
    ]
    assert Path(os.environ["TERMIN_SLANGC"]) == slangc
    assert (project_root / ".termin" / "shader-artifacts").is_dir()
    assert (project_root / ".termin" / "shader-cache").is_dir()


def test_player_source_runtime_requires_project_shader_runtime(monkeypatch, tmp_path: Path):
    calls: list[Path] = []

    expected_render_engine = object()

    def fake_configure(project_root: Path, *, label: str, render_engine: object) -> bool:
        assert label == "source player"
        assert render_engine is expected_render_engine
        calls.append(project_root)
        return True

    monkeypatch.setattr("termin.shader_runtime.configure_project_shader_runtime", fake_configure)

    runtime = PlayerRuntime(project_path=tmp_path, scene_name="scene.scene")
    runtime._engine = types.SimpleNamespace(
        rendering_manager=types.SimpleNamespace(render_engine=expected_render_engine)
    )

    assert runtime._configure_shader_runtime()
    assert calls == [tmp_path]


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


def test_player_runtime_uses_project_window_settings(tmp_path: Path):
    settings_path = tmp_path / "project_settings" / "project.json"
    settings_path.parent.mkdir()
    settings_path.write_text(
        '{"player_window": {"width": 1440, "height": 810, "fullscreen": false, "vsync": false}}',
        encoding="utf-8",
    )

    runtime = PlayerRuntime(project_path=tmp_path, scene_name="scene.scene")

    assert runtime.width == 1440
    assert runtime.height == 810
    assert runtime.fullscreen is False
    assert runtime.vsync is False


def test_player_runtime_explicit_window_args_override_project_settings(tmp_path: Path):
    settings_path = tmp_path / "project_settings" / "project.json"
    settings_path.parent.mkdir()
    settings_path.write_text(
        '{"player_window": {"width": 1440, "height": 810, "fullscreen": false, "vsync": false}}',
        encoding="utf-8",
    )

    runtime = PlayerRuntime(
        project_path=tmp_path,
        scene_name="scene.scene",
        width=800,
        height=600,
        fullscreen=True,
    )

    assert runtime.width == 800
    assert runtime.height == 600
    assert runtime.fullscreen is True
    assert runtime.vsync is False


def test_player_runtime_old_project_window_settings_default_to_vsync(tmp_path: Path):
    settings_path = tmp_path / "project_settings" / "project.json"
    settings_path.parent.mkdir()
    settings_path.write_text(
        '{"player_window": {"width": 1024, "height": 576, "fullscreen": false}}',
        encoding="utf-8",
    )

    runtime = PlayerRuntime(project_path=tmp_path, scene_name="scene.scene")

    assert runtime.vsync is True


def test_player_backend_window_receives_requested_presentation_mode():
    from termin.display import PresentationMode
    from termin.player.runtime import _create_player_backend_window

    calls = []

    class GraphicsSession:
        def create_window(self, title, width, height, *, presentation_mode):
            calls.append((title, width, height, presentation_mode))
            return object()

    _create_player_backend_window(
        GraphicsSession(),
        title="Game",
        width=1280,
        height=720,
        vsync=False,
    )

    assert calls == [("Game", 1280, 720, PresentationMode.IMMEDIATE)]


def test_player_backend_window_reports_unsupported_requested_mode():
    from termin.player.runtime import _create_player_backend_window

    class GraphicsSession:
        def create_window(self, _title, _width, _height, *, presentation_mode):
            raise RuntimeError(f"unsupported {presentation_mode}")

    with pytest.raises(
        RuntimeError,
        match="requested presentation mode 'immediate'",
    ):
        _create_player_backend_window(
            GraphicsSession(),
            title="Game",
            width=1280,
            height=720,
            vsync=False,
        )


def test_python_player_cli_exposes_source_modes_only(monkeypatch, capsys) -> None:
    from termin.player import __main__ as player_main

    monkeypatch.setattr(sys, "argv", ["termin.player", "--help"])
    with pytest.raises(SystemExit) as exit_info:
        player_main.main()

    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "--bundle" not in help_text
    assert "--app" not in help_text
    assert "--headless" in help_text
