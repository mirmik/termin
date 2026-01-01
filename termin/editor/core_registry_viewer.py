"""
Dialog for viewing internal state of core_c registries.

Shows meshes, scenes, and other resources stored in C hash tables.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QLabel,
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
        self.setMinimumSize(700, 450)

        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        """Create dialog UI."""
        layout = QVBoxLayout(self)

        # Tabs for different registries
        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget)

        # Meshes tab
        self._meshes_tree = QTreeWidget()
        self._meshes_tree.setHeaderLabels(["UUID", "Name", "Vertices", "Indices", "Refs", "Memory"])
        self._meshes_tree.setAlternatingRowColors(True)
        self._meshes_tree.itemClicked.connect(self._on_mesh_clicked)
        self._tab_widget.addTab(self._meshes_tree, "Meshes")

        # Scenes tab
        self._scenes_tree = QTreeWidget()
        self._scenes_tree.setHeaderLabels(["ID", "Name", "Entities", "Pending", "Update", "Fixed Update"])
        self._scenes_tree.setAlternatingRowColors(True)
        self._scenes_tree.itemClicked.connect(self._on_scene_clicked)
        self._tab_widget.addTab(self._scenes_tree, "Scenes")

        # Status
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

    def _refresh_meshes(self) -> None:
        """Refresh mesh list from tc_mesh registry."""
        self._meshes_tree.clear()

        infos = tc_mesh_get_all_info()
        for info in sorted(infos, key=lambda x: x["name"] or x["uuid"]):
            uuid = info["uuid"]
            name = info["name"] or "(unnamed)"
            vertices = str(info["vertex_count"])
            indices = str(info["index_count"])
            refs = str(info["ref_count"])
            memory = self._format_bytes(info["memory_bytes"])

            item = QTreeWidgetItem([uuid, name, vertices, indices, refs, memory])
            item.setData(0, Qt.ItemDataRole.UserRole, info)
            self._meshes_tree.addTopLevelItem(item)

        for i in range(6):
            self._meshes_tree.resizeColumnToContents(i)

    def _on_mesh_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Show mesh details on click."""
        info = item.data(0, Qt.ItemDataRole.UserRole)
        if info is None:
            return

        # Remove old children
        while item.childCount() > 0:
            item.takeChild(0)

        # If already expanded, just collapse
        if item.isExpanded():
            item.setExpanded(False)
            return

        # Add detailed info
        details = [
            ("UUID", info["uuid"]),
            ("Name", info["name"] or "(unnamed)"),
            ("Vertex Count", str(info["vertex_count"])),
            ("Index Count", str(info["index_count"])),
            ("Triangle Count", str(info["index_count"] // 3)),
            ("Stride", f"{info['stride']} bytes"),
            ("Memory", self._format_bytes(info["memory_bytes"])),
            ("Ref Count", str(info["ref_count"])),
            ("Version", str(info["version"])),
        ]

        for label, value in details:
            child = QTreeWidgetItem([label, value, "", "", "", ""])
            item.addChild(child)

        item.setExpanded(True)

    def _refresh_scenes(self) -> None:
        """Refresh scene list from tc_scene registry."""
        self._scenes_tree.clear()

        infos = tc_scene_registry_get_all_info()
        for info in sorted(infos, key=lambda x: x["id"]):
            scene_id = str(info["id"])
            name = info["name"] or "(unnamed)"
            entities = str(info["entity_count"])
            pending = str(info["pending_count"])
            update = str(info["update_count"])
            fixed_update = str(info["fixed_update_count"])

            item = QTreeWidgetItem([scene_id, name, entities, pending, update, fixed_update])
            item.setData(0, Qt.ItemDataRole.UserRole, info)
            self._scenes_tree.addTopLevelItem(item)

        for i in range(6):
            self._scenes_tree.resizeColumnToContents(i)

    def _on_scene_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Show scene details on click."""
        info = item.data(0, Qt.ItemDataRole.UserRole)
        if info is None:
            return

        # Remove old children
        while item.childCount() > 0:
            item.takeChild(0)

        # If already expanded, just collapse
        if item.isExpanded():
            item.setExpanded(False)
            return

        # Add detailed info
        details = [
            ("ID", str(info["id"])),
            ("Name", info["name"] or "(unnamed)"),
            ("Entity Count", str(info["entity_count"])),
            ("Pending Start", str(info["pending_count"])),
            ("Update List", str(info["update_count"])),
            ("Fixed Update List", str(info["fixed_update_count"])),
        ]

        for label, value in details:
            child = QTreeWidgetItem([label, value, "", "", "", ""])
            item.addChild(child)

        item.setExpanded(True)

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

        # Calculate total memory
        infos = tc_mesh_get_all_info()
        total_memory = sum(info["memory_bytes"] for info in infos)

        self._status_label.setText(
            f"Meshes: {mesh_count} | "
            f"Scenes: {scene_count} | "
            f"Mesh Memory: {self._format_bytes(total_memory)}"
        )
