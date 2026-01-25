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
from termin.texture._texture_native import tc_texture_get_all_info, tc_texture_count
from termin._native.scene import (
    tc_scene_registry_get_all_info,
    tc_scene_registry_count,
    tc_scene_get_entities,
    tc_scene_get_component_types,
)
from termin._native.render import (
    shader_get_all_info,
    shader_count,
    TcShader,
    tc_material_get_all_info,
    tc_material_count,
    TcMaterial,
    tc_pipeline_registry_count,
    tc_pipeline_registry_get_all_info,
    tc_pass_registry_get_all_instance_info,
    tc_pass_registry_get_all_types,
)
from termin.entity._entity_native import (
    component_registry_get_all_info,
    component_registry_type_count,
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

        # Enable maximize button
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        self._selected_scene_id: int | None = None

        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        """Create dialog UI."""
        layout = QVBoxLayout(self)

        # Main splitter: content on left, details on right
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(main_splitter, stretch=1)

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

        # Textures tab
        self._textures_tree = QTreeWidget()
        self._textures_tree.setHeaderLabels(["Name", "Size", "Channels", "Memory"])
        self._textures_tree.setAlternatingRowColors(True)
        self._textures_tree.itemClicked.connect(self._on_texture_clicked)
        self._tab_widget.addTab(self._textures_tree, "Textures")

        # Shaders tab
        self._shaders_tree = QTreeWidget()
        self._shaders_tree.setHeaderLabels(["Name", "Type", "Version", "Size"])
        self._shaders_tree.setAlternatingRowColors(True)
        self._shaders_tree.itemClicked.connect(self._on_shader_clicked)
        self._tab_widget.addTab(self._shaders_tree, "Shaders")

        # Materials tab
        self._materials_tree = QTreeWidget()
        self._materials_tree.setHeaderLabels(["Name", "Phases", "Textures", "Version"])
        self._materials_tree.setAlternatingRowColors(True)
        self._materials_tree.itemClicked.connect(self._on_material_clicked)
        self._tab_widget.addTab(self._materials_tree, "Materials")

        # Components tab
        self._components_tree = QTreeWidget()
        self._components_tree.setHeaderLabels(["Name", "Language", "Drawable", "Parent", "Descendants"])
        self._components_tree.setAlternatingRowColors(True)
        self._components_tree.itemClicked.connect(self._on_component_clicked)
        self._tab_widget.addTab(self._components_tree, "Components")

        # Pipelines tab
        self._pipelines_tree = QTreeWidget()
        self._pipelines_tree.setHeaderLabels(["Name", "Pass Count"])
        self._pipelines_tree.setAlternatingRowColors(True)
        self._pipelines_tree.itemClicked.connect(self._on_pipeline_clicked)
        self._tab_widget.addTab(self._pipelines_tree, "Pipelines")

        # Passes tab (shows registered pass types, like Components)
        self._passes_tree = QTreeWidget()
        self._passes_tree.setHeaderLabels(["Type Name", "Language"])
        self._passes_tree.setAlternatingRowColors(True)
        self._passes_tree.itemClicked.connect(self._on_pass_clicked)
        self._tab_widget.addTab(self._passes_tree, "Passes")

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

        # Set splitter proportions (55% left, 45% right)
        main_splitter.setSizes([550, 450])

        # Status bar (single line, fixed height)
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

        # Connect tab signal after all widgets exist
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int) -> None:
        """Clear details when switching tabs."""
        self._details_text.clear()

    def refresh(self) -> None:
        """Refresh all tabs."""
        self._refresh_meshes()
        self._refresh_textures()
        self._refresh_shaders()
        self._refresh_materials()
        self._refresh_components()
        self._refresh_pipelines()
        self._refresh_passes()
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
    # Textures
    # =========================================================================

    def _refresh_textures(self) -> None:
        """Refresh texture list from tc_texture registry."""
        self._textures_tree.clear()

        infos = tc_texture_get_all_info()
        for info in sorted(infos, key=lambda x: x["name"] or x["uuid"]):
            name = info["name"] or "(unnamed)"
            size = f"{info['width']}x{info['height']}"
            channels = str(info["channels"])
            memory = self._format_bytes(info["memory_bytes"])

            item = QTreeWidgetItem([name, size, channels, memory])
            item.setData(0, Qt.ItemDataRole.UserRole, ("texture", info))
            self._textures_tree.addTopLevelItem(item)

        for i in range(4):
            self._textures_tree.resizeColumnToContents(i)

    def _on_texture_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Show texture details in details panel."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None or data[0] != "texture":
            return

        info = data[1]
        self._show_texture_details(info)

    def _show_texture_details(self, info: dict) -> None:
        """Display texture details in the details panel."""
        lines = [
            "=== TEXTURE ===",
            "",
            f"Name:           {info['name'] or '(unnamed)'}",
            f"UUID:           {info['uuid']}",
            f"Source:         {info['source_path'] or '(none)'}",
            "",
            "--- Dimensions ---",
            f"Width:          {info['width']}",
            f"Height:         {info['height']}",
            f"Channels:       {info['channels']}",
            f"Format:         {info['format']}",
            "",
            "--- Memory ---",
            f"Size:           {self._format_bytes(info['memory_bytes'])}",
            "",
            "--- State ---",
            f"Ref count:      {info['ref_count']}",
            f"Version:        {info['version']}",
        ]
        self._details_text.setText("\n".join(lines))

    # =========================================================================
    # Shaders
    # =========================================================================

    def _refresh_shaders(self) -> None:
        """Refresh shader list from tc_shader registry."""
        self._shaders_tree.clear()

        infos = shader_get_all_info()
        for info in sorted(infos, key=lambda x: x["name"] or x["uuid"]):
            name = info["name"] or "(unnamed)"

            # Determine type
            if info["is_variant"]:
                variant_ops = ["none", "skinning", "instancing", "morphing"]
                op = info["variant_op"]
                shader_type = f"variant ({variant_ops[op] if op < len(variant_ops) else op})"
            elif info["has_geometry"]:
                shader_type = "geometry"
            else:
                shader_type = "standard"

            version = str(info["version"])
            size = self._format_bytes(info["source_size"])

            item = QTreeWidgetItem([name, shader_type, version, size])
            item.setData(0, Qt.ItemDataRole.UserRole, ("shader", info))
            self._shaders_tree.addTopLevelItem(item)

        for i in range(4):
            self._shaders_tree.resizeColumnToContents(i)

    def _format_shader_features(self, features: int) -> str:
        """Format shader features bitfield as readable string."""
        if features == 0:
            return "(none)"
        parts = []
        if features & 1:  # TC_SHADER_FEATURE_LIGHTING_UBO
            parts.append("LIGHTING_UBO")
        return ", ".join(parts) if parts else f"0x{features:x}"

    def _on_shader_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Show shader details in details panel."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None or data[0] != "shader":
            return

        info = data[1]
        self._show_shader_details(info)

    def _show_shader_details(self, info: dict) -> None:
        """Display shader details in the details panel."""
        variant_ops = ["NONE", "SKINNING", "INSTANCING", "MORPHING"]

        lines = [
            "=== SHADER ===",
            "",
            f"Name:           {info['name'] or '(unnamed)'}",
            f"UUID:           {info['uuid']}",
            f"Source path:    {info['source_path'] or '(inline)'}",
            f"Source hash:    {info['source_hash']}",
            "",
            "--- Type ---",
        ]

        if info["is_variant"]:
            op = info["variant_op"]
            op_name = variant_ops[op] if op < len(variant_ops) else str(op)
            lines.append(f"Is variant:     Yes ({op_name})")
        else:
            lines.append(f"Is variant:     No")

        lines.append(f"Has geometry:   {'Yes' if info['has_geometry'] else 'No'}")

        features = info.get("features", 0)
        features_str = self._format_shader_features(features)

        lines.extend([
            "",
            "--- Features ---",
            f"Features:       {features_str} (raw: {features})",
            "",
            "--- Memory ---",
            f"Source size:    {self._format_bytes(info['source_size'])}",
            "",
            "--- State ---",
            f"Ref count:      {info['ref_count']}",
            f"Version:        {info['version']}",
        ])

        # Get full shader sources
        shader = TcShader.from_uuid(info["uuid"])
        if shader.is_valid:
            lines.extend([
                "",
                "=" * 60,
                "VERTEX SHADER",
                "=" * 60,
                shader.vertex_source or "(empty)",
                "",
                "=" * 60,
                "FRAGMENT SHADER",
                "=" * 60,
                shader.fragment_source or "(empty)",
            ])

            if shader.has_geometry:
                lines.extend([
                    "",
                    "=" * 60,
                    "GEOMETRY SHADER",
                    "=" * 60,
                    shader.geometry_source or "(empty)",
                ])

        self._details_text.setText("\n".join(lines))

    # =========================================================================
    # Materials
    # =========================================================================

    def _refresh_materials(self) -> None:
        """Refresh material list from tc_material registry."""
        self._materials_tree.clear()

        infos = tc_material_get_all_info()
        for info in sorted(infos, key=lambda x: x["name"] or x["uuid"]):
            name = info["name"] or "(unnamed)"
            phases = str(info["phase_count"])
            textures = str(info["texture_count"])
            version = str(info["version"])

            item = QTreeWidgetItem([name, phases, textures, version])
            item.setData(0, Qt.ItemDataRole.UserRole, ("material", info))
            self._materials_tree.addTopLevelItem(item)

        for i in range(4):
            self._materials_tree.resizeColumnToContents(i)

    def _on_material_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Show material details in details panel."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None or data[0] != "material":
            return

        info = data[1]
        self._show_material_details(info)

    def _show_material_details(self, info: dict) -> None:
        """Display material details in the details panel."""
        lines = [
            "=== MATERIAL ===",
            "",
            f"Name:           {info['name'] or '(unnamed)'}",
            f"UUID:           {info['uuid']}",
            "",
            "--- Phases ---",
            f"Count:          {info['phase_count']}",
            "",
            "--- Textures ---",
            f"Count:          {info['texture_count']}",
            "",
            "--- State ---",
            f"Ref count:      {info['ref_count']}",
            f"Version:        {info['version']}",
        ]

        # Get more details from the material itself
        mat = TcMaterial.from_uuid(info["uuid"])
        if mat.is_valid:
            lines.extend([
                "",
                "--- Properties ---",
                f"Shader name:    {mat.shader_name or '(none)'}",
                f"Active mark:    {mat.active_phase_mark or '(none)'}",
            ])

            color = mat.color
            if color is not None:
                lines.append(f"Color:          ({color.x:.2f}, {color.y:.2f}, {color.z:.2f}, {color.w:.2f})")

        self._details_text.setText("\n".join(lines))

    # =========================================================================
    # Components
    # =========================================================================

    def _refresh_components(self) -> None:
        """Refresh component types from registry."""
        self._components_tree.clear()

        infos = component_registry_get_all_info()
        for info in sorted(infos, key=lambda x: x["name"]):
            name = info["name"]
            language = info["language"]
            is_drawable = "Yes" if info.get("is_drawable", False) else "-"
            parent = info["parent"] or "-"
            desc_count = len(info["descendants"])
            descendants = str(desc_count) if desc_count > 0 else "-"

            item = QTreeWidgetItem([name, language, is_drawable, parent, descendants])
            item.setData(0, Qt.ItemDataRole.UserRole, ("component", info))
            self._components_tree.addTopLevelItem(item)

        for i in range(5):
            self._components_tree.resizeColumnToContents(i)

    def _on_component_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Show component details in details panel."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None or data[0] != "component":
            return

        info = data[1]
        self._show_component_details(info)

    def _show_component_details(self, info: dict) -> None:
        """Display component type details in the details panel."""
        is_drawable = info.get("is_drawable", False)
        language = info["language"]
        lines = [
            "=== COMPONENT TYPE ===",
            "",
            f"Name:           {info['name']}",
            f"Language:       {language}",
            f"Drawable:       {'Yes' if is_drawable else 'No'}",
            f"Parent:         {info['parent'] or '(none)'}",
            "",
            "--- Descendants ---",
        ]

        descendants = info["descendants"]
        if descendants:
            for desc in descendants:
                lines.append(f"  - {desc}")
        else:
            lines.append("  (none)")

        self._details_text.setText("\n".join(lines))

    # =========================================================================
    # Pipelines
    # =========================================================================

    def _refresh_pipelines(self) -> None:
        """Refresh pipeline list from tc_pipeline registry."""
        self._pipelines_tree.clear()

        infos = tc_pipeline_registry_get_all_info()
        # Group by name to detect duplicates
        name_counts: dict[str, int] = {}
        for info in infos:
            name = info["name"] or "(unnamed)"
            name_counts[name] = name_counts.get(name, 0) + 1

        name_indices: dict[str, int] = {}
        for info in infos:
            name = info["name"] or "(unnamed)"
            # If multiple pipelines with same name, add index
            if name_counts[name] > 1:
                idx = name_indices.get(name, 0)
                name_indices[name] = idx + 1
                display_name = f"{name} #{idx + 1}"
            else:
                display_name = name
            pass_count = str(info["pass_count"])

            item = QTreeWidgetItem([display_name, pass_count])
            item.setData(0, Qt.ItemDataRole.UserRole, ("pipeline", info))
            self._pipelines_tree.addTopLevelItem(item)

        for i in range(2):
            self._pipelines_tree.resizeColumnToContents(i)

    def _on_pipeline_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Show pipeline details in details panel."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None or data[0] != "pipeline":
            return

        info = data[1]
        self._show_pipeline_details(info)

    def _show_pipeline_details(self, info: dict) -> None:
        """Display pipeline details in the details panel."""
        pipeline_ptr = info.get("ptr", 0)
        lines = [
            "=== PIPELINE ===",
            "",
            f"Name:           {info['name'] or '(unnamed)'}",
            f"Ptr:            0x{pipeline_ptr:x}",
            f"Pass count:     {info['pass_count']}",
        ]

        # Get passes for this pipeline (filter by ptr, not name)
        all_passes = tc_pass_registry_get_all_instance_info()
        pipeline_passes = [p for p in all_passes if p.get("pipeline_ptr") == pipeline_ptr]

        if pipeline_passes:
            lines.extend([
                "",
                "--- Passes ---",
            ])
            for i, p in enumerate(pipeline_passes):
                enabled = "+" if p["enabled"] else "-"
                lines.append(f"  {i}: [{enabled}] {p['pass_name']} ({p['type_name']})")

        self._details_text.setText("\n".join(lines))

    # =========================================================================
    # Passes
    # =========================================================================

    def _refresh_passes(self) -> None:
        """Refresh pass types from registry."""
        self._passes_tree.clear()

        infos = tc_pass_registry_get_all_types()
        for info in sorted(infos, key=lambda x: x["type_name"]):
            type_name = info["type_name"]
            language = info["language"]

            item = QTreeWidgetItem([type_name, language])
            item.setData(0, Qt.ItemDataRole.UserRole, ("pass_type", info))
            self._passes_tree.addTopLevelItem(item)

        for i in range(2):
            self._passes_tree.resizeColumnToContents(i)

    def _on_pass_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Show pass type details in details panel."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None or data[0] != "pass_type":
            return

        info = data[1]
        self._show_pass_details(info)

    def _show_pass_details(self, info: dict) -> None:
        """Display pass type details in the details panel."""
        lines = [
            "=== PASS TYPE ===",
            "",
            f"Type name:      {info['type_name']}",
            f"Language:       {info['language']}",
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

        # Get component type counts
        comp_types = tc_scene_get_component_types(info["id"])
        if comp_types:
            lines.extend([
                "",
                "--- Component Types ---",
            ])
            for ct in sorted(comp_types, key=lambda x: x["type_name"]):
                lines.append(f"{ct['type_name']:20} {ct['count']}")

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
            if not entity["enabled"]:
                status += " [disabled]"
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
            f"Enabled:        {info['enabled']}",
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
        mesh_count_val = tc_mesh_count()
        texture_count_val = tc_texture_count()
        shader_count_val = shader_count()
        material_count_val = tc_material_count()
        scene_count_val = tc_scene_registry_count()
        pipeline_count_val = tc_pipeline_registry_count()
        pass_count_val = len(tc_pass_registry_get_all_types())

        mesh_infos = tc_mesh_get_all_info()
        mesh_memory = sum(info["memory_bytes"] for info in mesh_infos)

        texture_infos = tc_texture_get_all_info()
        texture_memory = sum(info["memory_bytes"] for info in texture_infos)

        shader_infos = shader_get_all_info()
        shader_memory = sum(info["source_size"] for info in shader_infos)

        component_count_val = component_registry_type_count()

        self._status_label.setText(
            f"Meshes: {mesh_count_val} ({self._format_bytes(mesh_memory)}) | "
            f"Textures: {texture_count_val} ({self._format_bytes(texture_memory)}) | "
            f"Shaders: {shader_count_val} ({self._format_bytes(shader_memory)}) | "
            f"Materials: {material_count_val} | "
            f"Pipelines: {pipeline_count_val} | "
            f"Passes: {pass_count_val} | "
            f"Scenes: {scene_count_val}"
        )
