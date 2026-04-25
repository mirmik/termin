"""
ViewportListWidget — tree widget for managing Displays and Viewports.

Shows a two-level hierarchy:
- Level 1: Displays
- Level 2: Viewports belonging to each display
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

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
    from termin.visualization.core.entity import Entity


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


class EntityItem(QStandardItem):
    """Tree item representing an Entity (from viewport's internal_entities)."""

    def __init__(self, entity: "Entity", name: str):
        super().__init__(name)
        self.entity = entity
        self.setEditable(False)


class RenderTargetItem(QStandardItem):
    """Tree item representing a RenderTarget."""

    def __init__(self, render_target, name: str):
        super().__init__(name)
        self.render_target = render_target
        self.setEditable(False)
        # Drag-source: dropped onto a material texture slot, this binds the
        # RT's color channel as the slot's source. See drag_drop.py and
        # MaterialInspector._on_render_target_dropped.
        self.setFlags(self.flags() | Qt.ItemFlag.ItemIsDragEnabled)


class RenderTargetGroupItem(QStandardItem):
    """Tree group header for Render Targets section."""

    def __init__(self):
        super().__init__("Render Targets")
        self.setEditable(False)


class _ViewportListModel(QStandardItemModel):
    """Standard model with RT-ref drag payload for RenderTargetItem rows.

    Default QStandardItemModel.mimeData encodes its own internal format,
    which the material inspector can't consume. Override to emit
    RENDER_TARGET_REF when a RenderTargetItem is dragged.
    """

    def mimeTypes(self):
        from termin.editor.drag_drop import EditorMimeTypes
        types = list(super().mimeTypes())
        if EditorMimeTypes.RENDER_TARGET_REF not in types:
            types.append(EditorMimeTypes.RENDER_TARGET_REF)
        return types

    def mimeData(self, indexes):
        from termin.editor.drag_drop import (
            create_render_target_ref_mime_data,
        )
        for idx in indexes:
            if not idx.isValid():
                continue
            item = self.itemFromIndex(idx)
            if isinstance(item, RenderTargetItem):
                rt = item.render_target
                rt_name = getattr(rt, "name", None) or item.text() or ""
                if rt_name:
                    return create_render_target_ref_mime_data(rt_name, "color")
        return super().mimeData(indexes)


class ViewportListWidget(QWidget):
    """
    Widget displaying Displays, Viewports, and Render Targets in a tree structure.

    Signals:
        display_selected: Emitted when a display is selected, passes Display or None.
        viewport_selected: Emitted when a viewport is selected, passes Viewport or None.
        render_target_selected: Emitted when a render target is selected.
        display_add_requested: Emitted when user wants to add a new display.
        viewport_add_requested: Emitted when user wants to add a viewport to a display.
        display_remove_requested: Emitted when user wants to remove a display.
        viewport_remove_requested: Emitted when user wants to remove a viewport.
        render_target_add_requested: Emitted when user wants to add a render target.
        render_target_remove_requested: Emitted when user wants to remove a render target.
    """

    display_selected = pyqtSignal(object)  # Display or None
    viewport_selected = pyqtSignal(object)  # Viewport or None
    entity_selected = pyqtSignal(object)  # Entity or None (from internal_entities)
    render_target_selected = pyqtSignal(object)  # render_target or None
    display_add_requested = pyqtSignal()
    viewport_add_requested = pyqtSignal(object)  # Display
    display_remove_requested = pyqtSignal(object)  # Display
    viewport_remove_requested = pyqtSignal(object)  # Viewport
    viewport_renamed = pyqtSignal(object, str)  # Viewport, new_name
    render_target_add_requested = pyqtSignal()
    render_target_remove_requested = pyqtSignal(object)  # render_target

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._displays: List["Display"] = []
        self._display_names: dict[int, str] = {}  # tc_display_ptr -> name
        self._render_targets: list = []

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

        self._add_rt_btn = QPushButton("+ RT")
        self._add_rt_btn.setToolTip("Add render target")
        self._add_rt_btn.clicked.connect(self._on_add_rt_clicked)
        toolbar.addWidget(self._add_rt_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Tree view
        self._tree = QTreeView()
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        # Drag-source for RT items — see _ViewportListModel.mimeData.
        self._tree.setDragEnabled(True)
        self._tree.setDragDropMode(QTreeView.DragDropMode.DragOnly)
        layout.addWidget(self._tree)

        # Model
        self._model = _ViewportListModel()
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
        self._display_names[display.tc_display_ptr] = name
        self._rebuild_tree()

    def get_display_name(self, display: "Display") -> str:
        """Get display name (custom or default)."""
        if display.tc_display_ptr in self._display_names:
            return self._display_names[display.tc_display_ptr]
        idx = self._displays.index(display) if display in self._displays else 0
        return f"Display {idx}"

    def add_display(self, display: "Display", name: Optional[str] = None) -> None:
        """Add a display to the list."""
        if display not in self._displays:
            self._displays.append(display)
            if name is not None:
                self._display_names[display.tc_display_ptr] = name
            self._rebuild_tree()

    def remove_display(self, display: "Display") -> None:
        """Remove a display from the list."""
        if display in self._displays:
            self._displays.remove(display)
            self._display_names.pop(display.tc_display_ptr, None)
            self._rebuild_tree()

    def set_render_targets(self, render_targets: list) -> None:
        """Set the list of render targets to show."""
        self._render_targets = list(render_targets or [])
        self._rebuild_tree()

    def refresh(self) -> None:
        """Refresh the tree to reflect current state."""
        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        """Rebuild the tree model from current displays."""
        # Clear references in items before removing rows
        self._clear_item_refs_recursive(self._model.invisibleRootItem())

        # Clear the model (reuse same instance)
        self._model.removeRows(0, self._model.rowCount())

        for display in self._displays:
            display_name = self.get_display_name(display)
            display_item = DisplayItem(display, display_name)

            viewports = display.viewports
            for i, viewport in enumerate(viewports):
                vp_name = viewport.name if viewport.name else f"Viewport {i}"

                camera_name = "No Camera"
                camera = viewport.camera
                if camera is not None:
                    entity = camera.entity
                    if entity is not None:
                        camera_name = entity.name or f"Camera {i}"
                    else:
                        camera_name = f"Camera {i}"

                viewport_item = ViewportItem(viewport, f"{vp_name} ({camera_name})")

                internal_entities = viewport.internal_entities
                if internal_entities is not None:
                    self._add_entity_hierarchy(viewport_item, internal_entities)

                display_item.appendRow(viewport_item)

            self._model.appendRow(display_item)

        if self._render_targets:
            rt_group = RenderTargetGroupItem()
            for rt in self._render_targets:
                rt_name = rt.name if rt.name else "RenderTarget"
                rt_item = RenderTargetItem(rt, rt_name)
                rt_group.appendRow(rt_item)
            self._model.appendRow(rt_group)

        self._tree.expandAll()

    def _clear_item_refs_recursive(self, item: QStandardItem) -> None:
        """Recursively clear native object references in all items."""
        for row in range(item.rowCount()):
            child = item.child(row)
            if child is not None:
                self._clear_item_refs_recursive(child)
                if isinstance(child, DisplayItem):
                    child.display = None  # type: ignore
                elif isinstance(child, ViewportItem):
                    child.viewport = None  # type: ignore
                elif isinstance(child, EntityItem):
                    child.entity = None  # type: ignore

    def _add_entity_hierarchy(self, parent_item: QStandardItem, entity: "Entity") -> None:
        """Recursively add entity and its children to the tree."""
        if not entity.valid():
            return
        entity_name = entity.name or f"Entity ({entity.uuid[:8]})"
        entity_item = EntityItem(entity, entity_name)
        parent_item.appendRow(entity_item)

        # Add children
        for child_tf in entity.transform.children:
            child_entity = child_tf.entity
            if child_entity is not None and child_entity.valid():
                self._add_entity_hierarchy(entity_item, child_entity)

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        """Handle selection change in tree."""
        if not current.isValid():
            self._add_viewport_btn.setEnabled(False)
            self.display_selected.emit(None)
            self.viewport_selected.emit(None)
            self.entity_selected.emit(None)
            return

        item = self._model.itemFromIndex(current)

        if isinstance(item, EntityItem):
            self._add_viewport_btn.setEnabled(False)
            entity = item.entity
            if entity is not None and entity.valid():
                self.entity_selected.emit(entity)
            else:
                self.entity_selected.emit(None)
        elif isinstance(item, RenderTargetItem):
            self._add_viewport_btn.setEnabled(False)
            self.render_target_selected.emit(item.render_target)
        elif isinstance(item, ViewportItem):
            self._add_viewport_btn.setEnabled(True)
            self.viewport_selected.emit(item.viewport)
            self.entity_selected.emit(None)
        elif isinstance(item, DisplayItem):
            self._add_viewport_btn.setEnabled(True)
            self.display_selected.emit(item.display)
            self.viewport_selected.emit(None)
            self.entity_selected.emit(None)
        else:
            self._add_viewport_btn.setEnabled(False)
            self.display_selected.emit(None)
            self.viewport_selected.emit(None)
            self.entity_selected.emit(None)
            self.render_target_selected.emit(None)

    def _on_add_rt_clicked(self) -> None:
        self.render_target_add_requested.emit()

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

        elif isinstance(item, RenderTargetItem):
            menu.addSeparator()
            rename_rt_action = menu.addAction("Rename...")
            rename_rt_action.triggered.connect(
                lambda: self._rename_render_target(item.render_target)
            )
            remove_rt_action = menu.addAction("Remove Render Target")
            remove_rt_action.triggered.connect(
                lambda: self.render_target_remove_requested.emit(item.render_target)
            )

        elif isinstance(item, RenderTargetGroupItem):
            menu.addSeparator()
            add_rt_action = menu.addAction("Add Render Target")
            add_rt_action.triggered.connect(self.render_target_add_requested.emit)

        global_pos = self._tree.viewport().mapToGlobal(pos)
        menu.exec(global_pos)

    def _rename_render_target(self, render_target) -> None:
        """Show rename dialog for render target."""
        current_name = render_target.name or ""
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Render Target",
            "Render target name:",
            text=current_name,
        )
        if ok and new_name != current_name:
            render_target.name = new_name
            self._rebuild_tree()

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
