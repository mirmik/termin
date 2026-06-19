import os
import sys
import types
from pathlib import Path

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
