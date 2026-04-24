"""SpaceMouse Settings dialog — configure mode, sensitivity, axis inversion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.group_box import GroupBox

if TYPE_CHECKING:
    from termin.editor.spacemouse_controller import SpaceMouseController


def show_spacemouse_settings_dialog(
    ui,
    controller: "SpaceMouseController",
    on_changed: Callable[[], None] | None = None,
) -> None:
    """Show SpaceMouse settings dialog. Changes apply immediately."""
    content = VStack()
    content.spacing = 8

    # --- Mode ---
    mode_group = GroupBox()
    mode_group.title = "Mode"

    mode_row = HStack()
    mode_row.spacing = 8
    mode_lbl = Label()
    mode_lbl.text = "Mode:"
    mode_row.add_child(mode_lbl)
    mode_combo = ComboBox()
    mode_combo.items = ["Orbit", "Fly"]
    mode_combo.selected_index = 1 if controller.fly_mode else 0
    mode_row.add_child(mode_combo)
    mode_group.add_child(mode_row)

    horizon_lock = Checkbox()
    horizon_lock.text = "Horizon Lock"
    horizon_lock.checked = controller.horizon_lock
    mode_group.add_child(horizon_lock)

    content.add_child(mode_group)

    # --- Sensitivity ---
    sens_group = GroupBox()
    sens_group.title = "Sensitivity"

    def _make_sens_row(label_text: str, value: float, min_val: float, max_val: float,
                       step: float, decimals: int) -> tuple[HStack, SpinBox]:
        row = HStack()
        row.spacing = 8
        lbl = Label()
        lbl.text = label_text
        row.add_child(lbl)
        spin = SpinBox()
        spin.value = value
        spin.min_value = min_val
        spin.max_value = max_val
        spin.step = step
        spin.decimals = decimals
        spin.stretch = True
        row.add_child(spin)
        return row, spin

    pan_row, pan_spin = _make_sens_row("Pan:", controller.pan_sensitivity, 0.000001, 0.01, 0.000005, 6)
    zoom_row, zoom_spin = _make_sens_row("Zoom:", controller.zoom_sensitivity, 0.000001, 0.01, 0.00001, 6)
    orbit_row, orbit_spin = _make_sens_row("Orbit:", controller.orbit_sensitivity, 0.0001, 0.1, 0.0005, 4)
    fly_row, fly_spin = _make_sens_row("Fly:", controller.fly_sensitivity, 0.000001, 0.01, 0.00005, 6)

    deadzone_row = HStack()
    deadzone_row.spacing = 8
    dz_lbl = Label()
    dz_lbl.text = "Deadzone:"
    deadzone_row.add_child(dz_lbl)
    deadzone_spin = SpinBox()
    deadzone_spin.value = controller.deadzone
    deadzone_spin.min_value = 0
    deadzone_spin.max_value = 100
    deadzone_spin.step = 5
    deadzone_spin.decimals = 0
    deadzone_spin.stretch = True
    deadzone_row.add_child(deadzone_spin)

    sens_group.add_child(pan_row)
    sens_group.add_child(zoom_row)
    sens_group.add_child(orbit_row)
    sens_group.add_child(fly_row)
    sens_group.add_child(deadzone_row)

    content.add_child(sens_group)

    # --- Invert Axes ---
    invert_group = GroupBox()
    invert_group.title = "Invert Axes"

    def _make_invert_cb(label_text: str, checked: bool) -> Checkbox:
        cb = Checkbox()
        cb.text = label_text
        cb.checked = checked
        return cb

    invert_x = _make_invert_cb("Invert X (Left/Right)", controller.invert_x)
    invert_y = _make_invert_cb("Invert Y (Forward/Backward)", controller.invert_y)
    invert_z = _make_invert_cb("Invert Z (Up/Down)", controller.invert_z)
    invert_rx = _make_invert_cb("Invert RX (Pitch)", controller.invert_rx)
    invert_ry = _make_invert_cb("Invert RY (Yaw)", controller.invert_ry)
    invert_rz = _make_invert_cb("Invert RZ (Roll)", controller.invert_rz)

    invert_group.add_child(invert_x)
    invert_group.add_child(invert_y)
    invert_group.add_child(invert_z)
    invert_group.add_child(invert_rx)
    invert_group.add_child(invert_ry)
    invert_group.add_child(invert_rz)

    content.add_child(invert_group)

    # --- Apply on any change ---
    def _apply(*_args):
        controller.fly_mode = mode_combo.selected_index == 1
        controller.horizon_lock = horizon_lock.checked
        controller.pan_sensitivity = pan_spin.value
        controller.zoom_sensitivity = zoom_spin.value
        controller.orbit_sensitivity = orbit_spin.value
        controller.fly_sensitivity = fly_spin.value
        controller.deadzone = int(deadzone_spin.value)
        controller.invert_x = invert_x.checked
        controller.invert_y = invert_y.checked
        controller.invert_z = invert_z.checked
        controller.invert_rx = invert_rx.checked
        controller.invert_ry = invert_ry.checked
        controller.invert_rz = invert_rz.checked
        if on_changed is not None:
            on_changed()

    mode_combo.on_changed = _apply
    horizon_lock.on_changed = _apply
    pan_spin.on_changed = _apply
    zoom_spin.on_changed = _apply
    orbit_spin.on_changed = _apply
    fly_spin.on_changed = _apply
    deadzone_spin.on_changed = _apply
    invert_x.on_changed = _apply
    invert_y.on_changed = _apply
    invert_z.on_changed = _apply
    invert_rx.on_changed = _apply
    invert_ry.on_changed = _apply
    invert_rz.on_changed = _apply

    # --- Dialog ---
    dlg = Dialog()
    dlg.title = "SpaceMouse Settings"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 350

    dlg.show(ui, windowed=True)
