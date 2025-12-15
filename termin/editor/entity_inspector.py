"""
Entity inspector widget.

Shows entity properties: name, layer, flags.
"""

from __future__ import annotations

from typing import Optional, Callable, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QFormLayout,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QScrollArea,
    QFrame,
    QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal

from termin.editor.undo_stack import UndoCommand

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity
    from termin.visualization.core.scene import Scene


class EntityPropertyEditCommand(UndoCommand):
    """Undo command for editing entity properties."""

    def __init__(
        self,
        entity: "Entity",
        property_name: str,
        old_value,
        new_value,
    ):
        self._entity = entity
        self._property_name = property_name
        self._old_value = old_value
        self._new_value = new_value

    def do(self) -> None:
        setattr(self._entity, self._property_name, self._new_value)

    def undo(self) -> None:
        setattr(self._entity, self._property_name, self._old_value)

    def merge_with(self, other: UndoCommand) -> bool:
        if not isinstance(other, EntityPropertyEditCommand):
            return False
        if other._entity is not self._entity:
            return False
        if other._property_name != self._property_name:
            return False
        self._new_value = other._new_value
        return True

    def __repr__(self) -> str:
        return f"EntityPropertyEditCommand({self._property_name})"


class EntityInspector(QWidget):
    """Inspector widget for entity properties."""

    entity_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._entity: Optional["Entity"] = None
        self._scene: Optional["Scene"] = None
        self._updating_from_model = False
        self._push_undo_command: Optional[Callable[[UndoCommand, bool], None]] = None
        self._flag_checkboxes: list[QCheckBox] = []

        self._init_ui()
        self._set_enabled(False)

    def _init_ui(self) -> None:
        """Initialize UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Title
        title = QLabel("Entity")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        # Form layout for properties
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setContentsMargins(0, 0, 0, 0)

        # Name
        self._name_edit = QLineEdit()
        self._name_edit.editingFinished.connect(self._on_name_changed)
        form.addRow("Name:", self._name_edit)

        # Layer
        self._layer_combo = QComboBox()
        self._layer_combo.currentIndexChanged.connect(self._on_layer_changed)
        form.addRow("Layer:", self._layer_combo)

        layout.addLayout(form)

        # Flags section
        flags_label = QLabel("Flags:")
        layout.addWidget(flags_label)

        # Flags in a collapsible/scrollable area
        self._flags_container = QWidget()
        flags_layout = QVBoxLayout(self._flags_container)
        flags_layout.setContentsMargins(0, 0, 0, 0)
        flags_layout.setSpacing(2)

        # Create 64 checkboxes for flags (we'll show only named ones initially)
        for i in range(64):
            cb = QCheckBox(f"Flag {i}")
            cb.stateChanged.connect(lambda state, idx=i: self._on_flag_changed(idx, state))
            self._flag_checkboxes.append(cb)
            flags_layout.addWidget(cb)
            cb.setVisible(False)  # Hidden by default

        layout.addWidget(self._flags_container)
        layout.addStretch()

    def _set_enabled(self, enabled: bool) -> None:
        """Enable/disable all controls."""
        self._name_edit.setEnabled(enabled)
        self._layer_combo.setEnabled(enabled)
        for cb in self._flag_checkboxes:
            cb.setEnabled(enabled)

    def set_undo_command_handler(
        self, handler: Optional[Callable[[UndoCommand, bool], None]]
    ) -> None:
        """Register undo command handler."""
        self._push_undo_command = handler

    def set_scene(self, scene: Optional["Scene"]) -> None:
        """Set the scene for layer/flag names."""
        self._scene = scene
        self._update_layer_combo()
        self._update_flag_labels()

    def set_entity(self, entity: Optional["Entity"]) -> None:
        """Set the entity to inspect."""
        self._entity = entity
        self._set_enabled(entity is not None)
        self._refresh_from_entity()

    def _update_layer_combo(self) -> None:
        """Update layer combo box items from scene."""
        self._updating_from_model = True
        try:
            self._layer_combo.clear()
            for i in range(64):
                if self._scene is not None:
                    name = self._scene.get_layer_name(i)
                else:
                    name = f"Layer {i}"
                self._layer_combo.addItem(name, i)
        finally:
            self._updating_from_model = False

    def _update_flag_labels(self) -> None:
        """Update flag checkbox labels and visibility from scene."""
        for i, cb in enumerate(self._flag_checkboxes):
            if self._scene is not None:
                name = self._scene.get_flag_name(i)
                # Show if it has a custom name or is used
                has_custom_name = i in self._scene.flag_names
            else:
                name = f"Flag {i}"
                has_custom_name = False

            cb.setText(name)
            # Show first 8 flags always, others only if named
            cb.setVisible(i < 8 or has_custom_name)

    def _refresh_from_entity(self) -> None:
        """Refresh all widgets from entity values."""
        if self._entity is None:
            return

        self._updating_from_model = True
        try:
            # Name
            self._name_edit.setText(self._entity.name)

            # Layer
            self._layer_combo.setCurrentIndex(self._entity.layer)

            # Flags
            flags = self._entity.flags
            for i, cb in enumerate(self._flag_checkboxes):
                cb.setChecked(bool(flags & (1 << i)))
        finally:
            self._updating_from_model = False

    def _on_name_changed(self) -> None:
        """Handle name edit finished."""
        if self._updating_from_model or self._entity is None:
            return

        new_name = self._name_edit.text().strip()
        if not new_name:
            new_name = "entity"

        old_name = self._entity.name
        if new_name == old_name:
            return

        if self._push_undo_command is not None:
            cmd = EntityPropertyEditCommand(self._entity, "name", old_name, new_name)
            self._push_undo_command(cmd, False)
        else:
            self._entity.name = new_name

        self.entity_changed.emit()

    def _on_layer_changed(self, index: int) -> None:
        """Handle layer combo change."""
        if self._updating_from_model or self._entity is None:
            return

        new_layer = self._layer_combo.itemData(index)
        if new_layer is None:
            return

        old_layer = self._entity.layer
        if new_layer == old_layer:
            return

        if self._push_undo_command is not None:
            cmd = EntityPropertyEditCommand(self._entity, "layer", old_layer, new_layer)
            self._push_undo_command(cmd, False)
        else:
            self._entity.layer = new_layer

        self.entity_changed.emit()

    def _on_flag_changed(self, flag_index: int, state: int) -> None:
        """Handle flag checkbox change."""
        if self._updating_from_model or self._entity is None:
            return

        old_flags = self._entity.flags
        if state:
            new_flags = old_flags | (1 << flag_index)
        else:
            new_flags = old_flags & ~(1 << flag_index)

        if new_flags == old_flags:
            return

        if self._push_undo_command is not None:
            cmd = EntityPropertyEditCommand(self._entity, "flags", old_flags, new_flags)
            self._push_undo_command(cmd, False)
        else:
            self._entity.flags = new_flags

        self.entity_changed.emit()
