"""
NavMeshDisplayComponent — компонент для отображения навигационной сетки.

Реализует протокол Drawable и рендерит NavMesh как меш.
Выбирает NavMesh из ResourceManager через комбобокс.
Использует TcNavMesh для поддержки hot-reload.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Set, Tuple

import numpy as np

from termin.render import DrawableComponent
from termin.materials import TcMaterial as Material
from termin.mesh import TcMesh
from termin.navmesh._navmesh_native import TcNavMesh
from termin.render.drawable import GeometryDrawCall
from termin.inspect import InspectField

if TYPE_CHECKING:
    from termin.render_framework import RenderContext
    from termin.navmesh.types import NavMesh


def _build_line_ribbon(
    points: list[tuple[float, float, float]],
    width: float,
    up_hint: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Build a simple camera-independent ribbon mesh for a 3D polyline."""
    if len(points) < 2 or width <= 0.0:
        return (
            np.zeros((0, 3), dtype=np.float32),
            np.zeros((0, 3), dtype=np.int32),
        )

    up = np.asarray(up_hint, dtype=np.float32)
    up_norm = float(np.linalg.norm(up))
    if up_norm < 1e-6:
        up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    else:
        up = up / up_norm

    vertices: list[np.ndarray] = []
    triangles: list[tuple[int, int, int]] = []
    half_width = width * 0.5

    for index in range(len(points) - 1):
        p0 = np.asarray(points[index], dtype=np.float32)
        p1 = np.asarray(points[index + 1], dtype=np.float32)
        direction = p1 - p0
        length = float(np.linalg.norm(direction))
        if length < 1e-6:
            continue
        direction = direction / length

        side = np.cross(up, direction)
        side_norm = float(np.linalg.norm(side))
        if side_norm < 1e-6:
            side = np.cross(np.array([1.0, 0.0, 0.0], dtype=np.float32), direction)
            side_norm = float(np.linalg.norm(side))
        if side_norm < 1e-6:
            side = np.cross(np.array([0.0, 1.0, 0.0], dtype=np.float32), direction)
            side_norm = float(np.linalg.norm(side))
        if side_norm < 1e-6:
            continue
        side = (side / side_norm) * half_width

        base = len(vertices)
        vertices.extend([p0 - side, p0 + side, p1 - side, p1 + side])
        triangles.append((base, base + 1, base + 2))
        triangles.append((base + 1, base + 3, base + 2))

    if not vertices:
        return (
            np.zeros((0, 3), dtype=np.float32),
            np.zeros((0, 3), dtype=np.int32),
        )

    return (
        np.vstack(vertices).astype(np.float32),
        np.asarray(triangles, dtype=np.int32),
    )


def _get_navmesh_choices() -> list[tuple[str, str]]:
    """Получить список NavMesh для комбобокса."""
    from tcbase import log
    from termin_assets import get_resource_manager

    rm = get_resource_manager()
    if rm is None:
        log.error("[NavMeshDisplayComponent] Resource manager is not configured")
        return []
    names = rm.list_navmesh_names()
    return [(name, name) for name in names]


