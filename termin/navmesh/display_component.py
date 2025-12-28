"""
NavMeshDisplayComponent — компонент для отображения навигационной сетки.

Реализует протокол Drawable и рендерит NavMesh как меш.
Выбирает NavMesh из ResourceManager через комбобокс.
Использует NavMeshHandle для поддержки hot-reload.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Set, Tuple

import numpy as np

from termin.visualization.core.python_component import PythonComponent
from termin.visualization.core.material import Material
from termin.visualization.core.mesh_handle import MeshHandle
from termin.visualization.core.navmesh_handle import NavMeshHandle
from termin.visualization.render.drawable import GeometryDrawCall
from termin.visualization.render.components.line_renderer import _build_line_ribbon
from termin.mesh.mesh import Mesh3
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.render.render_context import RenderContext
    from termin.navmesh.types import NavMesh


def _get_navmesh_choices() -> list[tuple[str, str]]:
    """Получить список NavMesh для комбобокса."""
    from termin.visualization.core.resources import ResourceManager
    rm = ResourceManager.instance()
    names = rm.list_navmesh_names()
    return [(name, name) for name in names]


class NavMeshDisplayComponent(PythonComponent):
    """
    Компонент для отображения NavMesh из ResourceManager.

    Реализует протокол Drawable — рендерит NavMesh как меш.
    Выбирает сетку через комбобокс из зарегистрированных в ResourceManager.
    Использует NavMeshHandle для поддержки hot-reload.
    """

    inspect_fields = {
        "navmesh": InspectField(
            path="navmesh",
            label="NavMesh",
            kind="navmesh",
            setter=lambda obj, val: obj._set_navmesh(val),
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
        self._navmesh_handle: NavMeshHandle = NavMeshHandle()
        self._last_navmesh: Optional["NavMesh"] = None
        self._mesh_handle: Optional[MeshHandle] = None
        self._contour_handle: Optional[MeshHandle] = None
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
            self._navmesh_handle = NavMeshHandle.from_name(navmesh_name)

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
                self._navmesh_handle = NavMeshHandle.from_name(value)
            else:
                self._navmesh_handle = NavMeshHandle()
            self._needs_rebuild = True

    def _set_navmesh(self, value: "NavMesh") -> None:
        """Установить NavMesh (объект или None)."""
        if value is None:
            self.navmesh_name = ""
        elif hasattr(value, "name"):
            self.navmesh_name = value.name
        else:
            self.navmesh_name = ""

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
            from termin.visualization.render.renderpass import RenderState
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
            from termin.visualization.render.renderpass import RenderState
            from termin.visualization.render.shader import ShaderProgram

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
            shader = ShaderProgram(
                vertex_source=vertex_source,
                fragment_source=fragment_source,
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

    @property
    def navmesh(self) -> Optional["NavMesh"]:
        """Текущий NavMesh (через handle)."""
        return self._navmesh_handle.get_navmesh()

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
    GEOMETRY_MESH = "mesh"
    GEOMETRY_CONTOURS = "contours"

    def draw_geometry(self, context: "RenderContext", geometry_id: str = "") -> None:
        """Рисует геометрию NavMesh."""
        self._check_hot_reload()

        if geometry_id == "" or geometry_id == self.GEOMETRY_MESH:
            if self._mesh_handle is not None:
                mesh_data = self._mesh_handle.mesh
                gpu = self._mesh_handle.gpu
                if mesh_data is not None and gpu is not None:
                    gpu.draw(context, mesh_data, self._mesh_handle.version)

        if geometry_id == self.GEOMETRY_CONTOURS:
            if self._contour_handle is not None:
                mesh_data = self._contour_handle.mesh
                gpu = self._contour_handle.gpu
                if mesh_data is not None and gpu is not None:
                    gpu.draw(context, mesh_data, self._contour_handle.version)

    def _check_hot_reload(self) -> None:
        """Проверяет, изменился ли navmesh в keeper (hot-reload)."""
        current = self._navmesh_handle.get_navmesh()
        if self._needs_rebuild or current is not self._last_navmesh:
            self._needs_rebuild = False
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

        # Контуры (если включены и есть контурный handle)
        if self.show_contours and self._contour_handle is not None:
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
        # Очищаем старый меш
        if self._mesh_handle is not None:
            self._mesh_handle.delete()
            self._mesh_handle = None

        if self._contour_handle is not None:
            self._contour_handle.delete()
            self._contour_handle = None

        navmesh = self._navmesh_handle.get_navmesh()
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
            vertices = np.vstack(all_vertices).astype(np.float32)
            normals = np.vstack(all_normals).astype(np.float32)
            triangles = np.vstack(all_triangles).astype(np.int32)

            mesh = Mesh3(vertices=vertices, triangles=triangles, normals=normals)
            self._mesh_handle = MeshHandle.from_mesh3(mesh, name="navmesh_display")

        # Строим контуры (независимо от меша)
        self._build_contour_handle(navmesh)

    def _build_contour_handle(self, navmesh: "NavMesh") -> None:
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
        vertices = np.vstack(all_vertices).astype(np.float32)
        triangles = np.vstack(all_triangles).astype(np.int32)

        mesh = Mesh3(vertices=vertices, triangles=triangles)
        self._contour_handle = MeshHandle.from_mesh3(mesh, name="navmesh_contours")
