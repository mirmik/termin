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
        "slice_x": InspectField(
            path="slice_x",
            label="Slice X %",
            kind="float",
            min=0.0,
            max=100.0,
            step=1.0,
            setter=lambda obj, val: obj._set_slice("x", val),
        ),
        "slice_y": InspectField(
            path="slice_y",
            label="Slice Y %",
            kind="float",
            min=0.0,
            max=100.0,
            step=1.0,
            setter=lambda obj, val: obj._set_slice("y", val),
        ),
        "slice_z": InspectField(
            path="slice_z",
            label="Slice Z %",
            kind="float",
            min=0.0,
            max=100.0,
            step=1.0,
            setter=lambda obj, val: obj._set_slice("z", val),
        ),
    }

    serializable_fields = ["voxel_grid_name", "slice_x", "slice_y", "slice_z"]

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
        # Срезы по осям (0-100%), 100 = показать всё
        self.slice_x: float = 100.0
        self.slice_y: float = 100.0
        self.slice_z: float = 100.0

    def _set_slice(self, axis: str, value: float) -> None:
        """Установить срез по оси и перестроить меш."""
        if axis == "x":
            self.slice_x = value
        elif axis == "y":
            self.slice_y = value
        elif axis == "z":
            self.slice_z = value
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
        # Проверяем hot-reload перед отрисовкой
        self._check_hot_reload()

        if self._mesh_drawable is None:
            return
        self._mesh_drawable.draw(context)

    def _check_hot_reload(self) -> None:
        """Проверяет, изменился ли grid в keeper (hot-reload)."""
        current_grid = self._grid_handle.get()
        if current_grid is not self._last_grid:
            self._rebuild_mesh()

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
        """Перестроить меш из воксельной сетки с учётом срезов."""
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

        # Собираем все воксели и находим bounds для срезов
        all_voxels: list[tuple[int, int, int, int]] = []
        min_v = [float('inf'), float('inf'), float('inf')]
        max_v = [float('-inf'), float('-inf'), float('-inf')]

        for vx, vy, vz, vtype in grid.iter_non_empty():
            all_voxels.append((vx, vy, vz, vtype))
            min_v[0] = min(min_v[0], vx)
            min_v[1] = min(min_v[1], vy)
            min_v[2] = min(min_v[2], vz)
            max_v[0] = max(max_v[0], vx)
            max_v[1] = max(max_v[1], vy)
            max_v[2] = max(max_v[2], vz)

        if not all_voxels:
            return

        # Вычисляем пороги для срезов (в воксельных координатах)
        # slice 100% = показать всё, slice 50% = показать нижнюю половину
        threshold_x = min_v[0] + (max_v[0] - min_v[0] + 1) * (self.slice_x / 100.0)
        threshold_y = min_v[1] + (max_v[1] - min_v[1] + 1) * (self.slice_y / 100.0)
        threshold_z = min_v[2] + (max_v[2] - min_v[2] + 1) * (self.slice_z / 100.0)

        # Фильтруем воксели по срезам
        filtered_voxels = [
            (vx, vy, vz, vtype)
            for vx, vy, vz, vtype in all_voxels
            if vx < threshold_x and vy < threshold_y and vz < threshold_z
        ]

        if not filtered_voxels:
            return

        # Ограничение для производительности
        display_count = len(filtered_voxels)
        if display_count > MAX_VOXELS:
            print(f"VoxelDisplayComponent: too many voxels ({display_count}), showing first {MAX_VOXELS}")
            filtered_voxels = filtered_voxels[:MAX_VOXELS]
            display_count = MAX_VOXELS

        # Выделяем массивы
        vertices = np.zeros((display_count * VERTS_PER_CUBE, 3), dtype=np.float32)
        triangles = np.zeros((display_count * TRIS_PER_CUBE, 3), dtype=np.int32)
        normals = np.zeros((display_count * VERTS_PER_CUBE, 3), dtype=np.float32)

        cell_size = grid.cell_size
        idx = 0

        for vx, vy, vz, vtype in filtered_voxels:
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
        if self._voxel_grid_name and self._grid_handle.get() is None:
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
        """Обновить меш если нужно."""
        if self._needs_rebuild:
            self._rebuild_mesh()
            self._needs_rebuild = False

    def serialize_data(self) -> dict:
        """Сериализует данные компонента."""
        return {
            "voxel_grid_name": self._voxel_grid_name,
            "slice_x": self.slice_x,
            "slice_y": self.slice_y,
            "slice_z": self.slice_z,
        }

    @classmethod
    def deserialize(cls, data: dict, context) -> "VoxelDisplayComponent":
        """Десериализовать компонент."""
        comp = cls(
            voxel_grid_name=data.get("voxel_grid_name", ""),
        )
        comp.slice_x = data.get("slice_x", 100.0)
        comp.slice_y = data.get("slice_y", 100.0)
        comp.slice_z = data.get("slice_z", 100.0)
        return comp
