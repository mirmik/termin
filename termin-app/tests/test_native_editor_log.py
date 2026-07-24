from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
from termin.editor_core.editor_log_model import EditorLogModel
from termin.editor_native.editor_log import build_native_editor_log
from termin.gui_native import Rect


def test_native_editor_log_wraps_long_messages_in_narrow_view():
    document = tc_ui_document_create()
    controller = EditorLogModel()
    controller.append("long editor log message " * 20)
    log = build_native_editor_log(document, controller, lambda: None)
    assert document.add_root(log.root.handle)
    document.layout_roots(Rect(0.0, 0.0, 180.0, 180.0))

    assert log.output.word_wrap
    assert log.output.visual_line_count > len(log.output_model.lines)
    log.close()
    tc_ui_document_destroy(document)
