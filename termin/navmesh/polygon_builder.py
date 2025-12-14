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

    def build(
        self,
        grid: VoxelGrid,
        expand_regions: bool = True,
        stitch_polygons: bool = False,
        extract_contours: bool = False,
        simplify_contours: bool = False,
        retriangulate: bool = False,
    ) -> NavMesh:
        """
        Построить NavMesh из воксельной сетки.

        Args:
            grid: Воксельная сетка с поверхностными вокселями и нормалями.
            expand_regions: Расширять регионы (шаг 2.5).
            stitch_polygons: Сшивать полигоны через plane intersections.
            extract_contours: Извлекать контуры из треугольников (шаги 7-9).
            simplify_contours: Упрощать контуры Douglas-Peucker (шаг 10).
            retriangulate: Перетриангулировать через ear clipping (шаги 11-12).

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
        regions = self._region_growing_basic(surface_voxels, grid)

        # Шаг 2.5: Расширяем регионы (опционально)
        if expand_regions:
            regions = self._expand_regions(regions, surface_voxels)

        # Для сшивки: находим какие воксели в каких регионах
        voxel_to_regions: dict[tuple[int, int, int], list[int]] = {}
        if stitch_polygons:
            for region_idx, (region_voxels, _) in enumerate(regions):
                for voxel in region_voxels:
                    if voxel not in voxel_to_regions:
                        voxel_to_regions[voxel] = []
                    voxel_to_regions[voxel].append(region_idx)

        # Вычисляем плоскости для каждого региона (нужно для сшивки)
        region_planes: list[tuple[np.ndarray, np.ndarray]] = []  # (centroid, normal)
        for region_voxels, region_normal in regions:
            centers_3d = np.array([
                grid.origin + (np.array(v) + 0.5) * grid.cell_size
                for v in region_voxels
            ], dtype=np.float32)
            centroid = centers_3d.mean(axis=0)
            region_planes.append((centroid, region_normal))

        # Шаги 3-7: Для каждого региона строим полигон
        polygons: list[NavPolygon] = []
        for region_idx, (region_voxels, region_normal) in enumerate(regions):
            if len(region_voxels) < self.config.min_region_voxels:
                continue

            polygon = self._build_polygon(
                region_voxels,
                region_normal,
                grid,
                voxel_to_regions=voxel_to_regions if stitch_polygons else None,
                region_planes=region_planes if stitch_polygons else None,
                current_region_idx=region_idx,
                extract_contours=extract_contours,
                simplify_contours=simplify_contours,
                retriangulate=retriangulate,
            )
            if polygon is not None:
                polygons.append(polygon)

        return NavMesh(
            polygons=polygons,
            cell_size=grid.cell_size,
            origin=grid.origin.copy(),
        )

    def _collect_surface_voxels(
        self, grid: VoxelGrid
    ) -> dict[tuple[int, int, int], list[np.ndarray]]:
        """
        Шаг 1: Собрать поверхностные воксели с нормалями.

        Returns:
            {(vx, vy, vz): [normal, ...]} для всех поверхностных вокселей.
        """
        result: dict[tuple[int, int, int], list[np.ndarray]] = {}

        for coord, normals_list in grid.surface_normals.items():
            if grid.get(*coord) != 0 and normals_list:
                result[coord] = normals_list

        return result

    def _region_growing_basic(
        self,
        surface_voxels: dict[tuple[int, int, int], list[np.ndarray]],
        grid: VoxelGrid,
    ) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
        """
        Шаг 2: Группировка вокселей методом Region Growing.

        Использует первую нормаль из списка для начального роста региона.

        Returns:
            Список (список вокселей, усреднённая нормаль).
        """
        remaining = set(surface_voxels.keys())
        regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
        threshold = self.config.normal_threshold

        while remaining:
            seed = next(iter(remaining))
            seed_normal = surface_voxels[seed][0]  # Первая нормаль

            region: list[tuple[int, int, int]] = []
            normal_sum = np.zeros(3, dtype=np.float64)

            queue: deque[tuple[int, int, int]] = deque([seed])
            remaining.remove(seed)

            while queue:
                current = queue.popleft()
                current_normal = surface_voxels[current][0]  # Первая нормаль

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

    def _expand_regions(
        self,
        regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
        surface_voxels: dict[tuple[int, int, int], list[np.ndarray]],
    ) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
        """
        Шаг 2.5: Расширить регионы, добавляя граничные воксели с подходящими нормалями.

        Для каждого региона ищем соседние воксели (не в регионе), у которых
        хотя бы одна нормаль близка к нормали региона. Такие воксели добавляются
        в регион. После этого шага регионы могут перекрываться.

        Returns:
            Расширенные регионы.
        """
        threshold = self.config.normal_threshold
        expanded_regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []

        for region_voxels, region_normal in regions:
            region_set = set(region_voxels)
            expanded = list(region_voxels)

            # Собираем границу региона
            boundary: set[tuple[int, int, int]] = set()
            for vx, vy, vz in region_voxels:
                for dx, dy, dz in NEIGHBORS_26:
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor not in region_set and neighbor in surface_voxels:
                        boundary.add(neighbor)

            # Проверяем граничные воксели
            for neighbor in boundary:
                normals_list = surface_voxels[neighbor]
                # Проверяем, есть ли хотя бы одна нормаль, близкая к нормали региона
                for normal in normals_list:
                    dot = np.dot(region_normal, normal)
                    if dot >= threshold:
                        expanded.append(neighbor)
                        break  # Достаточно одной подходящей нормали

            expanded_regions.append((expanded, region_normal))

        return expanded_regions

    def _project_with_stitching(
        self,
        voxels: list[tuple[int, int, int]],
        centers_3d: np.ndarray,
        centroid: np.ndarray,
        normal: np.ndarray,
        voxel_to_regions: dict[tuple[int, int, int], list[int]],
        region_planes: list[tuple[np.ndarray, np.ndarray]],
        current_region_idx: int,
    ) -> np.ndarray:
        """
        Проецировать точки с учётом сшивки.

        - 1 регион: обычная проекция на плоскость
        - 2 региона: проекция на линию пересечения плоскостей
        - 3+ регионов: проекция в точку пересечения плоскостей
        """
        projected = np.zeros_like(centers_3d)
        current_plane = region_planes[current_region_idx]

        for i, voxel in enumerate(voxels):
            point = centers_3d[i]
            region_indices = voxel_to_regions.get(voxel, [current_region_idx])

            if len(region_indices) == 1:
                # Обычная проекция на плоскость текущего региона
                plane_point, plane_normal = current_plane
                dist = np.dot(point - plane_point, plane_normal)
                projected[i] = point - dist * plane_normal

            elif len(region_indices) == 2:
                # Проекция на линию пересечения двух плоскостей
                planes = [region_planes[idx] for idx in region_indices]
                projected[i] = self._project_to_line_intersection(point, planes)

            else:
                # 3+ региона: проекция в точку пересечения плоскостей
                # Берём первые 3 плоскости
                planes = [region_planes[idx] for idx in region_indices[:3]]
                intersection_point = self._intersect_three_planes(planes)
                if intersection_point is not None:
                    projected[i] = intersection_point
                else:
                    # Fallback: обычная проекция
                    plane_point, plane_normal = current_plane
                    dist = np.dot(point - plane_point, plane_normal)
                    projected[i] = point - dist * plane_normal

        return projected

    def _project_to_line_intersection(
        self,
        point: np.ndarray,
        planes: list[tuple[np.ndarray, np.ndarray]],
    ) -> np.ndarray:
        """
        Проецировать точку на линию пересечения двух плоскостей.

        Линия пересечения: направление = n1 × n2
        Находим точку на линии, ближайшую к исходной точке.
        """
        (p1, n1), (p2, n2) = planes

        # Направление линии пересечения
        direction = np.cross(n1, n2)
        dir_len = np.linalg.norm(direction)

        if dir_len < 1e-8:
            # Плоскости параллельны — проецируем на первую
            dist = np.dot(point - p1, n1)
            return point - dist * n1

        direction = direction / dir_len

        # Находим точку на линии пересечения
        # Решаем систему: n1·x = n1·p1, n2·x = n2·p2
        # Используем метод: находим точку как пересечение с плоскостью, перпендикулярной направлению
        d1 = np.dot(n1, p1)
        d2 = np.dot(n2, p2)

        # Матрица для решения (n1, n2, direction) · x = (d1, d2, 0)
        # Но проще: найдём любую точку на линии, затем проецируем point на линию

        # Находим точку на линии: решаем n1·x = d1, n2·x = d2, берём x с минимальной нормой
        # Используем псевдообратную матрицу
        A = np.array([n1, n2])
        b = np.array([d1, d2])

        # Least squares решение
        line_point, _, _, _ = np.linalg.lstsq(A, b, rcond=None)

        # Проецируем исходную точку на линию
        to_point = point - line_point
        proj_len = np.dot(to_point, direction)
        projected = line_point + proj_len * direction

        return projected.astype(np.float32)

    def _intersect_three_planes(
        self,
        planes: list[tuple[np.ndarray, np.ndarray]],
    ) -> np.ndarray | None:
        """
        Найти точку пересечения трёх плоскостей.

        Плоскость i: n_i · x = n_i · p_i = d_i
        Решаем систему 3x3.
        """
        if len(planes) < 3:
            return None

        (p1, n1), (p2, n2), (p3, n3) = planes[:3]

        # Матрица коэффициентов
        A = np.array([n1, n2, n3])

        # Вектор правых частей
        d = np.array([np.dot(n1, p1), np.dot(n2, p2), np.dot(n3, p3)])

        # Проверяем определитель
        det = np.linalg.det(A)
        if abs(det) < 1e-8:
            # Плоскости не пересекаются в одной точке
            return None

        # Решаем систему
        x = np.linalg.solve(A, d)
        return x.astype(np.float32)

    def _build_polygon(
        self,
        voxels: list[tuple[int, int, int]],
        normal: np.ndarray,
        grid: VoxelGrid,
        voxel_to_regions: dict[tuple[int, int, int], list[int]] | None = None,
        region_planes: list[tuple[np.ndarray, np.ndarray]] | None = None,
        current_region_idx: int = 0,
        extract_contours: bool = False,
        simplify_contours: bool = False,
        retriangulate: bool = False,
    ) -> NavPolygon | None:
        """
        Шаги 3-13: Построить полигон из группы вокселей.
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
        # Для сшивки: воксели в нескольких регионах проецируются на пересечение плоскостей
        if voxel_to_regions is not None and region_planes is not None:
            projected_3d = self._project_with_stitching(
                voxels, centers_3d, centroid, normal,
                voxel_to_regions, region_planes, current_region_idx
            )
        else:
            # Обычная проекция на плоскость
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
        vertices_3d = (
            centroid +
            points_2d[:, 0:1] * basis_u +
            points_2d[:, 1:2] * basis_v
        ).astype(np.float32)

        # Создаём базовый полигон
        polygon = NavPolygon(
            vertices=vertices_3d,
            triangles=triangles_2d,
            normal=normal,
            voxel_coords=voxels,
        )

        # Шаги 7-9: Извлечение контуров
        if extract_contours:
            outer, holes = self._extract_contours(triangles_2d, points_2d)
            polygon.outer_contour = outer
            polygon.holes = holes

        # Шаг 10: Упрощение контуров Douglas-Peucker
        if simplify_contours and polygon.outer_contour is not None:
            epsilon = self.config.contour_epsilon
            polygon.outer_contour = self._simplify_contour(
                polygon.outer_contour, points_2d, epsilon
            )
            polygon.holes = [
                self._simplify_contour(hole, points_2d, epsilon)
                for hole in polygon.holes
            ]

        # Шаги 11-12: Перетриангуляция через Voronoi
        if retriangulate and polygon.outer_contour is not None:
            voronoi_cell_size = self.config.voronoi_cell_size

            # Voronoi-разбиение в 2D
            new_verts_2d, new_tris = self._voronoi_decomposition(
                polygon.outer_contour,
                points_2d,
                voronoi_cell_size,
            )

            if len(new_tris) > 0:
                # Конвертируем обратно в 3D
                new_verts_3d = (
                    centroid +
                    new_verts_2d[:, 0:1] * basis_u +
                    new_verts_2d[:, 1:2] * basis_v
                ).astype(np.float32)

                polygon.vertices = new_verts_3d
                polygon.triangles = new_tris

        return polygon

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

    def _extract_contours(
        self,
        triangles: np.ndarray,
        points_2d: np.ndarray,
    ) -> tuple[list[int], list[list[int]]]:
        """
        Шаги 7-9: Извлечь контуры из треугольников.

        Returns:
            (outer_contour, holes) — внешний контур (CCW) и список дыр (CW).
        """
        from collections import defaultdict

        # Шаг 7: Извлекаем boundary edges
        edge_count: dict[tuple[int, int], int] = defaultdict(int)
        for tri in triangles:
            for i in range(3):
                v0, v1 = tri[i], tri[(i + 1) % 3]
                edge = (min(v0, v1), max(v0, v1))
                edge_count[edge] += 1

        # Boundary = рёбра, встречающиеся ровно 1 раз
        boundary_edges = {e for e, count in edge_count.items() if count == 1}

        if not boundary_edges:
            return [], []

        # Шаг 8: Строим граф смежности и собираем контуры
        adjacency: dict[int, list[int]] = defaultdict(list)
        for v0, v1 in boundary_edges:
            adjacency[v0].append(v1)
            adjacency[v1].append(v0)

        # Обходим граф, собирая замкнутые контуры
        visited_edges: set[tuple[int, int]] = set()
        contours: list[list[int]] = []

        for start_edge in boundary_edges:
            if start_edge in visited_edges:
                continue

            # Начинаем новый контур
            v0, v1 = start_edge
            contour = [v0]
            current = v0
            prev = -1

            while True:
                # Находим следующую вершину
                neighbors = adjacency[current]
                next_v = -1
                for n in neighbors:
                    if n != prev:
                        edge = (min(current, n), max(current, n))
                        if edge not in visited_edges:
                            next_v = n
                            break

                if next_v == -1:
                    break

                edge = (min(current, next_v), max(current, next_v))
                visited_edges.add(edge)

                if next_v == contour[0]:
                    # Замкнули контур
                    break

                contour.append(next_v)
                prev = current
                current = next_v

            if len(contour) >= 3:
                contours.append(contour)

        if not contours:
            return [], []

        # Шаг 9: Определяем внешний контур и дыры
        # Находим точку с минимальным X
        min_x = float('inf')
        outer_idx = 0

        for idx, contour in enumerate(contours):
            for v in contour:
                x = points_2d[v, 0]
                if x < min_x:
                    min_x = x
                    outer_idx = idx

        outer_contour = contours[outer_idx]
        holes = [c for i, c in enumerate(contours) if i != outer_idx]

        # Нормализуем ориентацию: внешний → CCW, дыры → CW
        if self._signed_area(outer_contour, points_2d) < 0:
            outer_contour = outer_contour[::-1]

        normalized_holes = []
        for hole in holes:
            if self._signed_area(hole, points_2d) > 0:
                hole = hole[::-1]
            normalized_holes.append(hole)

        return outer_contour, normalized_holes

    def _signed_area(self, contour: list[int], points_2d: np.ndarray) -> float:
        """Вычислить signed area контура. Положительная = CCW."""
        area = 0.0
        n = len(contour)
        for i in range(n):
            j = (i + 1) % n
            pi = points_2d[contour[i]]
            pj = points_2d[contour[j]]
            area += pi[0] * pj[1]
            area -= pj[0] * pi[1]
        return area / 2.0

    # =========== Шаг 10: Douglas-Peucker ===========

    def _simplify_contour(
        self,
        contour: list[int],
        points_2d: np.ndarray,
        epsilon: float,
    ) -> list[int]:
        """
        Упростить контур алгоритмом Douglas-Peucker.

        Args:
            contour: Список индексов вершин контура.
            points_2d: 2D координаты всех вершин.
            epsilon: Порог расстояния для упрощения.

        Returns:
            Упрощённый контур (подмножество индексов).
        """
        if len(contour) <= 3:
            return contour

        # Для замкнутого контура: разрываем в точке с макс. расстоянием от начала
        # чтобы Douglas-Peucker не удалил важные точки на стыке
        coords = np.array([points_2d[i] for i in contour])

        # Находим точку максимально удалённую от первой
        distances = np.linalg.norm(coords - coords[0], axis=1)
        split_idx = int(np.argmax(distances))

        if split_idx == 0:
            split_idx = len(contour) // 2

        # Разбиваем контур на две части
        part1 = list(range(0, split_idx + 1))
        part2 = list(range(split_idx, len(contour))) + [0]

        # Упрощаем каждую часть
        simplified1 = self._douglas_peucker(part1, coords, epsilon)
        simplified2 = self._douglas_peucker(part2, coords, epsilon)

        # Объединяем (убираем дублирующиеся точки на стыках)
        result_indices = simplified1[:-1] + simplified2[:-1]

        # Преобразуем обратно в индексы вершин
        return [contour[i] for i in result_indices]

    def _douglas_peucker(
        self,
        indices: list[int],
        coords: np.ndarray,
        epsilon: float,
    ) -> list[int]:
        """
        Рекурсивный алгоритм Douglas-Peucker.

        Args:
            indices: Индексы в массиве coords.
            coords: 2D координаты точек.
            epsilon: Порог расстояния.

        Returns:
            Упрощённый список индексов.
        """
        if len(indices) <= 2:
            return indices

        # Начальная и конечная точки
        start = coords[indices[0]]
        end = coords[indices[-1]]

        # Вектор линии
        line_vec = end - start
        line_len = np.linalg.norm(line_vec)

        if line_len < 1e-10:
            # Все точки совпадают — оставляем только начало и конец
            return [indices[0], indices[-1]]

        line_unit = line_vec / line_len

        # Находим точку с максимальным расстоянием до линии
        max_dist = 0.0
        max_idx = 0

        for i in range(1, len(indices) - 1):
            point = coords[indices[i]]
            # Вектор от начала до точки
            vec = point - start
            # Проекция на линию
            proj_len = np.dot(vec, line_unit)
            # Ближайшая точка на линии
            if proj_len < 0:
                closest = start
            elif proj_len > line_len:
                closest = end
            else:
                closest = start + proj_len * line_unit
            # Расстояние
            dist = np.linalg.norm(point - closest)

            if dist > max_dist:
                max_dist = dist
                max_idx = i

        if max_dist < epsilon:
            # Все промежуточные точки близко к линии — удаляем их
            return [indices[0], indices[-1]]
        else:
            # Рекурсивно обрабатываем обе части
            left = self._douglas_peucker(indices[:max_idx + 1], coords, epsilon)
            right = self._douglas_peucker(indices[max_idx:], coords, epsilon)
            # Объединяем (без дублирования средней точки)
            return left[:-1] + right

    # =========== Voronoi Decomposition ===========

    def _voronoi_decomposition(
        self,
        contour: list[int],
        points_2d: np.ndarray,
        cell_size: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Разбить регион на ячейки Вороного.

        Args:
            contour: Индексы вершин контура (CCW).
            points_2d: 2D координаты вершин.
            cell_size: Шаг сетки сидов.

        Returns:
            (vertices, triangles) — новые вершины и треугольники.
        """
        from scipy.spatial import Voronoi

        # Получаем координаты контура
        contour_points = points_2d[contour]

        # Bounding box
        min_xy = contour_points.min(axis=0)
        max_xy = contour_points.max(axis=0)

        # Расставляем сиды на сетке
        seeds = self._place_seeds_on_grid(contour_points, min_xy, max_xy, cell_size)

        if len(seeds) < 3:
            # Слишком мало сидов — возвращаем исходный контур как один полигон
            return self._triangulate_convex_polygon(contour_points)

        # Добавляем далёкие точки для ограничения бесконечных рёбер
        padding = max(max_xy[0] - min_xy[0], max_xy[1] - min_xy[1]) * 2
        far_points = np.array([
            [min_xy[0] - padding, min_xy[1] - padding],
            [max_xy[0] + padding, min_xy[1] - padding],
            [max_xy[0] + padding, max_xy[1] + padding],
            [min_xy[0] - padding, max_xy[1] + padding],
        ])
        all_seeds = np.vstack([seeds, far_points])

        # Вычисляем Voronoi
        try:
            vor = Voronoi(all_seeds)
        except Exception:
            return self._triangulate_convex_polygon(contour_points)

        # Собираем ячейки и обрезаем по контуру
        all_vertices: list[np.ndarray] = []
        all_triangles: list[np.ndarray] = []
        vertex_offset = 0

        for i in range(len(seeds)):  # Только наши сиды, не far_points
            region_idx = vor.point_region[i]
            region = vor.regions[region_idx]

            if -1 in region or len(region) < 3:
                continue  # Бесконечная или вырожденная ячейка

            # Вершины ячейки Вороного
            cell_verts = vor.vertices[region]

            # Обрезаем по контуру
            clipped = self._clip_polygon_to_boundary(cell_verts, contour_points)

            if len(clipped) < 3:
                continue

            # Триангулируем ячейку (fan triangulation для выпуклых)
            cell_verts_arr, cell_tris = self._triangulate_convex_polygon(clipped)

            # Добавляем со смещением индексов
            all_vertices.append(cell_verts_arr)
            all_triangles.append(cell_tris + vertex_offset)
            vertex_offset += len(cell_verts_arr)

        if not all_vertices:
            return self._triangulate_convex_polygon(contour_points)

        return np.vstack(all_vertices), np.vstack(all_triangles)

    def _place_seeds_on_grid(
        self,
        contour: np.ndarray,
        min_xy: np.ndarray,
        max_xy: np.ndarray,
        cell_size: float,
    ) -> np.ndarray:
        """
        Расставить сиды на сетке внутри контура.

        Returns:
            Массив 2D координат сидов.
        """
        seeds = []

        # Немного отступаем от границ
        x = min_xy[0] + cell_size / 2
        while x < max_xy[0]:
            y = min_xy[1] + cell_size / 2
            while y < max_xy[1]:
                point = np.array([x, y])
                if self._point_in_polygon(point, contour):
                    seeds.append(point)
                y += cell_size
            x += cell_size

        return np.array(seeds) if seeds else np.array([]).reshape(0, 2)

    def _point_in_polygon(self, point: np.ndarray, polygon: np.ndarray) -> bool:
        """
        Проверить, находится ли точка внутри полигона (ray casting).
        """
        x, y = point
        n = len(polygon)
        inside = False

        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]

            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside

            j = i

        return inside

    def _clip_polygon_to_boundary(
        self,
        polygon: np.ndarray,
        boundary: np.ndarray,
    ) -> np.ndarray:
        """
        Обрезать полигон по границе (Sutherland-Hodgman).

        Args:
            polygon: Вершины обрезаемого полигона.
            boundary: Вершины границы (CCW).

        Returns:
            Обрезанный полигон.
        """
        output = polygon.tolist()

        for i in range(len(boundary)):
            if len(output) < 3:
                return np.array([]).reshape(0, 2)

            input_list = output
            output = []

            # Ребро границы
            edge_start = boundary[i]
            edge_end = boundary[(i + 1) % len(boundary)]

            for j in range(len(input_list)):
                current = np.array(input_list[j])
                previous = np.array(input_list[j - 1])

                # Проверяем с какой стороны ребра находятся точки
                curr_inside = self._is_left(edge_start, edge_end, current)
                prev_inside = self._is_left(edge_start, edge_end, previous)

                if curr_inside:
                    if not prev_inside:
                        # Входим в область — добавляем пересечение
                        intersection = self._line_intersection(
                            previous, current, edge_start, edge_end
                        )
                        if intersection is not None:
                            output.append(intersection.tolist())
                    output.append(current.tolist())
                elif prev_inside:
                    # Выходим из области — добавляем пересечение
                    intersection = self._line_intersection(
                        previous, current, edge_start, edge_end
                    )
                    if intersection is not None:
                        output.append(intersection.tolist())

        return np.array(output) if output else np.array([]).reshape(0, 2)

    def _is_left(self, a: np.ndarray, b: np.ndarray, p: np.ndarray) -> bool:
        """Проверить, находится ли точка p слева от линии a→b."""
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0

    def _line_intersection(
        self,
        p1: np.ndarray,
        p2: np.ndarray,
        p3: np.ndarray,
        p4: np.ndarray,
    ) -> np.ndarray | None:
        """
        Найти точку пересечения отрезков p1-p2 и p3-p4.
        """
        d1 = p2 - p1
        d2 = p4 - p3
        d3 = p3 - p1

        cross = d1[0] * d2[1] - d1[1] * d2[0]

        if abs(cross) < 1e-10:
            return None

        t = (d3[0] * d2[1] - d3[1] * d2[0]) / cross

        return p1 + t * d1

    def _triangulate_convex_polygon(
        self,
        vertices: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Триангулировать выпуклый полигон (fan triangulation).

        Returns:
            (vertices, triangles)
        """
        n = len(vertices)
        if n < 3:
            return vertices, np.array([]).reshape(0, 3).astype(np.int32)

        # Fan triangulation от первой вершины
        triangles = []
        for i in range(1, n - 1):
            triangles.append([0, i, i + 1])

        return vertices.astype(np.float32), np.array(triangles, dtype=np.int32)

