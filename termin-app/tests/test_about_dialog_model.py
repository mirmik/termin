from termin.editor_core.about_model import build_editor_about_info


def test_native_editor_about_uses_created_window_backend():
    from pathlib import Path

    source = (
        Path(__file__).parents[1] / "termin" / "editor_native" / "run_editor.py"
    ).read_text(encoding="utf-8")

    assert "build_editor_about_info(backend_name=window.backend)" in source
    assert "compiled_backend_name" not in source


def test_about_info_resolves_environment_and_backend(monkeypatch):
    monkeypatch.setenv("TERMIN_BACKEND", "vulkan<debug>")

    info = build_editor_about_info(backend_name="vulkan")

    assert info.version
    assert info.configured_backend == "vulkan<debug>"
    assert info.active_backend == "vulkan"
