"""
VoxelVisualizer — визуализация воксельной сетки в редакторе.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
import numpy as np

from termin.mesh.mesh import Mesh3
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.core.material import Material
from termin.visualization.render.components import MeshRenderer
from termin.geombase.pose3 import Pose3

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity
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


class VoxelVisualizer:
    """
    Визуализатор воксельной сетки.

    Создаёт merged mesh из всех непустых вокселей и добавляет
    MeshRenderer к parent entity.
    """

    # Цвета для разных типов вокселей
    TYPE_COLORS = {
        1: (0.2, 0.6, 1.0, 0.7),   # Синий — обычный
        2: (0.2, 1.0, 0.3, 0.7),   # Зелёный — поверхностный
        3: (1.0, 0.3, 0.2, 0.7),   # Красный — внутренний
    }
    DEFAULT_COLOR = (0.5, 0.5, 0.5, 0.7)

    def __init__(self, grid: "VoxelGrid", parent_entity: "Entity") -> None:
        self._grid = grid
        self._parent = parent_entity
        self._mesh_drawable: Optional[MeshDrawable] = None
        self._renderer: Optional[MeshRenderer] = None
        self._material = Material(
            color=(0.2, 0.6, 1.0, 0.7),
            phase_mark="editor",
        )

    def rebuild(self) -> None:
        """Перестроить меш визуализации."""
        self._cleanup_renderer()

        voxel_count = self._grid.voxel_count
        if voxel_count == 0:
            return

        # Ограничение для производительности
        max_voxels = 100_000
        if voxel_count > max_voxels:
            print(f"VoxelVisualizer: too many voxels ({voxel_count}), showing first {max_voxels}")
            voxel_count = max_voxels

        # Выделяем массивы
        vertices = np.zeros((voxel_count * VERTS_PER_CUBE, 3), dtype=np.float32)
        triangles = np.zeros((voxel_count * TRIS_PER_CUBE, 3), dtype=np.int32)
        normals = np.zeros((voxel_count * VERTS_PER_CUBE, 3), dtype=np.float32)

        cell_size = self._grid.cell_size
        idx = 0

        for vx, vy, vz, vtype in self._grid.iter_non_empty():
            if idx >= max_voxels:
                break

            # Мировая позиция центра вокселя
            center = self._grid.voxel_to_world(vx, vy, vz)

            # Смещаем и масштабируем вершины куба
            v_start = idx * VERTS_PER_CUBE
            v_end = v_start + VERTS_PER_CUBE
            vertices[v_start:v_end] = _CUBE_VERTICES * cell_size + center
            normals[v_start:v_end] = _CUBE_NORMALS

            # Смещаем индексы треугольников
            t_start = idx * TRIS_PER_CUBE
            t_end = t_start + TRIS_PER_CUBE
            triangles[t_start:t_end] = _CUBE_TRIANGLES + v_start

            idx += 1

        # Обрезаем если меньше max_voxels
        if idx < max_voxels:
            vertices = vertices[:idx * VERTS_PER_CUBE]
            triangles = triangles[:idx * TRIS_PER_CUBE]
            normals = normals[:idx * VERTS_PER_CUBE]

        mesh = Mesh3(
            vertices=vertices,
            triangles=triangles,
            vertex_normals=normals,
        )
        self._mesh_drawable = MeshDrawable(mesh, name="voxel_grid_vis")
        self._renderer = MeshRenderer(
            self._mesh_drawable,
            self._material,
            cast_shadow=False,
        )
        self._parent.add_component(self._renderer)

    def cleanup(self) -> None:
        """Удалить визуализацию."""
        self._cleanup_renderer()

    def _cleanup_renderer(self) -> None:
        """Удалить текущий renderer если есть."""
        if self._renderer is not None:
            self._parent.remove_component(self._renderer)
            self._renderer = None
        if self._mesh_drawable is not None:
            self._mesh_drawable.delete()
            self._mesh_drawable = None

    def set_color(self, color: tuple[float, float, float, float]) -> None:
        """Установить цвет визуализации."""
        self._material = Material(color=color, phase_mark="editor")
        if self._renderer is not None:
            self._renderer.material = self._material
