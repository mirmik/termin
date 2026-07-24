"""Native SpaceMouse settings dialog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import weakref

from termin.editor_core.spacemouse_settings_model import (
    SpaceMouseSettingsController,
    SpaceMouseSettingsSnapshot,
)
from termin.gui_native import DialogAction, TcDocument, Rect, Size, WidgetRef

from .metrics import EDITOR_UI_METRICS


def _ref(document: TcDocument, widget) -> WidgetRef:
    return widget if isinstance(widget, WidgetRef) else document.ref(widget.handle)


def _row(document: TcDocument, label: str, control) -> WidgetRef:
    row = document.create_hstack(f"spacemouse-{label.lower().replace(' ', '-')}")
    row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    row.add_fixed_child(document.create_label(label), EDITOR_UI_METRICS.form_label)
    row.add_stretch_child(_ref(document, control))
    return row


@dataclass
class NativeSpaceMouseSettingsDialog:
    document: TcDocument
    controller: SpaceMouseSettingsController
    dialog: object
    mode: object
    horizon_lock: object
    pan: object
    zoom: object
    orbit: object
    fly: object
    deadzone: object
    inversions: tuple[object, ...]
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    _updating: bool = False
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native SpaceMouse settings dialog is closed")
        if self.dialog.open:
            return False
        self.apply_snapshot(self.controller.load())
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def apply_snapshot(self, value: SpaceMouseSettingsSnapshot) -> None:
        self._updating = True
        try:
            self.mode.selected_index = 1 if value.fly_mode else 0
            self.horizon_lock.checked = value.horizon_lock
            self.pan.value = value.pan_sensitivity
            self.zoom.value = value.zoom_sensitivity
            self.orbit.value = value.orbit_sensitivity
            self.fly.value = value.fly_sensitivity
            self.deadzone.value = value.deadzone
            inversion_values = (
                value.invert_x, value.invert_y, value.invert_z,
                value.invert_rx, value.invert_ry, value.invert_rz,
            )
            for control, checked in zip(self.inversions, inversion_values, strict=True):
                control.checked = checked
        finally:
            self._updating = False

    def apply_controls(self) -> None:
        if self._updating:
            return
        inversion_values = tuple(control.checked for control in self.inversions)
        self.apply_snapshot(self.controller.apply(SpaceMouseSettingsSnapshot(
            self.mode.selected_index == 1,
            self.horizon_lock.checked,
            self.pan.value,
            self.zoom.value,
            self.orbit.value,
            self.fly.value,
            int(self.deadzone.value),
            *inversion_values,
        )))
        self.request_render()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)


def build_native_spacemouse_settings_dialog(document, controller, *, viewport, request_render):
    root = document.create_vstack("native-spacemouse-settings")
    root.stable_id = "editor.spacemouse-settings"
    root.preferred_size = Size(460.0, 560.0)
    root.set_layout_padding(EDITOR_UI_METRICS.dialog_insets)
    root.set_layout_spacing(EDITOR_UI_METRICS.dialog_spacing)
    mode = document.create_combo_box()
    mode.add_item("Orbit")
    mode.add_item("Fly")
    horizon_lock = document.create_checkbox(False)
    root.add_fixed_child(_row(document, "Mode", mode), EDITOR_UI_METRICS.field_row)
    root.add_fixed_child(_row(document, "Horizon Lock", horizon_lock), EDITOR_UI_METRICS.compact_row)
    controls = []
    for label, minimum, maximum, step, decimals in (
        ("Pan", 0.000001, 0.01, 0.000005, 6),
        ("Zoom", 0.000001, 0.01, 0.00001, 6),
        ("Orbit", 0.0001, 0.1, 0.0005, 4),
        ("Fly", 0.000001, 0.01, 0.00005, 6),
        ("Deadzone", 0.0, 100.0, 5.0, 0),
    ):
        control = document.create_spin_box()
        control.set_range(minimum, maximum)
        control.step = step
        control.decimals = decimals
        root.add_fixed_child(_row(document, label, control), EDITOR_UI_METRICS.field_row)
        controls.append(control)
    root.add_fixed_child(document.create_label("Invert Axes"), EDITOR_UI_METRICS.section_row)
    inversion_labels = (
        "Invert X (Left/Right)", "Invert Y (Forward/Backward)",
        "Invert Z (Up/Down)", "Invert RX (Pitch)", "Invert RY (Yaw)",
        "Invert RZ (Roll)",
    )
    inversions = tuple(document.create_checkbox(False) for _label in inversion_labels)
    for label, control in zip(inversion_labels, inversions, strict=True):
        root.add_fixed_child(_row(document, label, control), EDITOR_UI_METRICS.compact_row)
    dialog = document.create_dialog("SpaceMouse Settings")
    dialog.actions = [DialogAction("close", "Close", is_default=True, is_cancel=True)]
    dialog.set_content(root)
    result = NativeSpaceMouseSettingsDialog(
        document, controller, dialog, mode, horizon_lock, *controls,
        inversions, viewport, request_render,
    )
    owner = weakref.ref(result)
    mode.connect_changed(lambda *_args: owner().apply_controls() if owner() is not None else None)
    for control in (horizon_lock, *controls, *inversions):
        control.connect_changed(lambda *_args: owner().apply_controls() if owner() is not None else None)
    return result


def connect_spacemouse_settings_command(menu_bar, command_id: int, dialog) -> None:
    owner = weakref.ref(dialog)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        current = owner()
        if activated_id == command_id and current is not None:
            current.show()

    menu_bar.connect_activated(activated)


__all__ = [
    "NativeSpaceMouseSettingsDialog", "build_native_spacemouse_settings_dialog",
    "connect_spacemouse_settings_command",
]
