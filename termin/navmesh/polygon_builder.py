"""
Построение полигонов из поверхностных вокселей.

Алгоритм:
1. Сбор поверхностных вокселей
2. Region Growing — группируем связные воксели с похожими нормалями
3. Извлечение контуров (внешний + дырки)
4. Douglas-Peucker упрощение
5. Bridge слияние дырок с внешним контуром
6. Ear Clipping триангуляция
"""

from __future__ import annotations

import numpy as np

from termin.navmesh.types import NavPolygon, NavMesh, NavMeshConfig
from termin.voxels.grid import VoxelGrid

from termin.navmesh.region_growing import (
    NEIGHBORS_26,
    collect_surface_voxels,
    region_growing_basic,
    greedy_absorption,
    expand_all_regions,
    filter_hanging_voxels,
    share_boundary_voxels,
    expand_regions,
)

from termin.navmesh.triangulation import (
    ear_clip,
    douglas_peucker_2d,
    merge_holes_with_bridges,
    transform_to_3d,
    build_2d_basis,
)

from termin.navmesh.contour_extraction import (
    bresenham_line,
    extract_contours_from_mask,
    extract_contours_from_region,
)


class PolygonBuilder:
    """
    Строит NavMesh из VoxelGrid.

    Использует Region Growing для группировки вокселей,
    затем Alpha Shape для построения полигонов.
    """

    def __init__(self, config: NavMeshConfig | None = None) -> None:
        self.config = config or NavMeshConfig()
        self._last_regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
        self._last_boundary_voxels: set[tuple[int, int, int]] = set()

    def build(
        self,
        grid: VoxelGrid,
        do_expand_regions: bool = True,
        share_boundary: bool = False,
        project_contours: bool = False,
        stitch_contours: bool = False,
    ) -> NavMesh:
        """
        Построить NavMesh из воксельной сетки.

        Args:
            grid: Воксельная сетка с поверхностными вокселями и нормалями.
            do_expand_regions: Расширять регионы (шаг 2.5).
            share_boundary: Граничные воксели добавляются в соседние регионы.
            project_contours: Проецировать контуры на плоскость региона.
            stitch_contours: Сшивать контуры на границах регионов.

        Returns:
            Навигационная сетка.
        """
        # Шаг 1: Собираем все поверхностные воксели с нормалями
        surface_voxels = collect_surface_voxels(grid)

        if not surface_voxels:
            return NavMesh(
                cell_size=grid.cell_size,
                origin=grid.origin.copy(),
            )

        # Шаг 2: Region Growing — разбиваем на группы
        regions = region_growing_basic(surface_voxels, self.config.normal_threshold)

        # Шаг 2.3: Жадное поглощение — большие регионы поглощают воксели меньших
        regions = greedy_absorption(regions, surface_voxels, self.config.normal_threshold)

        # Шаг 2.4: Расширение регионов на соседние воксели (отключено)
        # Каждый регион принимает соседей с подходящими нормалями
        # Воксель может участвовать в нескольких регионах
        # regions = expand_all_regions(regions, surface_voxels, self.config.normal_threshold)

        # Шаг 2.5: Расширяем регионы (опционально)
        # После этого шага воксели могут входить в несколько регионов
        if do_expand_regions:
            regions = expand_regions(regions, surface_voxels, self.config.normal_threshold)

        # Шаг 2.6: Фильтрация "висячих" вокселей (отключено)
        # Воксели с <=1 соседом (по всем регионам) выселяются в отдельные регионы
        # regions = filter_hanging_voxels(regions)

        # Шаг 2.7: Общие граничные воксели
        # Воксели на границе регионов добавляются в соседние регионы (тонкая граница)
        self._last_boundary_voxels = set()
        if share_boundary:
            regions, self._last_boundary_voxels = share_boundary_voxels(regions)

        # Для сшивки контуров: находим какие воксели в каких регионах
        voxel_to_regions: dict[tuple[int, int, int], list[int]] = {}
        region_planes: list[tuple[np.ndarray, np.ndarray]] = []  # (centroid, normal)

        if stitch_contours:
            for region_idx, (region_voxels, _) in enumerate(regions):
                for voxel in region_voxels:
                    if voxel not in voxel_to_regions:
                        voxel_to_regions[voxel] = []
                    voxel_to_regions[voxel].append(region_idx)

            # Вычисляем плоскости для каждого региона
            for region_voxels, region_normal in regions:
                centers_3d = np.array([
                    grid.origin + (np.array(v) + 0.5) * grid.cell_size
                    for v in region_voxels
                ], dtype=np.float32)
                centroid = centers_3d.mean(axis=0)
                region_planes.append((centroid, region_normal))

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
                region_idx=region_idx,
                project_contours=project_contours,
                stitch_contours=stitch_contours,
                voxel_to_regions=voxel_to_regions,
                region_planes=region_planes,
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
        surface_voxels = collect_surface_voxels(grid)
        if not surface_voxels:
            return []
        return region_growing_basic(surface_voxels, self.config.normal_threshold)

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

    def _extract_contour_from_voxels(
        self,
        voxels: list[tuple[int, int, int]],
        normal: np.ndarray,
        grid: VoxelGrid,
        region_idx: int = 0,
        project_contours: bool = False,
        stitch_contours: bool = False,
        voxel_to_regions: dict[tuple[int, int, int], list[int]] | None = None,
        region_planes: list[tuple[np.ndarray, np.ndarray]] | None = None,
    ) -> NavPolygon | None:
        """
        Извлечь контур региона напрямую из вокселей.

        Алгоритм:
        1. Проецируем воксели в 2D по доминантной оси нормали
        2. Находим граничные воксели (есть пустой сосед)
        3. Упорядочиваем обходом по часовой стрелке
        4. Возвращаем NavPolygon с контуром (без меша)

        Args:
            voxels: Список координат вокселей региона.
            normal: Нормаль региона.
            grid: Воксельная сетка.
            region_idx: Индекс текущего региона.
            project_contours: Проецировать вершины контура на плоскость региона.
            stitch_contours: Сшивать контуры на границах регионов.
            voxel_to_regions: Mapping voxel -> list of region indices.
            region_planes: List of (centroid, normal) for each region.
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
        # Сохраняем соответствие индекса вершины -> 3D координаты вокселя
        contour_3d = []
        contour_voxels_3d: list[tuple[int, int, int]] = []
        for v2d in contour_2d:
            v3d = voxel_2d_to_3d[v2d]
            center = origin + (np.array(v3d, dtype=np.float32) + 0.5) * cell_size
            contour_3d.append(center)
            contour_voxels_3d.append(v3d)

        vertices = np.array(contour_3d, dtype=np.float32)

        # Сшивка контуров: проецируем вершины на пересечение плоскостей соседних регионов
        if stitch_contours and voxel_to_regions is not None and region_planes is not None:
            current_plane = region_planes[region_idx]

            for i, v3d in enumerate(contour_voxels_3d):
                point = vertices[i]

                # Собираем все регионы, в которые входит воксель и его 26-соседи
                neighbor_regions: set[int] = set()
                vx, vy, vz = v3d
                for dx, dy, dz in NEIGHBORS_26:
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor in voxel_to_regions:
                        neighbor_regions.update(voxel_to_regions[neighbor])
                # Добавляем регионы самого вокселя
                if v3d in voxel_to_regions:
                    neighbor_regions.update(voxel_to_regions[v3d])

                # Сортируем для детерминированности
                region_list = sorted(neighbor_regions)

                if len(region_list) <= 1:
                    # Только один регион — проецируем на его плоскость
                    plane_point, plane_normal = current_plane
                    dist = np.dot(point - plane_point, plane_normal)
                    vertices[i] = point - dist * plane_normal

                elif len(region_list) == 2:
                    # Два региона — проецируем на линию пересечения плоскостей
                    planes = [region_planes[idx] for idx in region_list]
                    vertices[i] = self._project_to_line_intersection(point, planes)

                elif len(region_list) == 3:
                    # Три региона — перемещаем в точку пересечения плоскостей
                    planes = [region_planes[idx] for idx in region_list]
                    intersection = self._intersect_three_planes(planes)
                    if intersection is not None:
                        vertices[i] = intersection
                    else:
                        # Fallback: проекция на плоскость текущего региона
                        plane_point, plane_normal = current_plane
                        dist = np.dot(point - plane_point, plane_normal)
                        vertices[i] = point - dist * plane_normal

                else:
                    # 4+ региона — усредняем проекции на все плоскости
                    projected_sum = np.zeros(3, dtype=np.float32)
                    for ridx in region_list:
                        plane_point, plane_normal = region_planes[ridx]
                        dist = np.dot(point - plane_point, plane_normal)
                        projected_sum += point - dist * plane_normal
                    vertices[i] = projected_sum / len(region_list)

        # Простая проекция на плоскость региона (без сшивки)
        elif project_contours and len(voxels) > 0:
            # Вычисляем центроид всех вокселей региона
            all_centers = np.array([
                origin + (np.array(v, dtype=np.float32) + 0.5) * cell_size
                for v in voxels
            ], dtype=np.float32)
            centroid = all_centers.mean(axis=0)

            # Проецируем каждую вершину контура на плоскость
            normal_vec = np.array(normal, dtype=np.float32)
            for i in range(len(vertices)):
                point = vertices[i]
                dist = np.dot(point - centroid, normal_vec)
                vertices[i] = point - dist * normal_vec

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

    def extract_contours_from_region(
        self,
        region_voxels: list[tuple[int, int, int]],
        region_normal: np.ndarray,
        cell_size: float,
        origin: np.ndarray,
    ) -> tuple[list[tuple[int, int, int]], list[list[tuple[int, int, int]]]]:
        """
        Извлечь внешний и внутренние контуры из региона.

        Использует проекцию на 2D с алгоритмом Брезенхема для связности.

        Args:
            region_voxels: Список вокселей региона (vx, vy, vz).
            region_normal: Нормаль региона.
            cell_size: Размер вокселя.
            origin: Начало координат сетки.

        Returns:
            (outer_contour, holes) - внешний контур и список дырок.
            Каждый контур - список вокселей в порядке обхода.
        """
        if len(region_voxels) < 3:
            return list(region_voxels), []

        # Строим локальную 2D систему координат
        u_axis, v_axis = build_2d_basis(region_normal)

        # Центроид региона
        centers_3d = np.array([
            origin + (np.array(v) + 0.5) * cell_size
            for v in region_voxels
        ], dtype=np.float32)
        centroid = centers_3d.mean(axis=0)

        # Проецируем воксели на 2D (непрерывные координаты)
        voxel_to_2d_float: dict[tuple[int, int, int], tuple[float, float]] = {}
        for voxel in region_voxels:
            vx, vy, vz = voxel
            world_pos = origin + (np.array([vx, vy, vz]) + 0.5) * cell_size
            rel_pos = world_pos - centroid
            u = float(np.dot(rel_pos, u_axis))
            v = float(np.dot(rel_pos, v_axis))
            voxel_to_2d_float[voxel] = (u, v)

        # Квантизируем и строим маппинг
        voxel_to_2d: dict[tuple[int, int, int], tuple[int, int]] = {}
        grid_2d_to_voxels: dict[tuple[int, int], list[tuple[int, int, int]]] = {}

        for voxel, (u, v) in voxel_to_2d_float.items():
            grid_u = int(round(u / cell_size))
            grid_v = int(round(v / cell_size))
            voxel_to_2d[voxel] = (grid_u, grid_v)
            if (grid_u, grid_v) not in grid_2d_to_voxels:
                grid_2d_to_voxels[(grid_u, grid_v)] = []
            grid_2d_to_voxels[(grid_u, grid_v)].append(voxel)

        # Находим соседей в 3D (26-связность) и рисуем линии Брезенхема в 2D
        region_set = set(region_voxels)

        for voxel in region_voxels:
            vx, vy, vz = voxel
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        if dx == 0 and dy == 0 and dz == 0:
                            continue
                        neighbor = (vx + dx, vy + dy, vz + dz)
                        if neighbor in region_set and neighbor > voxel:  # Избегаем дублирования
                            # Рисуем линию между 2D проекциями
                            u1, v1 = voxel_to_2d[voxel]
                            u2, v2 = voxel_to_2d[neighbor]
                            line_cells = bresenham_line(u1, v1, u2, v2)

                            # Каждая ячейка на линии получает ближайший воксель
                            for cell in line_cells:
                                if cell not in grid_2d_to_voxels:
                                    grid_2d_to_voxels[cell] = [voxel]

        # Создаём бинарную маску
        all_2d = list(grid_2d_to_voxels.keys())
        min_u = min(p[0] for p in all_2d)
        max_u = max(p[0] for p in all_2d)
        min_v = min(p[1] for p in all_2d)
        max_v = max(p[1] for p in all_2d)

        # Добавляем padding для корректного flood fill
        width = max_u - min_u + 3
        height = max_v - min_v + 3
        offset_u = -min_u + 1
        offset_v = -min_v + 1

        mask = np.zeros((height, width), dtype=np.uint8)
        for (gu, gv) in all_2d:
            mask[gv + offset_v, gu + offset_u] = 1

        # Извлекаем контуры из маски
        outer_2d, holes_2d = extract_contours_from_mask(mask)

        # Конвертируем 2D контуры обратно в воксели
        outer_contour: list[tuple[int, int, int]] = []
        for (cu, cv) in outer_2d:
            grid_u = cu - offset_u
            grid_v = cv - offset_v
            if (grid_u, grid_v) in grid_2d_to_voxels:
                # Берём первый воксель из списка
                outer_contour.append(grid_2d_to_voxels[(grid_u, grid_v)][0])

        holes: list[list[tuple[int, int, int]]] = []
        for hole_2d in holes_2d:
            hole_voxels: list[tuple[int, int, int]] = []
            for (cu, cv) in hole_2d:
                grid_u = cu - offset_u
                grid_v = cv - offset_v
                if (grid_u, grid_v) in grid_2d_to_voxels:
                    hole_voxels.append(grid_2d_to_voxels[(grid_u, grid_v)][0])
            if hole_voxels:
                holes.append(hole_voxels)

        return outer_contour, holes

    # ========================================================================
    # Triangulation Pipeline (2D)
    # ========================================================================

    def triangulate_region(
        self,
        region_voxels: list[tuple[int, int, int]],
        region_normal: np.ndarray,
        cell_size: float,
        origin: np.ndarray,
        simplify_epsilon: float = 0.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Триангулировать регион: извлечь контуры, упростить, построить меш.

        Пайплайн:
        1. Извлечение контуров (воксели → упорядоченные списки)
        2. Проекция на плоскость → 2D координаты + базис
        3. Douglas-Peucker в 2D
        4. Bridge (объединение дырок) в 2D
        5. Ear Clipping в 2D → треугольники
        6. Преобразование вершин обратно в 3D

        Args:
            region_voxels: Список вокселей региона.
            region_normal: Нормаль региона.
            cell_size: Размер вокселя.
            origin: Начало координат сетки.
            simplify_epsilon: Параметр Douglas-Peucker (0 = без упрощения).

        Returns:
            (vertices, triangles):
                vertices: np.ndarray shape (N, 3) — вершины меша в 3D
                triangles: np.ndarray shape (M, 3) — индексы треугольников
        """
        # Шаг 1: Извлечение контуров
        outer_voxels, holes_voxels = extract_contours_from_region(
            region_voxels, region_normal, cell_size, origin
        )

        if len(outer_voxels) < 3:
            return np.array([]).reshape(0, 3), np.array([]).reshape(0, 3).astype(np.int32)

        # Шаг 2: Проекция на плоскость и переход в 2D
        u_axis, v_axis = build_2d_basis(region_normal)
        region_normal = region_normal / np.linalg.norm(region_normal)

        # Центроид региона
        centers_3d = np.array([
            origin + (np.array(v) + 0.5) * cell_size
            for v in region_voxels
        ], dtype=np.float32)
        centroid = centers_3d.mean(axis=0)

        def voxels_to_2d(voxels: list[tuple[int, int, int]]) -> np.ndarray:
            """Проецировать воксели на плоскость и вернуть 2D координаты."""
            if not voxels:
                return np.array([]).reshape(0, 2)
            points_2d = []
            for vx, vy, vz in voxels:
                world_pos = origin + (np.array([vx, vy, vz]) + 0.5) * cell_size
                # Проекция на плоскость
                to_point = world_pos - centroid
                distance = np.dot(to_point, region_normal)
                projected = world_pos - distance * region_normal
                # Переход в 2D
                rel = projected - centroid
                u = float(np.dot(rel, u_axis))
                v = float(np.dot(rel, v_axis))
                points_2d.append([u, v])
            return np.array(points_2d, dtype=np.float32)

        outer_2d = voxels_to_2d(outer_voxels)
        holes_2d = [voxels_to_2d(h) for h in holes_voxels]

        # Шаг 3: Douglas-Peucker в 2D
        if simplify_epsilon > 0:
            outer_2d = douglas_peucker_2d(outer_2d, simplify_epsilon)
            holes_2d = [douglas_peucker_2d(h, simplify_epsilon) for h in holes_2d if len(h) >= 3]

        # Удаляем слишком маленькие дырки после упрощения
        holes_2d = [h for h in holes_2d if len(h) >= 3]

        if len(outer_2d) < 3:
            return np.array([]).reshape(0, 3), np.array([]).reshape(0, 3).astype(np.int32)

        # Шаг 4: Bridge (объединение дырок с внешним контуром)
        if holes_2d:
            merged_2d = merge_holes_with_bridges(outer_2d, holes_2d)
        else:
            merged_2d = outer_2d

        if len(merged_2d) < 3:
            return np.array([]).reshape(0, 3), np.array([]).reshape(0, 3).astype(np.int32)

        # Шаг 5: Ear Clipping в 2D
        triangles = ear_clip(merged_2d)

        if len(triangles) == 0:
            return np.array([]).reshape(0, 3), np.array([]).reshape(0, 3).astype(np.int32)

        # Шаг 6: Преобразование вершин обратно в 3D
        vertices_3d = transform_to_3d(merged_2d, centroid, u_axis, v_axis)

        return vertices_3d, np.array(triangles, dtype=np.int32)

    def get_region_contours(
        self,
        region_voxels: list[tuple[int, int, int]],
        region_normal: np.ndarray,
        cell_size: float,
        origin: np.ndarray,
        simplify_epsilon: float = 0.0,
        stage: str = "simplified",
    ) -> tuple[np.ndarray, list[np.ndarray]]:
        """
        Получить контуры региона на заданной стадии обработки.

        Args:
            region_voxels: Список вокселей региона.
            region_normal: Нормаль региона.
            cell_size: Размер вокселя.
            origin: Начало координат сетки.
            simplify_epsilon: Параметр Douglas-Peucker (0 = без упрощения).
            stage: Стадия:
                - "simplified": После Douglas-Peucker (outer + holes отдельно)
                - "bridged": После merge_holes_with_bridges (один полигон)

        Returns:
            (outer_3d, holes_3d):
                outer_3d: np.ndarray shape (N, 3) — внешний контур в 3D
                holes_3d: list[np.ndarray] — дырки в 3D (пустой для "bridged")
        """
        # Шаг 1: Извлечение контуров
        outer_voxels, holes_voxels = extract_contours_from_region(
            region_voxels, region_normal, cell_size, origin
        )

        if len(outer_voxels) < 3:
            return np.array([]).reshape(0, 3), []

        # Шаг 2: Проекция на плоскость и переход в 2D
        u_axis, v_axis = build_2d_basis(region_normal)
        region_normal = region_normal / np.linalg.norm(region_normal)

        # Центроид региона
        centers_3d = np.array([
            origin + (np.array(v) + 0.5) * cell_size
            for v in region_voxels
        ], dtype=np.float32)
        centroid = centers_3d.mean(axis=0)

        def voxels_to_2d(voxels: list[tuple[int, int, int]]) -> np.ndarray:
            """Проецировать воксели на плоскость и вернуть 2D координаты."""
            if not voxels:
                return np.array([]).reshape(0, 2)
            points_2d = []
            for vx, vy, vz in voxels:
                world_pos = origin + (np.array([vx, vy, vz]) + 0.5) * cell_size
                to_point = world_pos - centroid
                distance = np.dot(to_point, region_normal)
                projected = world_pos - distance * region_normal
                rel = projected - centroid
                u = float(np.dot(rel, u_axis))
                v = float(np.dot(rel, v_axis))
                points_2d.append([u, v])
            return np.array(points_2d, dtype=np.float32)

        outer_2d = voxels_to_2d(outer_voxels)
        holes_2d = [voxels_to_2d(h) for h in holes_voxels]

        # Шаг 3: Douglas-Peucker в 2D
        if simplify_epsilon > 0:
            outer_2d = douglas_peucker_2d(outer_2d, simplify_epsilon)
            holes_2d = [douglas_peucker_2d(h, simplify_epsilon) for h in holes_2d if len(h) >= 3]

        holes_2d = [h for h in holes_2d if len(h) >= 3]

        if len(outer_2d) < 3:
            return np.array([]).reshape(0, 3), []

        if stage == "simplified":
            # Возвращаем outer + holes отдельно
            outer_3d = transform_to_3d(outer_2d, centroid, u_axis, v_axis)
            holes_3d = [transform_to_3d(h, centroid, u_axis, v_axis) for h in holes_2d]
            return outer_3d, holes_3d

        elif stage == "bridged":
            # Шаг 4: Bridge (объединение дырок с внешним контуром)
            if holes_2d:
                merged_2d = merge_holes_with_bridges(outer_2d, holes_2d)
            else:
                merged_2d = outer_2d

            if len(merged_2d) < 3:
                return np.array([]).reshape(0, 3), []

            merged_3d = transform_to_3d(merged_2d, centroid, u_axis, v_axis)
            return merged_3d, []  # Дырки уже слиты

        else:
            return np.array([]).reshape(0, 3), []

