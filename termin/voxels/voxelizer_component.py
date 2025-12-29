"""
VoxelizerComponent — компонент для вокселизации меша из инспектора.

Реализует протокол Drawable для отладочной визуализации регионов.
"""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Optional, List, Set

import numpy as np

from termin.visualization.core.python_component import PythonComponent
from termin.visualization.core.material import Material
from termin.visualization.core.mesh_handle import MeshHandle
from termin.mesh.mesh import Mesh3
from termin.visualization.render.drawable import GeometryDrawCall
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.render.render_context import RenderContext
    from termin.voxels.grid import VoxelGrid


class VoxelizeMode(IntEnum):
    """Режимы вокселизации (стадии пайплайна)."""
    SHELL = 0           # Только поверхность меша
    FILLED = 1          # Поверхность + заполнение внутри
    MARKED = 2          # Заполнение + пометка поверхности (SOLID + SURFACE)
    SURFACE_ONLY = 3    # Только поверхность (внутренние удалены)
    WITH_NORMALS = 4    # Поверхность + нормали
    FULL_GRID = 5       # Заполнить всю сетку (без вокселизации меша)


class VoxelizeSource(IntEnum):
    """Источник мешей для вокселизации."""
    CURRENT_MESH = 0      # Только меш текущего entity
    ALL_DESCENDANTS = 1   # Меши всех потомков (включая текущий entity)


class NavMeshStage(IntEnum):
    """Стадии алгоритма построения NavMesh."""
    REGIONS_BASIC = 0       # Регионы до расширения
    REGIONS_EXPANDED = 1    # Регионы после расширения
    STITCHED = 2            # Сшитые полигоны (plane intersections)
    WITH_CONTOURS = 3       # + извлечённые контуры
    SIMPLIFIED = 4          # + упрощённые контуры (Douglas-Peucker)
    FINAL = 5               # Перетриангулированное (ear clipping)


def _voxelize_action(component: "VoxelizerComponent") -> None:
    """Действие кнопки вокселизации."""
    component.voxelize()


def _build_navmesh_action(component: "VoxelizerComponent") -> None:
    """Действие кнопки построения NavMesh."""
    component.build_navmesh()


