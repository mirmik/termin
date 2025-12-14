"""
NavMeshDisplayComponent — компонент для отображения навигационной сетки.

Реализует протокол Drawable и рендерит NavMesh как меш.
Выбирает NavMesh из ResourceManager через комбобокс.
Использует NavMeshHandle для поддержки hot-reload.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Set, Tuple

import numpy as np

from termin.visualization.core.component import Component
from termin.visualization.core.material import Material
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.core.navmesh_handle import NavMeshHandle
from termin.visualization.core.polyline import Polyline, PolylineDrawable
from termin.visualization.core.serialization import serializable
from termin.mesh.mesh import Mesh3
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.material import MaterialPhase
    from termin.visualization.render.render_context import RenderContext
    from termin.navmesh.types import NavMesh


def _get_navmesh_choices() -> list[tuple[str, str]]:
    """Получить список NavMesh для комбобокса."""
    from termin.visualization.core.resources import ResourceManager
    rm = ResourceManager.instance()
    names = rm.list_navmesh_names()
    return [(name, name) for name in names]


@serializable(fields=["navmesh_name", "color", "wireframe", "show_normals", "show_contours"])
class NavMeshDisplayComponent(Component):
    """
    Компонент для отображения NavMesh из ResourceManager.

    Реализует протокол Drawable — рендерит NavMesh как меш.
    Выбирает сетку через комбобокс из зарегистрированных в ResourceManager.
    Использует NavMeshHandle для поддержки hot-reload.
    """

    inspect_fields = {
        "navmesh_name": InspectField(
            path="navmesh_name",
            label="NavMesh",
            kind="navmesh",
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
    }

    def __init__(self, navmesh_name: str = "") -> None:
        super().__init__()
        self._navmesh_name = navmesh_name
        self._navmesh_handle: NavMeshHandle = NavMeshHandle()
        self._last_navmesh: Optional["NavMesh"] = None
        self._mesh_drawable: Optional[MeshDrawable] = None
        self._contour_drawable: Optional[PolylineDrawable] = None
        self._material: Optional[Material] = None
        self._needs_rebuild = True

        # Цвет с альфа-каналом (RGBA) — полупрозрачный зелёный
        self.color: Tuple[float, float, float, float] = (0.2, 0.8, 0.3, 0.7)

        # Режим отображения
        self.wireframe: bool = False
        self.show_normals: bool = False
        self.show_contours: bool = False

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

    @property
    def navmesh(self) -> Optional["NavMesh"]:
        """Текущий NavMesh (через handle)."""
        return self._navmesh_handle.get()

    # --- Drawable protocol ---

    @property
    def phase_marks(self) -> Set[str]:
        """Фазы рендеринга."""
        mat = self._get_or_create_material()
        return {p.phase_mark for p in mat.phases}

    def draw_geometry(self, context: "RenderContext") -> None:
        """Рисует геометрию NavMesh."""
        self._check_hot_reload()

        if self._mesh_drawable is not None:
            self._mesh_drawable.draw(context)

        if self.show_contours and self._contour_drawable is not None:
            self._contour_drawable.draw(context)

    def _check_hot_reload(self) -> None:
        """Проверяет, изменился ли navmesh в keeper (hot-reload)."""
        current = self._navmesh_handle.get()
        if self._needs_rebuild or current is not self._last_navmesh:
            self._needs_rebuild = False
            self._rebuild_mesh()

    def get_phases(self, phase_mark: str | None = None) -> List["MaterialPhase"]:
        """Возвращает MaterialPhases для рендеринга."""
        mat = self._get_or_create_material()

        if phase_mark is None:
            result = list(mat.phases)
        else:
            result = [p for p in mat.phases if p.phase_mark == phase_mark]

        # Обновляем цвет
        for phase in result:
            phase.uniforms["u_color"] = np.array(self.color, dtype=np.float32)

        result.sort(key=lambda p: p.priority)
        return result

    # --- Построение меша ---

    def _rebuild_mesh(self) -> None:
        """Перестроить меш из NavMesh."""
        # Очищаем старый меш
        if self._mesh_drawable is not None:
            self._mesh_drawable.delete()
            self._mesh_drawable = None

        if self._contour_drawable is not None:
            self._contour_drawable.delete()
            self._contour_drawable = None

        navmesh = self._navmesh_handle.get()
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

        if not all_vertices:
            return

        # Объединяем в один меш
        vertices = np.vstack(all_vertices).astype(np.float32)
        normals = np.vstack(all_normals).astype(np.float32)
        triangles = np.vstack(all_triangles).astype(np.int32)

        # Создаём Mesh3
        mesh = Mesh3(vertices=vertices, triangles=triangles, normals=normals)
        self._mesh_drawable = MeshDrawable(mesh)

        # Создаём контуры если есть
        self._build_contour_drawable(navmesh)

        print(f"NavMeshDisplayComponent: built mesh with {len(vertices)} vertices, {len(triangles)} triangles")

    def _build_contour_drawable(self, navmesh: "NavMesh") -> None:
        """Построить drawable для контуров."""
        # Собираем все контуры из полигонов
        contour_segments: list[np.ndarray] = []

        for polygon in navmesh.polygons:
            if polygon.outer_contour is None:
                continue

            verts = polygon.vertices

            # Внешний контур
            outer = polygon.outer_contour
            if len(outer) >= 2:
                for i in range(len(outer)):
                    j = (i + 1) % len(outer)
                    contour_segments.append(verts[outer[i]])
                    contour_segments.append(verts[outer[j]])

            # Дыры
            for hole in polygon.holes:
                if len(hole) >= 2:
                    for i in range(len(hole)):
                        j = (i + 1) % len(hole)
                        contour_segments.append(verts[hole[i]])
                        contour_segments.append(verts[hole[j]])

        if not contour_segments:
            return

        # Создаём polyline из сегментов (GL_LINES режим)
        line_vertices = np.array(contour_segments, dtype=np.float32)
        polyline = Polyline(line_vertices, is_strip=False)
        self._contour_drawable = PolylineDrawable(polyline)

    # --- Сериализация ---

    @classmethod
    def deserialize(cls, data: dict, context) -> "NavMeshDisplayComponent":
        """Десериализовать компонент."""
        comp = cls(navmesh_name=data.get("navmesh_name", ""))
        comp.color = tuple(data.get("color", (0.2, 0.8, 0.3, 0.7)))
        comp.wireframe = data.get("wireframe", False)
        comp.show_normals = data.get("show_normals", False)
        comp.show_contours = data.get("show_contours", False)
        return comp
