"""
Agent Types dialog.

Allows configuring navigation agent types for the project.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QDoubleSpinBox,
    QDialogButtonBox,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QWidget,
    QSplitter,
    QMessageBox,
)

from termin.navmesh.settings import (
    AgentType,
    NavigationSettingsManager,
)


class AgentTypesDialog(QDialog):
    """
    Dialog for configuring navigation agent types.

    Left panel: list of agent types with add/remove buttons.
    Right panel: properties of selected agent type.

    Changes are saved when dialog is closed with OK.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_changed: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self._on_changed = on_changed
        self._manager = NavigationSettingsManager.instance()
        self._current_index: int = -1

        self.setWindowTitle("Agent Types")
        self.setMinimumSize(500, 400)

        self._list_widget: Optional[QListWidget] = None
        self._name_edit: Optional[QLineEdit] = None
        self._radius_spin: Optional[QDoubleSpinBox] = None
        self._height_spin: Optional[QDoubleSpinBox] = None
        self._max_slope_spin: Optional[QDoubleSpinBox] = None
        self._step_height_spin: Optional[QDoubleSpinBox] = None
        self._properties_group: Optional[QGroupBox] = None

        self._init_ui()
        self._load_agent_types()
        self._connect_signals()

    def _init_ui(self) -> None:
        """Create UI."""
        layout = QVBoxLayout(self)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - list of agent types
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._list_widget = QListWidget()
        left_layout.addWidget(self._list_widget)

        # Add/Remove buttons
        buttons_layout = QHBoxLayout()
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(30)
        add_btn.setToolTip("Add new agent type")
        add_btn.clicked.connect(self._on_add_agent)

        remove_btn = QPushButton("-")
        remove_btn.setFixedWidth(30)
        remove_btn.setToolTip("Remove selected agent type")
        remove_btn.clicked.connect(self._on_remove_agent)

        buttons_layout.addWidget(add_btn)
        buttons_layout.addWidget(remove_btn)
        buttons_layout.addStretch()
        left_layout.addLayout(buttons_layout)

        splitter.addWidget(left_widget)

        # Right panel - agent properties
        self._properties_group = QGroupBox("Agent Properties")
        form = QFormLayout(self._properties_group)

        # Name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Agent name")
        form.addRow("Name:", self._name_edit)

        # Radius
        self._radius_spin = QDoubleSpinBox()
        self._radius_spin.setRange(0.1, 10.0)
        self._radius_spin.setSingleStep(0.1)
        self._radius_spin.setDecimals(2)
        self._radius_spin.setSuffix(" m")
        self._radius_spin.setToolTip("Agent collision radius.\nAffects NavMesh erosion from obstacles.")
        form.addRow("Radius:", self._radius_spin)

        # Height
        self._height_spin = QDoubleSpinBox()
        self._height_spin.setRange(0.1, 20.0)
        self._height_spin.setSingleStep(0.1)
        self._height_spin.setDecimals(2)
        self._height_spin.setSuffix(" m")
        self._height_spin.setToolTip("Agent height.\nUsed for vertical clearance checks.")
        form.addRow("Height:", self._height_spin)

        # Max Slope
        self._max_slope_spin = QDoubleSpinBox()
        self._max_slope_spin.setRange(0.0, 90.0)
        self._max_slope_spin.setSingleStep(1.0)
        self._max_slope_spin.setDecimals(1)
        self._max_slope_spin.setSuffix("°")
        self._max_slope_spin.setToolTip("Maximum walkable slope angle.\nSteeper surfaces are not walkable.")
        form.addRow("Max Slope:", self._max_slope_spin)

        # Step Height
        self._step_height_spin = QDoubleSpinBox()
        self._step_height_spin.setRange(0.0, 5.0)
        self._step_height_spin.setSingleStep(0.05)
        self._step_height_spin.setDecimals(2)
        self._step_height_spin.setSuffix(" m")
        self._step_height_spin.setToolTip("Maximum step height agent can climb.\nHigher steps require jumping.")
        form.addRow("Step Height:", self._step_height_spin)

        splitter.addWidget(self._properties_group)

        # Set splitter sizes
        splitter.setSizes([150, 350])

        layout.addWidget(splitter)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Initially disable properties
        self._properties_group.setEnabled(False)

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self._list_widget.currentRowChanged.connect(self._on_selection_changed)
        self._name_edit.textChanged.connect(self._on_property_changed)
        self._radius_spin.valueChanged.connect(self._on_property_changed)
        self._height_spin.valueChanged.connect(self._on_property_changed)
        self._max_slope_spin.valueChanged.connect(self._on_property_changed)
        self._step_height_spin.valueChanged.connect(self._on_property_changed)

    def _load_agent_types(self) -> None:
        """Load agent types into list."""
        self._list_widget.clear()
        for agent in self._manager.settings.agent_types:
            self._list_widget.addItem(agent.name)

        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    def _on_selection_changed(self, row: int) -> None:
        """Handle agent type selection change."""
        if row < 0:
            self._current_index = -1
            self._properties_group.setEnabled(False)
            return

        self._current_index = row
        self._properties_group.setEnabled(True)

        # Load agent properties
        agent = self._manager.settings.agent_types[row]
        self._block_signals(True)
        self._name_edit.setText(agent.name)
        self._radius_spin.setValue(agent.radius)
        self._height_spin.setValue(agent.height)
        self._max_slope_spin.setValue(agent.max_slope)
        self._step_height_spin.setValue(agent.step_height)
        self._block_signals(False)

    def _block_signals(self, block: bool) -> None:
        """Block/unblock property widget signals."""
        self._name_edit.blockSignals(block)
        self._radius_spin.blockSignals(block)
        self._height_spin.blockSignals(block)
        self._max_slope_spin.blockSignals(block)
        self._step_height_spin.blockSignals(block)

    def _on_property_changed(self) -> None:
        """Handle property value change."""
        if self._current_index < 0:
            return

        # Update agent type
        agent = AgentType(
            name=self._name_edit.text(),
            radius=self._radius_spin.value(),
            height=self._height_spin.value(),
            max_slope=self._max_slope_spin.value(),
            step_height=self._step_height_spin.value(),
        )
        self._manager.update_agent_type(self._current_index, agent)

        # Update list item text
        item = self._list_widget.item(self._current_index)
        if item is not None:
            item.setText(agent.name)

    def _on_add_agent(self) -> None:
        """Add new agent type."""
        # Generate unique name
        base_name = "New Agent"
        name = base_name
        counter = 1
        existing_names = self._manager.settings.get_agent_type_names()
        while name in existing_names:
            name = f"{base_name} {counter}"
            counter += 1

        agent = AgentType(name=name)
        self._manager.add_agent_type(agent)

        # Add to list and select
        self._list_widget.addItem(agent.name)
        self._list_widget.setCurrentRow(self._list_widget.count() - 1)

    def _on_remove_agent(self) -> None:
        """Remove selected agent type."""
        if self._current_index < 0:
            return

        if len(self._manager.settings.agent_types) <= 1:
            QMessageBox.warning(
                self,
                "Cannot Remove",
                "At least one agent type must exist.",
            )
            return

        self._manager.remove_agent_type(self._current_index)
        self._list_widget.takeItem(self._current_index)

        # Select previous or first item
        new_row = min(self._current_index, self._list_widget.count() - 1)
        if new_row >= 0:
            self._list_widget.setCurrentRow(new_row)

    def _on_accept(self) -> None:
        """Handle OK button - save and close."""
        self._manager.save()

        if self._on_changed is not None:
            self._on_changed()

        self.accept()