class NavMeshDisplayComponent(DrawableComponent):
    """
    Компонент для отображения NavMesh из ResourceManager.

    Реализует протокол Drawable — рендерит NavMesh как меш.
    Выбирает сетку через комбобокс из зарегистрированных в ResourceManager.
    Использует TcNavMesh для поддержки hot-reload.
    """

    inspect_fields = {
        "navmesh": InspectField(
            path="navmesh",
            label="NavMesh",
            kind="navmesh_handle",
        ),
        "color": InspectField(
            path="color",
            label="Color",
            kind="color",
            setter=lambda obj, val: obj._set_color(val),
        ),
        "wireframe": InspectField(
            path="wireframe",
            label="Wireframe",
            kind="bool",
            setter=lambda obj, val: obj._set_wireframe(val),
        ),
        "show_normals": InspectField(
            path="show_normals",
            label="Show Normals",
            kind="bool",
        ),
        "show_contours": InspectField(
            path="show_contours",
            label="Show Contours",
            kind="bool",
            setter=lambda obj, val: obj._set_show_contours(val),
        ),
        "contour_width": InspectField(
            path="contour_width",
            label="Contour Width",
            kind="float",
            min=0.001,
            max=1.0,
            step=0.01,
            setter=lambda obj, val: obj._set_contour_width(val),
        ),
    }

    def __init__(self, navmesh_name: str = "") -> None:
        super().__init__()
        self._navmesh_name = navmesh_name
        self.navmesh: TcNavMesh = TcNavMesh()
        self._last_navmesh: Optional["NavMesh"] = None
        self._last_navmesh_version: int = -1
        self._mesh: Optional[TcMesh] = None
        self._contour_mesh: Optional[TcMesh] = None
        self._material: Optional[Material] = None
        self._contour_material: Optional[Material] = None
        self._needs_rebuild = True

        # Цвет с альфа-каналом (RGBA) — полупрозрачный зелёный
        self.color: Tuple[float, float, float, float] = (0.2, 0.8, 0.3, 0.7)

        # Режим отображения
        self.wireframe: bool = False
        self.show_normals: bool = False
        self.show_contours: bool = True
        self.contour_width: float = 0.05

        # Инициализируем handle если имя задано
        if navmesh_name:
            self.navmesh = TcNavMesh.from_name(navmesh_name)

    @property
    def navmesh_name(self) -> str:
        """Имя NavMesh."""
        return self._navmesh_name

    @navmesh_name.setter
    def navmesh_name(self, value: str) -> None:
        """Установить NavMesh по имени."""
        if value != self._navmesh_name:
            self._navmesh_name = value
            if value:
                self.navmesh = TcNavMesh.from_name(value)
            else:
                self.navmesh = TcNavMesh()
            self._needs_rebuild = True

    def _set_color(self, value: Tuple[float, float, float, float]) -> None:
        """Установить цвет."""
        self.color = value
        if self._material is not None:
            self._material.color = value

    def _set_wireframe(self, value: bool) -> None:
        """Установить режим wireframe."""
        self.wireframe = value
        # Пересоздаём материал с новым render_state
        self._material = None

    def _set_show_contours(self, value: bool) -> None:
        """Установить режим отображения контуров."""
        self.show_contours = value
        self._needs_rebuild = True

    def _set_contour_width(self, value: float) -> None:
        """Установить толщину контуров."""
        self.contour_width = value
        self._needs_rebuild = True

    def _get_or_create_material(self) -> Material:
        """Получить или создать материал."""
        if self._material is None:
            from tgfx import RenderState
            from termin.navmesh.navmesh_shader import navmesh_display_shader

            shader = navmesh_display_shader()

            self._material = Material(
                shader=shader,
                color=self.color,
                phase_mark="opaque",
                render_state=RenderState(
                    polygon_mode="line" if self.wireframe else "fill",
                    depth_test=True,
                    depth_write=True,
                    blend=True,
                    cull=False,  # Двухсторонний рендеринг для navmesh
                ),
            )
        return self._material

    def _get_or_create_contour_material(self) -> Material:
        """Получить или создать материал для контуров."""
        if self._contour_material is None:
            from tgfx import RenderState
            from tgfx import TcShader

            # Простой шейдер для линий
            vertex_source = """
#version 330 core

layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""
            fragment_source = """
#version 330 core

uniform vec4 u_color;

out vec4 FragColor;

