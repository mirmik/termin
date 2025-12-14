"""
VoxelDisplayComponent — компонент для отображения воксельной сетки.

Реализует протокол Drawable и рендерит воксели напрямую.
Выбирает сетку из ResourceManager через комбобокс.
Использует VoxelGridHandle для поддержки hot-reload.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Set

import numpy as np

from termin.visualization.core.component import Component
from termin.visualization.core.material import Material
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.core.voxel_grid_handle import VoxelGridHandle
from termin.mesh.mesh import Mesh3
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.material import MaterialPhase
    from termin.visualization.render.render_context import RenderContext
    from termin.voxels.grid import VoxelGrid


# Вершины единичного куба (центрирован в origin)
_CUBE_VERTICES = np.array([
    # Front face
    [-0.5, -0.5,  0.5],
    [ 0.5, -0.5,  0.5],
    [ 0.5,  0.5,  0.5],
    [-0.5,  0.5,  0.5],
    # Back face
    [-0.5, -0.5, -0.5],
    [-0.5,  0.5, -0.5],
    [ 0.5,  0.5, -0.5],
    [ 0.5, -0.5, -0.5],
    # Top face
    [-0.5,  0.5, -0.5],
    [-0.5,  0.5,  0.5],
    [ 0.5,  0.5,  0.5],
    [ 0.5,  0.5, -0.5],
    # Bottom face
    [-0.5, -0.5, -0.5],
    [ 0.5, -0.5, -0.5],
    [ 0.5, -0.5,  0.5],
    [-0.5, -0.5,  0.5],
    # Right face
    [ 0.5, -0.5, -0.5],
    [ 0.5,  0.5, -0.5],
    [ 0.5,  0.5,  0.5],
    [ 0.5, -0.5,  0.5],
    # Left face
    [-0.5, -0.5, -0.5],
    [-0.5, -0.5,  0.5],
    [-0.5,  0.5,  0.5],
    [-0.5,  0.5, -0.5],
], dtype=np.float32)

_CUBE_TRIANGLES = np.array([
    [0, 1, 2], [0, 2, 3],       # front
    [4, 5, 6], [4, 6, 7],       # back
    [8, 9, 10], [8, 10, 11],    # top
    [12, 13, 14], [12, 14, 15], # bottom
    [16, 17, 18], [16, 18, 19], # right
    [20, 21, 22], [20, 22, 23], # left
], dtype=np.int32)

_CUBE_NORMALS = np.array([
    # Front
    [0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, 1],
    # Back
    [0, 0, -1], [0, 0, -1], [0, 0, -1], [0, 0, -1],
    # Top
    [0, 1, 0], [0, 1, 0], [0, 1, 0], [0, 1, 0],
    # Bottom
    [0, -1, 0], [0, -1, 0], [0, -1, 0], [0, -1, 0],
    # Right
    [1, 0, 0], [1, 0, 0], [1, 0, 0], [1, 0, 0],
    # Left
    [-1, 0, 0], [-1, 0, 0], [-1, 0, 0], [-1, 0, 0],
], dtype=np.float32)

VERTS_PER_CUBE = 24
TRIS_PER_CUBE = 12
CUBE_SCALE = 0.85  # Размер кубика относительно ячейки
MAX_VOXELS = 100_000


class VoxelDisplayComponent(Component):
    """
    Компонент для отображения воксельной сетки из ResourceManager.

    Реализует протокол Drawable — рендерит воксели напрямую без MeshRenderer.
    Выбирает сетку через комбобокс из зарегистрированных в ResourceManager.
    Использует VoxelGridHandle для поддержки hot-reload.
    """

    inspect_fields = {
        "voxel_grid": InspectField(
            path="voxel_grid",
            label="Voxel Grid",
            kind="voxel_grid",
            setter=lambda obj, val: obj.set_voxel_grid(val),
        ),
    }

    serializable_fields = ["voxel_grid_name"]

    def __init__(self, voxel_grid_name: str = "") -> None:
        super().__init__()
        self._voxel_grid_name = voxel_grid_name
        self._grid_handle: VoxelGridHandle = VoxelGridHandle()
        self._last_grid: Optional["VoxelGrid"] = None  # Для отслеживания изменений
        self._mesh_drawable: Optional[MeshDrawable] = None
        self._material = Material(
            color=(0.2, 0.6, 1.0, 0.7),
            phase_mark="editor",
        )
        self._needs_rebuild = True

    @property
    def voxel_grid(self) -> Optional["VoxelGrid"]:
        """Текущая воксельная сетка (через handle)."""
        return self._grid_handle.get()

    @voxel_grid.setter
    def voxel_grid(self, value: Optional["VoxelGrid"]) -> None:
        self.set_voxel_grid(value)

    def set_voxel_grid(self, grid: Optional["VoxelGrid"]) -> None:
        """Установить воксельную сетку."""
        if grid is None:
            self._grid_handle = VoxelGridHandle()
            self._voxel_grid_name = ""
        else:
            # Создаём handle по имени для поддержки hot-reload
            name = grid.name
            if name:
                self._grid_handle = VoxelGridHandle.from_name(name)
                self._voxel_grid_name = name
            else:
                self._grid_handle = VoxelGridHandle.from_grid(grid)
                self._voxel_grid_name = ""
        self._needs_rebuild = True

    def set_voxel_grid_by_name(self, name: str) -> None:
        """Установить воксельную сетку по имени из ResourceManager."""
        if name:
            self._grid_handle = VoxelGridHandle.from_name(name)
            self._voxel_grid_name = name
        else:
            self._grid_handle = VoxelGridHandle()
            self._voxel_grid_name = ""
        self._needs_rebuild = True

    # --- Drawable protocol ---

    @property
    def phase_marks(self) -> Set[str]:
        """Фазы рендеринга."""
        if self._material is None:
            return set()
        return {p.phase_mark for p in self._material.phases}

    def draw_geometry(self, context: "RenderContext") -> None:
        """Рисует геометрию вокселей."""
        if self._mesh_drawable is None:
            return
        self._mesh_drawable.draw(context)

    def get_phases(self, phase_mark: str | None = None) -> List["MaterialPhase"]:
        """Возвращает MaterialPhases для рендеринга."""
        if self._material is None:
            return []

        if phase_mark is None:
            result = list(self._material.phases)
        else:
            result = [p for p in self._material.phases if p.phase_mark == phase_mark]

        result.sort(key=lambda p: p.priority)
        return result

    # --- Построение меша ---

    def _rebuild_mesh(self) -> None:
        """Перестроить меш из воксельной сетки."""
        # Очищаем старый меш
        if self._mesh_drawable is not None:
            self._mesh_drawable.delete()
            self._mesh_drawable = None

        grid = self._grid_handle.get()
        self._last_grid = grid

        if grid is None:
            return

        voxel_count = grid.voxel_count
        if voxel_count == 0:
            return

        # Ограничение для производительности
        if voxel_count > MAX_VOXELS:
            print(f"VoxelDisplayComponent: too many voxels ({voxel_count}), showing first {MAX_VOXELS}")
            voxel_count = MAX_VOXELS

        # Выделяем массивы
        vertices = np.zeros((voxel_count * VERTS_PER_CUBE, 3), dtype=np.float32)
        triangles = np.zeros((voxel_count * TRIS_PER_CUBE, 3), dtype=np.int32)
        normals = np.zeros((voxel_count * VERTS_PER_CUBE, 3), dtype=np.float32)

        cell_size = grid.cell_size
        idx = 0

        for vx, vy, vz, vtype in grid.iter_non_empty():
            if idx >= MAX_VOXELS:
                break

            # Позиция центра вокселя
            center = grid.voxel_to_world(vx, vy, vz)

            # Смещаем и масштабируем вершины куба
            v_start = idx * VERTS_PER_CUBE
            v_end = v_start + VERTS_PER_CUBE
            vertices[v_start:v_end] = _CUBE_VERTICES * (cell_size * CUBE_SCALE) + center
            normals[v_start:v_end] = _CUBE_NORMALS

            # Смещаем индексы треугольников
            t_start = idx * TRIS_PER_CUBE
            t_end = t_start + TRIS_PER_CUBE
            triangles[t_start:t_end] = _CUBE_TRIANGLES + v_start

            idx += 1

        # Обрезаем если меньше max_voxels
        if idx < MAX_VOXELS:
            vertices = vertices[:idx * VERTS_PER_CUBE]
            triangles = triangles[:idx * TRIS_PER_CUBE]
            normals = normals[:idx * VERTS_PER_CUBE]

        mesh = Mesh3(
            vertices=vertices,
            triangles=triangles,
        )
        mesh.vertex_normals = normals
        self._mesh_drawable = MeshDrawable(mesh, name="voxel_display")

    # --- Lifecycle ---

    def on_added(self, scene: "Scene") -> None:
        """При добавлении в сцену загрузить сетку и построить меш."""
        # Если есть сохранённое имя, загружаем сетку
        if self._voxel_grid_name and self._grid is None:
            self.set_voxel_grid_by_name(self._voxel_grid_name)

        if self._needs_rebuild:
            self._rebuild_mesh()
            self._needs_rebuild = False

    def on_removed(self) -> None:
        """Очистить меш при удалении."""
        if self._mesh_drawable is not None:
            self._mesh_drawable.delete()
            self._mesh_drawable = None

    def update(self, dt: float) -> None:
        """Обновить меш если нужно или если grid изменился (hot-reload)."""
        # Проверяем hot-reload: grid в keeper мог измениться
        current_grid = self._grid_handle.get()
        if current_grid is not self._last_grid:
            self._needs_rebuild = True

        if self._needs_rebuild:
            self._rebuild_mesh()
            self._needs_rebuild = False

    def serialize_data(self) -> dict:
        """Сериализует данные компонента."""
        return {
            "voxel_grid_name": self._voxel_grid_name,
        }

    @classmethod
    def deserialize(cls, data: dict, context) -> "VoxelDisplayComponent":
        """Десериализовать компонент."""
        return cls(
            voxel_grid_name=data.get("voxel_grid_name", ""),
        )
