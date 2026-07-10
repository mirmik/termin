from termin.editor_core.about_model import EditorAboutInfo
from termin.editor_native.about_dialog import build_native_about_dialog
from termin.gui_native import Document, Rect


def test_native_about_dialog_escapes_info_reopens_and_releases():
    document = Document()
    renders = []
    dialog = build_native_about_dialog(
        document,
        EditorAboutInfo("1<2", "vulkan<debug>", "vulkan"),
        viewport=lambda: Rect(0.0, 0.0, 800.0, 600.0),
        request_render=lambda: renders.append(True),
    )

    assert "1<2" in dialog.content_model.text
    assert "vulkan<debug>" in dialog.content_model.text
    assert dialog.show()
    assert dialog.dialog.activate("ok")
    assert dialog.show()

    dialog.close()
    assert not document.is_alive(dialog.dialog.handle)
    assert renders
