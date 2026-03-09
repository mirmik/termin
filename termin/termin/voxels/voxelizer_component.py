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
from termin.mesh import TcMesh
from termin.mesh.mesh import Mesh3
from termin.voxels.voxel_mesh import create_voxel_mesh
from termin.visualization.render.drawable import GeometryDrawCall
from termin.editor.inspect_field import InspectField
from tcbase import log

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

    is_drawable = True

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
            is_serializable=False,
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
        "contour_simplify": InspectField(
            path="contour_simplify",
            label="Contour Simplify",
            kind="float",
            min=0.0,
            max=10.0,
            step=0.1,
        ),
        "max_edge_length": InspectField(
            path="max_edge_length",
            label="Max Edge Length",
            kind="float",
            min=0.0,
            max=10.0,
            step=0.1,
        ),
        "min_edge_length": InspectField(
            path="min_edge_length",
            label="Min Edge Length",
            kind="float",
            min=0.0,
            max=5.0,
            step=0.05,
        ),
        "min_contour_edge_length": InspectField(
            path="min_contour_edge_length",
            label="Min Contour Edge",
            kind="float",
            min=0.0,
            max=5.0,
            step=0.05,
        ),
        "max_vertex_valence": InspectField(
            path="max_vertex_valence",
            label="Max Vertex Valence",
            kind="int",
            min=0,
            max=20,
            step=1,
        ),
        "use_delaunay_flip": InspectField(
            path="use_delaunay_flip",
            label="Delaunay Flip",
            kind="bool",
        ),
        "use_valence_flip": InspectField(
            path="use_valence_flip",
            label="Valence Flip",
            kind="bool",
        ),
        "use_angle_flip": InspectField(
            path="use_angle_flip",
            label="Angle Flip",
            kind="bool",
        ),
        "use_cvt_smoothing": InspectField(
            path="use_cvt_smoothing",
            label="CVT Smoothing",
            kind="bool",
        ),
        "use_edge_collapse": InspectField(
            path="use_edge_collapse",
            label="Edge Collapse",
            kind="bool",
        ),
        "use_second_pass": InspectField(
            path="use_second_pass",
            label="Second Pass",
            kind="bool",
        ),
        "build_navmesh_btn": InspectField(
            label="Build NavMesh",
            kind="button",
            action=_build_navmesh_action,
            is_serializable=False,
        ),
        # --- Debug ---
        "show_region_voxels": InspectField(
            path="show_region_voxels",
            label="Show Regions",
            kind="bool",
        ),
        "show_sparse_boundary": InspectField(
            path="show_sparse_boundary",
            label="Show Sparse Boundary",
            kind="bool",
        ),
        "show_simplified_contours": InspectField(
            path="show_simplified_contours",
            label="Show Simplified Contours",
            kind="bool",
        ),
        "show_bridged_contours": InspectField(
            path="show_bridged_contours",
            label="Show Bridged Contours",
            kind="bool",
        ),
        "show_triangulated": InspectField(
            path="show_triangulated",
            label="Show Triangulated",
            kind="bool",
        ),
    }

    serializable_fields = [
        "grid_name", "cell_size", "output_path", "voxelize_mode", "voxelize_source",
        "navmesh_output_path", "normal_angle", "contour_simplify", "max_edge_length",
        "min_edge_length", "min_contour_edge_length", "max_vertex_valence",
        "use_delaunay_flip", "use_valence_flip", "use_angle_flip", "use_cvt_smoothing",
        "use_edge_collapse", "use_second_pass", "show_region_voxels", "show_sparse_boundary",
        "show_simplified_contours", "show_bridged_contours", "show_triangulated",
    ]

    def __init__(
        self,
        grid_name: str = "",
        cell_size: float = 0.25,
        output_path: str = "",
        voxelize_mode: VoxelizeMode = VoxelizeMode.SHELL,
        voxelize_source: VoxelizeSource = VoxelizeSource.CURRENT_MESH,
        navmesh_output_path: str = "",
        normal_angle: float = 25.0,
        contour_simplify: float = 0.0,
        max_edge_length: float = 0.0,
        min_edge_length: float = 0.0,
        min_contour_edge_length: float = 0.0,
        max_vertex_valence: int = 0,
        use_delaunay_flip: bool = True,
        use_valence_flip: bool = False,
        use_angle_flip: bool = False,
        use_cvt_smoothing: bool = False,
        use_edge_collapse: bool = False,
        use_second_pass: bool = False,
        show_region_voxels: bool = False,
        show_sparse_boundary: bool = False,
        show_simplified_contours: bool = False,
        show_bridged_contours: bool = False,
        show_triangulated: bool = False,
    ) -> None:
        super().__init__()
        self.grid_name = grid_name
        self.cell_size = cell_size
        self.output_path = output_path
        self.voxelize_mode = voxelize_mode
        self.voxelize_source = voxelize_source
        self.navmesh_output_path = navmesh_output_path
        self.normal_angle = normal_angle
        self.contour_simplify = contour_simplify
        self.max_edge_length = max_edge_length
        self.min_edge_length = min_edge_length
        self.min_contour_edge_length = min_contour_edge_length
        self.max_vertex_valence = max_vertex_valence
        self.use_delaunay_flip = use_delaunay_flip
        self.use_valence_flip = use_valence_flip
        self.use_angle_flip = use_angle_flip
        self.use_cvt_smoothing = use_cvt_smoothing
        self.use_edge_collapse = use_edge_collapse
        self.use_second_pass = use_second_pass
        self._last_voxel_count: int = 0

        # Debug visualization
        self.show_region_voxels: bool = show_region_voxels
        self.show_sparse_boundary: bool = show_sparse_boundary
        self.show_simplified_contours: bool = show_simplified_contours
        self.show_bridged_contours: bool = show_bridged_contours
        self.show_triangulated: bool = show_triangulated
        self._debug_regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
        self._debug_grid: Optional["VoxelGrid"] = None
        self._debug_region_voxels_mesh: Optional[TcMesh] = None
        self._debug_sparse_boundary_mesh: Optional[TcMesh] = None
        self._debug_inner_contour_mesh: Optional[TcMesh] = None
        self._debug_simplified_contours_mesh: Optional[TcMesh] = None
        self._debug_bridged_contours_mesh: Optional[TcMesh] = None
        self._debug_triangulated_mesh: Optional[TcMesh] = None
        self._debug_material: Optional[Material] = None
        self._debug_transparent_material: Optional[Material] = None
        self._debug_bounds_min: np.ndarray = np.zeros(3, dtype=np.float32)
        self._debug_bounds_max: np.ndarray = np.zeros(3, dtype=np.float32)

    # --- Drawable protocol ---

    # Константы для geometry_id
    GEOMETRY_REGIONS = 1
    GEOMETRY_SPARSE_BOUNDARY = 2
    GEOMETRY_INNER_CONTOUR = 3
    GEOMETRY_SIMPLIFIED_CONTOURS = 4
    GEOMETRY_BRIDGED_CONTOURS = 5
    GEOMETRY_TRIANGULATED = 6

    @property
    def phase_marks(self) -> Set[str]:
        """Фазы рендеринга для отладочной визуализации."""
        marks: Set[str] = set()
        if self.show_region_voxels:
            mat = self._get_or_create_debug_material()
            marks.update(p.phase_mark for p in mat.phases)
        if self.show_sparse_boundary:
            mat = self._get_or_create_debug_material()
            marks.update(p.phase_mark for p in mat.phases)
            # Inner contours render in transparent phase
            mat_trans = self._get_or_create_transparent_material()
            marks.update(p.phase_mark for p in mat_trans.phases)
        if self.show_simplified_contours:
            mat = self._get_or_create_line_material()
            marks.update(p.phase_mark for p in mat.phases)
        if self.show_bridged_contours:
            mat = self._get_or_create_line_material()
            marks.update(p.phase_mark for p in mat.phases)
        if self.show_triangulated:
            mat = self._get_or_create_line_material()
            marks.update(p.phase_mark for p in mat.phases)
        return marks

    def draw_geometry(self, context: "RenderContext", geometry_id: int = 0) -> None:
        """Рисует отладочную геометрию."""
        if geometry_id == 0 or geometry_id == self.GEOMETRY_REGIONS:
            if self.show_region_voxels and self._debug_region_voxels_mesh is not None and self._debug_region_voxels_mesh.is_valid:
                self._debug_region_voxels_mesh.draw_gpu()
        if geometry_id == 0 or geometry_id == self.GEOMETRY_SPARSE_BOUNDARY:
            if self.show_sparse_boundary and self._debug_sparse_boundary_mesh is not None and self._debug_sparse_boundary_mesh.is_valid:
                self._debug_sparse_boundary_mesh.draw_gpu()
        if geometry_id == 0 or geometry_id == self.GEOMETRY_INNER_CONTOUR:
            if self.show_sparse_boundary and self._debug_inner_contour_mesh is not None and self._debug_inner_contour_mesh.is_valid:
                self._debug_inner_contour_mesh.draw_gpu()
        if geometry_id == 0 or geometry_id == self.GEOMETRY_SIMPLIFIED_CONTOURS:
            if self.show_simplified_contours and self._debug_simplified_contours_mesh is not None and self._debug_simplified_contours_mesh.is_valid:
                self._debug_simplified_contours_mesh.draw_gpu()
        if geometry_id == 0 or geometry_id == self.GEOMETRY_BRIDGED_CONTOURS:
            if self.show_bridged_contours and self._debug_bridged_contours_mesh is not None and self._debug_bridged_contours_mesh.is_valid:
                self._debug_bridged_contours_mesh.draw_gpu()
        if geometry_id == 0 or geometry_id == self.GEOMETRY_TRIANGULATED:
            if self.show_triangulated and self._debug_triangulated_mesh is not None and self._debug_triangulated_mesh.is_valid:
                self._debug_triangulated_mesh.draw_gpu()

    def get_geometry_draws(self, phase_mark: str | None = None) -> List[GeometryDrawCall]:
        """Возвращает GeometryDrawCalls для отладочного рендеринга."""
        result: List[GeometryDrawCall] = []

        # Region voxels (цвета по регионам в vertex colors)
        if self.show_region_voxels and self._debug_region_voxels_mesh is not None and self._debug_region_voxels_mesh.is_valid:
            mat = self._get_or_create_debug_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            # Используем vertex colors (UV.x = 2.0)
            white_color = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
            for phase in phases:
                phase.set_param("u_color_below", white_color)
                phase.set_param("u_color_above", white_color)
                phase.set_param("u_color_surface", white_color)
                phase.set_param("u_slice_axis", np.array([0.0, 0.0, 1.0], dtype=np.float32))
                phase.set_param("u_fill_percent", 1.0)
                phase.set_param("u_bounds_min", self._debug_bounds_min)
                phase.set_param("u_bounds_max", self._debug_bounds_max)
                phase.set_param("u_ambient_color", np.array([1.0, 1.0, 1.0], dtype=np.float32))
                phase.set_param("u_ambient_intensity", 0.5)

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_REGIONS) for p in phases)

        # Sparse boundary (воксели с < 8 соседями в регионе)
        if self.show_sparse_boundary and self._debug_sparse_boundary_mesh is not None and self._debug_sparse_boundary_mesh.is_valid:
            mat = self._get_or_create_debug_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            # Используем vertex colors
            white_color = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
            for phase in phases:
                phase.set_param("u_color_below", white_color)
                phase.set_param("u_color_above", white_color)
                phase.set_param("u_color_surface", white_color)
                phase.set_param("u_slice_axis", np.array([0.0, 0.0, 1.0], dtype=np.float32))
                phase.set_param("u_fill_percent", 1.0)
                phase.set_param("u_bounds_min", self._debug_bounds_min)
                phase.set_param("u_bounds_max", self._debug_bounds_max)
                phase.set_param("u_ambient_color", np.array([1.0, 1.0, 1.0], dtype=np.float32))
                phase.set_param("u_ambient_intensity", 0.5)

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_SPARSE_BOUNDARY) for p in phases)

        # Inner contours (дырки) - рендерим в transparent фазе
        if self.show_sparse_boundary and self._debug_inner_contour_mesh is not None and self._debug_inner_contour_mesh.is_valid:
            mat = self._get_or_create_transparent_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            for phase in phases:
                phase.set_param("u_slice_axis", np.array([0.0, 0.0, 1.0], dtype=np.float32))
                phase.set_param("u_fill_percent", 1.0)
                phase.set_param("u_bounds_min", self._debug_bounds_min)
                phase.set_param("u_bounds_max", self._debug_bounds_max)
                phase.set_param("u_ambient_color", np.array([1.0, 1.0, 1.0], dtype=np.float32))
                phase.set_param("u_ambient_intensity", 0.5)

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_INNER_CONTOUR) for p in phases)

        # Simplified contours (после Douglas-Peucker)
        if self.show_simplified_contours and self._debug_simplified_contours_mesh is not None and self._debug_simplified_contours_mesh.is_valid:
            mat = self._get_or_create_line_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_SIMPLIFIED_CONTOURS) for p in phases)

        # Bridged contours (после merge_holes_with_bridges)
        if self.show_bridged_contours and self._debug_bridged_contours_mesh is not None and self._debug_bridged_contours_mesh.is_valid:
            mat = self._get_or_create_line_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_BRIDGED_CONTOURS) for p in phases)

        # Triangulated mesh (триангулированные полигоны)
        if self.show_triangulated and self._debug_triangulated_mesh is not None and self._debug_triangulated_mesh.is_valid:
            mat = self._get_or_create_line_material()
            if phase_mark is None:
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]

            phases.sort(key=lambda p: p.priority)
            result.extend(GeometryDrawCall(phase=p, geometry_id=self.GEOMETRY_TRIANGULATED) for p in phases)

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

    def _get_or_create_transparent_material(self) -> Material:
        """Создаёт материал для transparent рендеринга (внутренние контуры)."""
        if self._debug_transparent_material is None:
            from termin.voxels.voxel_shader import voxel_display_shader
            from termin.visualization.render.renderpass import RenderState

            shader = voxel_display_shader()
            self._debug_transparent_material = Material(
                shader=shader,
                color=(1.0, 0.5, 0.0, 0.5),  # Полупрозрачный
                phase_mark="transparent",
                render_state=RenderState(
                    depth_test=True,
                    depth_write=False,  # Не пишем в depth для transparent
                    blend=True,
                    cull=True,
                ),
            )
        return self._debug_transparent_material

    _debug_line_material: Optional[Material] = None

    def _get_or_create_line_material(self) -> Material:
        """Создаёт материал для отрисовки контурных линий."""
        if self._debug_line_material is None:
            from termin.visualization.render.renderpass import RenderState
            from tgfx import TcShader

            # Простой шейдер для линий с vertex colors
            vertex_source = """
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 5) in vec3 a_color;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_color;

void main() {
    v_color = a_color;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""
            fragment_source = """
