"""
Построение полигонов из поверхностных вокселей.

Алгоритм:
1. Region Growing — группируем связные воксели с похожими нормалями
2. Для каждой группы строим контур
3. Триангулируем контур
"""

from __future__ import annotations

from collections import deque
from typing import Iterator
import numpy as np

from termin.navmesh.types import NavPolygon, NavMesh, NavMeshConfig
from termin.voxels.grid import VoxelGrid


# 6-связность для 3D
NEIGHBORS_6 = [
    (1, 0, 0), (-1, 0, 0),
    (0, 1, 0), (0, -1, 0),
    (0, 0, 1), (0, 0, -1),
]


class PolygonBuilder:
    """
    Строит NavMesh из VoxelGrid.

    Использует Region Growing для группировки вокселей,
    затем строит контуры и триангулирует.
    """

    def __init__(self, config: NavMeshConfig | None = None) -> None:
        self.config = config or NavMeshConfig()

    def build(self, grid: VoxelGrid) -> NavMesh:
        """
        Построить NavMesh из воксельной сетки.

        Args:
            grid: Воксельная сетка с поверхностными вокселями и нормалями.

        Returns:
            Навигационная сетка.
        """
        # 1. Собираем все поверхностные воксели с нормалями
        surface_voxels = self._collect_surface_voxels(grid)

        if not surface_voxels:
            return NavMesh(
                cell_size=grid.cell_size,
                origin=grid.origin.copy(),
            )

        # 2. Region Growing — разбиваем на группы
        regions = self._region_growing(surface_voxels, grid)

        # 3. Для каждого региона строим полигон
        polygons: list[NavPolygon] = []
        for region_voxels, region_normal in regions:
            if len(region_voxels) < self.config.min_region_voxels:
                continue

            polygon = self._build_polygon(region_voxels, region_normal, grid)
            if polygon is not None:
                polygons.append(polygon)

        return NavMesh(
            polygons=polygons,
            cell_size=grid.cell_size,
            origin=grid.origin.copy(),
        )

    def _collect_surface_voxels(
        self, grid: VoxelGrid
    ) -> dict[tuple[int, int, int], np.ndarray]:
        """
        Собрать поверхностные воксели с нормалями.

        Returns:
            {(vx, vy, vz): normal} для всех поверхностных вокселей.
        """
        result: dict[tuple[int, int, int], np.ndarray] = {}

        for coord, normal in grid.surface_normals.items():
            # Проверяем что воксель существует
            if grid.get(*coord) != 0:
                result[coord] = normal

        return result

    def _region_growing(
        self,
        surface_voxels: dict[tuple[int, int, int], np.ndarray],
        grid: VoxelGrid,
    ) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
        """
        Группировка вокселей методом Region Growing.

        Берём воксель из кучи, находим всех связных соседей
        с похожей нормалью, формируем регион.

        Returns:
            Список (список вокселей, усреднённая нормаль).
        """
        remaining = set(surface_voxels.keys())
        regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
        threshold = self.config.normal_threshold

        while remaining:
            # Берём произвольный воксель как seed
            seed = next(iter(remaining))
            seed_normal = surface_voxels[seed]

            # BFS для выращивания региона
            region: list[tuple[int, int, int]] = []
            normal_sum = np.zeros(3, dtype=np.float64)

            queue: deque[tuple[int, int, int]] = deque([seed])
            remaining.remove(seed)

            while queue:
                current = queue.popleft()
                current_normal = surface_voxels[current]

                # Проверяем совместимость нормали с seed
                dot = np.dot(seed_normal, current_normal)
                if dot < threshold:
                    # Нормаль слишком отличается — возвращаем в кучу
                    remaining.add(current)
                    continue

                # Добавляем в регион
                region.append(current)
                normal_sum += current_normal

                # Добавляем соседей
                vx, vy, vz = current
                for dx, dy, dz in NEIGHBORS_6:
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        queue.append(neighbor)

            if region:
                # Усредняем нормаль
                avg_normal = normal_sum / len(region)
                norm = np.linalg.norm(avg_normal)
                if norm > 1e-6:
                    avg_normal /= norm
                regions.append((region, avg_normal.astype(np.float32)))

        return regions

    def _build_polygon(
        self,
        voxels: list[tuple[int, int, int]],
        normal: np.ndarray,
        grid: VoxelGrid,
    ) -> NavPolygon | None:
        """
        Построить полигон из группы вокселей.

        1. Находим контур (границу) группы
        2. Строим вершины контура
        3. Триангулируем
        """
        if not voxels:
            return None

        # Строим контур в плоскости, перпендикулярной нормали
        contour_vertices = self._build_contour(voxels, normal, grid)

        if len(contour_vertices) < 3:
            return None

        # Триангулируем
        triangles = self._triangulate(contour_vertices, normal)

        if len(triangles) == 0:
            return None

        return NavPolygon(
            vertices=contour_vertices,
            triangles=triangles,
            normal=normal,
            voxel_coords=voxels,
        )

    def _build_contour(
        self,
        voxels: list[tuple[int, int, int]],
        normal: np.ndarray,
        grid: VoxelGrid,
    ) -> np.ndarray:
        """
        Построить контур группы вокселей.

        Для каждого вокселя находим грани, которые граничат с пустотой
        или вокселями из другой группы. Эти грани формируют контур.
        """
        voxel_set = set(voxels)
        cell_size = grid.cell_size
        origin = grid.origin

        # Собираем все граничные грани
        # Грань — это квадрат, определяемый 4 вершинами
        boundary_faces: list[np.ndarray] = []

        # 6 направлений и соответствующие им смещения вершин грани
        # Для каждого направления определяем 4 угла грани
        face_offsets = {
            (1, 0, 0): [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
            (-1, 0, 0): [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)],
            (0, 1, 0): [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)],
            (0, -1, 0): [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
            (0, 0, 1): [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
            (0, 0, -1): [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)],
        }

        for vx, vy, vz in voxels:
            for (dx, dy, dz), offsets in face_offsets.items():
                neighbor = (vx + dx, vy + dy, vz + dz)

                # Граничная грань — сосед не в нашей группе
                if neighbor not in voxel_set:
                    # Вычисляем мировые координаты вершин грани
                    face_verts = np.array([
                        origin + np.array([vx + ox, vy + oy, vz + oz]) * cell_size
                        for ox, oy, oz in offsets
                    ], dtype=np.float32)
                    boundary_faces.append(face_verts)

        if not boundary_faces:
            return np.array([], dtype=np.float32)

        # Собираем уникальные вершины
        all_verts = np.vstack(boundary_faces)
        unique_verts, inverse = np.unique(
            all_verts.round(decimals=6), axis=0, return_inverse=True
        )

        return unique_verts

    def _triangulate(
        self,
        vertices: np.ndarray,
        normal: np.ndarray,
    ) -> np.ndarray:
        """
        Триангулировать набор вершин.

        Простая ear clipping триангуляция в 2D проекции.
        """
        if len(vertices) < 3:
            return np.array([], dtype=np.int32).reshape(0, 3)

        # Проецируем на 2D плоскость, перпендикулярную нормали
        verts_2d, basis_u, basis_v = self._project_to_2d(vertices, normal)

        # Строим выпуклую оболочку для триангуляции
        # (для невыпуклых нужен более сложный алгоритм)
        hull_indices = self._convex_hull_2d(verts_2d)

        if len(hull_indices) < 3:
            return np.array([], dtype=np.int32).reshape(0, 3)

        # Fan triangulation от первой вершины
        triangles = []
        for i in range(1, len(hull_indices) - 1):
            triangles.append([
                hull_indices[0],
                hull_indices[i],
                hull_indices[i + 1],
            ])

        return np.array(triangles, dtype=np.int32)

    def _project_to_2d(
        self,
        vertices: np.ndarray,
        normal: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Проецировать 3D вершины на 2D плоскость.

        Returns:
            (2D координаты, базис U, базис V)
        """
        # Строим ортонормированный базис
        normal = normal / np.linalg.norm(normal)

        # Выбираем вектор, не параллельный нормали
        if abs(normal[0]) < 0.9:
            up = np.array([1, 0, 0], dtype=np.float32)
        else:
            up = np.array([0, 1, 0], dtype=np.float32)

        basis_u = np.cross(normal, up)
        basis_u /= np.linalg.norm(basis_u)

        basis_v = np.cross(normal, basis_u)
        basis_v /= np.linalg.norm(basis_v)

        # Проецируем вершины
        center = vertices.mean(axis=0)
        relative = vertices - center

        coords_2d = np.column_stack([
            np.dot(relative, basis_u),
            np.dot(relative, basis_v),
        ])

        return coords_2d, basis_u, basis_v

    def _convex_hull_2d(self, points: np.ndarray) -> list[int]:
        """
        Построить выпуклую оболочку 2D точек (алгоритм Джарвиса).

        Returns:
            Индексы точек, образующих выпуклую оболочку.
        """
        n = len(points)
        if n < 3:
            return list(range(n))

        # Находим самую левую точку
        start = 0
        for i in range(1, n):
            if points[i, 0] < points[start, 0]:
                start = i
            elif points[i, 0] == points[start, 0] and points[i, 1] < points[start, 1]:
                start = i

        hull = []
        current = start

        while True:
            hull.append(current)

            # Ищем самую "левую" точку относительно текущего направления
            next_point = 0
            for i in range(n):
                if i == current:
                    continue

                if next_point == current:
                    next_point = i
                    continue

                # Cross product для определения направления
                cross = self._cross_2d(
                    points[next_point] - points[current],
                    points[i] - points[current],
                )

                if cross < 0:
                    next_point = i
                elif cross == 0:
                    # Коллинеарные — берём более дальнюю
                    d1 = np.sum((points[next_point] - points[current]) ** 2)
                    d2 = np.sum((points[i] - points[current]) ** 2)
                    if d2 > d1:
                        next_point = i

            current = next_point

            if current == start:
                break

            if len(hull) > n:
                break

        return hull

    def _cross_2d(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """2D cross product (z-компонента)."""
        return v1[0] * v2[1] - v1[1] * v2[0]
