from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
from dataclasses import dataclass

import pytest

from termin.editor_core.inspector_fields_model import InspectorFieldsController
from termin.editor_core.inspector_resources import InspectorResourceCatalog
from termin.editor_core.inspector_special_choices import InspectorSpecialChoiceProvider
from termin.editor_core.undo_stack import UndoCommand, UndoStack
from termin.editor_native import build_native_inspector_fields, resolve_native_ui_font
from termin.editor_native.inspector_fields import (
    NativeIntervalSliderWidgets,
    NativeListFieldWidgets,
    NativeResourceFieldWidgets,
    NativeVec3ListFieldWidgets,
)
from termin.gui_native import (
    DrawList,
    DrawListRenderer,
    EventResult,
    KeyCode,
    KeyEvent,
    KeyEventType,
    PaintContext,
    PointerEvent,
    PointerEventType,
    Rect,
)
from termin.inspect import InspectField


@dataclass
class _Target:
    enabled: bool = True
    gain: float = 0.25
    mode: str = "a"
    tint: tuple[float, float, float, float] = (1.0, 0.5, 0.25, 1.0)
    layer_mask: int = 0b101
    resets: int = 0


def _fields(_target):
    def set_enabled(target, value):
        target.enabled = bool(value)

    def set_gain(target, value):
        target.gain = float(value)

    def set_mode(target, value):
        target.mode = str(value)

    def set_tint(target, value):
        target.tint = tuple(value)

    def set_layer_mask(target, value):
        target.layer_mask = int(value, 0)

    def reset(target):
        target.resets += 1

    return {
        "enabled": InspectField(
            path="enabled",
            label="Enabled",
            kind="bool",
            getter=lambda target: target.enabled,
            setter=set_enabled,
        ),
        "gain": InspectField(
            path="gain",
            label="Gain",
            kind="float",
            min=0.0,
            max=2.0,
            step=0.05,
            getter=lambda target: target.gain,
            setter=set_gain,
        ),
        "mode": InspectField(
            path="mode",
            label="Mode",
            kind="enum",
            choices=[("a", "A"), ("b", "B")],
            getter=lambda target: target.mode,
            setter=set_mode,
        ),
        "tint": InspectField(
            path="tint",
            label="Tint",
            kind="color",
            getter=lambda target: target.tint,
            setter=set_tint,
        ),
        "layer_mask": InspectField(
            path="layer_mask",
            label="Layer Mask",
            kind="layer_mask",
            getter=lambda target: f"0x{target.layer_mask:x}",
            setter=set_layer_mask,
        ),
        "reset": InspectField(
            path="reset",
            label="Reset",
            kind="button",
            getter=lambda _target: None,
            action=reset,
        ),
    }


def _metadata(_target):
    return {
        "layout": [
            {"kind": "section", "label": "General"},
            {"kind": "field", "path": "enabled"},
            {"kind": "field", "path": "gain", "visible_if": "enabled"},
            {"kind": "separator"},
        ]
    }


def _bind_font(document):
    renderer = DrawListRenderer()
    assert renderer.set_default_font_path(str(resolve_native_ui_font()), 15)
    renderer.bind_text_measurer(document)
    return renderer


def _click(widget) -> None:
    bounds = widget.bounds
    pointer = PointerEvent()
    pointer.x = bounds.x + bounds.width * 0.5
    pointer.y = bounds.y + bounds.height * 0.5
    pointer.type = PointerEventType.Down
    assert widget.dispatch_pointer_event(pointer) == EventResult.Handled
    pointer.type = PointerEventType.Up
    assert widget.dispatch_pointer_event(pointer) == EventResult.Handled


