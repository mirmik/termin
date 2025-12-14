"""
Построение полигонов из поверхностных вокселей.

Алгоритм (см. ALGORITHM.md):
1. Сбор поверхностных вокселей
2. Region Growing — группируем связные воксели с похожими нормалями
3. Для каждой группы вычисляем плоскость
4. Проецируем центры вокселей на плоскость
5. Переводим в 2D
6. Alpha Shape (Delaunay + фильтрация по circumradius)
7. Обратно в 3D
"""

from __future__ import annotations

from collections import deque
import numpy as np
from scipy.spatial import Delaunay

from termin.navmesh.types import NavPolygon, NavMesh, NavMeshConfig
from termin.voxels.grid import VoxelGrid


# 6-связность для 3D (только по осям)
NEIGHBORS_6 = [
    (1, 0, 0), (-1, 0, 0),
    (0, 1, 0), (0, -1, 0),
    (0, 0, 1), (0, 0, -1),
]

# 26-связность для 3D (все соседи включая диагональные)
NEIGHBORS_26 = [
    (dx, dy, dz)
    for dx in (-1, 0, 1)
    for dy in (-1, 0, 1)
    for dz in (-1, 0, 1)
    if (dx, dy, dz) != (0, 0, 0)
]


class PolygonBuilder:
    """
    Строит NavMesh из VoxelGrid.

    Использует Region Growing для группировки вокселей,
    затем Alpha Shape для построения полигонов.
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
        # Шаг 1: Собираем все поверхностные воксели с нормалями
        surface_voxels = self._collect_surface_voxels(grid)

        if not surface_voxels:
            return NavMesh(
                cell_size=grid.cell_size,
                origin=grid.origin.copy(),
            )

        # Шаг 2: Region Growing — разбиваем на группы
        regions = self._region_growing(surface_voxels, grid)

        # Шаги 3-7: Для каждого региона строим полигон
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
        Шаг 1: Собрать поверхностные воксели с нормалями.

        Returns:
            {(vx, vy, vz): normal} для всех поверхностных вокселей.
        """
        result: dict[tuple[int, int, int], np.ndarray] = {}

        for coord, normal in grid.surface_normals.items():
            if grid.get(*coord) != 0:
                result[coord] = normal

        return result

    def _region_growing(
        self,
        surface_voxels: dict[tuple[int, int, int], np.ndarray],
        grid: VoxelGrid,
    ) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
        """
        Шаг 2: Группировка вокселей методом Region Growing.

        Returns:
            Список (список вокселей, усреднённая нормаль).
        """
        remaining = set(surface_voxels.keys())
        regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
        threshold = self.config.normal_threshold

        while remaining:
            seed = next(iter(remaining))
            seed_normal = surface_voxels[seed]

            region: list[tuple[int, int, int]] = []
            normal_sum = np.zeros(3, dtype=np.float64)

            queue: deque[tuple[int, int, int]] = deque([seed])
            remaining.remove(seed)

            while queue:
                current = queue.popleft()
                current_normal = surface_voxels[current]

                dot = np.dot(seed_normal, current_normal)
                if dot < threshold:
                    remaining.add(current)
                    continue

                region.append(current)
                normal_sum += current_normal

                vx, vy, vz = current
                for dx, dy, dz in NEIGHBORS_26:
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        queue.append(neighbor)

            if region:
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
        Шаги 3-7: Построить полигон из группы вокселей.
        """
        if len(voxels) < 3:
            return None

        cell_size = grid.cell_size
        origin = grid.origin

        # Шаг 3: Вычисляем центры вокселей в мировых координатах
        centers_3d = np.array([
            origin + (np.array(v) + 0.5) * cell_size
            for v in voxels
        ], dtype=np.float32)

        # Плоскость: центроид + нормаль
        centroid = centers_3d.mean(axis=0)

        # Шаг 4: Проецируем центры на плоскость
        # projected = point - dot(point - centroid, normal) * normal
        relative = centers_3d - centroid
        distances = np.dot(relative, normal)
        projected_3d = centers_3d - np.outer(distances, normal)

        # Шаг 5: Переводим в 2D
        points_2d, basis_u, basis_v = self._project_to_2d(projected_3d, normal, centroid)

        if len(points_2d) < 3:
            return None

        # Шаг 6: Alpha Shape (Delaunay + фильтрация)
        alpha = cell_size * 1.5  # Немного больше диагонали вокселя
        triangles_2d = self._alpha_shape(points_2d, alpha)

        if len(triangles_2d) == 0:
            return None

        # Шаг 7: Обратно в 3D
        # vertices_3d = centroid + u * basis_u + v * basis_v
        vertices_3d = (
            centroid +
            points_2d[:, 0:1] * basis_u +
            points_2d[:, 1:2] * basis_v
        ).astype(np.float32)

        return NavPolygon(
            vertices=vertices_3d,
            triangles=triangles_2d,
            normal=normal,
            voxel_coords=voxels,
        )

    def _project_to_2d(
        self,
        points_3d: np.ndarray,
        normal: np.ndarray,
        centroid: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Шаг 5: Проецировать 3D точки на 2D плоскость.

        Returns:
            (2D координаты, базис U, базис V)
        """
        normal = normal / np.linalg.norm(normal)

        # Выбираем вектор, не параллельный нормали
        if abs(normal[0]) < 0.9:
            up = np.array([1, 0, 0], dtype=np.float32)
        else:
            up = np.array([0, 1, 0], dtype=np.float32)

        basis_u = np.cross(normal, up)
        basis_u = basis_u / np.linalg.norm(basis_u)

        basis_v = np.cross(normal, basis_u)
        basis_v = basis_v / np.linalg.norm(basis_v)

        # Проецируем относительно центроида
        relative = points_3d - centroid

        coords_2d = np.column_stack([
            np.dot(relative, basis_u),
            np.dot(relative, basis_v),
        ]).astype(np.float32)

        return coords_2d, basis_u, basis_v

    def _alpha_shape(
        self,
        points_2d: np.ndarray,
        alpha: float,
    ) -> np.ndarray:
        """
        Шаг 6: Alpha Shape через Delaunay + фильтрацию по circumradius.

        Returns:
            Треугольники (индексы вершин), shape (N, 3)
        """
        if len(points_2d) < 3:
            return np.array([], dtype=np.int32).reshape(0, 3)

        # Delaunay триангуляция
        try:
            tri = Delaunay(points_2d)
        except Exception:
            return np.array([], dtype=np.int32).reshape(0, 3)

        # Фильтруем треугольники по circumradius
        valid_triangles = []

        for simplex in tri.simplices:
            # Вершины треугольника
            p0 = points_2d[simplex[0]]
            p1 = points_2d[simplex[1]]
            p2 = points_2d[simplex[2]]

            # Длины сторон
            a = np.linalg.norm(p1 - p2)
            b = np.linalg.norm(p0 - p2)
            c = np.linalg.norm(p0 - p1)

            # Площадь (по формуле Герона)
            s = (a + b + c) / 2
            area_sq = s * (s - a) * (s - b) * (s - c)

            if area_sq <= 0:
                continue

            area = np.sqrt(area_sq)

            # Circumradius: R = abc / (4 * area)
            circumradius = (a * b * c) / (4 * area)

            if circumradius <= alpha:
                valid_triangles.append(simplex)

        if not valid_triangles:
            return np.array([], dtype=np.int32).reshape(0, 3)

        return np.array(valid_triangles, dtype=np.int32)
