"""
DisplayInspector — inspector panel for Display properties.

Currently displays basic info. Can be extended with more settings later.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from termin.visualization.core.display import Display


class DisplayInspector(QWidget):
    """
    Inspector panel for Display properties.

    Shows:
    - Display name (editable)
    - Surface type (read-only)
    - Size in pixels (read-only)
    - Number of viewports (read-only)

    Signals:
        name_changed: Emitted when display name is changed.
        display_changed: Emitted when any property changes.
    """

    name_changed = pyqtSignal(str)
    display_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._display: Optional["Display"] = None
        self._display_name: str = ""

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QLabel("Display")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # Form
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)

        # Name field (editable)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Display name")
        self._name_edit.editingFinished.connect(self._on_name_changed)
        form.addRow("Name:", self._name_edit)

        # Surface type (read-only)
        self._surface_type_label = QLabel("-")
        form.addRow("Surface:", self._surface_type_label)

        # Size (read-only)
        self._size_label = QLabel("-")
        form.addRow("Size:", self._size_label)

        # Viewport count (read-only)
        self._viewport_count_label = QLabel("-")
        form.addRow("Viewports:", self._viewport_count_label)

        layout.addLayout(form)
        layout.addStretch()

    def set_display(self, display: Optional["Display"], name: str = "") -> None:
        """
        Set the display to inspect.

        Args:
            display: Display to inspect, or None to clear.
            name: Display name to show.
        """
        self._display = display
        self._display_name = name

        if display is None:
            self._clear()
            return

        self._name_edit.setText(name)

        # Surface type
        surface = display.surface
        surface_type = type(surface).__name__
        self._surface_type_label.setText(surface_type)

        # Size
        width, height = display.get_size()
        self._size_label.setText(f"{width} x {height}")

        # Viewport count
        viewport_count = len(display.viewports)
        self._viewport_count_label.setText(str(viewport_count))

    def _clear(self) -> None:
        """Clear all fields."""
        self._name_edit.setText("")
        self._surface_type_label.setText("-")
        self._size_label.setText("-")
        self._viewport_count_label.setText("-")

    def _on_name_changed(self) -> None:
        """Handle name edit finished."""
        new_name = self._name_edit.text().strip()
        if new_name and new_name != self._display_name:
            self._display_name = new_name
            self.name_changed.emit(new_name)
            self.display_changed.emit()

    def refresh(self) -> None:
        """Refresh display info."""
        if self._display is not None:
            self.set_display(self._display, self._display_name)
