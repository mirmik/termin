"""Layer mask widget for selecting multiple layers via checkboxes."""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QFrame,
)
from PyQt6.QtCore import pyqtSignal

from termin.editor.widgets.field_widgets import FieldWidget

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class LayerMaskFieldWidget(FieldWidget):
    """
    Widget with checkboxes for selecting layers (64-bit mask).

    Shows first 8 layers always + any named layers from scene.layer_names.
    Returns uint64 bitmask where bit N corresponds to layer N.
    """

    value_changed = pyqtSignal()

    # How many layers to always show
    ALWAYS_VISIBLE_COUNT = 8

    def __init__(
        self,
        scene_getter: Optional[Callable[[], "Scene | None"]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._scene_getter = scene_getter
        self._checkboxes: dict[int, QCheckBox] = {}
        self._value: int = 0xFFFFFFFFFFFFFFFF  # All layers by default

        self._build_ui()

    def set_scene_getter(self, getter: Callable[[], "Scene | None"]) -> None:
        """Set callback for getting current scene."""
        self._scene_getter = getter
        self._rebuild_checkboxes()

    def _get_layer_names(self) -> dict[int, str]:
        """Get layer names from scene."""
        if self._scene_getter is None:
            return {}
        scene = self._scene_getter()
        if scene is None:
            return {}
        return scene.layer_names

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._checkbox_container = QWidget()
        self._checkbox_layout = QVBoxLayout(self._checkbox_container)
        self._checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self._checkbox_layout.setSpacing(1)

        layout.addWidget(self._checkbox_container)

        self._rebuild_checkboxes()

    def _rebuild_checkboxes(self) -> None:
        """Rebuild checkbox list based on current layer names."""
        # Clear existing checkboxes
        for cb in self._checkboxes.values():
            cb.setParent(None)
            cb.deleteLater()
        self._checkboxes.clear()

        # Clear layout
        while self._checkbox_layout.count():
            item = self._checkbox_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        layer_names = self._get_layer_names()

        # Determine which layers to show
        layers_to_show: set[int] = set(range(self.ALWAYS_VISIBLE_COUNT))
        layers_to_show.update(layer_names.keys())

        # Create checkboxes in rows of 4
        row_widget: QWidget | None = None
        row_layout: QHBoxLayout | None = None
        count_in_row = 0
        max_per_row = 4

        for layer_idx in sorted(layers_to_show):
            if count_in_row == 0 or count_in_row >= max_per_row:
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)
                self._checkbox_layout.addWidget(row_widget)
                count_in_row = 0

            # Get layer name
            if layer_idx in layer_names:
                name = f"{layer_idx}: {layer_names[layer_idx]}"
            else:
                name = f"{layer_idx}"

            cb = QCheckBox(name)
            cb.setChecked(bool(self._value & (1 << layer_idx)))
            cb.stateChanged.connect(self._on_checkbox_changed)
            self._checkboxes[layer_idx] = cb
            row_layout.addWidget(cb)
            count_in_row += 1

        # Add stretch to last row
        if row_layout is not None:
            row_layout.addStretch()

    def _on_checkbox_changed(self) -> None:
        """Handle checkbox state change."""
        self.value_changed.emit()

    def get_value(self) -> int:
        """Get current mask value."""
        mask = 0
        for layer_idx, cb in self._checkboxes.items():
            if cb.isChecked():
                mask |= (1 << layer_idx)
        return mask

    def set_value(self, value: int) -> None:
        """Set mask value."""
        if value is None:
            value = 0xFFFFFFFFFFFFFFFF

        self._value = int(value)

        # Update checkboxes without emitting signals
        for layer_idx, cb in self._checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(bool(self._value & (1 << layer_idx)))
            cb.blockSignals(False)

    def refresh(self) -> None:
        """Refresh layer names from scene."""
        current_value = self.get_value()
        self._rebuild_checkboxes()
        self.set_value(current_value)
