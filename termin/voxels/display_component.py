"""
VoxelDisplayComponent — компонент для отображения воксельной сетки.

Реализует протокол Drawable и рендерит воксели напрямую.
Выбирает сетку из ResourceManager через комбобокс.
Использует VoxelGridHandle для поддержки hot-reload.
Отсечка по оси выполняется в шейдере для производительности.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Set, Tuple

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
    Отсечка и заливка цветом выполняются в шейдере.
    """

    inspect_fields = {
        "voxel_grid": InspectField(
            path="voxel_grid",
            label="Voxel Grid",
            kind="voxel_grid",
            setter=lambda obj, val: obj.set_voxel_grid(val),
        ),
        "color_below": InspectField(
            path="color_below",
            label="Color Below",
            kind="color",
            setter=lambda obj, val: obj._set_color_below(val),
        ),
        "color_above": InspectField(
            path="color_above",
            label="Color Above",
            kind="color",
            setter=lambda obj, val: obj._set_color_above(val),
        ),
        "fill_percent": InspectField(
            path="fill_percent",
            label="Fill %",
            kind="slider",
            min=0,
            max=100,
            setter=lambda obj, val: obj._set_fill_percent(val),
        ),
    }

    serializable_fields = [
        "voxel_grid_name",
        "color_below",
        "color_above",
        "fill_percent",
        "slice_axis",
    ]

    def __init__(self, voxel_grid_name: str = "") -> None:
        super().__init__()
        self._voxel_grid_name = voxel_grid_name
        self._grid_handle: VoxelGridHandle = VoxelGridHandle()
        self._last_grid: Optional["VoxelGrid"] = None  # Для отслеживания изменений
        self._mesh_drawable: Optional[MeshDrawable] = None
        self._material: Optional[Material] = None
        self._needs_rebuild = True

        # Цвета с альфа-каналом (RGBA)
        self.color_below: Tuple[float, float, float, float] = (0.2, 0.6, 1.0, 0.8)
        self.color_above: Tuple[float, float, float, float] = (1.0, 0.3, 0.2, 0.8)

        # Процент заполнения (0-100), 100 = вся сетка
        self.fill_percent: float = 100.0

        # Ось отсечки (нормализованный вектор), по умолчанию Z вверх
        self.slice_axis: Tuple[float, float, float] = (0.0, 0.0, 1.0)

        # Границы сетки в мировых координатах (вычисляются при построении меша)
        self._bounds_min: np.ndarray = np.zeros(3, dtype=np.float32)
        self._bounds_max: np.ndarray = np.zeros(3, dtype=np.float32)

    def _set_color_below(self, value: Tuple[float, float, float, float]) -> None:
        """Установить цвет ниже порога."""
        self.color_below = value

    def _set_color_above(self, value: Tuple[float, float, float, float]) -> None:
        """Установить цвет выше порога."""
        self.color_above = value

    def _set_fill_percent(self, value: float) -> None:
        """Установить процент заполнения."""
        self.fill_percent = value

    def _get_or_create_material(self) -> Material:
        """Получить материал с voxel шейдером."""
        if self._material is None:
            from termin.voxels.voxel_shader import voxel_display_shader
            from termin.visualization.render.renderpass import RenderState

            shader = voxel_display_shader()
            self._material = Material(
                shader=shader,
                color=self.color_below,
                phase_mark="editor",
                render_state=RenderState(
                    depth_test=True,
                    depth_write=True,
                    blend=True,
                    cull=True,
                ),
            )
        return self._material

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
        mat = self._get_or_create_material()
        return {p.phase_mark for p in mat.phases}

    def draw_geometry(self, context: "RenderContext") -> None:
        """Рисует геометрию вокселей."""
        # Проверяем hot-reload перед отрисовкой
        self._check_hot_reload()

        if self._mesh_drawable is None:
            return

        mat = self._get_or_create_material()

        # Обновляем uniforms шейдера
        for phase in mat.phases:
            phase.uniforms["u_color_below"] = np.array(self.color_below, dtype=np.float32)
            phase.uniforms["u_color_above"] = np.array(self.color_above, dtype=np.float32)
            phase.uniforms["u_slice_axis"] = np.array(self.slice_axis, dtype=np.float32)
            phase.uniforms["u_fill_percent"] = self.fill_percent / 100.0
            phase.uniforms["u_bounds_min"] = self._bounds_min
            phase.uniforms["u_bounds_max"] = self._bounds_max
            # Ambient lighting
            phase.uniforms["u_ambient_color"] = np.array([1.0, 1.0, 1.0], dtype=np.float32)
            phase.uniforms["u_ambient_intensity"] = 0.4

        self._mesh_drawable.draw(context)

    def _check_hot_reload(self) -> None:
        """Проверяет, изменился ли grid в keeper (hot-reload)."""
        current_grid = self._grid_handle.get()
        if current_grid is not self._last_grid:
            self._rebuild_mesh()

    def get_phases(self, phase_mark: str | None = None) -> List["MaterialPhase"]:
        """Возвращает MaterialPhases для рендеринга."""
        mat = self._get_or_create_material()

        if phase_mark is None:
            result = list(mat.phases)
        else:
            result = [p for p in mat.phases if p.phase_mark == phase_mark]

        result.sort(key=lambda p: p.priority)
        return result

    # --- Построение меша ---

    def _rebuild_mesh(self) -> None:
        """Перестроить меш из воксельной сетки (без фильтрации, вся сетка)."""
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

        # Собираем все воксели и вычисляем bounds
        all_voxels: list[tuple[int, int, int, int]] = []
        min_world = np.array([float('inf'), float('inf'), float('inf')], dtype=np.float32)
        max_world = np.array([float('-inf'), float('-inf'), float('-inf')], dtype=np.float32)

        for vx, vy, vz, vtype in grid.iter_non_empty():
            all_voxels.append((vx, vy, vz, vtype))
            center = grid.voxel_to_world(vx, vy, vz)
            min_world = np.minimum(min_world, center)
            max_world = np.maximum(max_world, center)

        if not all_voxels:
            return

        # Расширяем bounds на половину размера куба
        half_cell = grid.cell_size * CUBE_SCALE * 0.5
        self._bounds_min = min_world - half_cell
        self._bounds_max = max_world + half_cell

        # Ограничение для производительности
        display_count = len(all_voxels)
        if display_count > MAX_VOXELS:
            print(f"VoxelDisplayComponent: too many voxels ({display_count}), showing first {MAX_VOXELS}")
            all_voxels = all_voxels[:MAX_VOXELS]
            display_count = MAX_VOXELS

        # Выделяем массивы
        vertices = np.zeros((display_count * VERTS_PER_CUBE, 3), dtype=np.float32)
        triangles = np.zeros((display_count * TRIS_PER_CUBE, 3), dtype=np.int32)
        normals = np.zeros((display_count * VERTS_PER_CUBE, 3), dtype=np.float32)

        cell_size = grid.cell_size
        idx = 0

        for vx, vy, vz, vtype in all_voxels:
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
        # Если есть сохранённое имя сетки, загружаем
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
            "color_below": list(self.color_below),
            "color_above": list(self.color_above),
            "fill_percent": self.fill_percent,
            "slice_axis": list(self.slice_axis),
        }

    @classmethod
    def deserialize(cls, data: dict, context) -> "VoxelDisplayComponent":
        """Десериализовать компонент."""
        comp = cls(
            voxel_grid_name=data.get("voxel_grid_name", ""),
        )
        color_below = data.get("color_below")
        if color_below is not None:
            comp.color_below = tuple(color_below)
        color_above = data.get("color_above")
        if color_above is not None:
            comp.color_above = tuple(color_above)
        comp.fill_percent = data.get("fill_percent", 100.0)
        slice_axis = data.get("slice_axis")
        if slice_axis is not None:
            comp.slice_axis = tuple(slice_axis)
        return comp
