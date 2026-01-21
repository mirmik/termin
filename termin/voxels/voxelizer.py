"""
Вокселизатор — преобразование мешей в воксели.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Callable
import numpy as np

from termin.voxels.grid import VoxelGrid
from termin.voxels.intersection import triangle_aabb_intersect, triangle_aabb

if TYPE_CHECKING:
    from termin.mesh.mesh import Mesh3
    from termin.visualization.core.entity import Entity
    from termin.visualization.core.scene import Scene


# Типы вокселей
VOXEL_EMPTY = 0
VOXEL_SOLID = 1      # Заполненный воксель (после вокселизации и fill)
VOXEL_SURFACE = 2    # Поверхностный воксель (после mark_surface)


def _compute_triangle_normal(v0: np.ndarray, v1: np.ndarray, v2: np.ndarray) -> np.ndarray:
    """Вычислить нормаль треугольника."""
    edge1 = v1 - v0
    edge2 = v2 - v0
    normal = np.cross(edge1, edge2)
    length = np.linalg.norm(normal)
    if length > 1e-8:
        normal /= length
    return normal.astype(np.float32)


class MeshVoxelizer:
    """
    Вокселизатор одного меша.

    Использует алгоритм triangle-box intersection для определения
    какие воксели пересекает поверхность меша.
    """

    def __init__(self, grid: VoxelGrid) -> None:
        self._grid = grid
        self._cell_size = grid.cell_size
        self._half_size = np.array([self._cell_size / 2] * 3, dtype=np.float32)

    def voxelize_mesh(
        self,
        mesh: "Mesh3",
        transform_matrix: Optional[np.ndarray] = None,
        voxel_type: int = VOXEL_SOLID,
    ) -> int:
        """
        Вокселизировать меш.

        Args:
            mesh: Меш для вокселизации.
            transform_matrix: Матрица трансформации 4x4 (world space).
            voxel_type: Тип вокселя для записи.

        Returns:
            Количество записанных вокселей.
        """
        vertices = mesh.vertices
        triangles = mesh.triangles

        if vertices is None or triangles is None:
            return 0

        # Применяем трансформацию если есть
        if transform_matrix is not None:
            vertices = self._transform_vertices(vertices, transform_matrix)

        count = 0

        for tri in triangles:
            v0 = vertices[tri[0]]
            v1 = vertices[tri[1]]
            v2 = vertices[tri[2]]

            count += self._voxelize_triangle(v0, v1, v2, voxel_type)

        return count

    def _transform_vertices(
        self,
        vertices: np.ndarray,
        matrix: np.ndarray,
    ) -> np.ndarray:
        """Применить матрицу трансформации к вершинам."""
        # Добавляем w=1 для homogeneous coordinates
        n = len(vertices)
        homogeneous = np.ones((n, 4), dtype=np.float32)
        homogeneous[:, :3] = vertices

        # Умножаем на транспонированную матрицу (vertices как строки)
        transformed = homogeneous @ matrix.T

        # Возвращаем xyz
        return transformed[:, :3]

    def _voxelize_triangle(
        self,
        v0: np.ndarray,
        v1: np.ndarray,
        v2: np.ndarray,
        voxel_type: int,
    ) -> int:
        """Вокселизировать один треугольник."""
        # AABB треугольника в мировых координатах
        tri_min, tri_max = triangle_aabb(v0, v1, v2)

        # Небольшое расширение для треугольников на границах вокселей
        epsilon = self._cell_size * 0.01
        tri_min = tri_min - epsilon
        tri_max = tri_max + epsilon

        # Преобразуем в индексы вокселей
        voxel_min = self._grid.world_to_voxel(tri_min)
        voxel_max = self._grid.world_to_voxel(tri_max)

        count = 0

        # Перебираем все воксели в AABB
        for vx in range(voxel_min[0], voxel_max[0] + 1):
            for vy in range(voxel_min[1], voxel_max[1] + 1):
                for vz in range(voxel_min[2], voxel_max[2] + 1):
                    # Центр вокселя в мировых координатах
                    center = self._grid.voxel_to_world(vx, vy, vz)

                    # Тест пересечения
                    if triangle_aabb_intersect(v0, v1, v2, center, self._half_size):
                        self._grid.set(vx, vy, vz, voxel_type)
                        count += 1

        return count

    def compute_surface_normals(
        self,
        mesh: "Mesh3",
        surface_voxels: set[tuple[int, int, int]],
        transform_matrix: Optional[np.ndarray] = None,
    ) -> int:
        """
        Вычислить нормали для поверхностных вокселей.

        Второй проход по треугольникам меша. Для каждого треугольника,
        пересекающего surface воксель, накапливаем его нормаль.
        Результат — усреднённые нормализованные нормали в grid.surface_normals.

        Args:
            mesh: Меш для вычисления нормалей.
            surface_voxels: Множество координат поверхностных вокселей.
            transform_matrix: Матрица трансформации 4x4 (world space).

        Returns:
            Количество вокселей с вычисленными нормалями.
        """
        vertices = mesh.vertices
        triangles = mesh.triangles

        if vertices is None or triangles is None:
            return 0

        if not surface_voxels:
            return 0

        # Применяем трансформацию если есть
        if transform_matrix is not None:
            vertices = self._transform_vertices(vertices, transform_matrix)

        # Накапливаем нормали для каждого surface вокселя
        voxels_with_normals: set[tuple[int, int, int]] = set()

        for tri in triangles:
            v0 = vertices[tri[0]]
            v1 = vertices[tri[1]]
            v2 = vertices[tri[2]]

            # Нормаль треугольника
            tri_normal = _compute_triangle_normal(v0, v1, v2)

            # AABB треугольника
            tri_min, tri_max = triangle_aabb(v0, v1, v2)
            epsilon = self._cell_size * 0.01
            tri_min = tri_min - epsilon
            tri_max = tri_max + epsilon

            voxel_min = self._grid.world_to_voxel(tri_min)
            voxel_max = self._grid.world_to_voxel(tri_max)

            # Проверяем воксели в AABB треугольника
            for vx in range(voxel_min[0], voxel_max[0] + 1):
                for vy in range(voxel_min[1], voxel_max[1] + 1):
                    for vz in range(voxel_min[2], voxel_max[2] + 1):
                        voxel_key = (vx, vy, vz)

                        # Только surface воксели
                        if voxel_key not in surface_voxels:
                            continue

                        # Проверяем пересечение
                        center = self._grid.voxel_to_world(vx, vy, vz)
                        if triangle_aabb_intersect(v0, v1, v2, center, self._half_size):
                            # Добавляем нормаль треугольника к списку (без усреднения)
                            self._grid.add_surface_normal(vx, vy, vz, tri_normal)
                            voxels_with_normals.add(voxel_key)

        return len(voxels_with_normals)


class SceneVoxelizer:
    """
    Вокселизатор сцены.

    Обходит все entity с MeshRenderer и вокселизирует их.
    """

    def __init__(
        self,
        grid: VoxelGrid,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """
        Args:
            grid: Воксельная сетка для записи.
            progress_callback: Колбэк прогресса (current, total).
        """
        self._grid = grid
        self._mesh_voxelizer = MeshVoxelizer(grid)
        self._progress_callback = progress_callback

    def voxelize_scene(self, scene: "Scene") -> int:
        """
        Вокселизировать всю сцену.

        Args:
            scene: Сцена для вокселизации.

        Returns:
            Общее количество записанных вокселей.
        """
        from termin.visualization.render.components import MeshRenderer

        # Собираем все entity с MeshRenderer
        mesh_entities = []
        for entity in scene.entities:
            if not entity.visible or not entity.enabled:
                continue
            comp = entity.get_component(MeshRenderer)
            if comp is not None:
                mesh_entities.append((entity, comp))

        total = len(mesh_entities)
        total_voxels = 0

        for i, (entity, renderer) in enumerate(mesh_entities):
            if self._progress_callback is not None:
                self._progress_callback(i, total)

            mesh_drawable = renderer.mesh
            if mesh_drawable is None:
                continue

            mesh = mesh_drawable.mesh
            if mesh is None:
                continue

            # Получаем world transform матрицу (включая scale)
            transform_matrix = entity.model_matrix()

            voxels = self._mesh_voxelizer.voxelize_mesh(
                mesh,
                transform_matrix=transform_matrix,
            )
            total_voxels += voxels

        if self._progress_callback is not None:
            self._progress_callback(total, total)

        return total_voxels


def voxelize_scene(
    scene: "Scene",
    cell_size: float = 0.25,
    padding: float = 1.0,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> VoxelGrid:
    """
    Удобная функция для вокселизации сцены.

    Автоматически вычисляет bounds и создаёт сетку.

    Args:
        scene: Сцена для вокселизации.
        cell_size: Размер вокселя.
        padding: Отступ вокруг сцены.
        progress_callback: Колбэк прогресса.

    Returns:
        Заполненная воксельная сетка.
    """
    # Вычисляем bounds сцены
    scene_min, scene_max = _compute_scene_bounds(scene)

    if scene_min is None:
        # Пустая сцена
        return VoxelGrid(origin=(0, 0, 0), cell_size=cell_size)

    # Добавляем padding
    origin = scene_min - padding
    size = scene_max - scene_min + 2 * padding

    # Выравниваем origin на cell_size
    origin = np.floor(origin / cell_size) * cell_size

    grid = VoxelGrid(origin=tuple(origin), cell_size=cell_size)

    voxelizer = SceneVoxelizer(grid, progress_callback)
    voxelizer.voxelize_scene(scene)

    return grid


def _compute_scene_bounds(scene: "Scene"):
    """Вычислить bounds сцены по всем мешам."""
    from termin.visualization.render.components import MeshRenderer

    scene_min = None
    scene_max = None

    for entity in scene.entities:
        if not entity.visible or not entity.enabled:
            continue

        for comp in entity.components:
            if not isinstance(comp, MeshRenderer):
                continue

            mesh_drawable = comp.mesh
            if mesh_drawable is None:
                continue

            mesh = mesh_drawable.mesh
            if mesh is None or mesh.vertices is None:
                continue

            # Трансформируем вершины в world space
            matrix = entity.model_matrix()
            vertices = mesh.vertices

            n = len(vertices)
            homogeneous = np.ones((n, 4), dtype=np.float32)
            homogeneous[:, :3] = vertices
            transformed = homogeneous @ matrix.T
            world_vertices = transformed[:, :3]

            mesh_min = world_vertices.min(axis=0)
            mesh_max = world_vertices.max(axis=0)

            if scene_min is None:
                scene_min = mesh_min
                scene_max = mesh_max
            else:
                scene_min = np.minimum(scene_min, mesh_min)
                scene_max = np.maximum(scene_max, mesh_max)

    return scene_min, scene_max
