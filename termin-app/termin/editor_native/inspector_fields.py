"""Native projection of toolkit-neutral inspect-field snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Callable
import weakref

from termin.editor_core.inspector_fields_model import (
    InspectorFieldRow,
    InspectorFieldsController,
    InspectorFieldsSnapshot,
    values_equal,
)
from termin.editor_core.inspector_resources import InspectorResourceCatalog
from termin.editor_core.inspector_special_choices import (
    InspectorSpecialChoiceProvider,
    InspectorSpecialChoices,
)
from termin.gui_native import (
    CollectionItem,
    CollectionModel,
    Color,
    Document,
    EdgeInsets,
    Size,
    WidgetRef,
)


_logger = logging.getLogger(__name__)
ColorDialogHandler = Callable[
    [tuple[float, float, float, float], Callable[[tuple[float, ...] | None], None]],
    None,
]
LayerMaskDialogHandler = Callable[
    [int, tuple[str, ...], Callable[[int | None], None]],
    None,
]


def _vector(value: Any, size: int) -> tuple[float, ...]:
    if value is None:
        return tuple(0.0 for _ in range(size))
    try:
        items = tuple(float(item) for item in value)
    except (TypeError, ValueError) as error:
        _logger.error("Inspector vector value is not iterable: %r: %s", value, error)
        raise ValueError("inspector vector value is not iterable") from error
    if len(items) != size:
        _logger.error("Inspector vector requires %d values, got %d", size, len(items))
        raise ValueError(f"inspector vector requires {size} values")
    return items


def _color(value: Any) -> tuple[float, float, float, float]:
    if value is None:
        items = (1.0, 1.0, 1.0, 1.0)
    else:
        try:
            items = tuple(float(item) for item in value)
        except (TypeError, ValueError) as error:
            _logger.error("Inspector color value is not iterable: %r: %s", value, error)
            raise ValueError("inspector color value is not iterable") from error
    if len(items) == 3:
        items = (*items, 1.0)
    if len(items) != 4:
        _logger.error("Inspector color requires three or four values, got %d", len(items))
        raise ValueError("inspector color requires three or four values")
    return tuple(max(0.0, min(1.0, item)) for item in items)


def _color_label(value: tuple[float, float, float, float]) -> str:
    return ", ".join(f"{component:.2f}" for component in value)


@dataclass(frozen=True)
class NativeResourceFieldWidgets:
    combo: object
    create_button: object | None


@dataclass
class NativeListFieldWidgets:
    model: CollectionModel
    list_widget: object
    move_up_button: object
    move_down_button: object
    remove_button: object
    selected_index: int = -1


@dataclass(frozen=True)
class NativeIntervalSliderWidgets:
    value: object
    minimum: object
    maximum: object


@dataclass
class NativeVec3ListFieldWidgets:
    model: CollectionModel
    list_widget: object
    coordinate_boxes: tuple[object, object, object]
    add_button: object
    move_up_button: object
    move_down_button: object
    remove_button: object
    selected_index: int = -1
    updating_coordinates: bool = False


@dataclass
class NativeInspectorFields:
    document: Document
    controller: InspectorFieldsController
    root: WidgetRef
    request_render: Callable[[], None]
    show_color_dialog: ColorDialogHandler | None = None
    show_layer_mask_dialog: LayerMaskDialogHandler | None = None
    layer_names: Callable[[], tuple[str, ...]] | None = None
    resource_catalog: InspectorResourceCatalog | None = None
    special_choices: InspectorSpecialChoiceProvider = field(default_factory=InspectorSpecialChoices)
    field_widgets: dict[str, object] = field(default_factory=dict)

    def set_targets(self, targets) -> None:
        self.rebuild(self.controller.set_targets(targets))

    def refresh(self) -> None:
        self.rebuild(self.controller.refresh())

    def rebuild(self, snapshot: InspectorFieldsSnapshot) -> None:
        self._destroy_rows()
        for row in snapshot.rows:
            if not row.visible:
                continue
            if row.kind == "section":
                label = self.document.create_label(row.label, "native-inspector-section")
                label.preferred_size = Size(260.0, 26.0)
                self.root.add_fixed_child(label, 26.0)
            elif row.kind == "separator":
                separator = self.document.create_hstack("native-inspector-separator")
                separator.set_layout_background(Color(0.24, 0.26, 0.31, 1.0))
                self.root.add_fixed_child(separator, 1.0)
            elif row.kind == "field":
                self._append_field(row)
            else:
                _logger.error("Unknown native inspector row kind: %s", row.kind)
        self.request_render()

    def _destroy_rows(self) -> None:
        for child in tuple(self.root.children):
            if not self.document.destroy_widget_recursive(child.handle):
                _logger.error("Failed to destroy native inspector row: %s", child.debug_name)
        self.field_widgets.clear()

    def _append_field(self, row: InspectorFieldRow) -> None:
        if row.field is None:
            _logger.error("Native inspector field row '%s' has no InspectField", row.key)
            return
        if row.field.kind == "list[vec3]":
            self._append_vec3_list_field(row)
            return
        if row.field.kind.startswith("list[") or row.field.kind == "entity_list":
            self._append_list_field(row)
            return
        if row.field.kind == "interval_slider":
            self._append_interval_slider_field(row)
            return
        container = self.document.create_hstack(f"native-inspector-row-{row.key}")
        container.set_layout_spacing(4.0)
        container.set_layout_padding(EdgeInsets(0.0, 1.0, 0.0, 1.0))
        container.preferred_size = Size(300.0, 28.0)
        if row.field.kind != "button":
            suffix = " (mixed)" if row.mixed else ""
            label = self.document.create_label(
                f"{row.label}{suffix}",
                f"native-inspector-label-{row.key}",
            )
            container.add_fixed_child(label, 130.0)
        control = self._create_control(row)
        if control is None:
            self.document.destroy_widget_recursive(container.handle)
            return
        container.add_stretch_child(control)
        self.root.add_fixed_child(container, 28.0)

    def _append_interval_slider_field(self, row: InspectorFieldRow) -> None:
        field_info = row.field
        if field_info is None:
            return
        values = (0.0, 0.0, 1.0) if row.mixed else _vector(row.value, 3)
        current, minimum, maximum = values
        if minimum > maximum:
            _logger.error(
                "Inspector interval slider '%s' has inverted range: %s > %s",
                row.key,
                minimum,
                maximum,
            )
            minimum, maximum = maximum, minimum
        current = max(minimum, min(maximum, current))

        container = self.document.create_vstack(f"native-inspector-interval-{row.key}")
        container.set_layout_spacing(3.0)
        slider = self.document.create_slider_edit(current)
        slider.label = f"{row.label} (mixed)" if row.mixed else row.label
        slider.set_range(minimum, maximum)
        slider.set_step(float(field_info.step) if field_info.step is not None else 0.01)
        slider.set_decimals(4)
        slider.widget.enabled = not field_info.read_only
        container.add_fixed_child(slider.widget, 30.0)

        bounds_row = self.document.create_hstack(f"native-inspector-interval-bounds-{row.key}")
        bounds_row.set_layout_spacing(3.0)
        minimum_box = self.document.create_spin_box(minimum)
        maximum_box = self.document.create_spin_box(maximum)
        for label_text, box in (("Min", minimum_box), ("Max", maximum_box)):
            label = self.document.create_label(
                label_text,
                f"native-inspector-interval-{label_text.lower()}-label-{row.key}",
            )
            bounds_row.add_fixed_child(label, 28.0)
            box.set_range(-1.0e9, 1.0e9)
            box.step = float(field_info.step) if field_info.step is not None else 0.01
            box.decimals = 4
            box.widget.enabled = not field_info.read_only
            bounds_row.add_stretch_child(box.widget)
        container.add_fixed_child(bounds_row, 28.0)

        controls = NativeIntervalSliderWidgets(slider, minimum_box, maximum_box)
        weak_owner = weakref.ref(self)

        def apply_value(value: float) -> None:
            owner = weak_owner()
            if owner is not None:
                owner._apply(row.key, [value, minimum, maximum], merge=True)

        def apply_minimum(value: float) -> None:
            owner = weak_owner()
            if owner is not None:
                new_minimum = min(value, maximum)
                owner._apply(
                    row.key,
                    [max(new_minimum, min(maximum, current)), new_minimum, maximum],
                    merge=True,
                )

        def apply_maximum(value: float) -> None:
            owner = weak_owner()
            if owner is not None:
                new_maximum = max(value, minimum)
                owner._apply(
                    row.key,
                    [max(minimum, min(new_maximum, current)), minimum, new_maximum],
                    merge=True,
                )

        slider.connect_changed(apply_value)
        minimum_box.connect_changed(apply_minimum)
        maximum_box.connect_changed(apply_maximum)
        self.field_widgets[row.key] = controls
        self.root.add_fixed_child(container, 61.0)

    def _append_vec3_list_field(self, row: InspectorFieldRow) -> None:
        field_info = row.field
        if field_info is None:
            return
        values = () if row.mixed or row.value is None else tuple(_vector(point, 3) for point in row.value)
        editable = not field_info.read_only and not row.mixed
        container = self.document.create_vstack(f"native-inspector-vec3-list-{row.key}")
        container.set_layout_spacing(3.0)
        suffix = " (mixed)" if row.mixed else f" ({len(values)})"
        label = self.document.create_label(
            f"{row.label}{suffix}",
            f"native-inspector-vec3-list-label-{row.key}",
        )
        container.add_fixed_child(label, 24.0)

        model = CollectionModel()
        model.set_items(
            [
                CollectionItem(
                    f"{row.key}:{index}",
                    f"{index}: ({point[0]:.4g}, {point[1]:.4g}, {point[2]:.4g})",
                )
                for index, point in enumerate(values)
            ]
        )
        list_widget = self.document.create_list_widget(model)
        list_widget.set_row_height(24.0)
        list_widget.set_row_spacing(1.0)
        list_widget.widget.enabled = editable
        container.add_fixed_child(list_widget.widget, 104.0)

        coordinate_row = self.document.create_hstack(f"native-inspector-vec3-list-coordinates-{row.key}")
        coordinate_row.set_layout_spacing(2.0)
        coordinate_boxes = []
        for axis in "XYZ":
            axis_label = self.document.create_label(
                axis,
                f"native-inspector-vec3-list-{axis.lower()}-label-{row.key}",
            )
            coordinate_row.add_fixed_child(axis_label, 14.0)
            box = self.document.create_spin_box(0.0)
            box.set_range(
                -1.0e9 if field_info.min is None else float(field_info.min),
                1.0e9 if field_info.max is None else float(field_info.max),
            )
            box.step = float(field_info.step) if field_info.step is not None else 0.01
            box.decimals = 4
            box.widget.enabled = False
            coordinate_row.add_stretch_child(box.widget)
            coordinate_boxes.append(box)
        container.add_fixed_child(coordinate_row, 28.0)

        buttons = self.document.create_hstack(f"native-inspector-vec3-list-buttons-{row.key}")
        buttons.set_layout_spacing(3.0)
        add = self.document.create_button("Add", f"native-inspector-vec3-list-add-{row.key}")
        move_up = self.document.create_button("↑", f"native-inspector-vec3-list-up-{row.key}")
        move_down = self.document.create_button("↓", f"native-inspector-vec3-list-down-{row.key}")
        remove = self.document.create_button("Remove", f"native-inspector-vec3-list-remove-{row.key}")
        buttons.add_stretch_child(add.widget)
        buttons.add_fixed_child(move_up.widget, 32.0)
        buttons.add_fixed_child(move_down.widget, 32.0)
        buttons.add_stretch_child(remove.widget)
        container.add_fixed_child(buttons, 28.0)

        controls = NativeVec3ListFieldWidgets(
            model=model,
            list_widget=list_widget,
            coordinate_boxes=tuple(coordinate_boxes),
            add_button=add,
            move_up_button=move_up,
            move_down_button=move_down,
            remove_button=remove,
        )
        weak_owner = weakref.ref(self)

        def update_actions() -> None:
            selected = 0 <= controls.selected_index < len(values)
            for box in controls.coordinate_boxes:
                box.widget.enabled = editable and selected
            add.widget.enabled = editable
            move_up.widget.enabled = editable and controls.selected_index > 0
            move_down.widget.enabled = editable and 0 <= controls.selected_index < len(values) - 1
            remove.widget.enabled = editable and selected

        def selected(indices: list[int]) -> None:
            controls.selected_index = indices[-1] if indices else -1
            controls.updating_coordinates = True
            try:
                point = (
                    values[controls.selected_index] if 0 <= controls.selected_index < len(values) else (0.0, 0.0, 0.0)
                )
                for box, component in zip(controls.coordinate_boxes, point, strict=True):
                    box.value = component
            finally:
                controls.updating_coordinates = False
            update_actions()

        def apply_reordered(offset: int) -> None:
            owner = weak_owner()
            source = controls.selected_index
            destination = source + offset
            if owner is None or not (0 <= source < len(values)) or not (0 <= destination < len(values)):
                return
            updated = [list(point) for point in values]
            updated[source], updated[destination] = updated[destination], updated[source]
            owner._apply(row.key, updated)

        def add_point() -> None:
            owner = weak_owner()
            if owner is not None and editable:
                owner._apply(row.key, [*[list(point) for point in values], [0.0, 0.0, 0.0]])

        def remove_selected() -> None:
            owner = weak_owner()
            index = controls.selected_index
            if owner is None or not (0 <= index < len(values)):
                return
            updated = [list(point) for point in values]
            del updated[index]
            owner._apply(row.key, updated)

        def coordinate_changed(_value: float) -> None:
            owner = weak_owner()
            index = controls.selected_index
            if owner is None or controls.updating_coordinates or not (0 <= index < len(values)):
                return
            updated = [list(point) for point in values]
            updated[index] = [box.value for box in controls.coordinate_boxes]
            owner._apply(row.key, updated, merge=True)

        list_widget.connect_selection_changed(selected)
        for box in controls.coordinate_boxes:
            box.connect_changed(coordinate_changed)
        add.connect_clicked(add_point)
        move_up.connect_clicked(lambda: apply_reordered(-1))
        move_down.connect_clicked(lambda: apply_reordered(1))
        remove.connect_clicked(remove_selected)
        update_actions()
        self.field_widgets[row.key] = controls
        self.root.add_fixed_child(container, 193.0)

    def _append_list_field(self, row: InspectorFieldRow) -> None:
        field_info = row.field
        if field_info is None:
            return
        values = () if row.mixed or row.value is None else tuple(row.value)
        container = self.document.create_vstack(f"native-inspector-list-{row.key}")
        container.set_layout_spacing(3.0)
        suffix = " (mixed)" if row.mixed else f" ({len(values)})"
        label = self.document.create_label(
            f"{row.label}{suffix}",
            f"native-inspector-list-label-{row.key}",
        )
        container.add_fixed_child(label, 24.0)
        model = CollectionModel()
        model.set_items([CollectionItem(f"{row.key}:{index}", str(value)) for index, value in enumerate(values)])
        list_widget = self.document.create_list_widget(model)
        list_widget.set_row_height(24.0)
        list_widget.set_row_spacing(1.0)
        list_widget.widget.enabled = not field_info.read_only and not row.mixed
        container.add_fixed_child(list_widget.widget, 104.0)
        buttons = self.document.create_hstack(f"native-inspector-list-buttons-{row.key}")
        buttons.set_layout_spacing(3.0)
        move_up = self.document.create_button("↑", f"native-inspector-list-up-{row.key}")
        move_down = self.document.create_button("↓", f"native-inspector-list-down-{row.key}")
        remove = self.document.create_button("Remove", f"native-inspector-list-remove-{row.key}")
        buttons.add_fixed_child(move_up.widget, 32.0)
        buttons.add_fixed_child(move_down.widget, 32.0)
        buttons.add_stretch_child(remove.widget)
        container.add_fixed_child(buttons, 28.0)
        controls = NativeListFieldWidgets(model, list_widget, move_up, move_down, remove)
        weak_owner = weakref.ref(self)

        def update_actions() -> None:
            editable = not field_info.read_only and not row.mixed
            move_up.widget.enabled = editable and controls.selected_index > 0
            move_down.widget.enabled = editable and 0 <= controls.selected_index < len(values) - 1
            remove.widget.enabled = editable and controls.selected_index >= 0

        def selected(indices: list[int]) -> None:
            controls.selected_index = indices[-1] if indices else -1
            update_actions()

        def apply_reordered(offset: int) -> None:
            owner = weak_owner()
            source = controls.selected_index
            destination = source + offset
            if owner is None or not (0 <= source < len(values)) or not (0 <= destination < len(values)):
                return
            updated = list(values)
            updated[source], updated[destination] = updated[destination], updated[source]
            owner._apply(row.key, updated)

        def remove_selected() -> None:
            owner = weak_owner()
            index = controls.selected_index
            if owner is None or not (0 <= index < len(values)):
                return
            updated = list(values)
            del updated[index]
            owner._apply(row.key, updated)

        list_widget.connect_selection_changed(selected)
        move_up.connect_clicked(lambda: apply_reordered(-1))
        move_down.connect_clicked(lambda: apply_reordered(1))
        remove.connect_clicked(remove_selected)
        update_actions()
        self.field_widgets[row.key] = controls
        self.root.add_fixed_child(container, 165.0)

    def _create_control(self, row: InspectorFieldRow) -> WidgetRef | None:
        field_info = row.field
        if field_info is None:
            return None
        kind = field_info.kind
        if kind in ("float", "double", "int"):
            value = 0.0 if row.mixed or row.value is None else float(row.value)
            spin = self.document.create_spin_box(value)
            minimum = -1.0e9 if field_info.min is None else float(field_info.min)
            maximum = 1.0e9 if field_info.max is None else float(field_info.max)
            spin.set_range(minimum, maximum)
            spin.step = float(field_info.step) if field_info.step is not None else (1.0 if kind == "int" else 0.01)
            spin.decimals = 0 if kind == "int" else 4
            weak_owner = weakref.ref(self)

            def changed(value: float) -> None:
                owner = weak_owner()
                if owner is not None:
                    owner._apply(row.key, int(round(value)) if kind == "int" else value, merge=True)

            spin.connect_changed(changed)
            spin.widget.enabled = not field_info.read_only
            self.field_widgets[row.key] = spin
            return spin.widget
        if kind == "slider":
            value = 0.0 if row.mixed or row.value is None else float(row.value)
            slider = self.document.create_slider_edit(value)
            minimum = 0.0 if field_info.min is None else float(field_info.min)
            maximum = 100.0 if field_info.max is None else float(field_info.max)
            slider.set_range(minimum, maximum)
            slider.set_step(float(field_info.step) if field_info.step is not None else 1.0)
            slider.set_decimals(0)
            weak_owner = weakref.ref(self)

            def changed(value: float) -> None:
                owner = weak_owner()
                if owner is not None:
                    owner._apply(row.key, int(round(value)), merge=True)

            slider.connect_changed(changed)
            slider.widget.enabled = not field_info.read_only
            self.field_widgets[row.key] = slider
            return slider.widget
        if kind in ("string", "text"):
            text = "<mixed>" if row.mixed else ("" if row.value is None else str(row.value))
            editor = self.document.create_text_input(text)
            weak_owner = weakref.ref(self)

            def submitted(value: str) -> None:
                owner = weak_owner()
                if owner is not None:
                    owner._apply(row.key, value)

            editor.connect_submitted(submitted)
            editor.widget.enabled = not field_info.read_only
            self.field_widgets[row.key] = editor
            return editor.widget
        if kind == "bool":
            checkbox = self.document.create_checkbox(False if row.mixed else bool(row.value))
            weak_owner = weakref.ref(self)

            def changed(value: bool) -> None:
                owner = weak_owner()
                if owner is not None:
                    owner._apply(row.key, value)

            checkbox.connect_changed(changed)
            checkbox.widget.enabled = not field_info.read_only
            self.field_widgets[row.key] = checkbox
            return checkbox.widget
        choices = tuple(field_info.choices or ())
        if not choices:
            choices = self.special_choices.choices(kind, self.controller.targets) or ()
        if kind in ("enum", "combo") or choices:
            combo = self.document.create_combo_box()
            for _value, label in choices:
                combo.add_item(label)
            selected = -1
            if not row.mixed:
                for index, (value, _label) in enumerate(choices):
                    if values_equal(value, row.value):
                        selected = index
                        break
            combo.selected_index = selected
            weak_owner = weakref.ref(self)

            def changed(index: int, _text: str) -> None:
                owner = weak_owner()
                if owner is not None and 0 <= index < len(choices):
                    owner._apply(row.key, choices[index][0])

            combo.connect_changed(changed)
            combo.widget.enabled = not field_info.read_only
            self.field_widgets[row.key] = combo
            return combo.widget
        resource_choices = None if self.resource_catalog is None else self.resource_catalog.choices(kind)
        if resource_choices is not None:
            control_row = self.document.create_hstack(f"native-inspector-resource-{row.key}")
            control_row.set_layout_spacing(2.0)
            combo = self.document.create_combo_box()
            for choice in resource_choices.items:
                combo.add_item(choice.label)
            combo.selected_index = -1 if row.mixed else resource_choices.index_for_value(row.value)
            weak_owner = weakref.ref(self)

            def changed(index: int, _text: str) -> None:
                owner = weak_owner()
                if owner is not None and 0 <= index < len(resource_choices.items):
                    owner._apply(row.key, resource_choices.items[index].value)

            combo.connect_changed(changed)
            combo.widget.enabled = not field_info.read_only
            control_row.add_stretch_child(combo.widget)
            create_button = None
            if resource_choices.can_create:
                create_button = self.document.create_button(
                    "+",
                    f"native-inspector-resource-create-{row.key}",
                )

                def create() -> None:
                    owner = weak_owner()
                    if owner is None or owner.resource_catalog is None:
                        return
                    created = owner.resource_catalog.create(kind)
                    if created is not None:
                        owner._apply(row.key, created.value)

                create_button.connect_clicked(create)
                create_button.widget.enabled = not field_info.read_only
                control_row.add_fixed_child(create_button.widget, 28.0)
            self.field_widgets[row.key] = NativeResourceFieldWidgets(combo, create_button)
            return control_row
        if kind in ("vec3", "vector3"):
            values = (0.0, 0.0, 0.0) if row.mixed else _vector(row.value, 3)
            vector_row = self.document.create_hstack(f"native-inspector-vector-{row.key}")
            vector_row.set_layout_spacing(2.0)
            boxes = []
            weak_owner = weakref.ref(self)
            for component_index, component in enumerate(values):
                box = self.document.create_spin_box(component)
                box.set_range(
                    -1.0e9 if field_info.min is None else float(field_info.min),
                    1.0e9 if field_info.max is None else float(field_info.max),
                )
                box.step = float(field_info.step) if field_info.step is not None else 0.01
                box.decimals = 4

                def changed(_value: float, index=component_index) -> None:
                    owner = weak_owner()
                    if owner is None:
                        return
                    controls = owner.field_widgets.get(row.key)
                    if not isinstance(controls, tuple):
                        return
                    updated = [control.value for control in controls]
                    owner._apply(row.key, updated, merge=True)

                box.connect_changed(changed)
                box.widget.enabled = not field_info.read_only
                vector_row.add_stretch_child(box.widget)
                boxes.append(box)
            self.field_widgets[row.key] = tuple(boxes)
            return vector_row
        if kind == "color":
            color = (1.0, 1.0, 1.0, 1.0) if row.mixed else _color(row.value)
            button = self.document.create_button(_color_label(color), f"native-inspector-color-{row.key}")
            weak_owner = weakref.ref(self)

            def clicked() -> None:
                owner = weak_owner()
                if owner is None:
                    return
                if owner.show_color_dialog is None:
                    _logger.error("No color dialog service for inspector field '%s'", row.key)
                    return

                def finished(value: tuple[float, ...] | None) -> None:
                    current = weak_owner()
                    if current is not None and value is not None:
                        current._apply(row.key, tuple(value))

                owner.show_color_dialog(color, finished)

            button.connect_clicked(clicked)
            button.widget.enabled = not field_info.read_only
            self.field_widgets[row.key] = button
            return button.widget
        if kind == "layer_mask":
            try:
                mask = 0 if row.mixed else int(row.value or 0, 0)
            except TypeError:
                mask = 0 if row.mixed else int(row.value or 0)
            except ValueError:
                _logger.error(
                    "Invalid layer mask value for inspector field '%s': %r",
                    row.key,
                    row.value,
                )
                raise
            button = self.document.create_button(
                f"0x{mask:016X}",
                f"native-inspector-layer-mask-{row.key}",
            )
            weak_owner = weakref.ref(self)

            def clicked() -> None:
                owner = weak_owner()
                if owner is None:
                    return
                if owner.show_layer_mask_dialog is None or owner.layer_names is None:
                    _logger.error("No layer mask dialog service for inspector field '%s'", row.key)
                    return

                def finished(value: int | None) -> None:
                    current = weak_owner()
                    if current is not None and value is not None:
                        current._apply(row.key, f"0x{value:016x}")

                owner.show_layer_mask_dialog(mask, owner.layer_names(), finished)

            button.connect_clicked(clicked)
            button.widget.enabled = not field_info.read_only
            self.field_widgets[row.key] = button
            return button.widget
        if kind == "button":
            button = self.document.create_button(row.label, f"native-inspector-action-{row.key}")
            weak_owner = weakref.ref(self)

            def clicked() -> None:
                owner = weak_owner()
                if owner is not None:
                    owner.controller.invoke_action(row.key)
                    owner.refresh()

            button.connect_clicked(clicked)
            button.widget.enabled = not field_info.read_only
            self.field_widgets[row.key] = button
            return button.widget

        _logger.error("Unsupported native inspector field kind '%s' for '%s'", kind, row.key)
        value = "<mixed>" if row.mixed else str(row.value)
        label = self.document.create_label(value, f"native-inspector-unsupported-{row.key}")
        label.enabled = False
        self.field_widgets[row.key] = label
        return label

    def _apply(self, key: str, value: Any, *, merge: bool = False) -> None:
        self.rebuild(self.controller.apply_value(key, value, merge=merge))


def build_native_inspector_fields(
    document: Document,
    controller: InspectorFieldsController,
    *,
    request_render: Callable[[], None],
    show_color_dialog: ColorDialogHandler | None = None,
    show_layer_mask_dialog: LayerMaskDialogHandler | None = None,
    layer_names: Callable[[], tuple[str, ...]] | None = None,
    resource_catalog: InspectorResourceCatalog | None = None,
    special_choices: InspectorSpecialChoiceProvider | None = None,
) -> NativeInspectorFields:
    root = document.create_vstack("native-inspector-fields")
    root.stable_id = "editor.inspector.fields"
    root.set_layout_spacing(3.0)
    return NativeInspectorFields(
        document=document,
        controller=controller,
        root=root,
        request_render=request_render,
        show_color_dialog=show_color_dialog,
        show_layer_mask_dialog=show_layer_mask_dialog,
        layer_names=layer_names,
        resource_catalog=resource_catalog,
        special_choices=special_choices or InspectorSpecialChoices(),
    )


__all__ = [
    "ColorDialogHandler",
    "LayerMaskDialogHandler",
    "NativeInspectorFields",
    "NativeIntervalSliderWidgets",
    "NativeListFieldWidgets",
    "NativeResourceFieldWidgets",
    "NativeVec3ListFieldWidgets",
    "build_native_inspector_fields",
]
