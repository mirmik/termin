"""Shadow settings dialog — configure shadow method, softness, bias."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.spin_box import SpinBox


_METHOD_NAMES = ["Hard", "PCF", "Poisson"]


def show_shadow_settings_dialog(
    ui,
    scene,
    on_changed: Callable[[], None] | None = None,
) -> None:
    """Show shadow settings dialog. Changes apply immediately.

    Uses scene.shadow_settings property (read/write) on TcSceneRef.
    """
    ss = scene.shadow_settings

    content = VStack()
    content.spacing = 8

    # Method
    method_row = HStack()
    method_row.spacing = 8
    method_lbl = Label()
    method_lbl.text = "Method:"
    method_row.add_child(method_lbl)
    method_combo = ComboBox()
    method_combo.items = _METHOD_NAMES
    method_combo.selected_index = ss.method
    method_row.add_child(method_combo)
    content.add_child(method_row)

    # Softness
    softness_row = HStack()
    softness_row.spacing = 8
    softness_lbl = Label()
    softness_lbl.text = "Softness:"
    softness_row.add_child(softness_lbl)
    softness_spin = SpinBox()
    softness_spin.value = ss.softness
    softness_spin.min_value = 0.0
    softness_spin.max_value = 10.0
    softness_spin.step = 0.1
    softness_spin.decimals = 2
    softness_row.add_child(softness_spin)
    content.add_child(softness_row)

    # Bias
    bias_row = HStack()
    bias_row.spacing = 8
    bias_lbl = Label()
    bias_lbl.text = "Bias:"
    bias_row.add_child(bias_lbl)
    bias_spin = SpinBox()
    bias_spin.value = ss.bias
    bias_spin.min_value = 0.0
    bias_spin.max_value = 0.1
    bias_spin.step = 0.001
    bias_spin.decimals = 4
    bias_row.add_child(bias_spin)
    content.add_child(bias_row)

    def _apply():
        ss = scene.shadow_settings
        ss.method = method_combo.selected_index
        ss.softness = softness_spin.value
        ss.bias = bias_spin.value
        scene.shadow_settings = ss
        if on_changed:
            on_changed()

    method_combo.on_selection_changed = lambda _idx: _apply()
    softness_spin.on_value_changed = lambda _val: _apply()
    bias_spin.on_value_changed = lambda _val: _apply()

    dlg = Dialog()
    dlg.title = "Shadow Settings"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 350

    dlg.show(ui, windowed=True)