#version 330 core

in vec3 v_color;

out vec4 FragColor;

void main() {
    FragColor = vec4(v_color, 1.0);
}
"""
            shader = TcShader.from_sources(
                vertex_source,
                fragment_source,
                "",
                "VoxelizerLine",
            )

            self._debug_line_material = Material(
                shader=shader,
                color=(1.0, 1.0, 0.0, 1.0),
                phase_mark="opaque",
                render_state=RenderState(
                    depth_test=True,
                    depth_write=True,
                    blend=False,
                    cull=False,
                ),
            )
        return self._debug_line_material

    def _collect_meshes_from_entity(
        self,
        entity,
        root_transform_inv: np.ndarray,
        recurse: bool = True,
    ) -> List[tuple["TcMesh", np.ndarray]]:
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

        result: List[tuple[TcMesh, np.ndarray]] = []

        # Проверяем MeshRenderer на текущем entity
        comp = entity.get_component(MeshRenderer)
        if comp is not None:
            mesh = comp.mesh
            if mesh is not None and mesh.is_valid:
                # Получаем мировую трансформацию entity с учётом scale
                world_matrix = entity.model_matrix()
                # Преобразуем в локальную систему координат корневого entity
                local_matrix = root_transform_inv @ world_matrix
                result.append((mesh, local_matrix))

        # Рекурсивно обходим детей (если нужно)
        if recurse:
            for child in entity.transform.children:
                if child.entity is not None:
                    result.extend(self._collect_meshes_from_entity(child.entity, root_transform_inv, recurse=True))

        return result

    def _create_combined_mesh(
        self,
        meshes: List[tuple["TcMesh", np.ndarray]],
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

        log.warning("VoxelizerComponent: starting voxelization")
        if self.entity is None:
            log.error("VoxelizerComponent: no entity")
            return False

        # Получаем обратную матрицу корневого entity для перевода в локальные координаты
        # model_matrix() включает position, rotation и scale
        root_world = self.entity.model_matrix()
        root_inv = np.linalg.inv(root_world)

        # Собираем меши в зависимости от режима
        recurse = (self.voxelize_source == VoxelizeSource.ALL_DESCENDANTS)
        meshes = self._collect_meshes_from_entity(self.entity, root_inv, recurse=recurse)

        if not meshes:
            log.error("VoxelizerComponent: no meshes found")
            return False

        if len(meshes) > 1:
            log.warning(f"VoxelizerComponent: found {len(meshes)} meshes")

        mesh = self._create_combined_mesh(meshes)
        if mesh is None:
            log.error("VoxelizerComponent: failed to create mesh")
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
                log.error("VoxelizerComponent: mesh has no vertices")
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
            log.warning(f"VoxelizerComponent: filled {fill_count} voxels in bounds")
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

        # Сохраняем grid для отладочного отображения
        self._debug_grid = grid
        self._rebuild_voxel_display_mesh()

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
            log.warning(f"VoxelizerComponent: saved to {output_path.absolute()}")

            return True
        except Exception as e:
            log.error(f"VoxelizerComponent: failed to save: {e}")
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
            log.error(f"VoxelizerComponent: voxel grid '{name}' not found. Run Voxelize first.")
            return False

        if not grid.surface_normals:
            log.error("VoxelizerComponent: voxel grid has no surface normals. Use WITH_NORMALS mode.")
            return False

        # Строим NavMesh
        # Конвертируем угол в косинус для threshold
        import math
        normal_threshold = math.cos(math.radians(self.normal_angle))

        # Используем contour_simplify как epsilon для Douglas-Peucker
        contour_epsilon = self.contour_simplify * grid.cell_size

        config = NavMeshConfig(
            normal_threshold=normal_threshold,
            contour_epsilon=contour_epsilon,
            max_edge_length=self.max_edge_length,
            min_edge_length=self.min_edge_length,
            min_contour_edge_length=self.min_contour_edge_length,
            max_vertex_valence=self.max_vertex_valence,
            use_delaunay_flip=self.use_delaunay_flip,
            use_valence_flip=self.use_valence_flip,
            use_angle_flip=self.use_angle_flip,
            use_cvt_smoothing=self.use_cvt_smoothing,
            use_edge_collapse=self.use_edge_collapse,
            use_second_pass=self.use_second_pass,
        )
        builder = PolygonBuilder(config)

        # Строим NavMesh
        navmesh = builder.build(
            grid,
            do_expand_regions=False,
            share_boundary=False,
            project_contours=False,
            stitch_contours=False,
        )

        # Сохраняем регионы и grid для отладочной визуализации
        self._debug_regions = builder._last_regions
        self._debug_grid = grid
        log.warning(f"VoxelizerComponent: saved {len(self._debug_regions)} regions for debug")

        # Перестраиваем отладочный меш
        self._rebuild_debug_mesh()

        # Строим отладочный меш из NavMesh
        self._build_debug_mesh_from_navmesh(navmesh)

        log.warning(f"VoxelizerComponent: built NavMesh with {navmesh.polygon_count()} polygons, {navmesh.triangle_count()} triangles")

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
        log.warning(f"VoxelizerComponent: registered NavMesh '{name}'")

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
            log.warning(f"VoxelizerComponent: saved NavMesh to {output_path.absolute()}")

            return True
        except Exception as e:
            log.error(f"VoxelizerComponent: failed to save NavMesh: {e}")
            return False

    def _rebuild_voxel_display_mesh(self) -> None:
        """Перестроить меш для отображения вокселей (после voxelize)."""
        from termin.voxels.display_component import (
            _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS,
            VERTS_PER_CUBE, TRIS_PER_CUBE, CUBE_SCALE,
        )

        # Очищаем старый меш
        self._debug_mesh = None

        if self._debug_grid is None:
            return

        grid = self._debug_grid
        voxel_count = grid.voxel_count
        if voxel_count == 0:
            return

        cell_size = grid.cell_size
        cube_size = cell_size * CUBE_SCALE

        # Собираем все воксели
        all_voxels: list[tuple[int, int, int, int]] = list(grid.iter_non_empty())
        if not all_voxels:
            return

        # Вычисляем bounds
        min_world = np.array([float('inf'), float('inf'), float('inf')], dtype=np.float32)
        max_world = np.array([float('-inf'), float('-inf'), float('-inf')], dtype=np.float32)

        for vx, vy, vz, _ in all_voxels:
            center = grid.voxel_to_world(vx, vy, vz)
            min_world = np.minimum(min_world, center)
            max_world = np.maximum(max_world, center)

        half_cube = cube_size * 0.5
        self._debug_bounds_min = min_world - half_cube
        self._debug_bounds_max = max_world + half_cube

        # Выделяем массивы
        count = len(all_voxels)
        vertices = np.zeros((count * VERTS_PER_CUBE, 3), dtype=np.float32)
        triangles = np.zeros((count * TRIS_PER_CUBE, 3), dtype=np.int32)
        normals = np.zeros((count * VERTS_PER_CUBE, 3), dtype=np.float32)
        uvs = np.zeros((count * VERTS_PER_CUBE, 2), dtype=np.float32)
        colors = np.ones((count * VERTS_PER_CUBE, 3), dtype=np.float32)

        surface_normals = grid.surface_normals

        for i, (vx, vy, vz, vtype) in enumerate(all_voxels):
            center = grid.voxel_to_world(vx, vy, vz)

            v_offset = i * VERTS_PER_CUBE
            t_offset = i * TRIS_PER_CUBE

            vertices[v_offset:v_offset + VERTS_PER_CUBE] = _CUBE_VERTICES * cube_size + center
            triangles[t_offset:t_offset + TRIS_PER_CUBE] = _CUBE_TRIANGLES + v_offset
            normals[v_offset:v_offset + VERTS_PER_CUBE] = _CUBE_NORMALS
            uvs[v_offset:v_offset + VERTS_PER_CUBE, 0] = float(vtype)

            # Кодируем нормаль в цвет если есть
            normals_list = surface_normals.get((vx, vy, vz))
            if normals_list and len(normals_list) > 0:
                first_normal = normals_list[0]
                encoded_color = (first_normal + 1.0) * 0.5
                colors[v_offset:v_offset + VERTS_PER_CUBE] = encoded_color

        self._debug_mesh = create_voxel_mesh(
            vertices=vertices,
            triangles=triangles,
            uvs=uvs,
            vertex_colors=colors,
            vertex_normals=normals,
            name="voxelizer_display_mesh",
        )

        log.warning(f"VoxelizerComponent: display mesh built ({count} voxels)")

    def _rebuild_debug_mesh(self) -> None:
        """Перестроить отладочные меши для регионов."""
        from termin.voxels.display_component import (
            _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS,
            VERTS_PER_CUBE, TRIS_PER_CUBE, CUBE_SCALE,
        )
        import random
        import colorsys

        # Очищаем debug meshes
        self._debug_region_voxels_mesh = None
        self._debug_sparse_boundary_mesh = None
        self._debug_inner_contour_mesh = None
        self._debug_simplified_contours_mesh = None
        self._debug_bridged_contours_mesh = None
        self._debug_triangulated_mesh = None

        if not self._debug_regions or self._debug_grid is None:
            return

        grid = self._debug_grid
        cell_size = grid.cell_size
        cube_size = cell_size * CUBE_SCALE

        # Генерируем яркие цвета для регионов через HSV
        random.seed(42)  # Фиксированный seed для воспроизводимости
        region_colors = []
        for _ in self._debug_regions:
            h = random.random()  # Полный диапазон оттенков
            s = random.random() * 0.3 + 0.7  # Насыщенность [0.7, 1.0]
            v = random.random() * 0.2 + 0.8  # Яркость [0.8, 1.0]
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            region_colors.append((r, g, b))

        # Строим меш для регионов (разные цвета)
        self._build_debug_region_voxels(grid, cube_size, _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS, VERTS_PER_CUBE, TRIS_PER_CUBE, region_colors)

        # Строим меш для sparse boundary (воксели с < 8 соседями в регионе)
        self._build_debug_sparse_boundary(grid, cube_size, _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS, VERTS_PER_CUBE, TRIS_PER_CUBE)

        # Строим контуры после упрощения (outer + holes)
        self._build_debug_simplified_contours(grid, region_colors)

        # Строим контуры после bridge (один полигон)
        self._build_debug_bridged_contours(grid, region_colors)

        total_voxels = sum(len(voxels) for voxels, _ in self._debug_regions)
        log.warning(f"VoxelizerComponent: debug mesh built for {len(self._debug_regions)} regions ({total_voxels} voxels)")

    def _build_debug_region_voxels(
        self,
        grid: "VoxelGrid",
        cube_size: float,
        cube_vertices: np.ndarray,
        cube_triangles: np.ndarray,
        cube_normals: np.ndarray,
        verts_per_cube: int,
        tris_per_cube: int,
        region_colors: list[tuple[float, float, float]],
    ) -> None:
        """Построить меш для отображения вокселей регионов разными цветами."""
        if not self._debug_regions:
            return

        # Считаем общее количество вокселей
        total_voxels = sum(len(voxels) for voxels, _ in self._debug_regions)
        if total_voxels == 0:
            return

        vertices = np.zeros((total_voxels * verts_per_cube, 3), dtype=np.float32)
        triangles = np.zeros((total_voxels * tris_per_cube, 3), dtype=np.int32)
        normals = np.zeros((total_voxels * verts_per_cube, 3), dtype=np.float32)
        uvs = np.zeros((total_voxels * verts_per_cube, 2), dtype=np.float32)
        colors = np.zeros((total_voxels * verts_per_cube, 3), dtype=np.float32)

        voxel_idx = 0
        for region_idx, (region_voxels, region_normal) in enumerate(self._debug_regions):
            region_color = region_colors[region_idx]

            for vx, vy, vz in region_voxels:
                center = grid.voxel_to_world(vx, vy, vz)

                v_offset = voxel_idx * verts_per_cube
                t_offset = voxel_idx * tris_per_cube

                vertices[v_offset:v_offset + verts_per_cube] = cube_vertices * cube_size + center
                triangles[t_offset:t_offset + tris_per_cube] = cube_triangles + v_offset
                normals[v_offset:v_offset + verts_per_cube] = cube_normals
                uvs[v_offset:v_offset + verts_per_cube, 0] = 2.0  # vertex color mode
                colors[v_offset:v_offset + verts_per_cube] = region_color

                voxel_idx += 1

        self._debug_region_voxels_mesh = create_voxel_mesh(
            vertices=vertices,
            triangles=triangles,
            uvs=uvs,
            vertex_colors=colors,
            vertex_normals=normals,
            name="voxelizer_debug_regions",
        )

        log.warning(f"VoxelizerComponent: region voxels mesh built ({total_voxels} voxels, {len(self._debug_regions)} regions)")

    def _build_debug_sparse_boundary(
        self,
        grid: "VoxelGrid",
        cube_size: float,
        cube_vertices: np.ndarray,
        cube_triangles: np.ndarray,
        cube_normals: np.ndarray,
        verts_per_cube: int,
        tris_per_cube: int,
    ) -> None:
        """Построить меши для внешних и внутренних контуров регионов."""
        if not self._debug_regions:
            return

        from termin.navmesh.polygon_builder import PolygonBuilder
        import colorsys
        import random
        random.seed(42)

        builder = PolygonBuilder()

        # Собираем воксели outer контуров и inner контуров отдельно
        outer_voxels: list[tuple[tuple[int, int, int], tuple[float, float, float]]] = []
        inner_voxels: list[tuple[tuple[int, int, int], tuple[float, float, float]]] = []

        for region_idx, (region_voxels, region_normal) in enumerate(self._debug_regions):
            # Генерируем цвет для региона
            h = random.random()
            s = random.random() * 0.3 + 0.7
            v = random.random() * 0.2 + 0.8
            region_color = colorsys.hsv_to_rgb(h, s, v)

            # Извлекаем контуры
            outer_contour, holes = builder.extract_contours_from_region(
                region_voxels,
                region_normal,
                grid.cell_size,
                grid.origin,
            )

            # Добавляем воксели outer контура
            for voxel in outer_contour:
                outer_voxels.append((voxel, region_color))

            # Добавляем воксели inner контуров (дырок)
            for hole in holes:
                for voxel in hole:
                    inner_voxels.append((voxel, region_color))

        # Строим меш для outer контуров
        if outer_voxels:
            count = len(outer_voxels)
            vertices = np.zeros((count * verts_per_cube, 3), dtype=np.float32)
            triangles = np.zeros((count * tris_per_cube, 3), dtype=np.int32)
            normals_arr = np.zeros((count * verts_per_cube, 3), dtype=np.float32)
            uvs = np.zeros((count * verts_per_cube, 2), dtype=np.float32)
            colors = np.zeros((count * verts_per_cube, 3), dtype=np.float32)

            for i, (voxel, color) in enumerate(outer_voxels):
                vx, vy, vz = voxel
                center = grid.voxel_to_world(vx, vy, vz)

                v_offset = i * verts_per_cube
                t_offset = i * tris_per_cube

                vertices[v_offset:v_offset + verts_per_cube] = cube_vertices * cube_size + center
                triangles[t_offset:t_offset + tris_per_cube] = cube_triangles + v_offset
                normals_arr[v_offset:v_offset + verts_per_cube] = cube_normals
                uvs[v_offset:v_offset + verts_per_cube, 0] = 2.0  # vertex color mode
                colors[v_offset:v_offset + verts_per_cube] = color

            self._debug_sparse_boundary_mesh = create_voxel_mesh(
                vertices=vertices,
                triangles=triangles,
                uvs=uvs,
                vertex_colors=colors,
                vertex_normals=normals_arr,
                name="voxelizer_debug_outer_contour",
            )
            log.warning(f"VoxelizerComponent: {count} outer contour voxels")
        else:
            self._debug_sparse_boundary_mesh = None

        # Строим меш для inner контуров (дырок) - полупрозрачный
        if inner_voxels:
            count = len(inner_voxels)
            vertices = np.zeros((count * verts_per_cube, 3), dtype=np.float32)
            triangles = np.zeros((count * tris_per_cube, 3), dtype=np.int32)
            normals_arr = np.zeros((count * verts_per_cube, 3), dtype=np.float32)
            uvs = np.zeros((count * verts_per_cube, 2), dtype=np.float32)
            colors = np.zeros((count * verts_per_cube, 3), dtype=np.float32)

            for i, (voxel, color) in enumerate(inner_voxels):
                vx, vy, vz = voxel
                center = grid.voxel_to_world(vx, vy, vz)

                v_offset = i * verts_per_cube
                t_offset = i * tris_per_cube

                vertices[v_offset:v_offset + verts_per_cube] = cube_vertices * cube_size + center
                triangles[t_offset:t_offset + tris_per_cube] = cube_triangles + v_offset
                normals_arr[v_offset:v_offset + verts_per_cube] = cube_normals
                uvs[v_offset:v_offset + verts_per_cube, 0] = 2.0  # vertex color mode
                # Делаем цвет немного темнее для inner контуров
                colors[v_offset:v_offset + verts_per_cube] = [c * 0.6 for c in color]

            self._debug_inner_contour_mesh = create_voxel_mesh(
                vertices=vertices,
                triangles=triangles,
                uvs=uvs,
                vertex_colors=colors,
                vertex_normals=normals_arr,
                name="voxelizer_debug_inner_contour",
            )
            log.warning(f"VoxelizerComponent: {count} inner contour voxels (holes)")
        else:
            self._debug_inner_contour_mesh = None

    def _build_debug_simplified_contours(
        self,
        grid: "VoxelGrid",
        region_colors: list[tuple[float, float, float]],
    ) -> None:
        """Построить линии контуров после Douglas-Peucker (outer + holes отдельно)."""
        from termin.navmesh.polygon_builder import PolygonBuilder
        from termin.navmesh.display_component import _build_line_ribbon

        if not self._debug_regions:
            return

        builder = PolygonBuilder()
        line_width = grid.cell_size * 0.1
        simplify_epsilon = self.contour_simplify * grid.cell_size

        all_vertices: list[np.ndarray] = []
        all_triangles: list[np.ndarray] = []
        all_colors: list[np.ndarray] = []
        vertex_offset = 0

        normal_offset = 0.15  # Смещение по нормали для видимости

        for region_idx, (region_voxels, region_normal) in enumerate(self._debug_regions):
            region_color = region_colors[region_idx]
            up_hint = np.array(region_normal, dtype=np.float32)
            offset_vec = up_hint * normal_offset

            # Получаем контуры на стадии "simplified"
            outer_3d, holes_3d = builder.get_region_contours(
                region_voxels,
                region_normal,
                grid.cell_size,
                np.array(grid.origin, dtype=np.float32),
                simplify_epsilon=simplify_epsilon,
                stage="simplified",
            )

            # Строим ribbon для outer контура
            if len(outer_3d) >= 3:
                points = [tuple(v) for v in outer_3d]
                points.append(points[0])  # Замыкаем

                ribbon_verts, ribbon_tris = _build_line_ribbon(points, line_width, up_hint)

                if len(ribbon_tris) > 0:
                    # Смещаем по нормали для видимости
                    ribbon_verts = ribbon_verts + offset_vec
                    all_vertices.append(ribbon_verts)
                    all_triangles.append(ribbon_tris + vertex_offset)
                    contour_colors = np.full((len(ribbon_verts), 3), region_color, dtype=np.float32)
                    all_colors.append(contour_colors)
                    vertex_offset += len(ribbon_verts)

            # Строим ribbons для дырок (более темные)
            for hole_3d in holes_3d:
                if len(hole_3d) < 3:
                    continue

                hole_points = [tuple(v) for v in hole_3d]
                hole_points.append(hole_points[0])  # Замыкаем

                hole_ribbon_verts, hole_ribbon_tris = _build_line_ribbon(hole_points, line_width, up_hint)

                if len(hole_ribbon_tris) > 0:
                    # Смещаем по нормали для видимости
                    hole_ribbon_verts = hole_ribbon_verts + offset_vec
                    all_vertices.append(hole_ribbon_verts)
                    all_triangles.append(hole_ribbon_tris + vertex_offset)
                    # Дырки более тёмные
                    hole_colors = np.full((len(hole_ribbon_verts), 3), [c * 0.6 for c in region_color], dtype=np.float32)
                    all_colors.append(hole_colors)
                    vertex_offset += len(hole_ribbon_verts)

        if not all_vertices:
            self._debug_simplified_contours_mesh = None
            return

        # Объединяем в один меш
        vertices = np.vstack(all_vertices).astype(np.float32)
        triangles = np.vstack(all_triangles).astype(np.int32)
        colors = np.vstack(all_colors).astype(np.float32)

        self._debug_simplified_contours_mesh = create_voxel_mesh(
            vertices=vertices,
            triangles=triangles,
            uvs=np.zeros((len(vertices), 2), dtype=np.float32),
            vertex_colors=colors,
            vertex_normals=np.zeros_like(vertices),
            name="voxelizer_debug_simplified_contours",
        )

        log.warning(f"VoxelizerComponent: simplified contours built ({len(self._debug_regions)} regions, {len(vertices)} vertices)")

    def _build_debug_bridged_contours(
        self,
        grid: "VoxelGrid",
        region_colors: list[tuple[float, float, float]],
    ) -> None:
        """Построить линии контуров после bridge (один полигон, дырки слиты)."""
        from termin.navmesh.polygon_builder import PolygonBuilder
        from termin.navmesh.display_component import _build_line_ribbon

        if not self._debug_regions:
            return

        builder = PolygonBuilder()
        line_width = grid.cell_size * 0.1
        simplify_epsilon = self.contour_simplify * grid.cell_size

        all_vertices: list[np.ndarray] = []
        all_triangles: list[np.ndarray] = []
        all_colors: list[np.ndarray] = []
        vertex_offset = 0

        for region_idx, (region_voxels, region_normal) in enumerate(self._debug_regions):
            region_color = region_colors[region_idx]
            up_hint = np.array(region_normal, dtype=np.float32)

            # Получаем контуры на стадии "bridged"
            merged_3d, _ = builder.get_region_contours(
                region_voxels,
                region_normal,
                grid.cell_size,
                np.array(grid.origin, dtype=np.float32),
                simplify_epsilon=simplify_epsilon,
                stage="bridged",
            )

            # Строим ribbon для объединённого контура
            if len(merged_3d) >= 3:
                points = [tuple(v) for v in merged_3d]
                points.append(points[0])  # Замыкаем

                ribbon_verts, ribbon_tris = _build_line_ribbon(points, line_width, up_hint)

                if len(ribbon_tris) > 0:
                    all_vertices.append(ribbon_verts)
                    all_triangles.append(ribbon_tris + vertex_offset)
                    contour_colors = np.full((len(ribbon_verts), 3), region_color, dtype=np.float32)
                    all_colors.append(contour_colors)
                    vertex_offset += len(ribbon_verts)

        if not all_vertices:
            self._debug_bridged_contours_mesh = None
            return

        # Объединяем в один меш
        vertices = np.vstack(all_vertices).astype(np.float32)
        triangles = np.vstack(all_triangles).astype(np.int32)
        colors = np.vstack(all_colors).astype(np.float32)

        self._debug_bridged_contours_mesh = create_voxel_mesh(
            vertices=vertices,
            triangles=triangles,
            uvs=np.zeros((len(vertices), 2), dtype=np.float32),
            vertex_colors=colors,
            vertex_normals=np.zeros_like(vertices),
            name="voxelizer_debug_bridged_contours",
        )

        log.warning(f"VoxelizerComponent: bridged contours built ({len(self._debug_regions)} regions, {len(vertices)} vertices)")

    def _build_debug_mesh_from_navmesh(self, navmesh: "NavMesh") -> None:
        """Построить отладочный меш из готового NavMesh."""
        import colorsys

        all_vertices: list[np.ndarray] = []
        all_triangles: list[np.ndarray] = []
        all_colors: list[np.ndarray] = []
        vertex_offset = 0

        normal_offset = 0.15  # Смещение по нормали для видимости

        for poly_idx, polygon in enumerate(navmesh.polygons):
            if len(polygon.vertices) == 0 or len(polygon.triangles) == 0:
                continue

            # Цвет региона
            hue = (poly_idx * 0.618033988749895) % 1.0
            region_color = colorsys.hsv_to_rgb(hue, 0.7, 0.9)

            # Смещаем вершины по нормали для видимости
            offset_vertices = polygon.vertices + polygon.normal * normal_offset

            all_vertices.append(offset_vertices)
            all_triangles.append(polygon.triangles + vertex_offset)

            vertex_colors = np.full((len(polygon.vertices), 3), region_color, dtype=np.float32)
            all_colors.append(vertex_colors)

            vertex_offset += len(polygon.vertices)

        if not all_vertices:
            return

        vertices = np.vstack(all_vertices).astype(np.float32)
        triangles = np.vstack(all_triangles).astype(np.int32)
        colors = np.vstack(all_colors).astype(np.float32)

        # Вычисляем нормали
        normals = np.zeros_like(vertices)
        for tri in triangles:
            v0, v1, v2 = vertices[tri[0]], vertices[tri[1]], vertices[tri[2]]
            face_normal = np.cross(v1 - v0, v2 - v0)
            norm = np.linalg.norm(face_normal)
            if norm > 1e-10:
                face_normal = face_normal / norm
            normals[tri[0]] += face_normal
            normals[tri[1]] += face_normal
            normals[tri[2]] += face_normal

        for i in range(len(normals)):
            norm = np.linalg.norm(normals[i])
            if norm > 1e-10:
                normals[i] = normals[i] / norm

        self._debug_triangulated_mesh = create_voxel_mesh(
            vertices=vertices,
            triangles=triangles,
            uvs=np.full((len(vertices), 2), [2.0, 0.0], dtype=np.float32),
            vertex_colors=colors,
            vertex_normals=normals.astype(np.float32),
            name="voxelizer_debug_triangulated",
        )

        log.warning(f"VoxelizerComponent: triangulated mesh from NavMesh ({len(navmesh.polygons)} polygons, {len(vertices)} vertices, {len(triangles)} triangles)")

