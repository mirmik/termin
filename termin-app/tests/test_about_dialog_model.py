from termin.editor_core.about_model import build_editor_about_info


def test_about_info_resolves_environment_and_backend(monkeypatch):
    monkeypatch.setenv("TERMIN_BACKEND", "vulkan<debug>")

    info = build_editor_about_info(backend_name="vulkan")

    assert info.version
    assert info.configured_backend == "vulkan<debug>"
    assert info.active_backend == "vulkan"
