"""
Shadow settings dialog.

Allows configuring shadow rendering method and parameters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QDoubleSpinBox,
    QDialogButtonBox,
    QGroupBox,
)

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class ShadowSettingsDialog(QDialog):
    """
    Dialog for configuring shadow rendering settings.

    Settings:
    - Method: Hard / PCF 5x5 / Poisson
    - Softness: Sampling radius multiplier
    - Bias: Depth bias to prevent shadow acne
    """

    def __init__(self, scene: "Scene", parent=None):
        super().__init__(parent)
        self._scene = scene
        self.setWindowTitle("Shadow Settings")
        self.setMinimumWidth(300)

        self._method_combo: QComboBox | None = None
        self._softness_spin: QDoubleSpinBox | None = None
        self._bias_spin: QDoubleSpinBox | None = None

        self._init_ui()
        self._load_from_scene()

    def _init_ui(self) -> None:
        """Create UI."""
        layout = QVBoxLayout(self)

        # Settings group
        group = QGroupBox("Shadow Rendering")
        form = QFormLayout(group)

        # Method combo
        self._method_combo = QComboBox()
        from termin.visualization.core.scene.lighting import ShadowSettings
        for name in ShadowSettings.METHOD_NAMES:
            self._method_combo.addItem(name)
        form.addRow("Method:", self._method_combo)

        # Softness spin
        self._softness_spin = QDoubleSpinBox()
        self._softness_spin.setRange(0.0, 10.0)
        self._softness_spin.setSingleStep(0.1)
        self._softness_spin.setDecimals(2)
        self._softness_spin.setToolTip(
            "Sampling radius multiplier.\n"
            "0 = sharp edges\n"
            "1 = default softness\n"
            ">1 = softer shadows"
        )
        form.addRow("Softness:", self._softness_spin)

        # Bias spin
        self._bias_spin = QDoubleSpinBox()
        self._bias_spin.setRange(0.0, 0.1)
        self._bias_spin.setSingleStep(0.001)
        self._bias_spin.setDecimals(4)
        self._bias_spin.setToolTip(
            "Depth bias to prevent shadow acne.\n"
            "Increase if you see striping artifacts on surfaces."
        )
        form.addRow("Bias:", self._bias_spin)

        layout.addWidget(group)

        # OK/Cancel buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_from_scene(self) -> None:
        """Load current settings from scene."""
        settings = self._scene.shadow_settings
        self._method_combo.setCurrentIndex(settings.method)
        self._softness_spin.setValue(settings.softness)
        self._bias_spin.setValue(settings.bias)

    def _save_and_accept(self) -> None:
        """Save settings to scene and close dialog."""
        settings = self._scene.shadow_settings
        settings.method = self._method_combo.currentIndex()
        settings.softness = self._softness_spin.value()
        settings.bias = self._bias_spin.value()
        self.accept()
