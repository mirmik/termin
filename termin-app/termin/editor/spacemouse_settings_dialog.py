"""
SpaceMouse settings dialog.

Allows configuring SpaceMouse mode, sensitivity, deadzone, and axis inversion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QDialogButtonBox,
    QGroupBox,
    QSpinBox,
)
from termin.editor.widgets.spinbox import DoubleSpinBox

if TYPE_CHECKING:
    from termin.editor.spacemouse_controller import SpaceMouseController


class SpaceMouseSettingsDialog(QDialog):
    """
    Dialog for configuring SpaceMouse settings.

    Settings:
    - Mode: Orbit / Fly
    - Sensitivity: Pan, Zoom, Orbit, Fly
    - Deadzone: integer threshold
    - Axis inversion: Pan X/Y, Zoom, Orbit X/Y

    Changes are applied immediately as the user edits values.
    """

    def __init__(
        self,
        controller: "SpaceMouseController",
        parent=None,
        on_changed: Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        self._controller = controller
        self._on_changed = on_changed
        self.setWindowTitle("SpaceMouse Settings")
        self.setMinimumWidth(320)

        self._horizon_lock: QCheckBox | None = None
        self._mode_combo: QComboBox | None = None
        self._pan_spin: DoubleSpinBox | None = None
        self._zoom_spin: DoubleSpinBox | None = None
        self._orbit_spin: DoubleSpinBox | None = None
        self._fly_spin: DoubleSpinBox | None = None
        self._deadzone_spin: QSpinBox | None = None
        self._invert_x: QCheckBox | None = None
        self._invert_y: QCheckBox | None = None
        self._invert_z: QCheckBox | None = None
        self._invert_rx: QCheckBox | None = None
        self._invert_ry: QCheckBox | None = None
        self._invert_rz: QCheckBox | None = None

        self._init_ui()
        self._load_from_controller()
        self._connect_signals()

    def _init_ui(self) -> None:
        """Create UI."""
        layout = QVBoxLayout(self)

        # Mode group
        mode_group = QGroupBox("Mode")
        mode_form = QFormLayout(mode_group)

        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Orbit")
        self._mode_combo.addItem("Fly")
        mode_form.addRow("Mode:", self._mode_combo)

        self._horizon_lock = QCheckBox("Horizon Lock")
        self._horizon_lock.setToolTip(
            "Keep the horizon level in fly mode.\n"
            "Removes accumulated roll after each rotation."
        )
        mode_form.addRow(self._horizon_lock)

        layout.addWidget(mode_group)

        # Sensitivity group
        sens_group = QGroupBox("Sensitivity")
        sens_form = QFormLayout(sens_group)

        self._pan_spin = DoubleSpinBox()
        self._pan_spin.setRange(0.000001, 0.01)
        self._pan_spin.setSingleStep(0.000005)
        self._pan_spin.setDecimals(6)
        sens_form.addRow("Pan:", self._pan_spin)

        self._zoom_spin = DoubleSpinBox()
        self._zoom_spin.setRange(0.000001, 0.01)
        self._zoom_spin.setSingleStep(0.00001)
        self._zoom_spin.setDecimals(6)
        sens_form.addRow("Zoom:", self._zoom_spin)

        self._orbit_spin = DoubleSpinBox()
        self._orbit_spin.setRange(0.0001, 0.1)
        self._orbit_spin.setSingleStep(0.0005)
        self._orbit_spin.setDecimals(4)
        sens_form.addRow("Orbit:", self._orbit_spin)

        self._fly_spin = DoubleSpinBox()
        self._fly_spin.setRange(0.000001, 0.01)
        self._fly_spin.setSingleStep(0.00005)
        self._fly_spin.setDecimals(6)
        sens_form.addRow("Fly:", self._fly_spin)

        self._deadzone_spin = QSpinBox()
        self._deadzone_spin.setRange(0, 100)
        self._deadzone_spin.setSingleStep(5)
        sens_form.addRow("Deadzone:", self._deadzone_spin)

        layout.addWidget(sens_group)

        # Invert axes group
        invert_group = QGroupBox("Invert Axes")
        invert_form = QFormLayout(invert_group)

        self._invert_x = QCheckBox("Invert X (Left/Right)")
        invert_form.addRow(self._invert_x)

        self._invert_y = QCheckBox("Invert Y (Forward/Backward)")
        invert_form.addRow(self._invert_y)

        self._invert_z = QCheckBox("Invert Z (Up/Down)")
        invert_form.addRow(self._invert_z)

        self._invert_rx = QCheckBox("Invert RX (Pitch)")
        invert_form.addRow(self._invert_rx)

        self._invert_ry = QCheckBox("Invert RY (Yaw)")
        invert_form.addRow(self._invert_ry)

        self._invert_rz = QCheckBox("Invert RZ (Roll)")
        invert_form.addRow(self._invert_rz)

        layout.addWidget(invert_group)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.close)
        layout.addWidget(button_box)

    def _connect_signals(self) -> None:
        """Connect widget signals to apply changes immediately."""
        self._mode_combo.currentIndexChanged.connect(self._apply_settings)
        self._horizon_lock.stateChanged.connect(self._apply_settings)
        self._pan_spin.valueChanged.connect(self._apply_settings)
        self._zoom_spin.valueChanged.connect(self._apply_settings)
        self._orbit_spin.valueChanged.connect(self._apply_settings)
        self._fly_spin.valueChanged.connect(self._apply_settings)
        self._deadzone_spin.valueChanged.connect(self._apply_settings)
        self._invert_x.stateChanged.connect(self._apply_settings)
        self._invert_y.stateChanged.connect(self._apply_settings)
        self._invert_z.stateChanged.connect(self._apply_settings)
        self._invert_rx.stateChanged.connect(self._apply_settings)
        self._invert_ry.stateChanged.connect(self._apply_settings)
        self._invert_rz.stateChanged.connect(self._apply_settings)

    def _load_from_controller(self) -> None:
        """Load current settings from controller."""
        c = self._controller
        self._mode_combo.setCurrentIndex(1 if c.fly_mode else 0)
        self._horizon_lock.setChecked(c.horizon_lock)
        self._pan_spin.setValue(c.pan_sensitivity)
        self._zoom_spin.setValue(c.zoom_sensitivity)
        self._orbit_spin.setValue(c.orbit_sensitivity)
        self._fly_spin.setValue(c.fly_sensitivity)
        self._deadzone_spin.setValue(c.deadzone)
        self._invert_x.setChecked(c.invert_x)
        self._invert_y.setChecked(c.invert_y)
        self._invert_z.setChecked(c.invert_z)
        self._invert_rx.setChecked(c.invert_rx)
        self._invert_ry.setChecked(c.invert_ry)
        self._invert_rz.setChecked(c.invert_rz)

    def _apply_settings(self) -> None:
        """Apply current widget values to controller."""
        c = self._controller
        c.fly_mode = self._mode_combo.currentIndex() == 1
        c.horizon_lock = self._horizon_lock.isChecked()
        c.pan_sensitivity = self._pan_spin.value()
        c.zoom_sensitivity = self._zoom_spin.value()
        c.orbit_sensitivity = self._orbit_spin.value()
        c.fly_sensitivity = self._fly_spin.value()
        c.deadzone = self._deadzone_spin.value()
        c.invert_x = self._invert_x.isChecked()
        c.invert_y = self._invert_y.isChecked()
        c.invert_z = self._invert_z.isChecked()
        c.invert_rx = self._invert_rx.isChecked()
        c.invert_ry = self._invert_ry.isChecked()
        c.invert_rz = self._invert_rz.isChecked()

        if self._on_changed is not None:
            self._on_changed()
