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
        self._last_regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []

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

        # Шаг 2.1: Фильтрация "висячих" вокселей
        # Воксели с <=1 соседом из своего региона выселяются в отдельные регионы
        regions = self._filter_hanging_voxels(regions)

        # NOTE: Стадии expand_regions и stitch_polygons временно отключены,
        # т.к. используется новый алгоритм построения меша из граней вокселей.
        # Флаги expand_regions и stitch_polygons игнорируются.

        # # Шаг 2.5: Расширяем регионы (опционально)
        # if expand_regions:
        #     regions = self._expand_regions(regions, surface_voxels)

        # # Для сшивки: находим какие воксели в каких регионах
        # voxel_to_regions: dict[tuple[int, int, int], list[int]] = {}
        # if stitch_polygons:
        #     for region_idx, (region_voxels, _) in enumerate(regions):
        #         for voxel in region_voxels:
        #             if voxel not in voxel_to_regions:
        #                 voxel_to_regions[voxel] = []
        #             voxel_to_regions[voxel].append(region_idx)

        # # Вычисляем плоскости для каждого региона (нужно для сшивки)
        # region_planes: list[tuple[np.ndarray, np.ndarray]] = []  # (centroid, normal)
        # for region_voxels, region_normal in regions:
        #     centers_3d = np.array([
        #         grid.origin + (np.array(v) + 0.5) * grid.cell_size
        #         for v in region_voxels
        #     ], dtype=np.float32)
        #     centroid = centers_3d.mean(axis=0)
        #     region_planes.append((centroid, region_normal))

        # Для каждого региона извлекаем контур напрямую из вокселей
        polygons: list[NavPolygon] = []
        stats = {
            "total_regions": len(regions),
            "skipped_small": 0,
            "build_failed": 0,
            "built": 0,
        }

        for region_idx, (region_voxels, region_normal) in enumerate(regions):
            if len(region_voxels) < self.config.min_region_voxels:
                stats["skipped_small"] += 1
                continue

            # Извлекаем контур напрямую из вокселей (без построения меша)
            polygon = self._extract_contour_from_voxels(
                region_voxels,
                region_normal,
                grid,
            )
            if polygon is not None:
                polygons.append(polygon)
                stats["built"] += 1
            else:
                stats["build_failed"] += 1

        print(f"NavMesh build stats: {stats}, final polygons: {len(polygons)}")

        # Сохраняем регионы для отладки
        self._last_regions = regions

        return NavMesh(
            polygons=polygons,
            cell_size=grid.cell_size,
            origin=grid.origin.copy(),
        )

    def get_regions(
        self, grid: VoxelGrid
    ) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
        """
        Получить регионы из воксельной сетки (без построения NavMesh).

        Returns:
            Список (список вокселей региона, нормаль региона).
        """
        surface_voxels = self._collect_surface_voxels(grid)
        if not surface_voxels:
            return []
        return self._region_growing_basic(surface_voxels, grid)

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

    def _filter_hanging_voxels(
        self,
        regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
    ) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
        """
        Шаг 2.1: Фильтрация "висячих" вокселей.

        Воксели с <=1 соседом из своего региона (по 26-связности)
        выселяются в отдельные одиночные регионы.

        Процесс повторяется итеративно, пока есть изменения.
        """
        result: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
        evicted: list[tuple[tuple[int, int, int], np.ndarray]] = []

        for region_voxels, region_normal in regions:
            if len(region_voxels) <= 2:
                # Слишком маленький регион — не фильтруем
                result.append((region_voxels, region_normal))
                continue

            region_set = set(region_voxels)
            changed = True

            while changed:
                changed = False
                to_evict: list[tuple[int, int, int]] = []

                for voxel in region_set:
                    # Считаем соседей из этого же региона
                    neighbor_count = 0
                    vx, vy, vz = voxel
                    for dx, dy, dz in NEIGHBORS_26:
                        neighbor = (vx + dx, vy + dy, vz + dz)
                        if neighbor in region_set:
                            neighbor_count += 1

                    if neighbor_count <= 1:
                        to_evict.append(voxel)

                # Выселяем помеченные воксели
                for voxel in to_evict:
                    region_set.discard(voxel)
                    evicted.append((voxel, region_normal))
                    changed = True

                # Если регион стал слишком маленьким — прекращаем
                if len(region_set) <= 2:
                    break

            # Добавляем оставшиеся воксели как регион
            if region_set:
                result.append((list(region_set), region_normal))

        # Добавляем выселенные воксели как одиночные регионы
        for voxel, normal in evicted:
            result.append(([voxel], normal))

        return result

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

    def _build_polygon_from_faces(
        self,
        voxels: list[tuple[int, int, int]],
        normal: np.ndarray,
        grid: VoxelGrid,
        current_region_idx: int = 0,
        extract_contours: bool = False,
        simplify_contours: bool = False,
        retriangulate: bool = False,
    ) -> NavPolygon | None:
        """
        Построить полигон из граней вокселей (квадратно-гнездовая сетка).

        Генерирует:
        1. Лицевые грани — по доминирующей оси нормали
        2. Замыкающие грани — боковые грани на ступеньках
        """
        if len(voxels) < 1:
            return None

        cell_size = grid.cell_size
        origin = grid.origin
        voxel_set = set(voxels)

        # Определяем доминирующую ось по нормали
        abs_normal = np.abs(normal)
        dominant_axis = int(np.argmax(abs_normal))  # 0=X, 1=Y, 2=Z
        axis_sign = 1 if normal[dominant_axis] >= 0 else -1

        # Оси для построения граней
        # dominant_axis — направление нормали грани
        # other_axes — две другие оси для плоскости грани
        other_axes = [i for i in range(3) if i != dominant_axis]

        # Смещения для 4 углов грани в локальных координатах вокселя
        # Грань лежит на плоскости dominant_axis = 0 или 1
        face_offset = 1 if axis_sign > 0 else 0  # какая сторона кубика

        # 4 угла грани (против часовой стрелки если смотреть по направлению нормали)
        corner_offsets = []
        for c0 in [0, 1]:
            for c1 in [0, 1]:
                offset = [0.0, 0.0, 0.0]
                offset[dominant_axis] = face_offset
                offset[other_axes[0]] = c0
                offset[other_axes[1]] = c1
                corner_offsets.append(offset)
        # Порядок: (0,0) -> (1,0) -> (1,1) -> (0,1) — CCW при взгляде в направлении +axis
        # Если axis_sign < 0, нужен обратный порядок
        if axis_sign > 0:
            corner_offsets = [corner_offsets[0], corner_offsets[1], corner_offsets[3], corner_offsets[2]]
        else:
            corner_offsets = [corner_offsets[0], corner_offsets[2], corner_offsets[3], corner_offsets[1]]

        # Собираем вершины и грани
        vertices: list[np.ndarray] = []
        vertex_map: dict[tuple[float, float, float], int] = {}
        quads: list[tuple[list[int], np.ndarray]] = []  # (indices, desired_normal)

        def get_or_add_vertex(pos: np.ndarray) -> int:
            key = (round(pos[0], 6), round(pos[1], 6), round(pos[2], 6))
            if key in vertex_map:
                return vertex_map[key]
            idx = len(vertices)
            vertices.append(pos.copy())
            vertex_map[key] = idx
            return idx

        # Нормаль для лицевых граней — по доминирующей оси
        face_normal = np.zeros(3, dtype=np.float32)
        face_normal[dominant_axis] = axis_sign

        # 1. Генерируем лицевые грани для каждого вокселя
        for vx, vy, vz in voxels:
            voxel_origin = origin + np.array([vx, vy, vz], dtype=np.float32) * cell_size
            quad_indices = []
            for offset in corner_offsets:
                pos = voxel_origin + np.array(offset, dtype=np.float32) * cell_size
                quad_indices.append(get_or_add_vertex(pos))
            quads.append((quad_indices, face_normal))

        # 2. Генерируем замыкающие (боковые) грани на ступеньках
        # Логика: кубик рисует боковые грани только к соседям в ярусе НИЖЕ него
        # (соседи выше сами нарисуют грани к нему)
        # "Нижний ярус" = смещение по dominant_axis в направлении -axis_sign
        lower_level_offset = -axis_sign

        # Направления для 4 соседей в нижнем ярусе (по other_axes)
        # side_directions[i] = (смещение по other_axes[0], смещение по other_axes[1])
        side_directions = [
            (1, 0),   # +other_axes[0]
            (-1, 0),  # -other_axes[0]
            (0, 1),   # +other_axes[1]
            (0, -1),  # -other_axes[1]
        ]

        for vx, vy, vz in voxels:
            voxel_coord = [vx, vy, vz]

            for dir_0, dir_1 in side_directions:
                # Проверяем, есть ли сосед на том же уровне в этом направлении
                # Если есть — он сам нарисует боковую грань к соседу снизу
                same_level_neighbor = list(voxel_coord)
                same_level_neighbor[other_axes[0]] += dir_0
                same_level_neighbor[other_axes[1]] += dir_1
                if tuple(same_level_neighbor) in voxel_set:
                    continue

                # Координата соседа в нижнем ярусе
                neighbor_coord = list(voxel_coord)
                neighbor_coord[dominant_axis] += lower_level_offset
                neighbor_coord[other_axes[0]] += dir_0
                neighbor_coord[other_axes[1]] += dir_1
                neighbor = tuple(neighbor_coord)

                # Если сосед в нижнем ярусе существует — рисуем боковую грань
                if neighbor not in voxel_set:
                    continue

                # Боковая грань соединяет верхние края лицевых граней
                # Текущий воксель: лицевая грань на dominant_axis + face_offset
                # Сосед: лицевая грань на (dominant_axis + lower_level_offset) + face_offset
                #      = dominant_axis + lower_level_offset + face_offset

                # Определяем какую боковую грань рисовать
                # Если dir_0 != 0, грань перпендикулярна other_axes[0]
                # Если dir_1 != 0, грань перпендикулярна other_axes[1]
                if dir_0 != 0:
                    side_axis = other_axes[0]
                    side_dir = dir_0
                    edge_axis = other_axes[1]
                else:
                    side_axis = other_axes[1]
                    side_dir = dir_1
                    edge_axis = other_axes[0]

                # Позиция боковой грани по side_axis
                side_pos = voxel_coord[side_axis] + (1 if side_dir > 0 else 0)

                # Диапазон по dominant_axis: от верха соседа до верха текущего
                # Верх текущего = voxel_coord[dominant_axis] + face_offset
                # Верх соседа = neighbor_coord[dominant_axis] + face_offset
                #             = voxel_coord[dominant_axis] + lower_level_offset + face_offset
                d_top = voxel_coord[dominant_axis] + face_offset
                d_bottom = voxel_coord[dominant_axis] + lower_level_offset + face_offset

                # 4 угла боковой грани
                voxel_origin = origin + np.array(voxel_coord, dtype=np.float32) * cell_size

                # Генерируем углы в порядке периметра (не Z-порядок!)
                # Порядок: (d_bottom, e=0) -> (d_top, e=0) -> (d_top, e=1) -> (d_bottom, e=1)
                corner_params = [
                    (d_bottom, 0),
                    (d_top, 0),
                    (d_top, 1),
                    (d_bottom, 1),
                ]
                side_corners = []
                for d_val, e_val in corner_params:
                    corner = [0.0, 0.0, 0.0]
                    corner[side_axis] = side_pos - voxel_coord[side_axis]
                    corner[dominant_axis] = d_val - voxel_coord[dominant_axis]
                    corner[edge_axis] = e_val
                    pos = voxel_origin + np.array(corner, dtype=np.float32) * cell_size
                    side_corners.append(get_or_add_vertex(pos))

                # Нормаль боковой грани — наружу от меша (в направлении side_dir по side_axis)
                side_normal = np.zeros(3, dtype=np.float32)
                side_normal[side_axis] = side_dir

                quad_indices = [side_corners[0], side_corners[1], side_corners[2], side_corners[3]]
                quads.append((quad_indices, side_normal))

        if not vertices or not quads:
            return None

        # Триангулируем квады с проверкой ориентации
        triangles = []
        vertices_arr = np.array(vertices, dtype=np.float32)

        for quad_indices, desired_normal in quads:
            # Вычисляем нормаль квада
            v0, v1, v2, v3 = [vertices_arr[i] for i in quad_indices]
            edge1 = v1 - v0
            edge2 = v3 - v0
            quad_normal = np.cross(edge1, edge2)

            # Проверяем, совпадает ли с желаемой нормалью
            if np.dot(quad_normal, desired_normal) < 0:
                # Инвертируем порядок
                quad_indices = [quad_indices[0], quad_indices[3], quad_indices[2], quad_indices[1]]
                v0, v1, v2, v3 = [vertices_arr[i] for i in quad_indices]

            # Выбираем диагональ согласованно по позиции (не по индексам)
            # Используем диагональ между вершинами с мин и макс суммой координат
            sums = [v0.sum(), v1.sum(), v2.sum(), v3.sum()]
            min_idx = int(np.argmin(sums))
            max_idx = int(np.argmax(sums))

            # Диагональ должна быть между противоположными вершинами (0-2 или 1-3)
            if (min_idx + max_idx) % 2 == 0:
                # Противоположные (0-2 или подобные) — используем эту диагональ
                if min_idx in [0, 2]:
                    # Диагональ 0-2
                    triangles.append([quad_indices[0], quad_indices[1], quad_indices[2]])
                    triangles.append([quad_indices[0], quad_indices[2], quad_indices[3]])
                else:
                    # Диагональ 1-3
                    triangles.append([quad_indices[0], quad_indices[1], quad_indices[3]])
                    triangles.append([quad_indices[1], quad_indices[2], quad_indices[3]])
            else:
                # min и max не противоположные — используем стандартную диагональ 0-2
                triangles.append([quad_indices[0], quad_indices[1], quad_indices[2]])
                triangles.append([quad_indices[0], quad_indices[2], quad_indices[3]])

        vertices_3d = np.array(vertices, dtype=np.float32)
        triangles_arr = np.array(triangles, dtype=np.int32)

        polygon = NavPolygon(
            vertices=vertices_3d,
            triangles=triangles_arr,
            normal=normal,
            voxel_coords=voxels,
        )

        # Извлечение контуров (если запрошено)
        if extract_contours:
            # Проецируем вершины в 2D для извлечения контуров
            centroid = vertices_3d.mean(axis=0)
            points_2d, basis_u, basis_v = self._project_to_2d(vertices_3d, normal, centroid)

            outer, holes = self._extract_contours(triangles_arr, points_2d)
            polygon.outer_contour = outer
            polygon.holes = holes

            # Упрощение контуров Douglas-Peucker
            if simplify_contours and polygon.outer_contour:
                epsilon = self.config.contour_epsilon
                polygon.outer_contour = self._simplify_contour(
                    polygon.outer_contour, points_2d, epsilon
                )
                polygon.holes = [
                    self._simplify_contour(hole, points_2d, epsilon)
                    for hole in polygon.holes
                ]

            # Перетриангуляция через Ear Clipping
            if retriangulate and polygon.outer_contour:
                contour_coords = points_2d[polygon.outer_contour]
                if len(contour_coords) >= 3 and not self._is_self_intersecting(contour_coords):
                    new_tris = self._ear_clipping(contour_coords)
                    expected_triangles = len(contour_coords) - 2

                    if len(new_tris) == expected_triangles:
                        # Конвертируем вершины контура в 3D
                        new_verts_3d = (
                            centroid +
                            contour_coords[:, 0:1] * basis_u +
                            contour_coords[:, 1:2] * basis_v
                        ).astype(np.float32)

                        polygon.vertices = new_verts_3d
                        polygon.triangles = new_tris
                        polygon.outer_contour = None
                        polygon.holes = []

        return polygon

    def _extract_contour_from_voxels(
        self,
        voxels: list[tuple[int, int, int]],
        normal: np.ndarray,
        grid: VoxelGrid,
    ) -> NavPolygon | None:
        """
        Извлечь контур региона напрямую из вокселей.

        Алгоритм:
        1. Проецируем воксели в 2D по доминантной оси нормали
        2. Находим граничные воксели (есть пустой сосед)
        3. Упорядочиваем обходом по часовой стрелке
        4. Возвращаем NavPolygon с контуром (без меша)
        """
        if len(voxels) < 1:
            return None

        cell_size = grid.cell_size
        origin = grid.origin

        # Определяем доминантную ось
        abs_normal = np.abs(normal)
        dominant_axis = int(np.argmax(abs_normal))
        other_axes = [i for i in range(3) if i != dominant_axis]

        # Проецируем в 2D: (voxel[other_axes[0]], voxel[other_axes[1]])
        voxel_set = set(voxels)
        voxel_2d_to_3d: dict[tuple[int, int], tuple[int, int, int]] = {}
        for v in voxels:
            key_2d = (v[other_axes[0]], v[other_axes[1]])
            # Если несколько вокселей проецируются в одну точку, берём верхний
            if key_2d not in voxel_2d_to_3d:
                voxel_2d_to_3d[key_2d] = v
            else:
                existing = voxel_2d_to_3d[key_2d]
                if v[dominant_axis] > existing[dominant_axis]:
                    voxel_2d_to_3d[key_2d] = v

        voxel_2d_set = set(voxel_2d_to_3d.keys())

        # 4-связные соседи в 2D
        neighbors_2d = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        # Находим граничные воксели (есть хотя бы один пустой сосед)
        boundary_voxels_2d: set[tuple[int, int]] = set()
        for v2d in voxel_2d_set:
            for dx, dy in neighbors_2d:
                neighbor = (v2d[0] + dx, v2d[1] + dy)
                if neighbor not in voxel_2d_set:
                    boundary_voxels_2d.add(v2d)
                    break

        if not boundary_voxels_2d:
            return None

        # Упорядочиваем граничные воксели обходом
        # Начинаем с минимального по (x, y)
        start = min(boundary_voxels_2d)
        contour_2d = self._trace_boundary_voxels(start, boundary_voxels_2d, voxel_2d_set)

        if len(contour_2d) < 3:
            return None

        # Конвертируем в 3D координаты центров вокселей
        contour_3d = []
        for v2d in contour_2d:
            v3d = voxel_2d_to_3d[v2d]
            center = origin + (np.array(v3d, dtype=np.float32) + 0.5) * cell_size
            contour_3d.append(center)

        vertices = np.array(contour_3d, dtype=np.float32)

        # Создаём NavPolygon с контуром, но без меша
        polygon = NavPolygon(
            vertices=vertices,
            triangles=np.array([], dtype=np.int32).reshape(0, 3),
            normal=normal,
            voxel_coords=voxels,
        )
        polygon.outer_contour = list(range(len(contour_2d)))

        return polygon

    def _trace_boundary_voxels(
        self,
        start: tuple[int, int],
        boundary_set: set[tuple[int, int]],
        voxel_set: set[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """
        Обход граничных вокселей по часовой стрелке (8-связность).
        """
        # 8 направлений по часовой стрелке начиная с востока
        directions = [
            (1, 0),   # E
            (1, 1),   # SE
            (0, 1),   # S
            (-1, 1),  # SW
            (-1, 0),  # W
            (-1, -1), # NW
            (0, -1),  # N
            (1, -1),  # NE
        ]

        contour = [start]
        visited = {start}
        current = start

        # Начальное направление: ищем первого соседа
        current_dir = 0
        for i, (dx, dy) in enumerate(directions):
            neighbor = (current[0] + dx, current[1] + dy)
            if neighbor in boundary_set:
                current_dir = i
                break

        max_steps = len(boundary_set) * 8
        for _ in range(max_steps):
            # Пробуем направления начиная с "правее текущего"
            found = False
            for offset in range(-2, 6):  # от -2 (сильно вправо) до 5 (почти назад)
                new_dir = (current_dir + offset) % 8
                dx, dy = directions[new_dir]
                neighbor = (current[0] + dx, current[1] + dy)

                if neighbor in boundary_set:
                    if neighbor == start and len(contour) > 2:
                        # Замкнули контур
                        return contour

                    if neighbor not in visited:
                        contour.append(neighbor)
                        visited.add(neighbor)
                        current = neighbor
                        current_dir = new_dir
                        found = True
                        break

            if not found:
                break

        return contour

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
            print(f"Region {current_region_idx}: too few voxels ({len(voxels)})")
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
            print(f"Region {current_region_idx}: too few points_2d ({len(points_2d)})")
            return None

        # Шаг 6: Alpha Shape (Delaunay + фильтрация)
        alpha = cell_size * 1.5  # Немного больше диагонали вокселя
        triangles_2d = self._alpha_shape(points_2d, alpha)

        if len(triangles_2d) == 0:
            print(f"Region {current_region_idx}: alpha shape returned 0 triangles ({len(points_2d)} points)")
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

        # Шаги 11-12: Перетриангуляция через Ear Clipping
        if retriangulate and polygon.outer_contour is not None:
            # Получаем координаты упрощённого контура
            contour_coords = points_2d[polygon.outer_contour]
            expected_triangles = len(contour_coords) - 2
            old_tri_count = len(polygon.triangles)

            if len(contour_coords) >= 3:
                # Проверяем на самопересечение
                if self._is_self_intersecting(contour_coords):
                    print(f"Region {current_region_idx}: Contour is self-intersecting ({len(contour_coords)} verts), skipping")
                else:
                    # Ear clipping триангуляция
                    new_tris = self._ear_clipping(contour_coords)

                    # Проверяем, что ear clipping дал ожидаемое число треугольников
                    if len(new_tris) != expected_triangles:
                        print(f"Region {current_region_idx}: Ear clipping failed: got {len(new_tris)}, expected {expected_triangles}")
                    else:
                        # Проверяем площадь
                        contour_area = abs(self._polygon_signed_area(contour_coords))
                        triangles_area = self._triangles_area(contour_coords, new_tris)

                        if contour_area > 1e-6 and abs(triangles_area - contour_area) / contour_area > 0.01:
                            print(f"Region {current_region_idx}: Ear clipping area mismatch: contour={contour_area:.4f}, triangles={triangles_area:.4f}")
                        else:
                            # Конвертируем вершины контура в 3D
                            new_verts_3d = (
                                centroid +
                                contour_coords[:, 0:1] * basis_u +
                                contour_coords[:, 1:2] * basis_v
                            ).astype(np.float32)

                            polygon.vertices = new_verts_3d
                            polygon.triangles = new_tris
                            # Контуры больше не валидны — индексы изменились
                            polygon.outer_contour = None
                            polygon.holes = []
                            print(f"Region {current_region_idx}: Ear clipping OK: {old_tri_count} -> {len(new_tris)} triangles, {len(contour_coords)} verts")
        elif retriangulate and polygon.outer_contour is None:
            print(f"Region {current_region_idx}: Ear clipping skipped: no outer_contour")

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

    # =========== Ear Clipping Triangulation ===========

    def _ear_clipping(self, vertices: np.ndarray) -> np.ndarray:
        """
        Триангулировать простой полигон методом Ear Clipping.

        Args:
            vertices: 2D координаты вершин полигона (CCW), shape (N, 2).

        Returns:
            Треугольники (индексы вершин), shape (N-2, 3).
        """
        n = len(vertices)
        if n < 3:
            return np.array([], dtype=np.int32).reshape(0, 3)
        if n == 3:
            return np.array([[0, 1, 2]], dtype=np.int32)

        # Список активных индексов вершин
        indices = list(range(n))
        triangles = []

        # Проверяем ориентацию — должна быть CCW (положительная площадь)
        area = self._polygon_signed_area(vertices)
        if area < 0:
            indices = indices[::-1]  # Разворачиваем в CCW

        while len(indices) > 3:
            ear_found = False

            for i in range(len(indices)):
                prev_i = (i - 1) % len(indices)
                next_i = (i + 1) % len(indices)

                prev_idx = indices[prev_i]
                curr_idx = indices[i]
                next_idx = indices[next_i]

                # Проверяем, является ли вершина "ухом"
                if self._is_ear(vertices, indices, prev_i, i, next_i):
                    # Добавляем треугольник
                    triangles.append([prev_idx, curr_idx, next_idx])
                    # Удаляем вершину
                    indices.pop(i)
                    ear_found = True
                    break

            if not ear_found:
                # Не нашли ухо — полигон вырожден или самопересекается
                break

        # Добавляем последний треугольник
        if len(indices) == 3:
            triangles.append([indices[0], indices[1], indices[2]])

        return np.array(triangles, dtype=np.int32) if triangles else np.array([], dtype=np.int32).reshape(0, 3)

    def _polygon_signed_area(self, vertices: np.ndarray) -> float:
        """Вычислить signed area полигона. Положительная = CCW."""
        n = len(vertices)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += vertices[i, 0] * vertices[j, 1]
            area -= vertices[j, 0] * vertices[i, 1]
        return area / 2.0

    def _triangles_area(self, vertices: np.ndarray, triangles: np.ndarray) -> float:
        """Вычислить суммарную площадь треугольников."""
        total = 0.0
        for tri in triangles:
            a = vertices[tri[0]]
            b = vertices[tri[1]]
            c = vertices[tri[2]]
            # Площадь треугольника через cross product
            area = abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2.0
            total += area
        return total

    def _is_ear(
        self,
        vertices: np.ndarray,
        indices: list[int],
        prev_i: int,
        curr_i: int,
        next_i: int,
    ) -> bool:
        """
        Проверить, является ли вершина curr_i "ухом".

        Ухо — это вершина, где:
        1. Угол выпуклый (не reflex)
        2. Внутри треугольника нет других вершин полигона
        """
        prev_idx = indices[prev_i]
        curr_idx = indices[curr_i]
        next_idx = indices[next_i]

        a = vertices[prev_idx]
        b = vertices[curr_idx]
        c = vertices[next_idx]

        # Проверяем выпуклость угла (cross product > 0 для CCW)
        cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if cross <= 0:
            return False  # Вогнутый угол — не ухо

        # Проверяем, что внутри треугольника нет других вершин
        for i, idx in enumerate(indices):
            if i in (prev_i, curr_i, next_i):
                continue

            p = vertices[idx]
            if self._point_in_triangle(p, a, b, c):
                return False

        return True

    def _point_in_triangle(
        self,
        p: np.ndarray,
        a: np.ndarray,
        b: np.ndarray,
        c: np.ndarray,
    ) -> bool:
        """
        Проверить, находится ли точка p строго внутри треугольника abc.

        Возвращает False для точек на границе треугольника, чтобы ear clipping
        мог корректно вырезать уши с вершинами на границе.
        """
        EPS = 1e-10

        def sign(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

        d1 = sign(p, a, b)
        d2 = sign(p, b, c)
        d3 = sign(p, c, a)

        # Точка на границе (любой sign близок к 0) — не считаем внутри
        if abs(d1) < EPS or abs(d2) < EPS or abs(d3) < EPS:
            return False

        has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)

        return not (has_neg and has_pos)

    def _is_self_intersecting(self, vertices: np.ndarray) -> bool:
        """
        Проверить, самопересекается ли контур.

        Проверяем все пары несмежных рёбер на пересечение.
        """
        n = len(vertices)
        if n < 4:
            return False

        for i in range(n):
            # Ребро i: vertices[i] -> vertices[(i+1) % n]
            a1 = vertices[i]
            a2 = vertices[(i + 1) % n]

            # Проверяем против всех несмежных рёбер
            for j in range(i + 2, n):
                # Пропускаем смежные рёбра
                if j == (i + n - 1) % n or (i == 0 and j == n - 1):
                    continue

                b1 = vertices[j]
                b2 = vertices[(j + 1) % n]

                if self._segments_intersect(a1, a2, b1, b2):
                    return True

        return False

    def _segments_intersect(
        self,
        a1: np.ndarray,
        a2: np.ndarray,
        b1: np.ndarray,
        b2: np.ndarray,
    ) -> bool:
        """Проверить, пересекаются ли отрезки a1-a2 и b1-b2."""
        def ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

        return (ccw(a1, b1, b2) != ccw(a2, b1, b2)) and (ccw(a1, a2, b1) != ccw(a1, a2, b2))

