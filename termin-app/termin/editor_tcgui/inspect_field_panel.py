"""tcgui port of InspectFieldPanel — shows inspect_fields for any object."""

from __future__ import annotations

from typing import Any, Callable, Optional

from tcbase import log
from tcgui.widgets.vstack import VStack
from tcgui.widgets.label import Label
from tcgui.widgets.grid_layout import GridLayout
from tcgui.widgets.separator import Separator
from tcgui.widgets.units import px

from termin.inspect import InspectField
from termin.editor_core.inspector_fields_model import (
    collect_inspect_fields,
    collect_inspector_metadata,
)
from termin.editor_tcgui.widgets.field_widgets import FieldWidget, FieldWidgetFactory


class InspectFieldPanel(VStack):
    """tcgui panel that shows inspect_fields for any object as a form."""

    def __init__(self, resources=None) -> None:
        super().__init__()
        self.spacing = 4

        self._target: Any = None
        self._fields: dict[str, InspectField] = {}
        self._field_metadata: dict[str, dict[str, Any]] = {}
        self._widgets: dict[str, FieldWidget] = {}
        self._row_widgets: dict[str, list[Any]] = {}
        self._updating_from_model: bool = False
        self._factory = FieldWidgetFactory(resources)
        self._grid = GridLayout(columns=2)
        self._grid.column_spacing = 4
        self._grid.row_spacing = 4
        self._grid.set_column_stretch(1, 1.0)
        self.add_child(self._grid)

        # on_field_changed(key, old_value, new_value)
        self.on_field_changed: Optional[Callable[[str, Any, Any], None]] = None

    def set_resources(self, resources) -> None:
        self._factory.set_resources(resources)

    def set_scene_getter(self, getter) -> None:
        self._factory.set_scene_getter(getter)

    def set_target(self, target: Any) -> None:
        # Remove old rows
        self._grid.clear()
        self._fields.clear()
        self._field_metadata.clear()
        self._widgets.clear()
        self._row_widgets.clear()
        self._target = target

        if target is None:
            if self._ui is not None:
                self._ui.request_layout()
            return

        fields = collect_inspect_fields(target)
        if not fields:
            if self._ui is not None:
                self._ui.request_layout()
            return

        self._fields = fields
        inspector_metadata = collect_inspector_metadata(target)
        field_metadata = inspector_metadata.get("fields", {})
        if isinstance(field_metadata, dict):
            self._field_metadata = {str(key): value for key, value in field_metadata.items() if isinstance(value, dict)}
        self._updating_from_model = True

        try:
            row_index = 0
            rendered: set[str] = set()
            layout = inspector_metadata.get("layout", [])
            if isinstance(layout, list):
                for item in layout:
                    if not isinstance(item, dict):
                        continue
                    row_index = self._add_layout_item(row_index, item, rendered)
            for key, field in fields.items():
                if key in rendered:
                    continue
                row_index = self._add_field_row(row_index, key, field, self._field_metadata.get(key, {}))
        finally:
            self._updating_from_model = False
            self._sync_visibility()
            if self._ui is not None:
                self._ui.request_layout()

    def _add_layout_item(self, row_index: int, item: dict[str, Any], rendered: set[str]) -> int:
        kind = item.get("kind", "field")
        if kind == "section":
            label = Label()
            label.text = str(item.get("label", ""))
            label.color = (0.72, 0.76, 0.84, 1.0)
            self._grid.add(label, row_index, 0, 1, 2)
            return row_index + 1
        if kind == "separator":
            sep = Separator()
            self._grid.add(sep, row_index, 0, 1, 2)
            return row_index + 1
        if kind != "field":
            log.error(f"InspectFieldPanel: unknown layout item kind '{kind}'")
            return row_index

        key = item.get("path")
        if not isinstance(key, str):
            log.error("InspectFieldPanel: field layout item has no string path")
            return row_index
        field = self._fields.get(key)
        if field is None:
            log.error(f"InspectFieldPanel: layout references unknown field '{key}'")
            return row_index
        metadata = dict(self._field_metadata.get(key, {}))
        metadata.update({k: v for k, v in item.items() if k not in ("kind", "path")})
        rendered.add(key)
        return self._add_field_row(row_index, key, field, metadata)

    def _add_field_row(self, row_index: int, key: str, field: InspectField, metadata: dict[str, Any]) -> int:
        widget = self._factory.create(field, metadata)
        widget.bind_field(key, field, self._target)
        self._widgets[key] = widget
        self._field_metadata[key] = metadata
        row_widgets: list[Any] = [widget]

        if widget.full_row():
            self._grid.add(widget, row_index, 0, 1, 2)
            widget.load_from_target()
        elif metadata.get("widget") in ("inline_material", "material_inline"):
            self._grid.add(widget, row_index, 0, 1, 2)
            widget.load_from_target()
        else:
            lbl = Label()
            lbl.text = field.label or key
            lbl.preferred_width = px(130)
            self._grid.add(lbl, row_index, 0)
            self._grid.add(widget, row_index, 1)
            row_widgets.append(lbl)
            widget.load_from_target()

        self._row_widgets[key] = row_widgets
        self._connect_widget(widget, key, field)
        return row_index + 1

    def _connect_widget(self, widget: FieldWidget, key: str, field: InspectField) -> None:
        target = self._target

        def on_change() -> None:
            if self._updating_from_model or self._target is None:
                return
            if self._target is not target:
                return
            applied = widget.apply_to_target()
            if applied is not None and self.on_field_changed is not None:
                old_value, new_value = applied
                self.on_field_changed(key, old_value, new_value)
            self._sync_visibility()

        widget.on_value_changed = on_change

    def _field_visible(self, key: str) -> bool:
        metadata = self._field_metadata.get(key, {})
        visible_if = metadata.get("visible_if")
        if visible_if is None:
            return True
        if not isinstance(visible_if, str):
            log.error(f"InspectFieldPanel: visible_if for '{key}' must be a string")
            return True
        field = self._fields.get(visible_if)
        if field is None or self._target is None:
            log.error(f"InspectFieldPanel: visible_if references unknown field '{visible_if}'")
            return True
        try:
            return bool(field.get_value(self._target))
        except Exception as e:
            log.error(f"InspectFieldPanel: visible_if evaluation failed for '{key}': {e}")
            return True

    def _sync_visibility(self) -> None:
        for key, row_widgets in self._row_widgets.items():
            visible = self._field_visible(key)
            for widget in row_widgets:
                widget.visible = visible
            if visible:
                self._widgets[key].load_from_target()

    def refresh(self) -> None:
        if self._target is None:
            return
        self._updating_from_model = True
        try:
            for key, _field in self._fields.items():
                widget = self._widgets.get(key)
                if widget is not None:
                    widget.load_from_target()
        finally:
            self._updating_from_model = False

    @property
    def target(self) -> Any:
        return self._target
