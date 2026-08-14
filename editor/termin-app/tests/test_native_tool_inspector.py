from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
import gc

from termin.editor_native.tool_inspector import build_native_tool_inspector
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.gui_native import Rect


def test_native_tool_inspector_register_show_and_unregister():
    document = tc_ui_document_create()
    inspector = build_native_tool_inspector(document)
    inspector.root.layout(Rect(0.0, 0.0, 340.0, 200.0))
    assert inspector.empty.bounds.x == EDITOR_UI_METRICS.embedded_panel_padding
    assert inspector.empty.bounds.y == EDITOR_UI_METRICS.embedded_panel_padding
    assert inspector.empty.bounds.height == EDITOR_UI_METRICS.compact_row
    panel = document.create_vstack("terrain-panel")
    assert document.add_root(inspector.root.handle)

    inspector.register("terrain", panel)
    inspector.set_target("terrain", label="Terrain")
    assert inspector.active_key == "terrain"
    assert not inspector.empty.visible
    assert any(child.handle == panel.handle for child in inspector.root.children)

    detached = inspector.unregister("terrain")
    assert detached is not None
    assert inspector.active_key is None
    assert inspector.empty.visible

    assert document.destroy_widget_recursive(inspector.root.handle)
    assert document.destroy_widget_recursive(panel.handle)
    tc_ui_document_destroy(document)
    del inspector, panel, document
    gc.collect()
