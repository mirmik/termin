from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
from termin.editor_core.about_model import EditorAboutInfo
from termin.editor_native.about_dialog import build_native_about_dialog
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.gui_native import Rect


def test_native_about_dialog_escapes_info_reopens_and_releases():
    document = tc_ui_document_create()
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
    content = dialog.root.children[0]
    assert content.bounds.x - dialog.root.bounds.x == EDITOR_UI_METRICS.dialog_padding
    assert content.bounds.y - dialog.root.bounds.y == EDITOR_UI_METRICS.dialog_padding
    assert dialog.dialog.activate("ok")
    assert dialog.show()

    dialog.close()
    assert not document.is_alive(dialog.dialog.handle)
    assert renders
    tc_ui_document_destroy(document)
