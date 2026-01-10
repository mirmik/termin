"""
ViewportListWidget — tree widget for managing Displays and Viewports.

Shows a two-level hierarchy:
- Level 1: Displays
- Level 2: Viewports belonging to each display
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional

from PyQt6.QtCore import Qt, QModelIndex, pyqtSignal
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QTreeView,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QWidget,
    QMenu,
    QInputDialog,
)

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport


class DisplayItem(QStandardItem):
    """Tree item representing a Display."""

    def __init__(self, display: "Display", name: str):
        super().__init__(name)
        self.display = display
        self.setEditable(False)


class ViewportItem(QStandardItem):
    """Tree item representing a Viewport."""

    def __init__(self, viewport: "Viewport", name: str):
        super().__init__(name)
        self.viewport = viewport
        self.setEditable(False)


class ViewportListWidget(QWidget):
    """
    Widget displaying Displays and their Viewports in a tree structure.

    Signals:
        display_selected: Emitted when a display is selected, passes Display or None.
        viewport_selected: Emitted when a viewport is selected, passes Viewport or None.
        display_add_requested: Emitted when user wants to add a new display.
        viewport_add_requested: Emitted when user wants to add a viewport to a display.
        display_remove_requested: Emitted when user wants to remove a display.
        viewport_remove_requested: Emitted when user wants to remove a viewport.
    """

    display_selected = pyqtSignal(object)  # Display or None
    viewport_selected = pyqtSignal(object)  # Viewport or None
    display_add_requested = pyqtSignal()
    viewport_add_requested = pyqtSignal(object)  # Display
    display_remove_requested = pyqtSignal(object)  # Display
    viewport_remove_requested = pyqtSignal(object)  # Viewport
    viewport_renamed = pyqtSignal(object, str)  # Viewport, new_name

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._displays: List["Display"] = []
        self._display_names: dict[int, str] = {}  # id(display) -> name

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Toolbar with Add buttons
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(4)

        self._add_display_btn = QPushButton("+ Display")
        self._add_display_btn.setToolTip("Add new display")
        self._add_display_btn.clicked.connect(self._on_add_display_clicked)
        toolbar.addWidget(self._add_display_btn)

        self._add_viewport_btn = QPushButton("+ Viewport")
        self._add_viewport_btn.setToolTip("Add viewport to selected display")
        self._add_viewport_btn.clicked.connect(self._on_add_viewport_clicked)
        self._add_viewport_btn.setEnabled(False)
        toolbar.addWidget(self._add_viewport_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Tree view
        self._tree = QTreeView()
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._tree)

        # Model
        self._model = QStandardItemModel()
        self._tree.setModel(self._model)

        # Selection handling
        self._tree.selectionModel().currentChanged.connect(self._on_current_changed)

    def set_displays(self, displays: List["Display"]) -> None:
        """
        Set the list of displays to show.

        Args:
            displays: List of Display objects.
        """
        self._displays = list(displays)
        self._rebuild_tree()

    def set_display_name(self, display: "Display", name: str) -> None:
        """Set custom name for a display."""
        self._display_names[id(display)] = name
        self._rebuild_tree()

    def get_display_name(self, display: "Display") -> str:
        """Get display name (custom or default)."""
        if id(display) in self._display_names:
            return self._display_names[id(display)]
        idx = self._displays.index(display) if display in self._displays else 0
        return f"Display {idx}"

    def add_display(self, display: "Display", name: Optional[str] = None) -> None:
        """Add a display to the list."""
        if display not in self._displays:
            self._displays.append(display)
            if name is not None:
                self._display_names[id(display)] = name
            self._rebuild_tree()

    def remove_display(self, display: "Display") -> None:
        """Remove a display from the list."""
        if display in self._displays:
            self._displays.remove(display)
            self._display_names.pop(id(display), None)
            self._rebuild_tree()

    def refresh(self) -> None:
        """Refresh the tree to reflect current state."""
        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        """Rebuild the tree model from current displays."""
        self._model.clear()

        for display in self._displays:
            display_name = self.get_display_name(display)
            display_item = DisplayItem(display, display_name)

            # Add viewports as children
            for i, viewport in enumerate(display.viewports):
                # Build viewport label: "name (camera)" or "Viewport i (camera)"
                vp_name = viewport.name if viewport.name else f"Viewport {i}"

                camera_name = "No Camera"
                if viewport.camera is not None:
                    entity = viewport.camera.entity
                    if entity is not None:
                        camera_name = entity.name or f"Camera {i}"
                    else:
                        camera_name = f"Camera {i}"

                viewport_item = ViewportItem(viewport, f"{vp_name} ({camera_name})")
                display_item.appendRow(viewport_item)

            self._model.appendRow(display_item)

        self._tree.expandAll()

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        """Handle selection change in tree."""
        if not current.isValid():
            self._add_viewport_btn.setEnabled(False)
            self.display_selected.emit(None)
            self.viewport_selected.emit(None)
            return

        item = self._model.itemFromIndex(current)

        if isinstance(item, ViewportItem):
            self._add_viewport_btn.setEnabled(True)
            self.viewport_selected.emit(item.viewport)
            # Don't emit display_selected here - it would override viewport inspector
        elif isinstance(item, DisplayItem):
            self._add_viewport_btn.setEnabled(True)
            self.display_selected.emit(item.display)
            self.viewport_selected.emit(None)
        else:
            self._add_viewport_btn.setEnabled(False)
            self.display_selected.emit(None)
            self.viewport_selected.emit(None)

    def _on_add_display_clicked(self) -> None:
        """Handle add display button click."""
        self.display_add_requested.emit()

    def _on_add_viewport_clicked(self) -> None:
        """Handle add viewport button click."""
        display = self._get_selected_display()
        if display is not None:
            self.viewport_add_requested.emit(display)

    def _get_selected_display(self) -> Optional["Display"]:
        """Get currently selected display (or parent display if viewport selected)."""
        current = self._tree.currentIndex()
        if not current.isValid():
            return None

        item = self._model.itemFromIndex(current)

        if isinstance(item, DisplayItem):
            return item.display
        elif isinstance(item, ViewportItem):
            parent = item.parent()
            if isinstance(parent, DisplayItem):
                return parent.display

        return None

    def _get_selected_viewport(self) -> Optional["Viewport"]:
        """Get currently selected viewport."""
        current = self._tree.currentIndex()
        if not current.isValid():
            return None

        item = self._model.itemFromIndex(current)
        if isinstance(item, ViewportItem):
            return item.viewport

        return None

    def _on_context_menu(self, pos) -> None:
        """Show context menu."""
        index = self._tree.indexAt(pos)
        item = self._model.itemFromIndex(index) if index.isValid() else None

        menu = QMenu(self)

        # Add display action (always available)
        add_display_action = menu.addAction("Add Display")
        add_display_action.triggered.connect(self.display_add_requested.emit)

        if isinstance(item, DisplayItem):
            menu.addSeparator()

            add_viewport_action = menu.addAction("Add Viewport")
            add_viewport_action.triggered.connect(
                lambda: self.viewport_add_requested.emit(item.display)
            )

            remove_display_action = menu.addAction("Remove Display")
            remove_display_action.triggered.connect(
                lambda: self.display_remove_requested.emit(item.display)
            )

        elif isinstance(item, ViewportItem):
            menu.addSeparator()

            rename_action = menu.addAction("Rename...")
            rename_action.triggered.connect(
                lambda: self._rename_viewport(item.viewport)
            )

            parent = item.parent()
            if isinstance(parent, DisplayItem):
                add_viewport_action = menu.addAction("Add Viewport")
                add_viewport_action.triggered.connect(
                    lambda: self.viewport_add_requested.emit(parent.display)
                )

            remove_viewport_action = menu.addAction("Remove Viewport")
            remove_viewport_action.triggered.connect(
                lambda: self.viewport_remove_requested.emit(item.viewport)
            )

        global_pos = self._tree.viewport().mapToGlobal(pos)
        menu.exec(global_pos)

    def _rename_viewport(self, viewport: "Viewport") -> None:
        """Show rename dialog for viewport."""
        current_name = viewport.name or ""
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Viewport",
            "Viewport name:",
            text=current_name,
        )
        if ok and new_name != current_name:
            viewport.name = new_name
            self.viewport_renamed.emit(viewport, new_name)
            self._rebuild_tree()