void main() {
    FragColor = u_color;
}
"""
            shader = TcShader.from_sources(
                vertex_source,
                fragment_source,
                "",
                "NavMeshContour",
            )

            # Контуры — яркий контрастный цвет (жёлтый)
            contour_color = (1.0, 1.0, 0.0, 1.0)

            self._contour_material = Material(
                shader=shader,
                color=contour_color,
                phase_mark="opaque",
                render_state=RenderState(
                    depth_test=True,
                    depth_write=True,
                    blend=False,
                    cull=False,
                ),
            )
        return self._contour_material

    # --- Drawable protocol ---

    @property
    def phase_marks(self) -> Set[str]:
        """Фазы рендеринга."""
        mat = self._get_or_create_material()
        marks = {p.phase_mark for p in mat.phases}

        # Добавляем фазы контуров если включены
        if self.show_contours:
            contour_mat = self._get_or_create_contour_material()
            marks.update(p.phase_mark for p in contour_mat.phases)

        return marks

    # Константы для geometry_id
    GEOMETRY_MESH = 1
    GEOMETRY_CONTOURS = 2

    def draw_geometry(self, context: "RenderContext", _geometry_id: int = 0) -> None:
        """Рисует геометрию NavMesh."""
        self._check_hot_reload()

    def _check_hot_reload(self) -> None:
        """Проверяет, изменился ли navmesh в keeper (hot-reload)."""
        current_version = self.navmesh.version
        if self._needs_rebuild or current_version != self._last_navmesh_version:
            self._needs_rebuild = False
            self._last_navmesh_version = current_version
            self._rebuild_mesh()

    def get_geometry_draws(self, phase_mark: str | None = None) -> List[GeometryDrawCall]:
        """Возвращает GeometryDrawCalls для рендеринга."""
        result: List[GeometryDrawCall] = []

        # Основной меш
        mat = self._get_or_create_material()

        if phase_mark is None:
            phases = list(mat.phases)
        else:
            phases = [p for p in mat.phases if p.phase_mark == phase_mark]

        # Обновляем цвет
        for phase in phases:
            phase.uniforms["u_color"] = np.array(self.color, dtype=np.float32)

        phases.sort(key=lambda p: p.priority)

        # Добавляем основной меш
        for phase in phases:
            result.append(GeometryDrawCall(phase=phase, geometry_id=self.GEOMETRY_MESH))

        # Контуры (если включены и есть контурный mesh)
        if self.show_contours and self._contour_mesh is not None and self._contour_mesh.is_valid:
            contour_material = self._get_or_create_contour_material()
            if phase_mark is None:
                contour_phases = list(contour_material.phases)
            else:
                contour_phases = [p for p in contour_material.phases if p.phase_mark == phase_mark]

            contour_phases.sort(key=lambda p: p.priority)
            for phase in contour_phases:
                result.append(GeometryDrawCall(phase=phase, geometry_id=self.GEOMETRY_CONTOURS))

        return result

    # --- Построение меша ---

    def _rebuild_mesh(self) -> None:
        """Перестроить меш из NavMesh."""
        # Очищаем старые meshes
        self._mesh = None
        self._contour_mesh = None

        navmesh = self._get_navmesh_payload()
        self._last_navmesh = navmesh

        if navmesh is None or navmesh.polygon_count() == 0:
            return

        # Собираем все вершины и треугольники из полигонов
        all_vertices: list[np.ndarray] = []
        all_normals: list[np.ndarray] = []
        all_triangles: list[np.ndarray] = []
        vertex_offset = 0

        for polygon in navmesh.polygons:
            verts = polygon.vertices
            tris = polygon.triangles
            normal = polygon.normal

            if len(verts) == 0 or len(tris) == 0:
                continue

            # Добавляем вершины
            all_vertices.append(verts)

            # Нормали — одна на всю поверхность полигона
            poly_normals = np.tile(normal, (len(verts), 1))
            all_normals.append(poly_normals)

            # Сдвигаем индексы треугольников
            shifted_tris = tris + vertex_offset
            all_triangles.append(shifted_tris)

            vertex_offset += len(verts)

        # Строим меш если есть треугольники
        if all_vertices:
            from termin.voxels.voxel_mesh import create_voxel_mesh
            vertices = np.vstack(all_vertices).astype(np.float32)
            normals = np.vstack(all_normals).astype(np.float32)
            triangles = np.vstack(all_triangles).astype(np.int32)

            self._mesh = create_voxel_mesh(
                vertices=vertices,
                triangles=triangles,
                vertex_normals=normals,
                name="navmesh_display",
            )

        # Строим контуры (независимо от меша)
        self._build_contour_mesh(navmesh)

    def _get_navmesh_payload(self) -> "NavMesh | None":
        """Resolve legacy polygon payload for the selected canonical TcNavMesh."""
        if not self.navmesh.is_valid:
            return None
        self.navmesh.ensure_loaded()
        from termin_assets import get_resource_manager
        from tcbase import log

        rm = get_resource_manager()
        if rm is None:
            log.error("[NavMeshDisplayComponent] Resource manager is not configured")
            return None
        asset = rm.get_navmesh_asset_by_uuid(self.navmesh.uuid)
        if asset is None and self.navmesh.name:
            asset = rm.get_navmesh_asset(self.navmesh.name)
        if asset is None:
            log.error(f"[NavMeshDisplayComponent] NavMesh asset not found: {self.navmesh.uuid}")
            return None
        return asset.navmesh

    def _build_contour_mesh(self, navmesh: "NavMesh") -> None:
        """Построить drawable для контуров как ribbon (толстые линии)."""
        all_vertices = []
        all_triangles = []
        vertex_offset = 0

        for polygon in navmesh.polygons:
            if polygon.outer_contour is None:
                continue

            verts = polygon.vertices
            normal = polygon.normal
            # up_hint перпендикулярен плоскости полигона
            up_hint = np.array(normal, dtype=np.float32)

            # Внешний контур
            outer = polygon.outer_contour
            if len(outer) >= 2:
                # Замыкаем контур
                points = [tuple(verts[idx]) for idx in outer]
                points.append(points[0])  # замыкаем

                ribbon_verts, ribbon_tris = _build_line_ribbon(
                    points, self.contour_width, up_hint
                )
                if len(ribbon_tris) > 0:
                    all_vertices.append(ribbon_verts)
                    all_triangles.append(ribbon_tris + vertex_offset)
                    vertex_offset += len(ribbon_verts)

            # Дыры
            for hole in polygon.holes:
                if len(hole) >= 2:
                    points = [tuple(verts[idx]) for idx in hole]
                    points.append(points[0])  # замыкаем

                    ribbon_verts, ribbon_tris = _build_line_ribbon(
                        points, self.contour_width, up_hint
                    )
                    if len(ribbon_tris) > 0:
                        all_vertices.append(ribbon_verts)
                        all_triangles.append(ribbon_tris + vertex_offset)
                        vertex_offset += len(ribbon_verts)

        if not all_vertices:
            return

        # Объединяем все ribbon'ы в один меш
        from termin.voxels.voxel_mesh import create_voxel_mesh
        vertices = np.vstack(all_vertices).astype(np.float32)
        triangles = np.vstack(all_triangles).astype(np.int32)

        self._contour_mesh = create_voxel_mesh(
            vertices=vertices,
            triangles=triangles,
            name="navmesh_contours",
        )
