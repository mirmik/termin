"""Shadow settings dialog - configure shadow method, softness, receiver bias."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.spin_box import SpinBox

from termin.editor_core.scene_settings_model import (
    SHADOW_METHODS,
    ShadowSettingsController,
    ShadowSettingsSnapshot,
)


def show_shadow_settings_dialog(
    ui,
    scene,
    mirror_scenes: list | None = None,
    on_changed: Callable[[], None] | None = None,
) -> None:
    """Show shadow settings dialog. Changes apply immediately.

    Uses SceneRenderState.shadow_settings property (read/write).
    """
    controller = ShadowSettingsController(
        scene,
        mirror_scenes=mirror_scenes or (),
        on_changed=on_changed,
    )
    snapshot = controller.load()

    content = VStack()
    content.spacing = 8

    # Method
    method_row = HStack()
    method_row.spacing = 8
    method_lbl = Label()
    method_lbl.text = "Method:"
    method_row.add_child(method_lbl)
    method_combo = ComboBox()
    method_combo.items = list(SHADOW_METHODS)
    method_combo.selected_index = snapshot.method
    method_row.add_child(method_combo)
    content.add_child(method_row)

    # Softness
    softness_row = HStack()
    softness_row.spacing = 8
    softness_lbl = Label()
    softness_lbl.text = "Softness:"
    softness_row.add_child(softness_lbl)
    softness_spin = SpinBox()
    softness_spin.value = snapshot.softness
    softness_spin.min_value = 0.0
    softness_spin.max_value = 10.0
    softness_spin.step = 0.1
    softness_spin.decimals = 2
    softness_row.add_child(softness_spin)
    content.add_child(softness_row)

    # Receiver bias
    bias_row = HStack()
    bias_row.spacing = 8
    bias_lbl = Label()
    bias_lbl.text = "Receiver Bias:"
    bias_lbl.tooltip = "World-space depth compare offset used while sampling shadow maps."
    bias_row.add_child(bias_lbl)
    bias_spin = SpinBox()
    bias_spin.value = snapshot.bias
    bias_spin.min_value = 0.0
    bias_spin.max_value = 0.05
    bias_spin.step = 0.0001
    bias_spin.decimals = 5
    bias_spin.tooltip = "Increase slightly to reduce self-shadow acne; too much detaches shadows."
    bias_row.add_child(bias_spin)
    content.add_child(bias_row)

    def _apply():
        controller.apply(
            ShadowSettingsSnapshot(
                method_combo.selected_index,
                softness_spin.value,
                bias_spin.value,
            )
        )

    method_combo.on_changed = lambda _idx, _text: _apply()
    softness_spin.on_changed = lambda _val: _apply()
    bias_spin.on_changed = lambda _val: _apply()

    dlg = Dialog()
    dlg.title = "Shadow Settings"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 350

    dlg.show(ui, windowed=True)
