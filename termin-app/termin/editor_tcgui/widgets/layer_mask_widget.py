"""Layer mask widget for tcgui — selects layers via checkboxes in a dialog."""

from __future__ import annotations

from typing import Any, Callable, Optional, TYPE_CHECKING

from tcbase import log

from tcgui.widgets.hstack import HStack
from tcgui.widgets.vstack import VStack
from tcgui.widgets.label import Label
from tcgui.widgets.button import Button
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.units import px

from termin.editor_tcgui.widgets.field_widgets import FieldWidget

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


def _show_layer_mask_dialog(
    ui,
    current_mask: int,
    scene_getter: Optional[Callable[[], Any]],
    on_result: Callable[[Optional[int]], None],
) -> None:
    """Open a dialog with checkboxes for each of the 64 layers."""

    layer_names: dict[int, str] = {}
    if scene_getter is not None:
        try:
            scene = scene_getter()
            if scene is not None:
                layer_names = scene.layer_names
        except Exception as e:
            log.debug(f"[LayerMaskWidget] failed to get layer names from scene: {e}")

    checkboxes: dict[int, Checkbox] = {}

    # Build vertical list of 64 checkboxes
    lst = VStack()
    lst.spacing = 1

    for layer_idx in range(64):
        if layer_idx in layer_names:
            name = f"{layer_idx}: {layer_names[layer_idx]}"
        else:
            name = f"Layer {layer_idx}"

        cb = Checkbox()
        cb.text = name
        cb.checked = bool(current_mask & (1 << layer_idx))
        checkboxes[layer_idx] = cb
        lst.add_child(cb)

    scroll = ScrollArea()
    scroll.preferred_height = px(360)
    scroll.add_child(lst)

    content = VStack()
    content.spacing = 8
    content.add_child(scroll)

    # All / None buttons
    btn_row = HStack()
    btn_row.spacing = 4

    def _select_all() -> None:
        for cb in checkboxes.values():
            cb.checked = True

    def _select_none() -> None:
        for cb in checkboxes.values():
            cb.checked = False

    all_btn = Button()
    all_btn.text = "All"
    all_btn.on_click = _select_all
    btn_row.add_child(all_btn)

    none_btn = Button()
    none_btn.text = "None"
    none_btn.on_click = _select_none
    btn_row.add_child(none_btn)

    content.add_child(btn_row)

    dlg = Dialog()
    dlg.title = "Layer Mask"
    dlg.content = content
    dlg.buttons = ["OK", "Cancel"]
    dlg.default_button = "OK"
    dlg.cancel_button = "Cancel"
    dlg.min_width = 300

    def _on_dlg_result(btn: str) -> None:
        if btn == "OK":
            mask = 0
            for layer_idx, cb in checkboxes.items():
                if cb.checked:
                    mask |= (1 << layer_idx)
            on_result(mask)
        else:
            on_result(None)

    dlg.on_result = _on_dlg_result
    dlg.show(ui, windowed=True)


class LayerMaskFieldWidget(FieldWidget):
    """Widget for editing 64-bit layer mask.

    Shows current mask as hex and a button to open a dialog
    with checkboxes for individual layers.
    """

    def __init__(self, scene_getter: Optional[Callable[[], Any]] = None) -> None:
        super().__init__()
        self._scene_getter = scene_getter
        self._value: int = 0xFFFFFFFFFFFFFFFF

        self._row = HStack()
        self._row.spacing = 4
        self.add_child(self._row)

        self._label = Label()
        self._label.text = self._format_mask(self._value)
        self._label.stretch = True
        self._row.add_child(self._label)

        self._btn = Button()
        self._btn.text = "..."
        self._btn.on_click = self._on_click
        self._row.add_child(self._btn)

    @staticmethod
    def _format_mask(value: int) -> str:
        return f"0x{value:016X}"

    def _on_click(self) -> None:
        if self._ui is None:
            return
        _show_layer_mask_dialog(
            self._ui,
            self._value,
            self._scene_getter,
            self._on_dialog_result,
        )

    def _on_dialog_result(self, new_value: Optional[int]) -> None:
        if new_value is not None:
            self._value = new_value
            self._label.text = self._format_mask(new_value)
            self._emit()

    def get_value(self) -> str:
        return self._format_mask(self._value)

    def set_value(self, value: Any) -> None:
        if isinstance(value, str):
            self._value = int(value, 0)
        elif value is not None:
            self._value = int(value)
        else:
            self._value = 0xFFFFFFFFFFFFFFFF
        self._label.text = self._format_mask(self._value)

    def set_scene_getter(self, getter: Callable[[], Any]) -> None:
        self._scene_getter = getter
