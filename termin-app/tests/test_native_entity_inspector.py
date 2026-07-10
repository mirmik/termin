import pytest

from termin.bootstrap import bootstrap_player, shutdown_player
from termin.editor_core.entity_inspector_model import (
    EntityInspectorComponentType,
    EntityInspectorController,
)
from termin.editor_core.undo_stack import UndoStack
from termin.editor_native import build_native_entity_inspector, resolve_native_ui_font
from termin.gui_native import (
    Document,
    DrawList,
    DrawListRenderer,
    KeyCode,
    KeyEvent,
    KeyEventType,
    PaintContext,
    Rect,
)
from termin.inspect import InspectField
from termin.scene import ComponentRegistry, PythonComponent, TcScene


@pytest.fixture(scope="module", autouse=True)
def player_runtime():
    bootstrap_player()
    yield
    shutdown_player()


def test_native_entity_inspector_selection_edit_undo_and_paint():
    class NativeInspectorAddProbeComponent(PythonComponent):
        component_category = "Editor/Internal"

    probe_type = "NativeInspectorAddProbeComponent"
    scene = TcScene.create("native-entity-inspector-test")
    try:
        entity = scene.create_entity("source")
        entity.add_component(PythonComponent())
        stack = UndoStack()

        def set_enabled(component, value):
            component.enabled = bool(value)

        controller = EntityInspectorController(
            undo_handler=stack.push,
            field_collector=lambda _component: {
                "enabled": InspectField(
                    path="enabled",
                    label="Enabled",
                    kind="bool",
                    getter=lambda component: component.enabled,
                    setter=set_enabled,
                )
            },
            metadata_collector=lambda _component: {},
            component_type_collector=lambda: (
                EntityInspectorComponentType(
                    probe_type,
                    "Native Inspector Probe",
                    "Editor/Internal",
                ),
            ),
        )
        controller.set_scene(scene)
        document = Document()
        renderer = DrawListRenderer()
        assert renderer.set_default_font_path(str(resolve_native_ui_font()), 15)
        renderer.bind_text_measurer(document)
        renders = []
        inspector = build_native_entity_inspector(
            document,
            controller,
            request_render=lambda: renders.append(True),
            viewport=lambda: Rect(0.0, 0.0, 420.0, 640.0),
        )
        assert document.add_root(inspector.root.handle)
        inspector.set_target(entity)
        document.layout_roots(Rect(0.0, 0.0, 420.0, 640.0))

        assert inspector.name_input.text == "source"
        assert inspector.uuid_value.text == entity.uuid
        assert inspector.component_model.item_count == 1
        assert inspector.component_model.items[0].subtitle == ""
        assert inspector.component_list.select(0)
        assert "enabled" in inspector.fields.field_widgets
        assert len(inspector.transform_boxes) == 3
        inspector.transform_boxes[0][0].value = 2.5
        assert tuple(entity.transform.local_pose().lin) == pytest.approx((2.5, 0.0, 0.0))
        stack.undo()
        controller.refresh()
        assert inspector.transform_boxes[0][0].value == pytest.approx(0.0)

        inspector.fields.field_widgets["enabled"].checked = False
        assert not entity.tc_components[0].enabled
        stack.undo()
        assert entity.tc_components[0].enabled

        inspector.layer_combo.selected_index = 4
        assert entity.layer == 4
        stack.undo()
        assert entity.layer == 0

        inspector.show_add_component_menu()
        assert document.overlay_count == 1
        key = KeyEvent()
        key.type = KeyEventType.Down
        key.key = KeyCode.Down
        assert document.dispatch_key_event(key)
        key.key = KeyCode.Right
        assert document.dispatch_key_event(key)
        key.key = KeyCode.Enter
        assert document.dispatch_key_event(key)
        assert inspector.component_model.item_count == 2
        assert document.overlay_count == 0
        stack.undo()
        controller.refresh()
        assert inspector.component_model.item_count == 1

        draw_list = DrawList()
        document.paint(PaintContext(draw_list))
        assert draw_list.command_count > 20
        extension_panel = document.create_vstack("test-native-extension-panel")
        extension_label = document.create_label("Extension tools")
        extension_panel.add_fixed_child(extension_label, 28.0)
        inspector.set_extension_panel(extension_panel)
        assert inspector.extension_host.visible
        assert document.is_alive(extension_panel.handle)
        inspector.clear_extension_panel()
        assert not inspector.extension_host.visible
        assert not document.is_alive(extension_panel.handle)
        controller.clear()
        assert controller.snapshot.entity is None
        assert controller.snapshot.selected_component == -1
        assert renders
        renderer.release_gpu()
    finally:
        scene.destroy()
        ComponentRegistry.instance().unregister_python(probe_type)
