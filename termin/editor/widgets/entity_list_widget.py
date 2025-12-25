"""
EntityListWidget - widget for editing a list of Entity references.

Used in inspector for fields like SkeletonController.bone_entities.
Supports drag-drop from SceneTree, reordering, and removal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Callable

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QAbstractItemView,
)
from PyQt6.QtCore import pyqtSignal

from termin.editor.drag_drop import EditorMimeTypes, parse_entity_mime_data
from termin.visualization.core.entity_handle import EntityHandle

if TYPE_CHECKING:
    pass


class EntityListWidget(QWidget):
    """
    Widget for editing a list of Entity references via EntityHandle.

    Features:
    - Displays entity names in a list (resolved from EntityHandle)
    - Drag-drop from SceneTree to add entities
    - Reorder buttons (up/down)
    - Remove button
    - Read-only mode

    The widget stores EntityHandle objects internally.
    Serialization converts to/from UUID strings.

    Signals:
        value_changed: Emitted when the list changes.
    """

    value_changed = pyqtSignal()

    def __init__(
        self,
        read_only: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._handles: List[EntityHandle] = []
        self._read_only = read_only
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header with count
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        self._count_label = QLabel("0 entities")
        header_layout.addWidget(self._count_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # List widget
        self._list = _DropListWidget(self._on_entity_dropped)
        self._list.setMaximumHeight(150)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.currentRowChanged.connect(self._on_selection_changed)

        if read_only:
            self._list.setAcceptDrops(False)
        layout.addWidget(self._list)

        # Control buttons (hidden in read-only mode)
        if not read_only:
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(4)

            self._move_up_btn = QPushButton("\u2191")
            self._move_up_btn.setFixedSize(24, 24)
            self._move_up_btn.setToolTip("Move up")
            self._move_up_btn.clicked.connect(self._move_up)
            btn_layout.addWidget(self._move_up_btn)

            self._move_down_btn = QPushButton("\u2193")
            self._move_down_btn.setFixedSize(24, 24)
            self._move_down_btn.setToolTip("Move down")
            self._move_down_btn.clicked.connect(self._move_down)
            btn_layout.addWidget(self._move_down_btn)

            self._remove_btn = QPushButton("-")
            self._remove_btn.setFixedSize(24, 24)
            self._remove_btn.setToolTip("Remove selected")
            self._remove_btn.clicked.connect(self._remove_selected)
            btn_layout.addWidget(self._remove_btn)

            btn_layout.addStretch()
            layout.addLayout(btn_layout)

            self._update_buttons()
        else:
            self._move_up_btn = None
            self._move_down_btn = None
            self._remove_btn = None

    def get_value(self) -> list:
        """
        Return current list of Entity objects.

        Unwraps EntityHandles to Entity* for C++ field compatibility.
        """
        result = []
        for handle in self._handles:
            entity = handle.entity
            if entity is not None:
                result.append(entity)
        return result

    def set_value(self, items: Optional[list]) -> None:
        """
        Set list of entities.

        Accepts:
        - List[EntityHandle]
        - List[Entity] (C++ Entity pointers)
        - Mixed list
        """
        # DEBUG
        print(f"[EntityListWidget.set_value] items={items}, type={type(items)}")
        if items:
            for i, item in enumerate(items):
                print(f"  [{i}] type={type(item)}, value={item}")

        self._updating = True
        try:
            self._handles = []
            if items:
                for item in items:
                    if item is None:
                        continue
                    if isinstance(item, EntityHandle):
                        self._handles.append(item)
                    elif hasattr(item, 'uuid') and hasattr(item, 'name'):
                        # It's an Entity object - wrap in EntityHandle
                        self._handles.append(EntityHandle.from_entity(item))
                    else:
                        print(f"  [EntityListWidget] Skipping invalid item: {item}")
            self._rebuild_list()
            self._update_buttons()
            print(f"[EntityListWidget.set_value] result: {len(self._handles)} handles")
        finally:
            self._updating = False

    def _rebuild_list(self) -> None:
        """Rebuild QListWidget from current handles."""
        current_row = self._list.currentRow()
        self._list.clear()

        for i, handle in enumerate(self._handles):
            # Display entity name (or UUID prefix if not resolved)
            name = handle.name
            item = QListWidgetItem(f"{i}: {name}")
            self._list.addItem(item)

        # Restore selection
        if 0 <= current_row < len(self._handles):
            self._list.setCurrentRow(current_row)
        elif self._handles:
            self._list.setCurrentRow(len(self._handles) - 1)

        # Update count label
        count = len(self._handles)
        self._count_label.setText(f"{count} {'entity' if count == 1 else 'entities'}")

    def _update_buttons(self) -> None:
        """Update button enabled states."""
        if self._read_only:
            return

        has_selection = self._list.currentRow() >= 0
        self._remove_btn.setEnabled(has_selection)
        self._move_up_btn.setEnabled(has_selection and self._list.currentRow() > 0)
        self._move_down_btn.setEnabled(
            has_selection and self._list.currentRow() < len(self._handles) - 1
        )

    def _on_selection_changed(self, row: int) -> None:
        """Handle selection change."""
        self._update_buttons()

    def _on_entity_dropped(self, entity_uuid: str, entity_name: str) -> None:
        """Handle entity dropped from SceneTree."""
        if self._read_only:
            return

        # Avoid duplicates by UUID
        for handle in self._handles:
            if handle.uuid == entity_uuid:
                return

        # Create new handle (resolves via EntityRegistry)
        handle = EntityHandle(uuid=entity_uuid)
        self._handles.append(handle)
        self._rebuild_list()
        self._list.setCurrentRow(len(self._handles) - 1)
        self._update_buttons()
        self.value_changed.emit()

    def _remove_selected(self) -> None:
        """Remove selected entity from list."""
        row = self._list.currentRow()
        if row < 0 or row >= len(self._handles):
            return

        del self._handles[row]
        self._rebuild_list()
        self._update_buttons()
        self.value_changed.emit()

    def _move_up(self) -> None:
        """Move selected entity up in the list."""
        row = self._list.currentRow()
        if row <= 0 or row >= len(self._handles):
            return

        self._handles[row], self._handles[row - 1] = (
            self._handles[row - 1],
            self._handles[row],
        )
        self._rebuild_list()
        self._list.setCurrentRow(row - 1)
        self._update_buttons()
        self.value_changed.emit()

    def _move_down(self) -> None:
        """Move selected entity down in the list."""
        row = self._list.currentRow()
        if row < 0 or row >= len(self._handles) - 1:
            return

        self._handles[row], self._handles[row + 1] = (
            self._handles[row + 1],
            self._handles[row],
        )
        self._rebuild_list()
        self._list.setCurrentRow(row + 1)
        self._update_buttons()
        self.value_changed.emit()


class _DropListWidget(QListWidget):
    """QListWidget subclass that accepts entity drops."""

    def __init__(self, on_drop_callback: Callable[[str, str], None], parent=None):
        super().__init__(parent)
        self._on_drop = on_drop_callback
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(EditorMimeTypes.ENTITY):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(EditorMimeTypes.ENTITY):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        data = parse_entity_mime_data(event.mimeData())
        if data is not None:
            entity_uuid = data.get("entity_uuid")
            entity_name = data.get("entity_name", "")
            if entity_uuid:
                self._on_drop(entity_uuid, entity_name)
                event.acceptProposedAction()
                return
        event.ignore()