def test_native_inspector_fields_typed_edits_color_action_and_rebuild_lifetime():
    document = tc_ui_document_create()
    renderer = _bind_font(document)
    first = _Target()
    second = _Target(gain=0.75, mode="b")
    controller = InspectorFieldsController(
        field_collector=_fields,
        metadata_collector=_metadata,
    )
    colors = []
    layer_masks = []

    def show_color(initial, callback):
        colors.append(initial)
        callback((0.1, 0.2, 0.3, 0.4))

    def show_layer_mask(initial, layer_names, callback):
        layer_masks.append((initial, layer_names))
        callback(0b110)

    renders = []
    panel = build_native_inspector_fields(
        document,
        controller,
        request_render=lambda: renders.append(True),
        show_color_dialog=show_color,
        show_layer_mask_dialog=show_layer_mask,
        layer_names=lambda: tuple(f"Layer {index}" for index in range(64)),
    )
    assert document.add_root(panel.root.handle)
    panel.set_targets([first, second])
    document.layout_roots(Rect(0.0, 0.0, 420.0, 600.0))
    live_count = document.live_widget_count

    assert panel.field_widgets["enabled"].checked
    assert panel.field_widgets["gain"].value == pytest.approx(0.0)
    assert panel.field_widgets["mode"].selected_index == -1

    panel.field_widgets["gain"].value = 1.5
    assert first.gain == pytest.approx(1.5)
    assert second.gain == pytest.approx(1.5)
    panel.field_widgets["mode"].selected_index = 1
    assert first.mode == "b"
    assert second.mode == "b"
    panel.field_widgets["enabled"].checked = False
    assert not first.enabled
    assert not second.enabled
    assert "gain" not in panel.field_widgets

    panel.controller.invoke_action("reset")
    panel.refresh()
    assert first.resets == 1
    assert second.resets == 1
    document.layout_roots(Rect(0.0, 0.0, 420.0, 600.0))
    tint_button = panel.field_widgets["tint"]
    bounds = tint_button.widget.bounds
    pointer = PointerEvent()
    pointer.type = PointerEventType.Down
    pointer.x = bounds.x + bounds.width * 0.5
    pointer.y = bounds.y + bounds.height * 0.5
    assert tint_button.widget.dispatch_pointer_event(pointer) == EventResult.Handled
    pointer.type = PointerEventType.Up
    assert tint_button.widget.dispatch_pointer_event(pointer) == EventResult.Handled
    assert colors == [(1.0, 0.5, 0.25, 1.0)]
    assert first.tint == pytest.approx((0.1, 0.2, 0.3, 0.4))
    assert second.tint == pytest.approx((0.1, 0.2, 0.3, 0.4))

    layer_mask_button = panel.field_widgets["layer_mask"]
    bounds = layer_mask_button.widget.bounds
    pointer.x = bounds.x + bounds.width * 0.5
    pointer.y = bounds.y + bounds.height * 0.5
    pointer.type = PointerEventType.Down
    assert layer_mask_button.widget.dispatch_pointer_event(pointer) == EventResult.Handled
    pointer.type = PointerEventType.Up
    assert layer_mask_button.widget.dispatch_pointer_event(pointer) == EventResult.Handled
    assert layer_masks == [(0b101, tuple(f"Layer {index}" for index in range(64)))]
    assert first.layer_mask == 0b110
    assert second.layer_mask == 0b110

    panel.refresh()
    assert document.live_widget_count == live_count - 3
    draw_list = DrawList()
    document.paint(PaintContext(draw_list))
    assert draw_list.command_count > 10
    assert renders
    renderer.release_gpu()
    tc_ui_document_destroy(document)


def test_native_inspector_uint32_preserves_values_above_signed_int_range():
    @dataclass
    class Target:
        stable_id: int = 4_000_000_000

    def set_stable_id(item, value):
        item.stable_id = value

    target = Target()
    controller = InspectorFieldsController(
        field_collector=lambda _target: {
            "stable_id": InspectField(
                path="stable_id",
                label="Stable Id",
                kind="uint32",
                min=0,
                max=4_294_967_295,
                step=1,
                getter=lambda item: item.stable_id,
                setter=set_stable_id,
            )
        },
        metadata_collector=lambda _target: {},
    )
    document = tc_ui_document_create()
    panel = build_native_inspector_fields(document, controller, request_render=lambda: None)
    assert document.add_root(panel.root.handle)
    panel.set_targets([target])

    editor = panel.field_widgets["stable_id"]
    assert editor.text == "4000000000"
    assert document.set_focus(editor.handle)
    editor.text = "4294967295"
    key = KeyEvent()
    key.type = KeyEventType.Down
    key.key = KeyCode.Enter
    assert document.dispatch_key_event(key) == EventResult.Handled
    assert target.stable_id == 4_294_967_295
    tc_ui_document_destroy(document)


