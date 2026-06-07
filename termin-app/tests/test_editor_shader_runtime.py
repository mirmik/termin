import os
from pathlib import Path

from termin.editor_tcgui import editor_window
from termin.editor_tcgui.editor_window import EditorWindowTcgui
from termin.editor_core.settings import EditorSettings


def test_editor_project_load_configures_shader_runtime(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    compiler = tmp_path / "termin_shaderc"
    compiler.write_text("#!/bin/sh\n", encoding="utf-8")
    slangc = tmp_path / "slangc"
    slangc.write_text("#!/bin/sh\n", encoding="utf-8")

    calls: list[dict] = []

    def fake_configure_shader_runtime(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(editor_window, "_resolve_termin_shaderc", lambda: compiler)
    monkeypatch.setattr(EditorSettings.instance(), "get_slang_compiler", lambda: str(slangc))
    monkeypatch.delenv("TERMIN_SLANGC", raising=False)
    monkeypatch.setattr("tgfx.configure_shader_runtime", fake_configure_shader_runtime)

    win = EditorWindowTcgui.__new__(EditorWindowTcgui)
    win._configure_shader_runtime_for_project(project_root)

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


def test_editor_shader_runtime_rejects_missing_configured_slangc(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    compiler = tmp_path / "termin_shaderc"
    compiler.write_text("#!/bin/sh\n", encoding="utf-8")

    calls: list[dict] = []

    monkeypatch.setattr(editor_window, "_resolve_termin_shaderc", lambda: compiler)
    monkeypatch.setattr(
        EditorSettings.instance(),
        "get_slang_compiler",
        lambda: str(tmp_path / "missing-slangc"),
    )
    monkeypatch.setattr("tgfx.configure_shader_runtime", lambda **kwargs: calls.append(kwargs))

    win = EditorWindowTcgui.__new__(EditorWindowTcgui)
    win._configure_shader_runtime_for_project(project_root)

    assert calls == []
