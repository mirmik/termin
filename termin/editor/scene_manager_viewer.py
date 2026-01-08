"""
Scene Manager debug viewer.

Shows all scenes managed by SceneManager, their modes, and entity counts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QLabel,
    QTextEdit,
    QSplitter,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush

if TYPE_CHECKING:
    from termin.editor.scene_manager import SceneManager


class SceneManagerViewer(QWidget):
    """
    Window for viewing SceneManager state.

    Shows:
    - All scenes by name
    - Scene mode (INACTIVE, EDITOR, GAME)
    - Entity count
    - File path
    - Active scene indicator
    """

    def __init__(self, scene_manager: "SceneManager", parent=None):
        super().__init__(parent)
        self._scene_manager = scene_manager
        self._selected_scene_name: str | None = None

        self.setWindowTitle("Scene Manager")
        self.setMinimumSize(600, 400)

        # Make it a standalone window
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        """Create UI."""
        layout = QVBoxLayout(self)

        # Splitter: left - scene list, right - details
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # Left panel - scene list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        scenes_label = QLabel("Scenes")
        scenes_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(scenes_label)

        self._scenes_tree = QTreeWidget()
        self._scenes_tree.setHeaderLabels(["Name", "Mode", "Entities"])
        self._scenes_tree.setAlternatingRowColors(True)
        self._scenes_tree.itemClicked.connect(self._on_scene_clicked)
        left_layout.addWidget(self._scenes_tree)

        splitter.addWidget(left_widget)

        # Right panel - details
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        details_label = QLabel("Scene Details")
        details_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(details_label)

        self._details_text = QTextEdit()
        self._details_text.setReadOnly(True)
        self._details_text.setPlaceholderText("Select a scene to view details")
        right_layout.addWidget(self._details_text)

        splitter.addWidget(right_widget)
        splitter.setSizes([300, 300])

        # Status bar
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

    def _on_scene_clicked(self, item: QTreeWidgetItem) -> None:
        """Handle scene item click."""
        # Get slot name from UserRole data
        scene_name = item.data(0, Qt.ItemDataRole.UserRole)
        if scene_name is None:
            scene_name = item.text(0)  # Fallback
        self._selected_scene_name = scene_name
        self._update_details(scene_name)

    def _update_details(self, scene_name: str) -> None:
        """Update details panel for selected scene."""
        scene = self._scene_manager.get_scene(scene_name)
        if scene is None:
            self._details_text.setText(f"Scene '{scene_name}' not found")
            return

        mode = self._scene_manager.get_mode(scene_name)
        path = self._scene_manager.get_scene_path(scene_name)

        lines = [
            f"Name: {scene_name}",
            f"Mode: {mode.name}",
            f"Path: {path or '(unsaved)'}",
            f"",
            f"=== Entities ===",
        ]

        # List entities
        entity_count = 0
        root_entities = []
        for entity in scene.entities:
            entity_count += 1
            if entity.transform.parent is None:
                root_entities.append(entity)

        lines.append(f"Total: {entity_count}")
        lines.append(f"Root entities: {len(root_entities)}")
        lines.append(f"")

        # List root entities
        for entity in root_entities[:20]:  # Limit to 20
            serializable = "S" if entity.serializable else "-"
            enabled = "E" if entity.enabled else "-"
            lines.append(f"  [{serializable}{enabled}] {entity.name}")

        if len(root_entities) > 20:
            lines.append(f"  ... and {len(root_entities) - 20} more")

        self._details_text.setText("\n".join(lines))

    def refresh(self) -> None:
        """Refresh scene list."""
        self._scenes_tree.clear()

        debug_info = self._scene_manager.get_debug_info()

        # Color brushes for different modes
        mode_colors = {
            "INACTIVE": QBrush(QColor(128, 128, 128)),  # Gray
            "EDITOR": QBrush(QColor(70, 130, 180)),     # Steel blue
            "GAME": QBrush(QColor(50, 205, 50)),        # Lime green
        }

        for name, info in sorted(debug_info.items()):
            mode = info["mode"]
            entity_count = info["entity_count"]
            path = info.get("path")

            # Show file name if available, otherwise slot name
            if path:
                import os
                display_name = os.path.splitext(os.path.basename(path))[0]
                display_name = f"{display_name} [{name}]"
            else:
                display_name = f"{name} (unsaved)"

            item = QTreeWidgetItem([
                display_name,
                mode,
                str(entity_count),
            ])
            # Store slot name for click handler
            item.setData(0, Qt.ItemDataRole.UserRole, name)

            # Color by mode
            if mode in mode_colors:
                item.setForeground(1, mode_colors[mode])

            self._scenes_tree.addTopLevelItem(item)

        # Resize columns
        for i in range(3):
            self._scenes_tree.resizeColumnToContents(i)

        # Update details if scene selected
        if self._selected_scene_name:
            self._update_details(self._selected_scene_name)

        # Update status
        total_scenes = len(debug_info)
        total_entities = sum(info["entity_count"] for info in debug_info.values())
        game_scenes = sum(1 for info in debug_info.values() if info["mode"] == "GAME")
        self._status_label.setText(
            f"Scenes: {total_scenes} | "
            f"Total entities: {total_entities} | "
            f"Game scenes: {game_scenes}"
        )

