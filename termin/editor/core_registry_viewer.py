"""
Dialog for viewing internal state of core_c registries.

Shows meshes, scenes, entities and other resources stored in C hash tables.
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
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QPushButton,
    QLabel,
    QWidget,
)
from PyQt6.QtCore import Qt

from termin.mesh._mesh_native import tc_mesh_get_all_info, tc_mesh_count
from termin._native.scene import (
    tc_scene_registry_get_all_info,
    tc_scene_registry_count,
    tc_scene_get_entities,
)


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
        self.setMinimumSize(1000, 600)

        self._selected_scene_id: int | None = None

        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        """Create dialog UI."""
        layout = QVBoxLayout(self)

        # Main splitter: content on left, details on right
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(main_splitter)

        # Left side: tabs
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._tab_widget = QTabWidget()
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        left_layout.addWidget(self._tab_widget)

        # Meshes tab
        self._meshes_tree = QTreeWidget()
        self._meshes_tree.setHeaderLabels(["Name", "Vertices", "Triangles", "Memory"])
        self._meshes_tree.setAlternatingRowColors(True)
        self._meshes_tree.itemClicked.connect(self._on_mesh_clicked)
        self._tab_widget.addTab(self._meshes_tree, "Meshes")

        # Scenes tab - with splitter for scenes and entities lists
        scenes_widget = QWidget()
        scenes_layout = QHBoxLayout(scenes_widget)
        scenes_layout.setContentsMargins(0, 0, 0, 0)

        # Scenes list
        scenes_left = QWidget()
        scenes_left_layout = QVBoxLayout(scenes_left)
        scenes_left_layout.setContentsMargins(0, 0, 0, 0)
        scenes_left_layout.addWidget(QLabel("Scenes"))

        self._scenes_list = QListWidget()
        self._scenes_list.setAlternatingRowColors(True)
        self._scenes_list.itemClicked.connect(self._on_scene_clicked)
        scenes_left_layout.addWidget(self._scenes_list)

        # Entities list
        entities_right = QWidget()
        entities_right_layout = QVBoxLayout(entities_right)
        entities_right_layout.setContentsMargins(0, 0, 0, 0)
        self._entities_label = QLabel("Entities")
        entities_right_layout.addWidget(self._entities_label)

        self._entities_list = QListWidget()
        self._entities_list.setAlternatingRowColors(True)
        self._entities_list.itemClicked.connect(self._on_entity_clicked)
        entities_right_layout.addWidget(self._entities_list)

        scenes_splitter = QSplitter(Qt.Orientation.Horizontal)
        scenes_splitter.addWidget(scenes_left)
        scenes_splitter.addWidget(entities_right)
        scenes_splitter.setSizes([200, 300])

        scenes_layout.addWidget(scenes_splitter)
        self._tab_widget.addTab(scenes_widget, "Scenes")

        main_splitter.addWidget(left_widget)

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

        main_splitter.addWidget(right_widget)

        # Set splitter proportions (60% left, 40% right)
        main_splitter.setSizes([600, 400])

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

    def _on_tab_changed(self, index: int) -> None:
        """Clear details when switching tabs."""
        self._details_text.clear()

    def refresh(self) -> None:
        """Refresh all tabs."""
        self._refresh_meshes()
        self._refresh_scenes()
        self._update_status()
        self._details_text.clear()
        self._entities_list.clear()
        self._selected_scene_id = None
        self._entities_label.setText("Entities")

    # =========================================================================
    # Meshes
    # =========================================================================

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

    # =========================================================================
    # Scenes
    # =========================================================================

    def _refresh_scenes(self) -> None:
        """Refresh scene list from tc_scene registry."""
        self._scenes_list.clear()

        infos = tc_scene_registry_get_all_info()
        for info in sorted(infos, key=lambda x: x["id"]):
            name = info["name"] or f"Scene #{info['id']}"
            text = f"{name} ({info['entity_count']} entities)"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, info)
            self._scenes_list.addItem(item)

    def _on_scene_clicked(self, item: QListWidgetItem) -> None:
        """Show scene details and load entities."""
        info = item.data(Qt.ItemDataRole.UserRole)
        if info is None:
            return

        self._selected_scene_id = info["id"]
        self._show_scene_details(info)
        self._load_entities(info["id"])

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

    def _load_entities(self, scene_id: int) -> None:
        """Load entities for the selected scene."""
        self._entities_list.clear()

        entities = tc_scene_get_entities(scene_id)
        self._entities_label.setText(f"Entities ({len(entities)})")

        for entity in sorted(entities, key=lambda x: x["name"] or x["uuid"]):
            name = entity["name"] or "(unnamed)"
            comp_count = entity["component_count"]

            # Add status indicators
            status = ""
            if not entity["active"]:
                status += " [inactive]"
            if not entity["visible"]:
                status += " [hidden]"

            text = f"{name} ({comp_count} comp){status}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entity)
            self._entities_list.addItem(item)

    def _on_entity_clicked(self, item: QListWidgetItem) -> None:
        """Show entity details in details panel."""
        info = item.data(Qt.ItemDataRole.UserRole)
        if info is None:
            return

        self._show_entity_details(info)

    def _show_entity_details(self, info: dict) -> None:
        """Display entity details in the details panel."""
        lines = [
            "=== ENTITY ===",
            "",
            f"Name:           {info['name'] or '(unnamed)'}",
            f"UUID:           {info['uuid']}",
            "",
            "--- State ---",
            f"Active:         {info['active']}",
            f"Visible:        {info['visible']}",
            "",
            "--- Components ---",
            f"Count:          {info['component_count']}",
        ]
        self._details_text.setText("\n".join(lines))

    # =========================================================================
    # Utils
    # =========================================================================

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
