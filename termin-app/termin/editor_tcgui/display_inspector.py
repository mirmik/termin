"""Display inspector for tcgui."""

from __future__ import annotations

from typing import Callable, Optional

from tcbase import log
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.grid_layout import GridLayout
from tcgui.widgets.label import Label
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.separator import Separator
from tcgui.widgets.units import px


class DisplayInspectorTcgui(VStack):
    """Inspector panel for Display properties."""

    def __init__(self) -> None:
        super().__init__()
        self.spacing = 4

        self._display = None
        self._display_name: str = ""
        self._updating = False
        self.on_changed: Optional[Callable[[], None]] = None

        title = Label()
        title.text = "Display Inspector"
        self.add_child(title)

        self._subtitle = Label()
        self._subtitle.color = (0.62, 0.66, 0.74, 1.0)
        self.add_child(self._subtitle)
        self.add_child(Separator())

        grid = GridLayout(columns=2)
        grid.column_spacing = 4
        grid.row_spacing = 4
        grid.set_column_stretch(1, 1.0)
        self.add_child(grid)

        name_lbl = Label()
        name_lbl.text = "Name:"
        name_lbl.preferred_width = px(96)
        grid.add(name_lbl, 0, 0)
        self._name_input = TextInput()
        self._name_input.on_submit = self._on_name_submitted
        grid.add(self._name_input, 0, 1)

        surface_lbl = Label()
        surface_lbl.text = "Surface:"
        surface_lbl.preferred_width = px(96)
        grid.add(surface_lbl, 1, 0)
        self._surface_value = Label()
        self._surface_value.color = (0.70, 0.72, 0.76, 1.0)
        grid.add(self._surface_value, 1, 1)

        size_lbl = Label()
        size_lbl.text = "Size:"
        size_lbl.preferred_width = px(96)
        grid.add(size_lbl, 2, 0)
        self._size_value = Label()
        self._size_value.color = (0.70, 0.72, 0.76, 1.0)
        grid.add(self._size_value, 2, 1)

        vp_lbl = Label()
        vp_lbl.text = "Viewports:"
        vp_lbl.preferred_width = px(96)
        grid.add(vp_lbl, 3, 0)
        self._viewports_value = Label()
        self._viewports_value.color = (0.70, 0.72, 0.76, 1.0)
        grid.add(self._viewports_value, 3, 1)

        editor_only_row = HStack()
        editor_only_row.spacing = 6
        editor_only_lbl = Label()
        editor_only_lbl.text = "Editor only:"
        editor_only_lbl.preferred_width = px(96)
        self._editor_only = Checkbox()
        self._editor_only.on_changed = self._on_editor_only_changed
        editor_only_row.add_child(editor_only_lbl)
        editor_only_row.add_child(self._editor_only)
        editor_only_row.add_child(Label())
        editor_only_row.children[-1].stretch = True
        self.add_child(editor_only_row)

        self.add_child(Separator())

        self._debug = Label()
        self._debug.color = (0.56, 0.60, 0.66, 1.0)
        self._debug.text = "-"
        self.add_child(self._debug)

        self._empty = Label()
        self._empty.text = "No display selected."
        self._empty.color = (0.52, 0.56, 0.62, 1.0)
        self.add_child(self._empty)

        self._set_visible_state(False)

    def set_display(self, display=None, name: str = "") -> None:
        self._display = display
        self._subtitle.text = f"Display: {name}" if name else "Display"

        self._updating = True
        try:
            if display is None:
                self._set_visible_state(False)
                self._name_input.text = ""
                self._surface_value.text = "-"
                self._size_value.text = "-"
                self._viewports_value.text = "-"
                self._editor_only.checked = False
                self._debug.text = "-"
                return

            self._set_visible_state(True)
            self._display_name = name or (display.name or "")
            self._name_input.text = self._display_name

            surface_type = type(display.surface).__name__ if display.surface is not None else "-"
            self._surface_value.text = surface_type

            try:
                w, h = display.get_size()
                self._size_value.text = f"{w} x {h}"
            except Exception as e:
                log.error(f"[DisplayInspectorTcgui] get_size failed: {e}")
                self._size_value.text = "-"

            self._viewports_value.text = str(len(display.viewports))
            self._editor_only.checked = bool(display.editor_only)
            self._debug.text = f"display=0x{display.tc_display_ptr:X}"
        finally:
            self._updating = False
            if self._ui is not None:
                self._ui.request_layout()

    def _set_visible_state(self, has_display: bool) -> None:
        self._name_input.visible = has_display
        self._surface_value.visible = has_display
        self._size_value.visible = has_display
        self._viewports_value.visible = has_display
        self._editor_only.visible = has_display
        self._debug.visible = has_display
        self._empty.visible = not has_display

    def _on_name_submitted(self, text: str) -> None:
        if self._updating or self._display is None:
            return
        new_name = text.strip()
        if not new_name:
            return
        if self._display.name != new_name:
            self._display.name = new_name
            self._emit_changed()

    def _on_editor_only_changed(self, checked: bool) -> None:
        if self._updating or self._display is None:
            return
        self._display.editor_only = bool(checked)
        self._emit_changed()

    def _emit_changed(self) -> None:
        if self.on_changed is not None:
            self.on_changed()
