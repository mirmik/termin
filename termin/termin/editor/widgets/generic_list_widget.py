"""
GenericListWidget - reusable widget for displaying/editing lists in inspector.

Supports different item types via callbacks for name extraction and item creation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Callable, Any, TypeVar

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
from PyQt6.QtCore import pyqtSignal, QMimeData

if TYPE_CHECKING:
    pass

T = TypeVar("T")


class GenericListWidget(QWidget):
    """
    Generic widget for editing lists of items.

    Features:
    - Displays items in a list using get_item_name callback
    - Optional drag-drop support
    - Reorder buttons (up/down)
    - Remove button
    - Read-only mode

    Args:
        get_item_name: Callback to get display name from item
        item_type_label: Label for count display (e.g., "clip", "entity")
        read_only: If True, disable editing
        accept_drop: Callback (mime_data) -> item or None for drag-drop support
    """

    value_changed = pyqtSignal()

    def __init__(
        self,
        get_item_name: Callable[[Any], str],
        item_type_label: str = "item",
        read_only: bool = False,
        accept_drop: Optional[Callable[[QMimeData], Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._items: List[Any] = []
        self._get_item_name = get_item_name
        self._item_type_label = item_type_label
        self._read_only = read_only
        self._accept_drop = accept_drop
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header with count
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        self._count_label = QLabel(f"0 {item_type_label}s")
        header_layout.addWidget(self._count_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # List widget
        if accept_drop is not None and not read_only:
            self._list = _DropListWidget(self._on_item_dropped, accept_drop)
        else:
            self._list = QListWidget()
            self._list.setAcceptDrops(False)

        self._list.setMaximumHeight(150)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.currentRowChanged.connect(self._on_selection_changed)
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

    def get_value(self) -> List[Any]:
        """Return current list of items."""
        return list(self._items)

    def set_value(self, items: Optional[List[Any]]) -> None:
        """Set list of items."""
        self._updating = True
        try:
            self._items = list(items) if items else []
            self._rebuild_list()
            self._update_buttons()
        finally:
            self._updating = False

    def _rebuild_list(self) -> None:
        """Rebuild QListWidget from current items."""
        current_row = self._list.currentRow()
        self._list.clear()

        for i, item in enumerate(self._items):
            name = self._get_item_name(item)
            list_item = QListWidgetItem(f"{i}: {name}")
            self._list.addItem(list_item)

        # Restore selection
        if 0 <= current_row < len(self._items):
            self._list.setCurrentRow(current_row)
        elif self._items:
            self._list.setCurrentRow(len(self._items) - 1)

        # Update count label
        count = len(self._items)
        label = self._item_type_label if count == 1 else f"{self._item_type_label}s"
        self._count_label.setText(f"{count} {label}")

    def _update_buttons(self) -> None:
        """Update button enabled states."""
        if self._read_only:
            return

        has_selection = self._list.currentRow() >= 0
        self._remove_btn.setEnabled(has_selection)
        self._move_up_btn.setEnabled(has_selection and self._list.currentRow() > 0)
        self._move_down_btn.setEnabled(
            has_selection and self._list.currentRow() < len(self._items) - 1
        )

    def _on_selection_changed(self, row: int) -> None:
        """Handle selection change."""
        self._update_buttons()

    def _on_item_dropped(self, item: Any) -> None:
        """Handle item dropped."""
        if self._read_only or item is None:
            return

        self._items.append(item)
        self._rebuild_list()
        self._list.setCurrentRow(len(self._items) - 1)
        self._update_buttons()
        self.value_changed.emit()

    def _remove_selected(self) -> None:
        """Remove selected item from list."""
        row = self._list.currentRow()
        if row < 0 or row >= len(self._items):
            return

        del self._items[row]
        self._rebuild_list()
        self._update_buttons()
        self.value_changed.emit()

    def _move_up(self) -> None:
        """Move selected item up in the list."""
        row = self._list.currentRow()
        if row <= 0 or row >= len(self._items):
            return

        self._items[row], self._items[row - 1] = (
            self._items[row - 1],
            self._items[row],
        )
        self._rebuild_list()
        self._list.setCurrentRow(row - 1)
        self._update_buttons()
        self.value_changed.emit()

    def _move_down(self) -> None:
        """Move selected item down in the list."""
        row = self._list.currentRow()
        if row < 0 or row >= len(self._items) - 1:
            return

        self._items[row], self._items[row + 1] = (
            self._items[row + 1],
            self._items[row],
        )
        self._rebuild_list()
        self._list.setCurrentRow(row + 1)
        self._update_buttons()
        self.value_changed.emit()


class _DropListWidget(QListWidget):
    """QListWidget subclass that accepts drops via callback."""

    def __init__(
        self,
        on_drop_callback: Callable[[Any], None],
        accept_drop: Callable[[QMimeData], Any],
        parent=None,
    ):
        super().__init__(parent)
        self._on_drop = on_drop_callback
        self._accept_drop = accept_drop
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if self._accept_drop(event.mimeData()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._accept_drop(event.mimeData()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        item = self._accept_drop(event.mimeData())
        if item is not None:
            self._on_drop(item)
            event.acceptProposedAction()
        else:
            event.ignore()
