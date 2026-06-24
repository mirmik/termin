from termin.editor_tcgui.widgets.field_widgets import (
    ComboFieldWidget,
    FieldWidgetFactory,
    HandleSelectorWidget,
    Vec3ListFieldWidget,
)
from termin.inspect import InspectField


def test_vec3_list_field_widget_edits_and_rebuilds_rows():
    widget = Vec3ListFieldWidget()
    widget.set_value([(1, 2, 3), [4, 5, 6]])

    changes = []
    widget.on_value_changed = lambda: changes.append(widget.get_value())

    widget._set_point_component(0, 1, 8.5)
    assert widget.get_value() == [[1.0, 8.5, 3.0], [4.0, 5.0, 6.0]]

    widget._insert_point_after(0)
    assert widget.get_value() == [
        [1.0, 8.5, 3.0],
        [0.0, 0.0, 0.0],
        [4.0, 5.0, 6.0],
    ]

    widget._remove_point(1)
    assert widget.get_value() == [[1.0, 8.5, 3.0], [4.0, 5.0, 6.0]]
    assert len(changes) == 3


def test_field_widget_factory_uses_vec3_list_widget():
    field = InspectField(path="points", label="Positions", kind="list[vec3]")

    widget = FieldWidgetFactory().create(field)

    assert isinstance(widget, Vec3ListFieldWidget)


def test_field_widget_factory_uses_combo_for_enum_choices():
    field = InspectField(
        path="render_mode",
        label="Render Mode",
        kind="enum",
        choices=[("0", "World Billboard"), ("4", "World Tube")],
    )

    widget = FieldWidgetFactory().create(field)
    widget.set_value(4)

    assert isinstance(widget, ComboFieldWidget)
    assert widget.get_value() == "4"


def test_field_widget_factory_uses_handle_selector_for_tc_texture():
    field = InspectField(path="albedo", label="Albedo", kind="tc_texture")

    widget = FieldWidgetFactory().create(field)

    assert isinstance(widget, HandleSelectorWidget)
