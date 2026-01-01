"""
Dialog for viewing internal state of core_c registries.

Shows meshes, scenes, and other resources stored in C hash tables.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QPushButton,
    QLabel,
    QWidget,
)
from PyQt6.QtCore import Qt

from termin.mesh._mesh_native import tc_mesh_get_all_info, tc_mesh_count
from termin._native.scene import tc_scene_registry_get_all_info, tc_scene_registry_count


class CoreRegistryViewer(QDialog):
    """
    Dialog for viewing internal core_c registry state.

    Shows:
    - tc_mesh registry (meshes stored in C hash table)
    - tc_scene registry (scenes and their entities)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Core Registry Viewer")
        self.setMinimumSize(900, 550)

        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        """Create dialog UI."""
        layout = QVBoxLayout(self)

        # Main splitter: tabs on left, details on right
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left side: tabs
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._tab_widget = QTabWidget()
        left_layout.addWidget(self._tab_widget)

        # Meshes tab
        self._meshes_tree = QTreeWidget()
        self._meshes_tree.setHeaderLabels(["Name", "Vertices", "Triangles", "Memory"])
        self._meshes_tree.setAlternatingRowColors(True)
        self._meshes_tree.itemClicked.connect(self._on_mesh_clicked)
        self._tab_widget.addTab(self._meshes_tree, "Meshes")

        # Scenes tab
        self._scenes_tree = QTreeWidget()
        self._scenes_tree.setHeaderLabels(["Name", "Entities", "Update", "Fixed"])
        self._scenes_tree.setAlternatingRowColors(True)
        self._scenes_tree.itemClicked.connect(self._on_scene_clicked)
        self._tab_widget.addTab(self._scenes_tree, "Scenes")

        splitter.addWidget(left_widget)

        # Right side: details panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        details_label = QLabel("Details")
        details_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(details_label)

        self._details_text = QTextEdit()
        self._details_text.setReadOnly(True)
        self._details_text.setFontFamily("monospace")
        right_layout.addWidget(self._details_text)

        splitter.addWidget(right_widget)

        # Set splitter proportions (60% left, 40% right)
        splitter.setSizes([540, 360])

        # Status bar
        self._status_label = QLabel()
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
        """Refresh all tabs."""
        self._refresh_meshes()
        self._refresh_scenes()
        self._update_status()
        self._details_text.clear()

    def _refresh_meshes(self) -> None:
        """Refresh mesh list from tc_mesh registry."""
        self._meshes_tree.clear()

        infos = tc_mesh_get_all_info()
        for info in sorted(infos, key=lambda x: x["name"] or x["uuid"]):
            name = info["name"] or "(unnamed)"
            vertices = str(info["vertex_count"])
            triangles = str(info["index_count"] // 3)
            memory = self._format_bytes(info["memory_bytes"])

            item = QTreeWidgetItem([name, vertices, triangles, memory])
            item.setData(0, Qt.ItemDataRole.UserRole, ("mesh", info))
            self._meshes_tree.addTopLevelItem(item)

        for i in range(4):
            self._meshes_tree.resizeColumnToContents(i)

    def _on_mesh_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Show mesh details in details panel."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None or data[0] != "mesh":
            return

        info = data[1]
        self._show_mesh_details(info)

    def _show_mesh_details(self, info: dict) -> None:
        """Display mesh details in the details panel."""
        lines = [
            "=== MESH ===",
            "",
            f"Name:           {info['name'] or '(unnamed)'}",
            f"UUID:           {info['uuid']}",
            "",
            "--- Geometry ---",
            f"Vertices:       {info['vertex_count']:,}",
            f"Indices:        {info['index_count']:,}",
            f"Triangles:      {info['index_count'] // 3:,}",
            f"Stride:         {info['stride']} bytes/vertex",
            "",
            "--- Memory ---",
            f"Vertex data:    {self._format_bytes(info['vertex_count'] * info['stride'])}",
            f"Index data:     {self._format_bytes(info['index_count'] * 4)}",
            f"Total:          {self._format_bytes(info['memory_bytes'])}",
            "",
            "--- State ---",
            f"Ref count:      {info['ref_count']}",
            f"Version:        {info['version']}",
        ]
        self._details_text.setText("\n".join(lines))

    def _refresh_scenes(self) -> None:
        """Refresh scene list from tc_scene registry."""
        self._scenes_tree.clear()

        infos = tc_scene_registry_get_all_info()
        for info in sorted(infos, key=lambda x: x["id"]):
            name = info["name"] or f"Scene #{info['id']}"
            entities = str(info["entity_count"])
            update = str(info["update_count"])
            fixed = str(info["fixed_update_count"])

            item = QTreeWidgetItem([name, entities, update, fixed])
            item.setData(0, Qt.ItemDataRole.UserRole, ("scene", info))
            self._scenes_tree.addTopLevelItem(item)

        for i in range(4):
            self._scenes_tree.resizeColumnToContents(i)

    def _on_scene_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Show scene details in details panel."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None or data[0] != "scene":
            return

        info = data[1]
        self._show_scene_details(info)

    def _show_scene_details(self, info: dict) -> None:
        """Display scene details in the details panel."""
        lines = [
            "=== SCENE ===",
            "",
            f"ID:             {info['id']}",
            f"Name:           {info['name'] or '(unnamed)'}",
            "",
            "--- Entities ---",
            f"Total:          {info['entity_count']}",
            "",
            "--- Component Scheduler ---",
            f"Pending start:  {info['pending_count']}",
            f"Update list:    {info['update_count']}",
            f"Fixed update:   {info['fixed_update_count']}",
        ]
        self._details_text.setText("\n".join(lines))

    def _format_bytes(self, size: int) -> str:
        """Format size in human-readable form."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.2f} MB"

    def _update_status(self) -> None:
        """Update status bar."""
        mesh_count = tc_mesh_count()
        scene_count = tc_scene_registry_count()

        infos = tc_mesh_get_all_info()
        total_memory = sum(info["memory_bytes"] for info in infos)

        self._status_label.setText(
            f"Meshes: {mesh_count} | "
            f"Scenes: {scene_count} | "
            f"Mesh Memory: {self._format_bytes(total_memory)}"
        )
