"""
DisplayInspector — inspector panel for Display properties.

Currently displays basic info. Can be extended with more settings later.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    input_mode_changed = pyqtSignal(str)  # "none", "simple", "basic", "editor"
    block_input_in_editor_changed = pyqtSignal(bool)

    # Available input modes
    INPUT_MODES = [
        ("none", "None"),
        ("simple", "Simple (Game)"),
        ("basic", "Basic (C)"),
        ("editor", "Editor"),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._display: Optional["Display"] = None
        self._display_name: str = ""
        self._current_input_mode: str = "none"
        self._updating: bool = False

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

        # Editor only checkbox
        self._editor_only_checkbox = QCheckBox()
        self._editor_only_checkbox.setToolTip(
            "If checked, this display is only created and rendered in the editor.\n"
            "It will be skipped when running the game outside the editor."
        )
        self._editor_only_checkbox.stateChanged.connect(self._on_editor_only_changed)
        form.addRow("Editor Only:", self._editor_only_checkbox)

        # Input mode combo
        self._input_mode_combo = QComboBox()
        self._input_mode_combo.setToolTip(
            "Input handling mode for this display:\n"
            "- None: No input handling\n"
            "- Simple (Game): Routes input to scene with raycast\n"
            "- Basic (C): Routes input to scene (C impl, no raycast)\n"
            "- Editor: Full editor input (picking, gizmo, etc.)"
        )
        for mode_id, mode_label in self.INPUT_MODES:
            self._input_mode_combo.addItem(mode_label, mode_id)
        self._input_mode_combo.currentIndexChanged.connect(self._on_input_mode_changed)
        form.addRow("Input:", self._input_mode_combo)

        # Block input in editor checkbox
        self._block_input_in_editor_checkbox = QCheckBox()
        self._block_input_in_editor_checkbox.setToolTip(
            "Block input for this display when running in editor mode.\n"
            "Prevents accidental camera movement while editing."
        )
        self._block_input_in_editor_checkbox.stateChanged.connect(self._on_block_input_in_editor_changed)
        form.addRow("Block in Editor:", self._block_input_in_editor_checkbox)

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

        # Editor only
        self._editor_only_checkbox.blockSignals(True)
        self._editor_only_checkbox.setChecked(display.editor_only)
        self._editor_only_checkbox.blockSignals(False)

    def _clear(self) -> None:
        """Clear all fields."""
        self._name_edit.setText("")
        self._surface_type_label.setText("-")
        self._size_label.setText("-")
        self._viewport_count_label.setText("-")
        self._editor_only_checkbox.blockSignals(True)
        self._editor_only_checkbox.setChecked(False)
        self._editor_only_checkbox.blockSignals(False)
        self._block_input_in_editor_checkbox.blockSignals(True)
        self._block_input_in_editor_checkbox.setChecked(False)
        self._block_input_in_editor_checkbox.blockSignals(False)
        self._updating = True
        self._input_mode_combo.setCurrentIndex(0)
        self._current_input_mode = "none"
        self._updating = False

    def _on_name_changed(self) -> None:
        """Handle name edit finished."""
        new_name = self._name_edit.text().strip()
        if new_name and new_name != self._display_name:
            self._display_name = new_name
            self.name_changed.emit(new_name)
            self.display_changed.emit()

    def _on_editor_only_changed(self, state: int) -> None:
        """Handle editor only checkbox changed."""
        if self._display is not None:
            self._display.editor_only = bool(state)
            self.display_changed.emit()

    def _on_input_mode_changed(self, index: int) -> None:
        """Handle input mode combo changed."""
        if self._updating or self._display is None:
            return

        mode_id = self._input_mode_combo.itemData(index)
        if mode_id and mode_id != self._current_input_mode:
            self._current_input_mode = mode_id
            self.input_mode_changed.emit(mode_id)
            self.display_changed.emit()

    def _on_block_input_in_editor_changed(self, state: int) -> None:
        """Handle block input in editor checkbox changed."""
        if self._updating or self._display is None:
            return
        self.block_input_in_editor_changed.emit(bool(state))
        self.display_changed.emit()

    def set_input_mode(self, mode: str) -> None:
        """Set the current input mode selection."""
        self._current_input_mode = mode
        self._updating = True
        try:
            for i in range(self._input_mode_combo.count()):
                if self._input_mode_combo.itemData(i) == mode:
                    self._input_mode_combo.setCurrentIndex(i)
                    break
        finally:
            self._updating = False

    def set_block_input_in_editor(self, blocked: bool) -> None:
        """Set the block input in editor checkbox state."""
        self._updating = True
        self._block_input_in_editor_checkbox.setChecked(blocked)
        self._updating = False

    def refresh(self) -> None:
        """Refresh display info."""
        if self._display is not None:
            self.set_display(self._display, self._display_name)