def test_native_inspector_resource_selection_and_creation():
    @dataclass
    class Target:
        texture: dict[str, str | None] | None = None

    class Accessors:
        allow_none = True

        def __init__(self):
            self.created = False
            self.create_item = self.create

        def list_items(self):
            items = [("first", "uuid-1"), ("second", "uuid-2")]
            if self.created:
                items.append(("created", "uuid-3"))
            return items

        def create(self):
            self.created = True
            return "created", "uuid-3"

    class Resources:
        def __init__(self):
            self.accessors = Accessors()

        def get_handle_accessors(self, kind):
            return self.accessors if kind == "tc_texture" else None

    def set_texture(target, value):
        target.texture = value

    target = Target()
    resources = Resources()
    controller = InspectorFieldsController(
        field_collector=lambda _target: {
            "texture": InspectField(
                path="texture",
                label="Texture",
                kind="tc_texture",
                getter=lambda item: item.texture,
                setter=set_texture,
            )
        },
        metadata_collector=lambda _target: {},
    )
    document = tc_ui_document_create()
    panel = build_native_inspector_fields(
        document,
        controller,
        request_render=lambda: None,
        resource_catalog=InspectorResourceCatalog(resources),
    )
    assert document.add_root(panel.root.handle)
    panel.set_targets([target])
    document.layout_roots(Rect(0.0, 0.0, 420.0, 200.0))

    controls = panel.field_widgets["texture"]
    assert isinstance(controls, NativeResourceFieldWidgets)
    assert controls.combo.selected_index == 0
    controls.combo.selected_index = 2
    assert target.texture == {"uuid": "uuid-2", "name": "second"}

    controls = panel.field_widgets["texture"]
    assert isinstance(controls, NativeResourceFieldWidgets)
    assert controls.create_button is not None
    document.layout_roots(Rect(0.0, 0.0, 420.0, 200.0))
    _click(controls.create_button.widget)
    assert target.texture == {"uuid": "uuid-3", "name": "created"}
    tc_ui_document_destroy(document)


def test_native_inspector_list_reorder_remove_and_undo():
    @dataclass
    class Target:
        items: list[str]

    class ListEditCommand(UndoCommand):
        def __init__(self, target, field_info, old_value, new_value):
            super().__init__("List edit")
            self.target = target
            self.field_info = field_info
            self.old_value = list(old_value)
            self.new_value = list(new_value)

        def do(self):
            self.field_info.set_value(self.target, list(self.new_value))

        def undo(self):
            self.field_info.set_value(self.target, list(self.old_value))

    target = Target(["a", "b", "c"])
    stack = UndoStack()

    def set_items(item, value):
        item.items = list(value)

    def apply_change(field_info, targets, old_values, value, _merge):
        assert len(targets) == 1
        stack.push(ListEditCommand(targets[0], field_info, old_values[0], value))

    controller = InspectorFieldsController(
        field_collector=lambda _target: {
            "items": InspectField(
                path="items",
                label="Items",
                kind="list[string]",
                getter=lambda item: list(item.items),
                setter=set_items,
            )
        },
        metadata_collector=lambda _target: {},
        change_handler=apply_change,
    )
    document = tc_ui_document_create()
    panel = build_native_inspector_fields(document, controller, request_render=lambda: None)
    assert document.add_root(panel.root.handle)
    panel.set_targets([target])
    document.layout_roots(Rect(0.0, 0.0, 420.0, 240.0))

    controls = panel.field_widgets["items"]
    assert isinstance(controls, NativeListFieldWidgets)
    assert controls.list_widget.select(1)
    _click(controls.move_up_button.widget)
    assert target.items == ["b", "a", "c"]
    stack.undo()
    assert target.items == ["a", "b", "c"]

    panel.refresh()
    document.layout_roots(Rect(0.0, 0.0, 420.0, 240.0))
    controls = panel.field_widgets["items"]
    assert isinstance(controls, NativeListFieldWidgets)
    assert controls.list_widget.select(1)
    _click(controls.remove_button.widget)
    assert target.items == ["a", "c"]
    stack.undo()
    assert target.items == ["a", "b", "c"]
    tc_ui_document_destroy(document)


def test_native_inspector_specialized_choice_presenters():
    @dataclass
    class Target:
        agent: str = "Human"
        area: int = 2
        clip: str = "Run"

    class Choices(InspectorSpecialChoiceProvider):
        def choices(self, kind, _targets):
            values = {
                "agent_type": (("Human", "Human"), ("Vehicle", "Vehicle")),
                "navmesh_area": ((0, "0: Walkable"), (2, "2: Jump")),
                "clip_selector": (("", "(none)"), ("Run", "Run")),
            }
            return values.get(kind)

    def set_agent(item, value):
        item.agent = value

    def set_area(item, value):
        item.area = value

    def set_clip(item, value):
        item.clip = value

    def fields(_target):
        return {
            "agent": InspectField(
                path="agent",
                label="Agent",
                kind="agent_type",
                getter=lambda item: item.agent,
                setter=set_agent,
            ),
            "area": InspectField(
                path="area",
                label="Area",
                kind="navmesh_area",
                getter=lambda item: item.area,
                setter=set_area,
            ),
            "clip": InspectField(
                path="clip",
                label="Clip",
                kind="clip_selector",
                getter=lambda item: item.clip,
                setter=set_clip,
            ),
        }

    target = Target()
    controller = InspectorFieldsController(
        field_collector=fields,
        metadata_collector=lambda _target: {},
    )
    document = tc_ui_document_create()
    panel = build_native_inspector_fields(
        document,
        controller,
        request_render=lambda: None,
        special_choices=Choices(),
    )
    panel.set_targets([target])

    assert panel.field_widgets["agent"].selected_index == 0
    assert panel.field_widgets["area"].selected_index == 1
    assert panel.field_widgets["clip"].selected_index == 1
    panel.field_widgets["agent"].selected_index = 1
    panel.field_widgets["area"].selected_index = 0
    panel.field_widgets["clip"].selected_index = 0
    assert target == Target(agent="Vehicle", area=0, clip="")
    tc_ui_document_destroy(document)