class VoxelizerComponent(PythonComponent):
    """
    Компонент для вокселизации меша entity.

    Добавляется к entity с MeshRenderer.
    В инспекторе показывает кнопку "Voxelize" и настройки.
    По нажатию кнопки вокселизирует меш, регистрирует в ResourceManager и сохраняет в файл.
    """

    inspect_fields = {
        "grid_name": InspectField(
            path="grid_name",
            label="Grid Name",
            kind="string",
        ),
        "cell_size": InspectField(
            path="cell_size",
            label="Cell Size",
            kind="float",
            min=0.001,
            max=10.0,
            step=0.001,
        ),
        "voxelize_mode": InspectField(
            path="voxelize_mode",
            label="Mode",
            kind="enum",
            choices=[
                (VoxelizeMode.SHELL, "Shell (surface only)"),
                (VoxelizeMode.FILLED, "Filled (interior)"),
                (VoxelizeMode.MARKED, "Marked (surface tagged)"),
                (VoxelizeMode.SURFACE_ONLY, "Surface Only (interior removed)"),
                (VoxelizeMode.WITH_NORMALS, "With Normals"),
                (VoxelizeMode.FULL_GRID, "Full Grid (fill bounds)"),
            ],
        ),
        "voxelize_source": InspectField(
            path="voxelize_source",
            label="Source",
            kind="enum",
            choices=[
                (VoxelizeSource.CURRENT_MESH, "Current Mesh"),
                (VoxelizeSource.ALL_DESCENDANTS, "All Descendants"),
            ],
        ),
        "output_path": InspectField(
            path="output_path",
            label="Output Path",
            kind="string",
        ),
        "voxelize_btn": InspectField(
            label="Voxelize",
            kind="button",
            action=_voxelize_action,
            non_serializable=True,
        ),
        # --- NavMesh ---
        "navmesh_output_path": InspectField(
            path="navmesh_output_path",
            label="NavMesh Path",
            kind="string",
        ),
        "normal_angle": InspectField(
            path="normal_angle",
            label="Region Merge Angle (°)",
            kind="float",
            min=0.0,
            max=90.0,
            step=1.0,
        ),
        "expand_regions": InspectField(
            path="expand_regions",
            label="Expand Regions",
            kind="bool",
        ),
        "navmesh_stage": InspectField(
            path="navmesh_stage",
            label="NavMesh Stage",
            kind="enum",
            choices=[
                (NavMeshStage.REGIONS_BASIC, "1. Regions (basic)"),
                (NavMeshStage.REGIONS_EXPANDED, "2. Regions (expanded)"),
                (NavMeshStage.STITCHED, "3. Stitched (plane intersections)"),
                (NavMeshStage.WITH_CONTOURS, "4. With Contours"),
                (NavMeshStage.SIMPLIFIED, "5. Simplified (Douglas-Peucker)"),
                (NavMeshStage.FINAL, "6. Final (Ear Clipping)"),
            ],
        ),
        "contour_epsilon": InspectField(
            path="contour_epsilon",
            label="Contour Epsilon",
            kind="float",
            min=0.001,
            max=1.0,
            step=0.001,
        ),
        "build_navmesh_btn": InspectField(
            label="Build NavMesh",
            kind="button",
            action=_build_navmesh_action,
            non_serializable=True,
        ),
        # --- Debug ---
        "show_debug_voxels": InspectField(
            path="show_debug_voxels",
            label="Show Voxels",
            kind="bool",
        ),
        "show_debug_contours": InspectField(
            path="show_debug_contours",
            label="Show Contours",
            kind="bool",
        ),
        "project_contours": InspectField(
            path="project_contours",
            label="Project to Plane",
            kind="bool",
        ),
        "stitch_contours": InspectField(
            path="stitch_contours",
            label="Stitch Contours",
            kind="bool",
        ),
        "share_boundary": InspectField(
            path="share_boundary",
            label="Share Boundary",
            kind="bool",
        ),
        "show_multi_normal_voxels": InspectField(
            path="show_multi_normal_voxels",
            label="Show Multi-Normal",
            kind="bool",
        ),
        "show_boundary_voxels": InspectField(
            path="show_boundary_voxels",
            label="Show Boundary",
            kind="bool",
        ),
    }

    serializable_fields = ["grid_name", "cell_size", "output_path", "voxelize_mode", "voxelize_source", "navmesh_output_path", "normal_angle", "expand_regions", "navmesh_stage", "contour_epsilon", "show_debug_voxels", "show_debug_contours", "project_contours", "stitch_contours", "share_boundary", "show_multi_normal_voxels", "show_boundary_voxels"]

    def __init__(
        self,
        grid_name: str = "",
        cell_size: float = 0.25,
        output_path: str = "",
        voxelize_mode: VoxelizeMode = VoxelizeMode.SHELL,
        voxelize_source: VoxelizeSource = VoxelizeSource.CURRENT_MESH,
        navmesh_output_path: str = "",
        normal_angle: float = 25.0,
        expand_regions: bool = False,
        navmesh_stage: NavMeshStage = NavMeshStage.REGIONS_BASIC,
        contour_epsilon: float = 0.1,
        show_debug_voxels: bool = True,
        show_debug_contours: bool = True,
        project_contours: bool = False,
        stitch_contours: bool = False,
        share_boundary: bool = False,
        show_multi_normal_voxels: bool = False,
        show_boundary_voxels: bool = False,
    ) -> None:
        super().__init__()
        self.grid_name = grid_name
        self.cell_size = cell_size
        self.output_path = output_path
        self.voxelize_mode = voxelize_mode
        self.voxelize_source = voxelize_source
        self.navmesh_output_path = navmesh_output_path
        self.normal_angle = normal_angle
        self.expand_regions = expand_regions
        self.navmesh_stage = navmesh_stage
        self.contour_epsilon = contour_epsilon
        self._last_voxel_count: int = 0

        # Debug visualization
        self.show_debug_voxels: bool = show_debug_voxels
        self.show_debug_contours: bool = show_debug_contours
        self.project_contours: bool = project_contours
        self.stitch_contours: bool = stitch_contours
        self.share_boundary: bool = share_boundary
        self.show_multi_normal_voxels: bool = show_multi_normal_voxels
        self.show_boundary_voxels: bool = show_boundary_voxels
        self._debug_regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
        self._debug_boundary_voxels: set[tuple[int, int, int]] = set()
        self._debug_grid: Optional["VoxelGrid"] = None
        self._debug_mesh_handle: Optional[MeshHandle] = None
        self._debug_contours_handle: Optional[MeshHandle] = None
        self._debug_multi_normal_handle: Optional[MeshHandle] = None
        self._debug_boundary_handle: Optional[MeshHandle] = None
        self._debug_material: Optional[Material] = None
        self._debug_contour_material: Optional[Material] = None
        self._debug_bounds_min: np.ndarray = np.zeros(3, dtype=np.float32)
        self._debug_bounds_max: np.ndarray = np.zeros(3, dtype=np.float32)

    # --- Drawable protocol ---

    # Константы для geometry_id
    GEOMETRY_VOXELS = "voxels"
    GEOMETRY_CONTOURS = "contours"
    GEOMETRY_MULTI_NORMAL = "multi_normal"
    GEOMETRY_BOUNDARY = "boundary"

    @property
    def phase_marks(self) -> Set[str]:
        """Фазы рендеринга для отладочной визуализации."""
        marks: Set[str] = set()
        if self.show_debug_voxels:
            mat = self._get_or_create_debug_material()
            marks.update(p.phase_mark for p in mat.phases)
        if self.show_debug_contours:
            mat = self._get_or_create_contour_material()
            marks.update(p.phase_mark for p in mat.phases)
        if self.show_multi_normal_voxels:
            mat = self._get_or_create_debug_material()
            marks.update(p.phase_mark for p in mat.phases)
        if self.show_boundary_voxels:
            mat = self._get_or_create_debug_material()
            marks.update(p.phase_mark for p in mat.phases)
        return marks

    def draw_geometry(self, context: "RenderContext", geometry_id: str = "") -> None:
        """Рисует отладочную геометрию."""
        if geometry_id == "" or geometry_id == self.GEOMETRY_VOXELS:
            if self.show_debug_voxels and self._debug_mesh_handle is not None:
                mesh_data = self._debug_mesh_handle.mesh
                gpu = self._debug_mesh_handle.gpu
                if mesh_data is not None and gpu is not None:
                    gpu.draw(context, mesh_data, self._debug_mesh_handle.version)
        if geometry_id == "" or geometry_id == self.GEOMETRY_CONTOURS:
            if self.show_debug_contours and self._debug_contours_handle is not None:
                mesh_data = self._debug_contours_handle.mesh
                gpu = self._debug_contours_handle.gpu
                if mesh_data is not None and gpu is not None:
                    gpu.draw(context, mesh_data, self._debug_contours_handle.version)
        if geometry_id == "" or geometry_id == self.GEOMETRY_MULTI_NORMAL:
            if self.show_multi_normal_voxels and self._debug_multi_normal_handle is not None:
                mesh_data = self._debug_multi_normal_handle.mesh
                gpu = self._debug_multi_normal_handle.gpu
                if mesh_data is not None and gpu is not None:
                    gpu.draw(context, mesh_data, self._debug_multi_normal_handle.version)
        if geometry_id == "" or geometry_id == self.GEOMETRY_BOUNDARY:
            if self.show_boundary_voxels and self._debug_boundary_handle is not None:
                mesh_data = self._debug_boundary_handle.mesh
                gpu = self._debug_boundary_handle.gpu
                if mesh_data is not None and gpu is not None:
                    gpu.draw(context, mesh_data, self._debug_boundary_handle.version)

    def get_geometry_draws(self, phase_mark: str | None = None) -> List[GeometryDrawCall]:
        """Возвращает GeometryDrawCalls для отладочного рендеринга."""
        result: List[GeometryDrawCall] = []

        # Воксели
        if self.show_debug_voxels and self._debug_mesh_handle is not None:
            mat = self._get_or_create_debug_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            # Устанавливаем uniforms для voxel шейдера
            debug_color = np.array([1.0, 0.5, 0.0, 0.8], dtype=np.float32)
            for phase in phases:
                phase.uniforms["u_color_below"] = debug_color
                phase.uniforms["u_color_above"] = debug_color
                phase.uniforms["u_color_surface"] = debug_color
                phase.uniforms["u_slice_axis"] = np.array([0.0, 0.0, 1.0], dtype=np.float32)
                phase.uniforms["u_fill_percent"] = 1.0
                phase.uniforms["u_bounds_min"] = self._debug_bounds_min
                phase.uniforms["u_bounds_max"] = self._debug_bounds_max
                phase.uniforms["u_ambient_color"] = np.array([1.0, 1.0, 1.0], dtype=np.float32)
                phase.uniforms["u_ambient_intensity"] = 0.4

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_VOXELS) for p in phases)

        # Контуры
        if self.show_debug_contours and self._debug_contours_handle is not None:
            mat = self._get_or_create_contour_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            # Устанавливаем uniforms для контуров (непрозрачные)
            contour_color = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
            for phase in phases:
                phase.uniforms["u_color_below"] = contour_color
                phase.uniforms["u_color_above"] = contour_color
                phase.uniforms["u_color_surface"] = contour_color
                phase.uniforms["u_slice_axis"] = np.array([0.0, 0.0, 1.0], dtype=np.float32)
                phase.uniforms["u_fill_percent"] = 1.0
                phase.uniforms["u_bounds_min"] = self._debug_bounds_min
                phase.uniforms["u_bounds_max"] = self._debug_bounds_max
                phase.uniforms["u_ambient_color"] = np.array([1.0, 1.0, 1.0], dtype=np.float32)
                phase.uniforms["u_ambient_intensity"] = 0.6  # Ярче для контуров

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_CONTOURS) for p in phases)

        # Multi-normal воксели
        if self.show_multi_normal_voxels and self._debug_multi_normal_handle is not None:
            mat = self._get_or_create_debug_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            # Яркий цвет для multi-normal вокселей
            multi_color = np.array([1.0, 0.2, 0.5, 1.0], dtype=np.float32)
            for phase in phases:
                phase.uniforms["u_color_below"] = multi_color
                phase.uniforms["u_color_above"] = multi_color
                phase.uniforms["u_color_surface"] = multi_color
                phase.uniforms["u_slice_axis"] = np.array([0.0, 0.0, 1.0], dtype=np.float32)
                phase.uniforms["u_fill_percent"] = 1.0
                phase.uniforms["u_bounds_min"] = self._debug_bounds_min
                phase.uniforms["u_bounds_max"] = self._debug_bounds_max
                phase.uniforms["u_ambient_color"] = np.array([1.0, 1.0, 1.0], dtype=np.float32)
                phase.uniforms["u_ambient_intensity"] = 0.5

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_MULTI_NORMAL) for p in phases)

        # Boundary воксели
        if self.show_boundary_voxels and self._debug_boundary_handle is not None:
            mat = self._get_or_create_debug_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            # Яркий жёлтый цвет для boundary вокселей
            boundary_color = np.array([1.0, 1.0, 0.2, 1.0], dtype=np.float32)
            for phase in phases:
                phase.uniforms["u_color_below"] = boundary_color
                phase.uniforms["u_color_above"] = boundary_color
                phase.uniforms["u_color_surface"] = boundary_color
                phase.uniforms["u_slice_axis"] = np.array([0.0, 0.0, 1.0], dtype=np.float32)
                phase.uniforms["u_fill_percent"] = 1.0
                phase.uniforms["u_bounds_min"] = self._debug_bounds_min
                phase.uniforms["u_bounds_max"] = self._debug_bounds_max
                phase.uniforms["u_ambient_color"] = np.array([1.0, 1.0, 1.0], dtype=np.float32)
                phase.uniforms["u_ambient_intensity"] = 0.5

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_BOUNDARY) for p in phases)

        return result

    def _get_or_create_debug_material(self) -> Material:
        """Создаёт материал для отладочной визуализации."""
        if self._debug_material is None:
            from termin.voxels.voxel_shader import voxel_display_shader
            from termin.visualization.render.renderpass import RenderState

            shader = voxel_display_shader()
            self._debug_material = Material(
                shader=shader,
                color=(1.0, 0.5, 0.0, 0.8),  # Оранжевый для отладки
                phase_mark="opaque",
                render_state=RenderState(
                    depth_test=True,
                    depth_write=True,
                    blend=True,
                    cull=True,
                ),
            )
        return self._debug_material

    def _get_or_create_contour_material(self) -> Material:
        """Создаёт материал для контуров (без прозрачности, без culling)."""
        if self._debug_contour_material is None:
            from termin.voxels.voxel_shader import voxel_display_shader
            from termin.visualization.render.renderpass import RenderState

            shader = voxel_display_shader()
            self._debug_contour_material = Material(
                shader=shader,
                color=(1.0, 1.0, 1.0, 1.0),  # Полностью непрозрачный
                phase_mark="opaque",
                render_state=RenderState(
                    depth_test=True,
                    depth_write=True,
                    blend=False,  # Без прозрачности
                    cull=False,   # Двусторонний рендеринг
                ),
            )
        return self._debug_contour_material

    def _collect_meshes_from_entity(
        self,
        entity,
        root_transform_inv: np.ndarray,
        recurse: bool = True,
    ) -> List[tuple["Mesh3", np.ndarray]]:
        """
        Собрать меши из entity (и опционально его потомков).

        Args:
            entity: Entity для обхода
            root_transform_inv: Обратная матрица трансформа корневого entity
            recurse: Если True — рекурсивно обходить детей

        Returns:
            Список (mesh, transform_matrix) для каждого найденного меша
        """
        from termin.visualization.render.components import MeshRenderer

        result: List[tuple["Mesh3", np.ndarray]] = []

        # Проверяем MeshRenderer на текущем entity
        for comp in entity.components:
            if isinstance(comp, MeshRenderer):
                mesh_drawable = comp.mesh
                if mesh_drawable is not None and mesh_drawable.mesh is not None:
                    # Получаем мировую трансформацию entity с учётом scale
                    world_matrix = entity.model_matrix()
                    # Преобразуем в локальную систему координат корневого entity
                    local_matrix = root_transform_inv @ world_matrix
                    result.append((mesh_drawable.mesh, local_matrix))
                break  # Только один MeshRenderer на entity

        # Рекурсивно обходим детей (если нужно)
        if recurse:
            for child in entity.transform.children:
                if child.entity is not None:
                    result.extend(self._collect_meshes_from_entity(child.entity, root_transform_inv, recurse=True))

        return result

    def _create_combined_mesh(
        self,
        meshes: List[tuple["Mesh3", np.ndarray]],
    ) -> Optional["Mesh3"]:
        """
        Объединить несколько мешей в один с применением трансформаций.

        Args:
            meshes: Список (mesh, transform_matrix)

        Returns:
            Объединённый меш или None если нет данных
        """
        if not meshes:
            return None

        all_vertices = []
        all_indices = []
        all_normals = []
        vertex_offset = 0

        for mesh, transform in meshes:
            vertices = mesh.vertices
            triangles = mesh.triangles
            normals = mesh.vertex_normals

            if vertices is None or len(vertices) == 0:
                continue

            # Применяем трансформацию к вершинам
            # transform - матрица 4x4
            ones = np.ones((len(vertices), 1), dtype=np.float32)
            vertices_h = np.hstack([vertices, ones])  # Nx4
            transformed = (transform @ vertices_h.T).T[:, :3]  # Nx3
            all_vertices.append(transformed.astype(np.float32))

            # Применяем трансформацию к нормалям (только вращение, без переноса)
            if normals is not None and len(normals) > 0:
                # Нормали трансформируются обратно-транспонированной матрицей
                # Но для uniform scale достаточно просто вращения
                rotation = transform[:3, :3]
                # Нормализуем после трансформации (на случай non-uniform scale)
                transformed_normals = (rotation @ normals.T).T
                norms = np.linalg.norm(transformed_normals, axis=1, keepdims=True)
                norms[norms == 0] = 1  # Избегаем деления на 0
                transformed_normals = transformed_normals / norms
                all_normals.append(transformed_normals.astype(np.float32))

            # Смещаем индексы треугольников
            if triangles is not None and len(triangles) > 0:
                all_indices.append(triangles + vertex_offset)
                vertex_offset += len(vertices)

        if not all_vertices:
            return None

        combined_vertices = np.vstack(all_vertices)
        combined_triangles = np.vstack(all_indices) if all_indices else None
        combined_normals = np.vstack(all_normals) if all_normals else None

        return Mesh3(
            vertices=combined_vertices,
            triangles=combined_triangles.astype(np.uint32) if combined_triangles is not None else None,
            vertex_normals=combined_normals,
        )

    def voxelize(self) -> bool:
        """
        Вокселизировать меш entity, зарегистрировать в ResourceManager и сохранить в файл.

        Returns:
            True если успешно, False если ошибка.
        """
        from termin.visualization.core.resources import ResourceManager
        from termin.voxels.grid import VoxelGrid
        from termin.voxels.voxelizer import VOXEL_SOLID
        from termin.voxels.persistence import VoxelPersistence
        from termin.voxels.native_voxelizer import voxelize_mesh_native

        print("VoxelizerComponent: starting voxelization")
        if self.entity is None:
            print("VoxelizerComponent: no entity")
            return False

        # Получаем обратную матрицу корневого entity для перевода в локальные координаты
        # model_matrix() включает position, rotation и scale
        root_world = self.entity.model_matrix()
        root_inv = np.linalg.inv(root_world)

        # Собираем меши в зависимости от режима
        recurse = (self.voxelize_source == VoxelizeSource.ALL_DESCENDANTS)
        meshes = self._collect_meshes_from_entity(self.entity, root_inv, recurse=recurse)

        if not meshes:
            print("VoxelizerComponent: no meshes found")
            return False

        if len(meshes) > 1:
            print(f"VoxelizerComponent: found {len(meshes)} meshes")

        mesh = self._create_combined_mesh(meshes)
        if mesh is None:
            print("VoxelizerComponent: failed to create mesh")
            return False

        # Определяем имя сетки
        name = self.grid_name.strip()
        if not name:
            name = self.entity.name or "voxel_grid"

        # Определяем путь для сохранения
        output = self.output_path.strip()
        if not output:
            output = f"{name}.voxels"

        if not output.endswith(".voxels"):
            output += ".voxels"

        # Создаём пустую сетку
        grid = VoxelGrid(origin=(0, 0, 0), cell_size=self.cell_size, name=name)

        mode = self.voxelize_mode

        if mode == VoxelizeMode.FULL_GRID:
            # Режим заполнения всей сетки — вычисляем bounds меша и заполняем
            vertices = mesh.vertices
            if vertices is None or len(vertices) == 0:
                print("VoxelizerComponent: mesh has no vertices")
                return False

            mesh_min = vertices.min(axis=0)
            mesh_max = vertices.max(axis=0)

            # Преобразуем в индексы вокселей
            voxel_min = grid.world_to_voxel(mesh_min)
            voxel_max = grid.world_to_voxel(mesh_max)

            # Заполняем все воксели в bounds
            fill_count = 0
            for vx in range(voxel_min[0], voxel_max[0] + 1):
                for vy in range(voxel_min[1], voxel_max[1] + 1):
                    for vz in range(voxel_min[2], voxel_max[2] + 1):
                        grid.set(vx, vy, vz, VOXEL_SOLID)
                        fill_count += 1
            print(f"VoxelizerComponent: filled {fill_count} voxels in bounds")
        else:
            # C++ native voxelization
            grid = voxelize_mesh_native(
                mesh,
                cell_size=self.cell_size,
                fill_interior=(mode >= VoxelizeMode.FILLED),
                mark_surface=(mode >= VoxelizeMode.MARKED),
                clear_interior=(mode >= VoxelizeMode.SURFACE_ONLY),
                compute_normals=(mode >= VoxelizeMode.WITH_NORMALS),
            )
            grid.name = name

        self._last_voxel_count = grid.voxel_count

        # Сохраняем в файл
        rm = ResourceManager.instance()
        try:
            output_path = Path(output)

            # Если путь относительный, разрешаем относительно директории проекта
            if not output_path.is_absolute():
                from termin.editor.project_browser import ProjectBrowser
                project_root = ProjectBrowser.current_project_path
                if project_root is not None:
                    output_path = project_root / output_path

            # Создаём директорию если не существует
            if output_path.parent and not output_path.parent.exists():
                output_path.parent.mkdir(parents=True, exist_ok=True)

            VoxelPersistence.save(grid, output_path)
            print(f"VoxelizerComponent: saved to {output_path.absolute()}")

            # Регистрируем в ResourceManager по имени файла (не внутреннему имени грида)
            asset_name = output_path.stem
            rm.register_voxel_grid(asset_name, grid)
            print(f"VoxelizerComponent: registered '{asset_name}' with {grid.voxel_count} voxels")

            # Mark asset as just saved to prevent hot-reload from file watcher
            asset = rm.get_voxel_grid_asset(asset_name)
            if asset is not None:
                asset.mark_just_saved()

            return True
        except Exception as e:
            print(f"VoxelizerComponent: failed to save: {e}")
            return False

    def build_navmesh(self) -> bool:
        """
        Построить NavMesh из воксельной сетки.

        Требует предварительной вокселизации с нормалями (режим WITH_NORMALS).

        Returns:
            True если успешно, False если ошибка.
        """
        from termin.visualization.core.resources import ResourceManager
        from termin.navmesh import PolygonBuilder, NavMeshConfig
        from termin.navmesh.persistence import NavMeshPersistence

        # Определяем имя сетки
        name = self.grid_name.strip()
        if not name:
            if self.entity is not None:
                name = self.entity.name or "voxel_grid"
            else:
                name = "voxel_grid"

        # Получаем воксельную сетку из ResourceManager
        rm = ResourceManager.instance()
        grid = rm.get_voxel_grid(name)

        if grid is None:
            print(f"VoxelizerComponent: voxel grid '{name}' not found. Run Voxelize first.")
            return False

        if not grid.surface_normals:
            print("VoxelizerComponent: voxel grid has no surface normals. Use WITH_NORMALS mode.")
            return False

        # Строим NavMesh
        # Конвертируем угол в косинус для threshold
        import math
        normal_threshold = math.cos(math.radians(self.normal_angle))

        config = NavMeshConfig(
            normal_threshold=normal_threshold,
            contour_epsilon=self.contour_epsilon,
        )
        builder = PolygonBuilder(config)

        # Выбираем стадию алгоритма
        stage = self.navmesh_stage
        stitch_polygons = stage >= NavMeshStage.STITCHED
        extract_contours = stage >= NavMeshStage.WITH_CONTOURS
        simplify_contours = stage >= NavMeshStage.SIMPLIFIED
        retriangulate = stage >= NavMeshStage.FINAL

        navmesh = builder.build(
            grid,
            expand_regions=self.expand_regions,  # Из чекбокса
            share_boundary=self.share_boundary,  # Из чекбокса
            project_contours=self.project_contours,  # Из чекбокса
            stitch_contours=self.stitch_contours,  # Из чекбокса
            stitch_polygons=stitch_polygons,
            extract_contours=extract_contours,
            simplify_contours=simplify_contours,
            retriangulate=retriangulate,
        )

        # Сохраняем регионы и grid для отладочной визуализации
        self._debug_regions = builder._last_regions
        self._debug_boundary_voxels = builder._last_boundary_voxels
        self._debug_grid = grid
        print(f"VoxelizerComponent: saved {len(self._debug_regions)} regions for debug")

        # Перестраиваем отладочный меш
        self._rebuild_debug_mesh()

        print(f"VoxelizerComponent: built NavMesh (stage {stage.name}) with {navmesh.polygon_count()} polygons, {navmesh.triangle_count()} triangles")

        # Определяем путь для сохранения
        output = self.navmesh_output_path.strip()
        if not output:
            output = f"{name}.navmesh"

        if not output.endswith(".navmesh"):
            output += ".navmesh"

        # Устанавливаем имя navmesh (такое же как у voxel grid)
        navmesh.name = name

        # Регистрируем в ResourceManager
        rm.register_navmesh(name, navmesh)
        print(f"VoxelizerComponent: registered NavMesh '{name}'")

        # Сохраняем в файл
        try:
            output_path = Path(output)

            # Если путь относительный, разрешаем относительно директории проекта
            if not output_path.is_absolute():
                from termin.editor.project_browser import ProjectBrowser
                project_root = ProjectBrowser.current_project_path
                if project_root is not None:
                    output_path = project_root / output_path

            # Создаём директорию если не существует
            if output_path.parent and not output_path.parent.exists():
                output_path.parent.mkdir(parents=True, exist_ok=True)

            NavMeshPersistence.save(navmesh, output_path)
            print(f"VoxelizerComponent: saved NavMesh to {output_path.absolute()}")

            # Mark asset as just saved to prevent hot-reload
            asset_name = output_path.stem
            asset = rm.get_navmesh_asset(asset_name)
            if asset is not None:
                asset.mark_just_saved()

            return True
        except Exception as e:
            print(f"VoxelizerComponent: failed to save NavMesh: {e}")
            return False

    def _rebuild_debug_mesh(self) -> None:
        """Перестроить отладочный меш для всех регионов."""
        from termin.voxels.display_component import (
            _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS,
            VERTS_PER_CUBE, TRIS_PER_CUBE, CUBE_SCALE,
        )
        from termin.voxels.voxel_mesh import VoxelMesh
        import random

        # Очищаем старые handles
        if self._debug_mesh_handle is not None:
            self._debug_mesh_handle.delete()
            self._debug_mesh_handle = None
        if self._debug_contours_handle is not None:
            self._debug_contours_handle.delete()
            self._debug_contours_handle = None
        if self._debug_multi_normal_handle is not None:
            self._debug_multi_normal_handle.delete()
            self._debug_multi_normal_handle = None
        if self._debug_boundary_handle is not None:
            self._debug_boundary_handle.delete()
            self._debug_boundary_handle = None

        if not self._debug_regions or self._debug_grid is None:
            return

        grid = self._debug_grid
        cell_size = grid.cell_size
        cube_size = cell_size * CUBE_SCALE

        # Считаем общее количество вокселей
        total_voxels = sum(len(voxels) for voxels, _ in self._debug_regions)
        if total_voxels == 0:
            return

        # Выделяем массивы
        vertices = np.zeros((total_voxels * VERTS_PER_CUBE, 3), dtype=np.float32)
        triangles = np.zeros((total_voxels * TRIS_PER_CUBE, 3), dtype=np.int32)
        normals = np.zeros((total_voxels * VERTS_PER_CUBE, 3), dtype=np.float32)
        uvs = np.zeros((total_voxels * VERTS_PER_CUBE, 2), dtype=np.float32)
        colors = np.zeros((total_voxels * VERTS_PER_CUBE, 3), dtype=np.float32)

        # Вычисляем bounds
        min_world = np.array([float('inf'), float('inf'), float('inf')], dtype=np.float32)
        max_world = np.array([float('-inf'), float('-inf'), float('-inf')], dtype=np.float32)

        # Генерируем яркие цвета для регионов через HSV
        # H = случайный, S = высокая насыщенность, V = высокая яркость
        import colorsys
        random.seed(42)  # Фиксированный seed для воспроизводимости
        region_colors = []
        for _ in self._debug_regions:
            h = random.random()  # Полный диапазон оттенков
            s = random.random() * 0.3 + 0.7  # Насыщенность [0.7, 1.0]
            v = random.random() * 0.2 + 0.8  # Яркость [0.8, 1.0]
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            region_colors.append((r, g, b))

        voxel_idx = 0
        for region_idx, (region_voxels, region_normal) in enumerate(self._debug_regions):
            region_color = region_colors[region_idx]

            for vx, vy, vz in region_voxels:
                center = grid.voxel_to_world(vx, vy, vz)
                min_world = np.minimum(min_world, center)
                max_world = np.maximum(max_world, center)

                v_offset = voxel_idx * VERTS_PER_CUBE
                t_offset = voxel_idx * TRIS_PER_CUBE

                vertices[v_offset:v_offset + VERTS_PER_CUBE] = (
                    _CUBE_VERTICES * cube_size + center
                )
                triangles[t_offset:t_offset + TRIS_PER_CUBE] = (
                    _CUBE_TRIANGLES + v_offset
                )
                normals[v_offset:v_offset + VERTS_PER_CUBE] = _CUBE_NORMALS
                # UV.x = 2.0 (VOXEL_SURFACE) чтобы шейдер использовал vertex color
                uvs[v_offset:v_offset + VERTS_PER_CUBE, 0] = 2.0
                colors[v_offset:v_offset + VERTS_PER_CUBE] = region_color

                voxel_idx += 1

        # Расширяем bounds на половину куба
        half_cube = cube_size * 0.5
        self._debug_bounds_min = min_world - half_cube
        self._debug_bounds_max = max_world + half_cube

        mesh = VoxelMesh(vertices=vertices, triangles=triangles, uvs=uvs, vertex_colors=colors)
        mesh.vertex_normals = normals
        self._debug_mesh_handle = MeshHandle.from_mesh3(mesh, name="voxelizer_debug_mesh")

        # Строим контуры для всех регионов
        self._build_debug_contours(grid, region_colors)

        # Строим меш для вокселей с несколькими нормалями
        self._build_debug_multi_normal(grid, cube_size, _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS, VERTS_PER_CUBE, TRIS_PER_CUBE)

        # Строим меш для граничных вокселей
        self._build_debug_boundary(grid, cube_size, _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS, VERTS_PER_CUBE, TRIS_PER_CUBE)

        print(f"VoxelizerComponent: debug mesh built for {len(self._debug_regions)} regions ({total_voxels} voxels)")

    def _build_debug_contours(
        self,
        grid: "VoxelGrid",
        region_colors: list[tuple[float, float, float]],
    ) -> None:
        """Построить контуры для всех регионов с vertex colors."""
        from termin.navmesh.polygon_builder import PolygonBuilder
        from termin.navmesh.display_component import _build_line_ribbon
        from termin.voxels.voxel_mesh import VoxelMesh

        builder = PolygonBuilder()
        contour_width = grid.cell_size * 0.15

        # Для сшивки контуров: строим mapping и плоскости
        voxel_to_regions: dict[tuple[int, int, int], list[int]] = {}
        region_planes: list[tuple[np.ndarray, np.ndarray]] = []

        if self.stitch_contours:
            for region_idx, (region_voxels, _) in enumerate(self._debug_regions):
                for voxel in region_voxels:
                    if voxel not in voxel_to_regions:
                        voxel_to_regions[voxel] = []
                    voxel_to_regions[voxel].append(region_idx)

            for region_voxels, region_normal in self._debug_regions:
                centers_3d = np.array([
                    grid.voxel_to_world(vx, vy, vz)
                    for vx, vy, vz in region_voxels
                ], dtype=np.float32)
                centroid = centers_3d.mean(axis=0)
                region_planes.append((centroid, region_normal))

        all_vertices: list[np.ndarray] = []
        all_triangles: list[np.ndarray] = []
        all_colors: list[np.ndarray] = []
        vertex_offset = 0

        for region_idx, (region_voxels, region_normal) in enumerate(self._debug_regions):
            # Извлекаем контур с учётом настроек проекции/сшивки
            polygon = builder._extract_contour_from_voxels(
                region_voxels,
                region_normal,
                grid,
                region_idx=region_idx,
                project_contours=self.project_contours,
                stitch_contours=self.stitch_contours,
                voxel_to_regions=voxel_to_regions if self.stitch_contours else None,
                region_planes=region_planes if self.stitch_contours else None,
            )

            if polygon is None or polygon.outer_contour is None:
                continue

            outer = polygon.outer_contour
            verts = polygon.vertices.copy()

            if len(outer) < 2:
                continue

            # Строим ribbon для контура
            up_hint = np.array(region_normal, dtype=np.float32)
            points = [tuple(verts[idx]) for idx in outer]
            points.append(points[0])  # Замыкаем

            ribbon_verts, ribbon_tris = _build_line_ribbon(points, contour_width, up_hint)

            if len(ribbon_tris) == 0:
                continue

            # Добавляем вершины и треугольники
            all_vertices.append(ribbon_verts)
            all_triangles.append(ribbon_tris + vertex_offset)

            # Цвет для всех вершин этого контура
            region_color = region_colors[region_idx]
            contour_colors = np.full((len(ribbon_verts), 3), region_color, dtype=np.float32)
            all_colors.append(contour_colors)

            vertex_offset += len(ribbon_verts)

        if not all_vertices:
            return

        # Объединяем в один меш
        vertices = np.vstack(all_vertices).astype(np.float32)
        triangles = np.vstack(all_triangles).astype(np.int32)
        colors = np.vstack(all_colors).astype(np.float32)

        # Нормали и UV для совместимости с voxel шейдером
        normals = np.zeros_like(vertices)
        normals[:, 2] = 1.0  # Вверх по Z
        uvs = np.full((len(vertices), 2), [2.0, 0.0], dtype=np.float32)  # UV.x = 2.0 для vertex color

        mesh = VoxelMesh(vertices=vertices, triangles=triangles, uvs=uvs, vertex_colors=colors)
        mesh.vertex_normals = normals
        self._debug_contours_handle = MeshHandle.from_mesh3(mesh, name="voxelizer_debug_contours")

    def _build_debug_multi_normal(
        self,
        grid: "VoxelGrid",
        cube_size: float,
        cube_vertices: np.ndarray,
        cube_triangles: np.ndarray,
        cube_normals: np.ndarray,
        verts_per_cube: int,
        tris_per_cube: int,
    ) -> None:
        """Построить меш для вокселей с несколькими нормалями."""
        from termin.voxels.voxel_mesh import VoxelMesh

        # Собираем воксели с более чем одной нормалью
        multi_normal_voxels: list[tuple[int, int, int]] = []
        for coord, normals_list in grid.surface_normals.items():
            if len(normals_list) > 1:
                multi_normal_voxels.append(coord)

        if not multi_normal_voxels:
            return

        count = len(multi_normal_voxels)
        vertices = np.zeros((count * verts_per_cube, 3), dtype=np.float32)
        triangles = np.zeros((count * tris_per_cube, 3), dtype=np.int32)
        normals = np.zeros((count * verts_per_cube, 3), dtype=np.float32)
        uvs = np.zeros((count * verts_per_cube, 2), dtype=np.float32)
        colors = np.zeros((count * verts_per_cube, 3), dtype=np.float32)

        # Яркий цвет для multi-normal вокселей (красный/магента)
        multi_color = (1.0, 0.2, 0.5)

        for i, (vx, vy, vz) in enumerate(multi_normal_voxels):
            center = grid.voxel_to_world(vx, vy, vz)

            v_offset = i * verts_per_cube
            t_offset = i * tris_per_cube

            vertices[v_offset:v_offset + verts_per_cube] = cube_vertices * cube_size + center
            triangles[t_offset:t_offset + tris_per_cube] = cube_triangles + v_offset
            normals[v_offset:v_offset + verts_per_cube] = cube_normals
            uvs[v_offset:v_offset + verts_per_cube, 0] = 2.0  # vertex color mode
            colors[v_offset:v_offset + verts_per_cube] = multi_color

        mesh = VoxelMesh(vertices=vertices, triangles=triangles, uvs=uvs, vertex_colors=colors)
        mesh.vertex_normals = normals
        self._debug_multi_normal_handle = MeshHandle.from_mesh3(mesh, name="voxelizer_debug_multi_normal")

        print(f"VoxelizerComponent: {count} voxels with multiple normals")

    def _build_debug_boundary(
        self,
        grid: "VoxelGrid",
        cube_size: float,
        cube_vertices: np.ndarray,
        cube_triangles: np.ndarray,
        cube_normals: np.ndarray,
        verts_per_cube: int,
        tris_per_cube: int,
    ) -> None:
        """Построить меш для граничных вокселей (общих между регионами)."""
        from termin.voxels.voxel_mesh import VoxelMesh

        if not self._debug_boundary_voxels:
            return

        count = len(self._debug_boundary_voxels)
        vertices = np.zeros((count * verts_per_cube, 3), dtype=np.float32)
        triangles = np.zeros((count * tris_per_cube, 3), dtype=np.int32)
        normals = np.zeros((count * verts_per_cube, 3), dtype=np.float32)
        uvs = np.zeros((count * verts_per_cube, 2), dtype=np.float32)
        colors = np.zeros((count * verts_per_cube, 3), dtype=np.float32)

        # Яркий жёлтый цвет для boundary вокселей
        boundary_color = (1.0, 1.0, 0.2)

        for i, (vx, vy, vz) in enumerate(self._debug_boundary_voxels):
            center = grid.voxel_to_world(vx, vy, vz)

            v_offset = i * verts_per_cube
            t_offset = i * tris_per_cube

            vertices[v_offset:v_offset + verts_per_cube] = cube_vertices * cube_size + center
            triangles[t_offset:t_offset + tris_per_cube] = cube_triangles + v_offset
            normals[v_offset:v_offset + verts_per_cube] = cube_normals
            uvs[v_offset:v_offset + verts_per_cube, 0] = 2.0  # vertex color mode
            colors[v_offset:v_offset + verts_per_cube] = boundary_color

        mesh = VoxelMesh(vertices=vertices, triangles=triangles, uvs=uvs, vertex_colors=colors)
        mesh.vertex_normals = normals
        self._debug_boundary_handle = MeshHandle.from_mesh3(mesh, name="voxelizer_debug_boundary")

        print(f"VoxelizerComponent: {count} boundary voxels")

    @classmethod
    def deserialize(cls, data: dict, context) -> "VoxelizerComponent":
        """Десериализовать компонент."""
        return cls(
            grid_name=data.get("grid_name", ""),
            cell_size=data.get("cell_size", 0.25),
            output_path=data.get("output_path", ""),
            voxelize_mode=VoxelizeMode(data.get("voxelize_mode", VoxelizeMode.SHELL)),
            navmesh_output_path=data.get("navmesh_output_path", ""),
            normal_angle=data.get("normal_angle", 25.0),
            expand_regions=data.get("expand_regions", False),
            navmesh_stage=NavMeshStage(data.get("navmesh_stage", NavMeshStage.REGIONS_BASIC)),
            contour_epsilon=data.get("contour_epsilon", 0.1),
            show_debug_voxels=data.get("show_debug_voxels", True),
            show_debug_contours=data.get("show_debug_contours", True),
            project_contours=data.get("project_contours", False),
            stitch_contours=data.get("stitch_contours", False),
            share_boundary=data.get("share_boundary", False),
            show_multi_normal_voxels=data.get("show_multi_normal_voxels", False),
            show_boundary_voxels=data.get("show_boundary_voxels", False),
        )
