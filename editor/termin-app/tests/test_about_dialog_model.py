from termin.editor_core.about_model import (
    build_editor_about_info,
    build_software_renderer_warning,
)


def test_native_editor_about_uses_created_window_backend():
    from pathlib import Path

    source = (
        Path(__file__).parents[1] / "termin" / "editor_native" / "run_editor.py"
    ).read_text(encoding="utf-8")

    assert "backend_name=window.backend" in source
    assert "compiled_backend_name" not in source


def test_about_info_resolves_environment_and_backend(monkeypatch):
    monkeypatch.setenv("TERMIN_BACKEND", "vulkan<debug>")

    info = build_editor_about_info(
        backend_name="vulkan",
        adapter_name="llvmpipe",
        adapter_driver="Mesa 26",
        adapter_class="cpu",
    )

    assert info.version
    assert info.configured_backend == "vulkan<debug>"
    assert info.active_backend == "vulkan"
    assert info.adapter_name == "llvmpipe"
    assert info.adapter_driver == "Mesa 26"
    assert info.adapter_class == "cpu"


def test_software_vulkan_warning_is_actionable_and_does_not_select_a_backend():
    info = build_editor_about_info(
        backend_name="vulkan",
        adapter_name="llvmpipe (LLVM 20.1.8)",
        adapter_driver="Mesa 25.1",
        adapter_class="cpu",
    )

    warning = build_software_renderer_warning(info)

    assert warning is not None
    assert "llvmpipe" in warning
    assert "Mesa 25.1" in warning
    assert "kept Vulkan selected" in warning
    assert "TERMIN_BACKEND" in warning


def test_hardware_vulkan_and_non_vulkan_backends_do_not_warn():
    hardware = build_editor_about_info(
        backend_name="vulkan",
        adapter_class="integrated-gpu",
    )
    cpu_opengl = build_editor_about_info(
        backend_name="opengl",
        adapter_class="cpu",
    )

    assert build_software_renderer_warning(hardware) is None
    assert build_software_renderer_warning(cpu_opengl) is None
