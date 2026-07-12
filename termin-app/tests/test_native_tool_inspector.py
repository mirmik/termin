import gc

from termin.editor_native.tool_inspector import build_native_tool_inspector
from termin.gui_native import Document


def test_native_tool_inspector_register_show_and_unregister():
    document = Document()
    inspector = build_native_tool_inspector(document)
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
    del inspector, panel, document
    gc.collect()
