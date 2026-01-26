"""
Диалог просмотра состояния ResourceManager.

Показывает зарегистрированные материалы, меши, текстуры и компоненты.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QLabel,
    QTextEdit,
    QWidget,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from termin.editor.project_file_watcher import ProjectFileWatcher

from termin.visualization.core.resources import ResourceManager


class ResourceManagerViewer(QDialog):
    """
    Диалог просмотра состояния ResourceManager.
    """

    def __init__(
        self,
        resource_manager: ResourceManager,
        project_file_watcher: "ProjectFileWatcher | None" = None,
        parent=None,
    ):
        super().__init__(parent)
        self._resource_manager = resource_manager
        self._project_file_watcher = project_file_watcher
        self._selected_asset: Any = None
        self._selected_asset_type: str = ""

        self.setWindowTitle("Resource Manager")
        self.setMinimumSize(900, 600)

        # Enable maximize button
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        """Создаёт UI диалога."""
        layout = QVBoxLayout(self)

        # Splitter: левая часть - дерево, правая - детали
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # Левая панель с табами
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._tab_widget = QTabWidget()
        left_layout.addWidget(self._tab_widget)

        # Материалы
        self._materials_tree = QTreeWidget()
        self._materials_tree.setHeaderLabels(["Name", "Status", "Ver", "UUID"])
        self._materials_tree.setAlternatingRowColors(True)
        self._materials_tree.itemClicked.connect(lambda item: self._on_item_clicked("material", item))
        self._tab_widget.addTab(self._materials_tree, "Materials")

        # Шейдеры
        self._shaders_tree = QTreeWidget()
        self._shaders_tree.setHeaderLabels(["Name", "Status", "Ver", "UUID"])
        self._shaders_tree.setAlternatingRowColors(True)
        self._shaders_tree.itemClicked.connect(lambda item: self._on_item_clicked("shader", item))
        self._tab_widget.addTab(self._shaders_tree, "Shaders")

        # Меши
        self._meshes_tree = QTreeWidget()
        self._meshes_tree.setHeaderLabels(["Name", "Status", "Ver", "UUID"])
        self._meshes_tree.setAlternatingRowColors(True)
        self._meshes_tree.itemClicked.connect(lambda item: self._on_item_clicked("mesh", item))
        self._tab_widget.addTab(self._meshes_tree, "Meshes")

        # Текстуры
        self._textures_tree = QTreeWidget()
        self._textures_tree.setHeaderLabels(["Name", "Status", "Ver", "UUID"])
        self._textures_tree.setAlternatingRowColors(True)
        self._textures_tree.itemClicked.connect(lambda item: self._on_item_clicked("texture", item))
        self._tab_widget.addTab(self._textures_tree, "Textures")

        # VoxelGrid
        self._voxelgrids_tree = QTreeWidget()
        self._voxelgrids_tree.setHeaderLabels(["Name", "Status", "Ver", "UUID"])
        self._voxelgrids_tree.setAlternatingRowColors(True)
        self._voxelgrids_tree.itemClicked.connect(lambda item: self._on_item_clicked("voxelgrid", item))
        self._tab_widget.addTab(self._voxelgrids_tree, "VoxelGrids")

        # NavMesh
        self._navmeshes_tree = QTreeWidget()
        self._navmeshes_tree.setHeaderLabels(["Name", "Status", "Ver", "UUID"])
        self._navmeshes_tree.setAlternatingRowColors(True)
        self._navmeshes_tree.itemClicked.connect(lambda item: self._on_item_clicked("navmesh", item))
        self._tab_widget.addTab(self._navmeshes_tree, "NavMeshes")

        # Skeletons
        self._skeletons_tree = QTreeWidget()
        self._skeletons_tree.setHeaderLabels(["Name", "Status", "Ver", "UUID"])
        self._skeletons_tree.setAlternatingRowColors(True)
        self._skeletons_tree.itemClicked.connect(lambda item: self._on_item_clicked("skeleton", item))
        self._tab_widget.addTab(self._skeletons_tree, "Skeletons")

        # Pipelines
        self._pipelines_tree = QTreeWidget()
        self._pipelines_tree.setHeaderLabels(["Name", "Passes", "Ver", "UUID"])
        self._pipelines_tree.setAlternatingRowColors(True)
        self._pipelines_tree.itemClicked.connect(lambda item: self._on_item_clicked("pipeline", item))
        self._tab_widget.addTab(self._pipelines_tree, "Pipelines")

        # Scene Pipelines
        self._scene_pipelines_tree = QTreeWidget()
        self._scene_pipelines_tree.setHeaderLabels(["Name", "Passes", "Ver", "UUID"])
        self._scene_pipelines_tree.setAlternatingRowColors(True)
        self._scene_pipelines_tree.itemClicked.connect(lambda item: self._on_item_clicked("scene_pipeline", item))
        self._tab_widget.addTab(self._scene_pipelines_tree, "Scene Pipelines")

        # Компоненты (Python ResourceManager)
        self._components_tree = QTreeWidget()
        self._components_tree.setHeaderLabels(["Name", "Module"])
        self._components_tree.setAlternatingRowColors(True)
        self._tab_widget.addTab(self._components_tree, "Components")

        # Component Registry (C++)
        self._registry_tree = QTreeWidget()
        self._registry_tree.setHeaderLabels(["Name", "Type"])
        self._registry_tree.setAlternatingRowColors(True)
        self._tab_widget.addTab(self._registry_tree, "Component Registry")

        # Отслеживаемые файлы
        self._watched_tree = QTreeWidget()
        self._watched_tree.setHeaderLabels(["File", "Resources"])
        self._watched_tree.setAlternatingRowColors(True)
        self._tab_widget.addTab(self._watched_tree, "Watched Files")

        splitter.addWidget(left_widget)

        # Правая панель - детали
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        details_label = QLabel("Details")
        details_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(details_label)

        self._details_text = QTextEdit()
        self._details_text.setReadOnly(True)
        self._details_text.setPlaceholderText("Select an asset to view details")
        right_layout.addWidget(self._details_text)

        # Кнопка Load
        self._load_btn = QPushButton("Load Asset")
        self._load_btn.setEnabled(False)
        self._load_btn.clicked.connect(self._on_load_clicked)
        right_layout.addWidget(self._load_btn)

        splitter.addWidget(right_widget)
        splitter.setSizes([500, 400])

        # Статус (single line, fixed height)
        self._status_label = QLabel()
        self._status_label.setFixedHeight(20)
        layout.addWidget(self._status_label)

        # Кнопки
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _on_item_clicked(self, asset_type: str, item: QTreeWidgetItem) -> None:
        """Обработчик клика на элемент дерева."""
        name = item.text(0)
        self._selected_asset_type = asset_type
        self._selected_asset = None

        if asset_type == "shader":
            asset = self._resource_manager._shader_assets.get(name)
            if asset:
                self._selected_asset = asset
                self._show_shader_details(name, asset)
        elif asset_type == "mesh":
            asset = self._resource_manager._mesh_assets.get(name)
            if asset:
                self._selected_asset = asset
                self._show_mesh_details(name, asset)
        elif asset_type == "texture":
            asset = self._resource_manager._texture_assets.get(name)
            if asset:
                self._selected_asset = asset
                self._show_texture_details(name, asset)
        elif asset_type == "material":
            mat = self._resource_manager.materials.get(name)
            if mat:
                self._selected_asset = mat
                self._show_material_details(name, mat)
        elif asset_type == "voxelgrid":
            asset = self._resource_manager._voxel_grid_assets.get(name)
            if asset:
                self._selected_asset = asset
                self._show_voxelgrid_details(name, asset)
        elif asset_type == "navmesh":
            asset = self._resource_manager._navmesh_assets.get(name)
            if asset:
                self._selected_asset = asset
                self._show_navmesh_details(name, asset)
        elif asset_type == "skeleton":
            asset = self._resource_manager._skeleton_assets.get(name)
            if asset:
                self._selected_asset = asset
                self._show_skeleton_details(name, asset)
        elif asset_type == "pipeline":
            asset = self._resource_manager.get_pipeline_asset(name)
            if asset:
                self._selected_asset = asset
                self._show_pipeline_details(name, asset)
        elif asset_type == "scene_pipeline":
            asset = self._resource_manager.get_scene_pipeline_asset(name)
            if asset:
                self._selected_asset = asset
                self._show_scene_pipeline_details(name, asset)

        # Enable/disable load button
        can_load = (
            self._selected_asset is not None
            and hasattr(self._selected_asset, 'is_loaded')
            and not self._selected_asset.is_loaded
        )
        self._load_btn.setEnabled(can_load)

    def _show_mesh_details(self, name: str, asset) -> None:
        """Показать детали меша."""
        lines = [
            f"Name: {name}",
            f"UUID: {asset.uuid}",
            f"Source: {asset.source_path or '(none)'}",
            f"Loaded: {asset.is_loaded}",
            f"Version: {asset.version}",
        ]

        if asset.is_loaded:
            mesh = asset.data
            if mesh is not None and mesh.is_valid:
                lines.append(f"")
                lines.append(f"=== Mesh Data ===")
                lines.append(f"Vertices: {mesh.vertex_count}")
                lines.append(f"Triangles: {mesh.triangle_count}")
                lines.append(f"Stride: {mesh.stride}")
                lines.append(f"TcMesh UUID: {mesh.uuid}")
                lines.append(f"TcMesh Name: {mesh.name}")

        self._details_text.setText("\n".join(lines))

    def _show_texture_details(self, name: str, asset) -> None:
        """Показать детали текстуры."""
        lines = [
            f"Name: {name}",
            f"UUID: {asset.uuid}",
            f"Source: {asset.source_path or '(none)'}",
            f"Loaded: {asset.is_loaded}",
            f"Version: {asset.version}",
        ]

        if asset.is_loaded:
            lines.append(f"")
            lines.append(f"=== Texture Data ===")
            lines.append(f"Size: {asset.width}x{asset.height}")

        self._details_text.setText("\n".join(lines))

    def _show_material_details(self, name: str, mat) -> None:
        """Показать детали материала."""
        # mat is Material (C++), get version from MaterialAsset if available
        mat_asset = self._resource_manager._material_assets.get(name)
        version = str(mat_asset.version) if mat_asset and hasattr(mat_asset, 'version') else "-"
        lines = [
            f"Name: {name}",
            f"Source: {mat.source_path or '(inline)'}",
            f"Shader: {mat.shader_name or '(none)'}",
            f"Phases: {len(mat.phases)}",
            f"Version: {version}",
        ]

        for i, phase in enumerate(mat.phases):
            lines.append(f"")
            lines.append(f"=== Phase {i}: {phase.phase_mark} ===")
            lines.append(f"Priority: {phase.priority}")
            lines.append(f"Uniforms: {len(phase.uniforms)}")
            for uname, uval in phase.uniforms.items():
                lines.append(f"  {uname}: {uval}")
            lines.append(f"Textures: {len(phase.textures)}")
            for tname, tval in phase.textures.items():
                lines.append(f"  {tname}: {tval}")

        self._details_text.setText("\n".join(lines))

    def _show_shader_details(self, name: str, asset) -> None:
        """Показать детали шейдера."""
        lines = [
            f"Name: {name}",
            f"UUID: {asset.uuid}",
            f"Source: {asset.source_path or '(none)'}",
            f"Loaded: {asset.is_loaded}",
            f"Version: {asset.version}",
        ]

        if asset.is_loaded:
            program = asset.program
            if program is not None:
                lines.append(f"")
                lines.append(f"=== Shader Program ===")
                lines.append(f"Phases: {len(program.phases)}")

                for i, phase_data in enumerate(program.phases):
                    phase_mark = phase_data.phase_mark if hasattr(phase_data, 'phase_mark') else f"phase_{i}"
                    lines.append(f"")
                    lines.append(f"--- Phase: {phase_mark} ---")
                    if hasattr(phase_data, 'uniforms') and phase_data.uniforms:
                        lines.append(f"Uniforms: {len(phase_data.uniforms)}")
                        for uname in phase_data.uniforms:
                            lines.append(f"  - {uname}")

        self._details_text.setText("\n".join(lines))

    def _show_voxelgrid_details(self, name: str, asset) -> None:
        """Показать детали VoxelGrid."""
        lines = [
            f"Name: {name}",
            f"UUID: {asset.uuid}",
            f"Source: {asset.source_path or '(none)'}",
            f"Loaded: {asset.is_loaded}",
            f"Version: {asset.version}",
        ]

        if asset.is_loaded:
            grid = asset.data
            if grid is not None:
                lines.append(f"")
                lines.append(f"=== VoxelGrid Data ===")
                lines.append(f"Cell Size: {grid.cell_size}")
                lines.append(f"Voxel Count: {grid.voxel_count()}")
                origin = grid.origin
                lines.append(f"Origin: ({origin.x:.2f}, {origin.y:.2f}, {origin.z:.2f})")

        self._details_text.setText("\n".join(lines))

    def _show_navmesh_details(self, name: str, asset) -> None:
        """Показать детали NavMesh."""
        lines = [
            f"Name: {name}",
            f"UUID: {asset.uuid}",
            f"Source: {asset.source_path or '(none)'}",
            f"Loaded: {asset.is_loaded}",
            f"Version: {asset.version}",
        ]

        if asset.is_loaded:
            navmesh = asset.data
            if navmesh is not None:
                lines.append(f"")
                lines.append(f"=== NavMesh Data ===")
                lines.append(f"Cell Size: {navmesh.cell_size}")
                lines.append(f"Polygons: {navmesh.polygon_count()}")
                lines.append(f"Triangles: {navmesh.triangle_count()}")
                lines.append(f"Vertices: {navmesh.vertex_count()}")
                origin = navmesh.origin
                lines.append(f"Origin: ({origin[0]:.2f}, {origin[1]:.2f}, {origin[2]:.2f})")

        self._details_text.setText("\n".join(lines))

    def _show_skeleton_details(self, name: str, asset) -> None:
        """Показать детали Skeleton."""
        lines = [
            f"Name: {name}",
            f"UUID: {asset.uuid}",
            f"Source: {asset.source_path or '(none)'}",
            f"Loaded: {asset.is_loaded}",
            f"Version: {asset.version}",
        ]

        if asset.is_loaded:
            skeleton = asset.data
            if skeleton is not None:
                lines.append(f"")
                lines.append(f"=== Skeleton Data ===")
                bone_count = skeleton.get_bone_count() if hasattr(skeleton, 'get_bone_count') else len(skeleton.bones)
                lines.append(f"Bone Count: {bone_count}")

                # List bones
                if hasattr(skeleton, 'bones') and skeleton.bones:
                    lines.append(f"")
                    lines.append(f"=== Bones ===")
                    for i, bone in enumerate(skeleton.bones):
                        bone_name = bone.name if hasattr(bone, 'name') else str(bone)
                        parent_idx = bone.parent_index if hasattr(bone, 'parent_index') else -1
                        lines.append(f"  [{i}] {bone_name} (parent: {parent_idx})")

        self._details_text.setText("\n".join(lines))

    def _show_pipeline_details(self, name: str, asset) -> None:
        """Показать детали Pipeline."""
        lines = [
            f"Name: {name}",
            f"UUID: {asset.uuid}",
            f"Source: {asset.source_path or '(builtin)'}",
            f"Loaded: {asset.is_loaded}",
            f"Version: {asset.version}",
        ]

        if asset.is_loaded:
            pipeline = asset.data
            if pipeline is not None:
                lines.append(f"")
                lines.append(f"=== Pipeline Data ===")
                lines.append(f"Pipeline Name: {pipeline.name}")
                lines.append(f"Passes: {len(pipeline.passes)}")
                lines.append(f"")
                lines.append(f"=== Passes ===")
                for i, pass_obj in enumerate(pipeline.passes):
                    pass_name = pass_obj.pass_name if hasattr(pass_obj, 'pass_name') else type(pass_obj).__name__
                    pass_type = type(pass_obj).__name__
                    lines.append(f"  [{i}] {pass_name} ({pass_type})")

        self._details_text.setText("\n".join(lines))

    def _show_scene_pipeline_details(self, name: str, asset) -> None:
        """Показать детали Scene Pipeline."""
        lines = [
            f"Name: {name}",
            f"UUID: {asset.uuid}",
            f"Source: {asset.source_path or '(builtin)'}",
            f"Loaded: {asset.is_loaded}",
            f"Version: {asset.version}",
        ]

        if asset.is_loaded:
            # ScenePipelineAsset stores graph data (nodes, connections), not serialized pipeline
            graph_data = asset.data
            if graph_data is not None:
                lines.append(f"")
                lines.append(f"=== Scene Pipeline Graph ===")
                nodes = graph_data.get("nodes", [])
                connections = graph_data.get("connections", [])
                lines.append(f"Nodes: {len(nodes)}")
                lines.append(f"Connections: {len(connections)}")
                lines.append(f"")
                lines.append(f"=== Nodes ===")
                for i, node_data in enumerate(nodes):
                    node_type = node_data.get("type", "?")
                    node_id = node_data.get("id", "?")
                    params = node_data.get("params", {})
                    pass_name = params.get("pass_name", "")
                    if pass_name:
                        lines.append(f"  [{i}] {node_type}: {pass_name}")
                    else:
                        lines.append(f"  [{i}] {node_type} (id={node_id})")

        self._details_text.setText("\n".join(lines))

    def _on_load_clicked(self) -> None:
        """Загрузить выбранный ассет."""
        if self._selected_asset is None:
            return

        if hasattr(self._selected_asset, 'ensure_loaded'):
            self._selected_asset.ensure_loaded()
        elif hasattr(self._selected_asset, 'data'):
            # Accessing .data triggers lazy load
            _ = self._selected_asset.data

        self.refresh()

        # Re-select to update details
        if self._selected_asset_type == "mesh":
            for i in range(self._meshes_tree.topLevelItemCount()):
                item = self._meshes_tree.topLevelItem(i)
                if item and item.text(0) == self._selected_asset._name:
                    self._on_item_clicked("mesh", item)
                    break

    def refresh(self) -> None:
        """Обновляет содержимое всех вкладок."""
        self._refresh_materials()
        self._refresh_shaders()
        self._refresh_meshes()
        self._refresh_textures()
        self._refresh_voxelgrids()
        self._refresh_navmeshes()
        self._refresh_skeletons()
        self._refresh_pipelines()
        self._refresh_scene_pipelines()
        self._refresh_components()
        self._refresh_registry()
        self._refresh_watched()
        self._update_status()

    def _refresh_materials(self) -> None:
        """Обновляет список материалов."""
        self._materials_tree.clear()

        for name, mat in sorted(self._resource_manager.materials.items()):
            phases = f"{len(mat.phases)} phases"
            # Get version from MaterialAsset
            mat_asset = self._resource_manager._material_assets.get(name)
            version = str(mat_asset.version) if mat_asset and hasattr(mat_asset, 'version') else "-"
            # Get UUID from MaterialAsset
            uuid_str = ""
            if mat_asset:
                uuid_str = mat_asset.uuid[:16] + "..." if len(mat_asset.uuid) > 16 else mat_asset.uuid

            item = QTreeWidgetItem([name, phases, version, uuid_str])
            self._materials_tree.addTopLevelItem(item)

        self._materials_tree.resizeColumnToContents(0)
        self._materials_tree.resizeColumnToContents(1)
        self._materials_tree.resizeColumnToContents(2)

    def _refresh_shaders(self) -> None:
        """Обновляет список шейдеров."""
        self._shaders_tree.clear()

        for name, asset in sorted(self._resource_manager._shader_assets.items()):
            status = "loaded" if asset.is_loaded else "not loaded"
            version = str(asset.version) if hasattr(asset, 'version') else "-"
            uuid_str = asset.uuid[:16] + "..." if len(asset.uuid) > 16 else asset.uuid

            item = QTreeWidgetItem([name, status, version, uuid_str])
            self._shaders_tree.addTopLevelItem(item)

        self._shaders_tree.resizeColumnToContents(0)
        self._shaders_tree.resizeColumnToContents(1)
        self._shaders_tree.resizeColumnToContents(2)

    def _refresh_meshes(self) -> None:
        """Обновляет список мешей."""
        self._meshes_tree.clear()

        for name, asset in sorted(self._resource_manager._mesh_assets.items()):
            status = "loaded" if asset.is_loaded else "not loaded"
            version = str(asset.version) if hasattr(asset, 'version') else "-"
            uuid_str = asset.uuid[:16] + "..." if len(asset.uuid) > 16 else asset.uuid

            item = QTreeWidgetItem([name, status, version, uuid_str])
            self._meshes_tree.addTopLevelItem(item)

        self._meshes_tree.resizeColumnToContents(0)
        self._meshes_tree.resizeColumnToContents(1)
        self._meshes_tree.resizeColumnToContents(2)

    def _refresh_textures(self) -> None:
        """Обновляет список текстур."""
        self._textures_tree.clear()

        for name, asset in sorted(self._resource_manager._texture_assets.items()):
            status = "loaded" if asset.is_loaded else "not loaded"
            version = str(asset.version) if hasattr(asset, 'version') else "-"
            uuid_str = asset.uuid[:16] + "..." if len(asset.uuid) > 16 else asset.uuid

            item = QTreeWidgetItem([name, status, version, uuid_str])
            self._textures_tree.addTopLevelItem(item)

        self._textures_tree.resizeColumnToContents(0)
        self._textures_tree.resizeColumnToContents(1)
        self._textures_tree.resizeColumnToContents(2)

    def _refresh_voxelgrids(self) -> None:
        """Обновляет список VoxelGrid."""
        self._voxelgrids_tree.clear()

        for name, asset in sorted(self._resource_manager._voxel_grid_assets.items()):
            status = "loaded" if asset.is_loaded else "not loaded"
            version = str(asset.version) if hasattr(asset, 'version') else "-"
            uuid_str = asset.uuid[:16] + "..." if len(asset.uuid) > 16 else asset.uuid

            item = QTreeWidgetItem([name, status, version, uuid_str])
            self._voxelgrids_tree.addTopLevelItem(item)

        self._voxelgrids_tree.resizeColumnToContents(0)
        self._voxelgrids_tree.resizeColumnToContents(1)
        self._voxelgrids_tree.resizeColumnToContents(2)

    def _refresh_navmeshes(self) -> None:
        """Обновляет список NavMesh."""
        self._navmeshes_tree.clear()

        for name, asset in sorted(self._resource_manager._navmesh_assets.items()):
            status = "loaded" if asset.is_loaded else "not loaded"
            version = str(asset.version) if hasattr(asset, 'version') else "-"
            uuid_str = asset.uuid[:16] + "..." if len(asset.uuid) > 16 else asset.uuid

            item = QTreeWidgetItem([name, status, version, uuid_str])
            self._navmeshes_tree.addTopLevelItem(item)

        self._navmeshes_tree.resizeColumnToContents(0)
        self._navmeshes_tree.resizeColumnToContents(1)
        self._navmeshes_tree.resizeColumnToContents(2)

    def _refresh_skeletons(self) -> None:
        """Обновляет список Skeleton."""
        self._skeletons_tree.clear()

        for name, asset in sorted(self._resource_manager._skeleton_assets.items()):
            status = "loaded" if asset.is_loaded else "not loaded"
            version = str(asset.version) if hasattr(asset, 'version') else "-"
            uuid_str = asset.uuid[:16] + "..." if len(asset.uuid) > 16 else asset.uuid

            item = QTreeWidgetItem([name, status, version, uuid_str])
            self._skeletons_tree.addTopLevelItem(item)

        self._skeletons_tree.resizeColumnToContents(0)
        self._skeletons_tree.resizeColumnToContents(1)
        self._skeletons_tree.resizeColumnToContents(2)

    def _refresh_pipelines(self) -> None:
        """Обновляет список Pipelines."""
        self._pipelines_tree.clear()

        for name in self._resource_manager.list_pipeline_names():
            asset = self._resource_manager.get_pipeline_asset(name)
            if asset:
                pipeline = asset.data if asset.is_loaded else None
                passes_count = len(pipeline.passes) if pipeline else "?"
                status = f"{passes_count} passes"
                version = str(asset.version) if hasattr(asset, 'version') else "-"
                uuid_str = asset.uuid[:16] + "..." if len(asset.uuid) > 16 else asset.uuid

                item = QTreeWidgetItem([name, status, version, uuid_str])
                self._pipelines_tree.addTopLevelItem(item)

        self._pipelines_tree.resizeColumnToContents(0)
        self._pipelines_tree.resizeColumnToContents(1)
        self._pipelines_tree.resizeColumnToContents(2)

    def _refresh_scene_pipelines(self) -> None:
        """Обновляет список Scene Pipelines."""
        self._scene_pipelines_tree.clear()

        for name in self._resource_manager.list_scene_pipeline_names():
            asset = self._resource_manager.get_scene_pipeline_asset(name)
            if asset:
                # ScenePipelineAsset stores graph data (nodes, connections), not serialized pipeline
                graph_data = asset.data if asset.is_loaded else None
                if graph_data:
                    # Count pass nodes (nodes that are not ViewportFrame, ResourceNode, etc.)
                    nodes = graph_data.get("nodes", [])
                    passes_count = sum(1 for n in nodes if n.get("type", "").endswith("Pass"))
                else:
                    passes_count = "?"
                status = f"{passes_count} passes"
                version = str(asset.version) if hasattr(asset, 'version') else "-"
                uuid_str = asset.uuid[:16] + "..." if len(asset.uuid) > 16 else asset.uuid

                item = QTreeWidgetItem([name, status, version, uuid_str])
                self._scene_pipelines_tree.addTopLevelItem(item)

        self._scene_pipelines_tree.resizeColumnToContents(0)
        self._scene_pipelines_tree.resizeColumnToContents(1)
        self._scene_pipelines_tree.resizeColumnToContents(2)

    def _refresh_components(self) -> None:
        """Обновляет список компонентов."""
        self._components_tree.clear()

        for name, cls in sorted(self._resource_manager.components.items()):
            module = cls.__module__ if hasattr(cls, '__module__') else "?"

            item = QTreeWidgetItem([name, module])
            self._components_tree.addTopLevelItem(item)

        self._components_tree.resizeColumnToContents(0)
        self._components_tree.resizeColumnToContents(1)

    def _refresh_registry(self) -> None:
        """Обновляет список компонентов из C++ ComponentRegistry."""
        from termin.entity import ComponentRegistry

        self._registry_tree.clear()
        reg = ComponentRegistry.instance()

        # Native (C++) components
        native_names = reg.list_native()
        if native_names:
            native_item = QTreeWidgetItem([f"Native ({len(native_names)})", "C++"])
            native_item.setExpanded(True)
            self._registry_tree.addTopLevelItem(native_item)
            for name in sorted(native_names):
                child = QTreeWidgetItem([name, "C++"])
                native_item.addChild(child)

        # Python components
        python_names = reg.list_python()
        if python_names:
            python_item = QTreeWidgetItem([f"Python ({len(python_names)})", "Python"])
            python_item.setExpanded(True)
            self._registry_tree.addTopLevelItem(python_item)
            for name in sorted(python_names):
                child = QTreeWidgetItem([name, "Python"])
                python_item.addChild(child)

        self._registry_tree.expandAll()
        self._registry_tree.resizeColumnToContents(0)

    def _refresh_watched(self) -> None:
        """Обновляет список отслеживаемых файлов и директорий."""
        self._watched_tree.clear()

        watcher = self._project_file_watcher
        if watcher is None:
            return

        # By Extension — статистика по всем расширениям
        all_files_stats = watcher.get_all_files_by_extension()
        if all_files_stats:
            total_files = watcher.get_all_files_count()
            all_item = QTreeWidgetItem(["By Extension", f"{total_files} files"])
            self._watched_tree.addTopLevelItem(all_item)
            for ext, count in all_files_stats.items():
                child = QTreeWidgetItem([ext, str(count)])
                all_item.addChild(child)

        # Директории
        watched_dirs = watcher.watched_dirs
        if watched_dirs:
            dirs_item = QTreeWidgetItem(["Watched Directories", f"{len(watched_dirs)} dirs"])
            self._watched_tree.addTopLevelItem(dirs_item)
            for path in sorted(watched_dirs):
                child = QTreeWidgetItem([path, "directory"])
                dirs_item.addChild(child)

        # Файлы по типам (из процессоров)
        for processor in watcher.get_all_processors():
            tracked = processor.get_tracked_files()
            if tracked:
                type_name = processor.resource_type.capitalize()
                type_item = QTreeWidgetItem([f"{type_name} Files", f"{len(tracked)} files"])
                self._watched_tree.addTopLevelItem(type_item)
                for path, names in sorted(tracked.items()):
                    resources = ", ".join(sorted(names)) if names else "(pending)"
                    child = QTreeWidgetItem([path, resources])
                    type_item.addChild(child)

        self._watched_tree.expandAll()
        self._watched_tree.resizeColumnToContents(0)

    def _update_status(self) -> None:
        """Обновляет строку статуса."""
        rm = self._resource_manager
        watcher = self._project_file_watcher

        if watcher is not None:
            watching = "enabled" if watcher.is_enabled else "disabled"
            watched_dirs = len(watcher.watched_dirs)
            watched_files = watcher.get_file_count()
        else:
            watching = "disabled"
            watched_dirs = 0
            watched_files = 0

        self._status_label.setText(
            f"Materials: {len(rm.materials)} | "
            f"Shaders: {len(rm._shader_assets)} | "
            f"Meshes: {len(rm._mesh_assets)} | "
            f"Textures: {len(rm._texture_assets)} | "
            f"VoxelGrids: {len(rm._voxel_grid_assets)} | "
            f"NavMeshes: {len(rm._navmesh_assets)} | "
            f"Skeletons: {len(rm._skeleton_assets)} | "
            f"Pipelines: {len(rm.list_pipeline_names())} | "
            f"Scene Pipelines: {len(rm.list_scene_pipeline_names())} | "
            f"Components: {len(rm.components)}"
        )
