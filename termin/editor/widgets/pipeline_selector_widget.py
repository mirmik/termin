"""Pipeline selector widget for choosing render pipelines."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QComboBox
from PyQt6.QtCore import pyqtSignal

from termin.editor.widgets.field_widgets import FieldWidget

if TYPE_CHECKING:
    from termin.visualization.core.resources import ResourceManager


class PipelineSelectorWidget(FieldWidget):
    """
    Widget for selecting a render pipeline by name.

    Shows options:
    - "(Default)" - use default pipeline
    - "(Editor)" - use editor pipeline (if available)
    - Named pipelines from ResourceManager

    Returns pipeline name as string.
    """

    value_changed = pyqtSignal()

    def __init__(
        self,
        resources: Optional["ResourceManager"] = None,
        include_editor: bool = True,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._resources = resources
        self._include_editor = include_editor

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(lambda _: self.value_changed.emit())
        layout.addWidget(self._combo)

        self._refresh_items()

    def set_resources(self, resources: "ResourceManager") -> None:
        """Set resource manager for pipeline list."""
        self._resources = resources
        self._refresh_items()

    def _refresh_items(self) -> None:
        """Refresh pipeline list from ResourceManager."""
        self._combo.blockSignals(True)
        current_text = self._combo.currentText()
        self._combo.clear()

        # Add special options
        self._combo.addItem("(Default)", userData="(Default)")
        if self._include_editor:
            self._combo.addItem("(Editor)", userData="(Editor)")

        # Add named pipelines from ResourceManager
        if self._resources is not None:
            pipeline_names = self._resources.list_pipeline_names()
            for name in pipeline_names:
                self._combo.addItem(name, userData=name)

        # Restore selection
        idx = self._combo.findText(current_text)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        else:
            self._combo.setCurrentIndex(0)  # Default

        self._combo.blockSignals(False)

    def get_value(self) -> str:
        """Get currently selected pipeline name."""
        return self._combo.currentData() or "(Default)"

    def set_value(self, value: str) -> None:
        """Set pipeline name."""
        self._combo.blockSignals(True)

        # Refresh in case list changed
        self._refresh_items()

        if value is None:
            value = "(Default)"

        idx = self._combo.findData(value)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        else:
            # Try by text
            idx = self._combo.findText(value)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
            else:
                self._combo.setCurrentIndex(0)  # Default

        self._combo.blockSignals(False)
