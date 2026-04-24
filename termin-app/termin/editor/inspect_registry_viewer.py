"""
Dialog for viewing InspectRegistry state.

Shows all registered types, their fields, backends, and inheritance.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QPushButton,
    QLabel,
    QLineEdit,
)
from PyQt6.QtCore import Qt


class InspectRegistryViewer(QDialog):
    """
    Dialog for viewing InspectRegistry state.

    Shows:
    - All registered types
    - Fields for each type (own and inherited)
    - Backend (Python/C++)
    - Type inheritance
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Inspect Registry Viewer")
        self.setMinimumSize(900, 600)

        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        """Create dialog UI."""
        layout = QVBoxLayout(self)

        # Filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Type name...")
        self._filter_edit.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self._filter_edit)
        layout.addLayout(filter_layout)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # Left: types tree
        self._types_tree = QTreeWidget()
        self._types_tree.setHeaderLabels(["Type", "Backend", "Parent", "Fields"])
        self._types_tree.setAlternatingRowColors(True)
        self._types_tree.itemClicked.connect(self._on_type_clicked)
        splitter.addWidget(self._types_tree)

        # Right: details
        self._details_text = QTextEdit()
        self._details_text.setReadOnly(True)
        self._details_text.setFontFamily("monospace")
        splitter.addWidget(self._details_text)

        splitter.setSizes([450, 450])

        # Status
        self._status_label = QLabel()
        self._status_label.setFixedHeight(20)
        layout.addWidget(self._status_label)

        # Buttons
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def refresh(self) -> None:
        """Refresh types list from InspectRegistry."""
        self._types_tree.clear()
        self._details_text.clear()

        try:
            from termin._native.inspect import InspectRegistry
            registry = InspectRegistry.instance()
        except ImportError:
            self._status_label.setText("InspectRegistry not available")
            return

        type_names = registry.types()

        for type_name in sorted(type_names):
            backend = registry.get_type_backend(type_name)
            backend_str = backend.name if hasattr(backend, 'name') else str(backend)

            parent = registry.get_type_parent(type_name) or "-"

            # Count fields
            own_fields = registry.fields(type_name)
            all_fields = registry.all_fields(type_name)
            field_count = f"{len(own_fields)}/{len(all_fields)}"

            item = QTreeWidgetItem([type_name, backend_str, parent, field_count])
            item.setData(0, Qt.ItemDataRole.UserRole, type_name)
            self._types_tree.addTopLevelItem(item)

        for i in range(4):
            self._types_tree.resizeColumnToContents(i)

        self._status_label.setText(f"Types: {len(type_names)}")

    def _apply_filter(self, text: str) -> None:
        """Filter types by name."""
        text = text.lower()
        for i in range(self._types_tree.topLevelItemCount()):
            item = self._types_tree.topLevelItem(i)
            if item is None:
                continue
            type_name = item.text(0).lower()
            item.setHidden(text not in type_name)

    def _on_type_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Show type details."""
        type_name = item.data(0, Qt.ItemDataRole.UserRole)
        if type_name is None:
            return

        try:
            from termin._native.inspect import InspectRegistry
            registry = InspectRegistry.instance()
        except ImportError:
            return

        backend = registry.get_type_backend(type_name)
        backend_str = backend.name if hasattr(backend, 'name') else str(backend)
        parent = registry.get_type_parent(type_name) or "(none)"

        own_fields = registry.fields(type_name)
        all_fields = registry.all_fields(type_name)

        lines = [
            f"=== {type_name} ===",
            "",
            f"Backend:        {backend_str}",
            f"Parent:         {parent}",
            f"Own fields:     {len(own_fields)}",
            f"Total fields:   {len(all_fields)}",
            "",
            "--- Own Fields ---",
        ]

        if own_fields:
            for f in own_fields:
                lines.append(f"  {f.path}")
                lines.append(f"    label: {f.label}")
                lines.append(f"    kind:  {f.kind}")
                if f.min is not None or f.max is not None:
                    lines.append(f"    range: [{f.min}, {f.max}]")
                if f.step is not None:
                    lines.append(f"    step:  {f.step}")
                if f.choices:
                    choices_str = ", ".join(f"{c.value}={c.label}" for c in f.choices)
                    lines.append(f"    choices: {choices_str}")
                if not f.is_serializable:
                    lines.append(f"    is_serializable: False")
                if not f.is_inspectable:
                    lines.append(f"    is_inspectable: False")
                lines.append("")
        else:
            lines.append("  (none)")
            lines.append("")

        # Show inherited fields
        inherited = [f for f in all_fields if f not in own_fields]
        if inherited:
            lines.append("--- Inherited Fields ---")
            for f in inherited:
                lines.append(f"  {f.path} (kind: {f.kind})")
            lines.append("")

        self._details_text.setText("\n".join(lines))