def test_native_inspector_slider_and_interval_slider_edits():
    @dataclass
    class Target:
        fill_percent: int = 25
        coordinate: tuple[float, float, float] = (2.0, -5.0, 10.0)

    def set_fill_percent(item, value):
        item.fill_percent = value

    def set_coordinate(item, value):
        item.coordinate = tuple(value)

    def fields(_target):
        return {
            "fill_percent": InspectField(
                path="fill_percent",
                label="Fill",
                kind="slider",
                min=0,
                max=100,
                getter=lambda item: item.fill_percent,
                setter=set_fill_percent,
            ),
            "coordinate": InspectField(
                path="coordinate",
                label="Coordinate",
                kind="interval_slider",
                step=0.1,
                getter=lambda item: list(item.coordinate),
                setter=set_coordinate,
            ),
        }

    target = Target()
    controller = InspectorFieldsController(
        field_collector=fields,
        metadata_collector=lambda _target: {},
    )
    document = tc_ui_document_create()
    panel = build_native_inspector_fields(document, controller, request_render=lambda: None)
    panel.set_targets([target])

    slider = panel.field_widgets["fill_percent"]
    slider.value = 42.4
    assert target.fill_percent == 42

    interval = panel.field_widgets["coordinate"]
    assert isinstance(interval, NativeIntervalSliderWidgets)
    interval.value.value = 7.0
    assert target.coordinate == pytest.approx([7.0, -5.0, 10.0])

    interval = panel.field_widgets["coordinate"]
    assert isinstance(interval, NativeIntervalSliderWidgets)
    interval.minimum.value = 8.0
    assert target.coordinate == pytest.approx([8.0, 8.0, 10.0])

    interval = panel.field_widgets["coordinate"]
    assert isinstance(interval, NativeIntervalSliderWidgets)
    interval.maximum.value = 6.0
    assert target.coordinate == pytest.approx([8.0, 8.0, 8.0])
    tc_ui_document_destroy(document)


def test_native_inspector_vec3_list_add_edit_reorder_and_remove():
    @dataclass
    class Target:
        points: list[list[float]]

    def set_points(item, value):
        item.points = [list(point) for point in value]

    target = Target([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    controller = InspectorFieldsController(
        field_collector=lambda _target: {
            "points": InspectField(
                path="points",
                label="Points",
                kind="list[vec3]",
                step=0.25,
                getter=lambda item: [list(point) for point in item.points],
                setter=set_points,
            )
        },
        metadata_collector=lambda _target: {},
    )
    document = tc_ui_document_create()
    panel = build_native_inspector_fields(document, controller, request_render=lambda: None)
    assert document.add_root(panel.root.handle)
    panel.set_targets([target])
    document.layout_roots(Rect(0.0, 0.0, 420.0, 280.0))

    controls = panel.field_widgets["points"]
    assert isinstance(controls, NativeVec3ListFieldWidgets)
    assert controls.list_widget.select(0)
    controls.coordinate_boxes[1].value = 7.5
    assert target.points == [[1.0, 7.5, 3.0], [4.0, 5.0, 6.0]]

    controls = panel.field_widgets["points"]
    assert isinstance(controls, NativeVec3ListFieldWidgets)
    document.layout_roots(Rect(0.0, 0.0, 420.0, 280.0))
    _click(controls.add_button.widget)
    assert target.points[-1] == pytest.approx([0.0, 0.0, 0.0])

    controls = panel.field_widgets["points"]
    assert isinstance(controls, NativeVec3ListFieldWidgets)
    assert controls.list_widget.select(2)
    document.layout_roots(Rect(0.0, 0.0, 420.0, 280.0))
    _click(controls.move_up_button.widget)
    assert target.points[1] == pytest.approx([0.0, 0.0, 0.0])

    controls = panel.field_widgets["points"]
    assert isinstance(controls, NativeVec3ListFieldWidgets)
    assert controls.list_widget.select(1)
    document.layout_roots(Rect(0.0, 0.0, 420.0, 280.0))
    _click(controls.remove_button.widget)
    assert target.points == [[1.0, 7.5, 3.0], [4.0, 5.0, 6.0]]
    tc_ui_document_destroy(document)
