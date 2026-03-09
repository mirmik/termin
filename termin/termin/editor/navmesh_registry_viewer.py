"""
Dialog for viewing NavMeshRegistry state.

Shows registered NavMesh for each agent type and scene.
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
)
from PyQt6.QtCore import Qt


class NavMeshRegistryViewer(QDialog):
    """
    Dialog for viewing NavMeshRegistry state.

    Shows:
    - Registered agent types
    - NavMesh sources for each agent type
    - NavMesh details (polygon count, vertices, etc.)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("NavMesh Registry Viewer")
        self.setMinimumSize(800, 500)

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

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # Left: tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Agent Type / Source", "Polygons", "Triangles", "Vertices"])
        self._tree.setAlternatingRowColors(True)
        self._tree.itemClicked.connect(self._on_item_clicked)
        splitter.addWidget(self._tree)

        # Right: details
        details_widget = QLabel()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)

        details_label = QLabel("Details")
        details_label.setStyleSheet("font-weight: bold;")
        details_layout.addWidget(details_label)

        self._details_text = QTextEdit()
        self._details_text.setReadOnly(True)
        self._details_text.setFontFamily("monospace")
        details_layout.addWidget(self._details_text)

        splitter.addWidget(details_widget)
        splitter.setSizes([400, 400])

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
        """Refresh data from all NavMeshRegistry instances."""
        self._tree.clear()
        self._details_text.clear()

        from termin.navmesh.registry import NavMeshRegistry

        total_scenes = 0
        total_meshes = 0
        total_polygons = 0
        total_agent_types = 0

        # Iterate over all scene registries
        for scene_uuid, registry in NavMeshRegistry._instances.items():
            agent_types = registry.list_agent_types()
            if not agent_types:
                continue

            total_scenes += 1

            # Scene item
            scene_item = QTreeWidgetItem([f"Scene: {scene_uuid[:8]}...", "", "", ""])
            scene_item.setData(0, Qt.ItemDataRole.UserRole, ("scene", scene_uuid))
            self._tree.addTopLevelItem(scene_item)

            for agent_type in sorted(agent_types):
                entries = registry.get_all(agent_type)
                if not entries:
                    continue

                total_agent_types += 1

                # Agent type item
                agent_polygons = sum(nm.polygon_count() for nm, _ in entries)
                agent_tris = sum(nm.triangle_count() for nm, _ in entries)
                agent_verts = sum(nm.vertex_count() for nm, _ in entries)

                agent_item = QTreeWidgetItem([
                    agent_type,
                    str(agent_polygons),
                    str(agent_tris),
                    str(agent_verts),
                ])
                agent_item.setData(0, Qt.ItemDataRole.UserRole, ("agent_type", agent_type, entries))
                scene_item.addChild(agent_item)

                # Source items
                for navmesh, entity in entries:
                    source_name = entity.name if entity else "(no entity)"
                    source_uuid = entity.uuid if entity else "?"

                    source_item = QTreeWidgetItem([
                        f"  {source_name}",
                        str(navmesh.polygon_count()),
                        str(navmesh.triangle_count()),
                        str(navmesh.vertex_count()),
                    ])
                    source_item.setData(0, Qt.ItemDataRole.UserRole, ("navmesh", navmesh, entity, source_uuid))
                    agent_item.addChild(source_item)

                    total_meshes += 1
                    total_polygons += navmesh.polygon_count()

                agent_item.setExpanded(True)

            scene_item.setExpanded(True)

        for i in range(4):
            self._tree.resizeColumnToContents(i)

        if total_scenes == 0:
            self._status_label.setText("No NavMesh registered")
        else:
            self._status_label.setText(
                f"Scenes: {total_scenes} | "
                f"Agent types: {total_agent_types} | "
                f"NavMesh: {total_meshes} | "
                f"Polygons: {total_polygons}"
            )

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Show details for selected item."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return

        if data[0] == "agent_type":
            self._show_agent_type_details(data[1], data[2])
        elif data[0] == "navmesh":
            self._show_navmesh_details(data[1], data[2], data[3])

    def _show_agent_type_details(self, agent_type: str, entries: list) -> None:
        """Show details for an agent type."""
        total_polygons = sum(nm.polygon_count() for nm, _ in entries)
        total_tris = sum(nm.triangle_count() for nm, _ in entries)
        total_verts = sum(nm.vertex_count() for nm, _ in entries)

        lines = [
            f"=== AGENT TYPE: {agent_type} ===",
            "",
            f"Sources:        {len(entries)}",
            f"Total polygons: {total_polygons}",
            f"Total tris:     {total_tris}",
            f"Total vertices: {total_verts}",
            "",
            "--- Sources ---",
        ]

        for navmesh, entity in entries:
            name = entity.name if entity else "(no entity)"
            uuid = entity.uuid if entity else "?"
            lines.append(f"  {name} ({navmesh.polygon_count()} polys) - {uuid}")

        self._details_text.setText("\n".join(lines))

    def _show_navmesh_details(self, navmesh, entity, source_uuid: str) -> None:
        """Show details for a specific NavMesh."""
        entity_name = entity.name if entity else "(no entity)"

        lines = [
            "=== NAVMESH ===",
            "",
            f"Name:           {navmesh.name}",
            f"Source entity:  {entity_name}",
            f"Source UUID:    {source_uuid}",
            "",
            "--- Geometry ---",
            f"Polygons:       {navmesh.polygon_count()}",
            f"Triangles:      {navmesh.triangle_count()}",
            f"Vertices:       {navmesh.vertex_count()}",
            f"Cell size:      {navmesh.cell_size}",
            f"Origin:         ({navmesh.origin[0]:.2f}, {navmesh.origin[1]:.2f}, {navmesh.origin[2]:.2f})",
            "",
            "--- Polygons ---",
        ]

        for i, poly in enumerate(navmesh.polygons[:20]):  # Limit to 20
            verts = len(poly.vertices) if poly.vertices is not None else 0
            tris = len(poly.triangles) if poly.triangles is not None else 0
            neighbors = len(poly.neighbors)
            lines.append(f"  [{i}] {verts} verts, {tris} tris, {neighbors} neighbors")

        if navmesh.polygon_count() > 20:
            lines.append(f"  ... and {navmesh.polygon_count() - 20} more")

        self._details_text.setText("\n".join(lines))
