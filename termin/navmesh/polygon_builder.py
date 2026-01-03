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
        self._last_boundary_voxels: set[tuple[int, int, int]] = set()

    def build(
        self,
        grid: VoxelGrid,
        expand_regions: bool = True,
        share_boundary: bool = False,
        project_contours: bool = False,
        stitch_contours: bool = False,
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
            share_boundary: Граничные воксели добавляются в соседние регионы (тонкая общая граница).
            project_contours: Проецировать контуры на плоскость региона.
            stitch_contours: Сшивать контуры на границах регионов (проекция на пересечение плоскостей).
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

        # Шаг 2.3: Жадное поглощение — большие регионы поглощают воксели меньших
        regions = self._greedy_absorption(regions, surface_voxels)

        # Шаг 2.4: Расширение регионов на соседние воксели (отключено)
        # Каждый регион принимает соседей с подходящими нормалями
        # Воксель может участвовать в нескольких регионах
        # regions = self._expand_all_regions(regions, surface_voxels)

        # Шаг 2.5: Расширяем регионы (опционально, старый алгоритм)
        # После этого шага воксели могут входить в несколько регионов
        if expand_regions:
            regions = self._expand_regions(regions, surface_voxels)

        # Шаг 2.6: Фильтрация "висячих" вокселей (отключено)
        # Воксели с <=1 соседом (по всем регионам) выселяются в отдельные регионы
        # regions = self._filter_hanging_voxels(regions)

        # Шаг 2.7: Общие граничные воксели
        # Воксели на границе регионов добавляются в соседние регионы (тонкая граница)
        self._last_boundary_voxels = set()
        if share_boundary:
            regions, self._last_boundary_voxels = self._share_boundary_voxels(regions)

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

    def _greedy_absorption(
        self,
        regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
        surface_voxels: dict[tuple[int, int, int], list[np.ndarray]],
    ) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
        """
        Шаг 2.3: Жадное поглощение — большие регионы поглощают воксели меньших.

        Алгоритм:
        1. Сортируем регионы по площади (количеству вокселей) — от большего к меньшему
        2. Для каждого региона (от большего к меньшему):
           - Ищем на границе воксели из меньших регионов с подходящими нормалями
           - Переносим их в текущий регион
           - Повторяем пока есть изменения
        3. Удаляем пустые регионы

        Returns:
            Обновлённый список регионов.
        """
        if len(regions) <= 1:
            return regions

        threshold = self.config.normal_threshold

        # Создаём изменяемые структуры данных
        # region_sets[i] = set of voxels in region i
        region_sets: list[set[tuple[int, int, int]]] = [set(voxels) for voxels, _ in regions]
        region_normals: list[np.ndarray] = [normal.copy() for _, normal in regions]

        # voxel_to_region[voxel] = region index
        voxel_to_region: dict[tuple[int, int, int], int] = {}
        for idx, voxel_set in enumerate(region_sets):
            for v in voxel_set:
                voxel_to_region[v] = idx

        # Сортируем индексы регионов по размеру (убывание)
        sorted_indices = sorted(range(len(regions)), key=lambda i: len(region_sets[i]), reverse=True)

        total_absorbed = 0
        total_pruned = 0

        # Обрабатываем каждый регион от большего к меньшему
        for rank, region_idx in enumerate(sorted_indices):
            region_normal = region_normals[region_idx]
            region_set = region_sets[region_idx]

            if len(region_set) == 0:
                continue

            # Размер текущего региона — регионы меньше этого размера могут терять воксели
            current_size = len(region_set)

            # Итеративно поглощаем воксели
            changed = True
            iteration = 0
            absorbed_this_region = 0

            while changed:
                changed = False
                iteration += 1

                # Собираем границу текущего региона
                # Ищем соседей, которые либо в другом регионе, либо "свободные" (в surface_voxels, но не в регионе)
                boundary_neighbors: set[tuple[int, int, int]] = set()
                for vx, vy, vz in region_set:
                    for dx, dy, dz in NEIGHBORS_26:
                        neighbor = (vx + dx, vy + dy, vz + dz)
                        if neighbor not in region_set and neighbor in surface_voxels:
                            boundary_neighbors.add(neighbor)

                # Проверяем каждого соседа на возможность поглощения
                to_absorb: list[tuple[int, int, int]] = []

                for neighbor in boundary_neighbors:
                    # Проверяем, принадлежит ли воксель другому региону
                    if neighbor in voxel_to_region:
                        neighbor_region_idx = voxel_to_region[neighbor]
                        neighbor_region_size = len(region_sets[neighbor_region_idx])
                        # Можем поглощать только из регионов меньшего размера
                        if neighbor_region_size >= current_size:
                            continue
                    # Если воксель не в регионе (свободный) — можно поглощать

                    # Проверяем совместимость нормали
                    neighbor_normals = surface_voxels[neighbor]
                    compatible = False
                    for normal in neighbor_normals:
                        dot = np.dot(region_normal, normal)
                        if dot >= threshold:
                            compatible = True
                            break

                    if compatible:
                        to_absorb.append(neighbor)

                # Переносим воксели
                for voxel in to_absorb:
                    if voxel in voxel_to_region:
                        old_region_idx = voxel_to_region[voxel]
                        # Удаляем из старого региона
                        region_sets[old_region_idx].discard(voxel)
                    # Добавляем в текущий регион
                    region_set.add(voxel)
                    voxel_to_region[voxel] = region_idx
                    changed = True
                    absorbed_this_region += 1

            total_absorbed += absorbed_this_region

            # Перераспределение висячих вокселей в регион с большинством соседей
            redistributed_this_region = 0
            redistribute_changed = True
            while redistribute_changed and len(region_set) > 1:
                redistribute_changed = False
                to_redistribute: list[tuple[tuple[int, int, int], int]] = []  # (voxel, target_region)

                for voxel in list(region_set):
                    vx, vy, vz = voxel
                    # Считаем соседей в текущем регионе
                    neighbors_in_current = 0
                    for dx, dy, dz in NEIGHBORS_26:
                        neighbor = (vx + dx, vy + dy, vz + dz)
                        if neighbor in region_set:
                            neighbors_in_current += 1

                    # Если мало соседей — ищем лучший регион
                    if neighbors_in_current < 2:
                        # Считаем соседей в других регионах
                        neighbor_counts: dict[int, int] = {}
                        for dx, dy, dz in NEIGHBORS_26:
                            neighbor = (vx + dx, vy + dy, vz + dz)
                            if neighbor in voxel_to_region:
                                other_idx = voxel_to_region[neighbor]
                                if other_idx != region_idx:
                                    neighbor_counts[other_idx] = neighbor_counts.get(other_idx, 0) + 1

                        # Ищем регион с максимумом соседей, допустимый по нормали
                        best_region = None
                        best_count = neighbors_in_current
                        voxel_normals = surface_voxels.get(voxel, [])

                        for other_idx, count in neighbor_counts.items():
                            if count > best_count:
                                # Проверяем допустимость по нормали
                                other_normal = region_normals[other_idx]
                                for vn in voxel_normals:
                                    if np.dot(vn, other_normal) >= threshold:
                                        best_region = other_idx
                                        best_count = count
                                        break

                        if best_region is not None:
                            to_redistribute.append((voxel, best_region))

                for voxel, target_idx in to_redistribute:
                    region_set.discard(voxel)
                    region_sets[target_idx].add(voxel)
                    voxel_to_region[voxel] = target_idx
                    redistribute_changed = True
                    redistributed_this_region += 1

            total_pruned += redistributed_this_region  # Используем total_pruned для статистики

            if absorbed_this_region > 0 or redistributed_this_region > 0:
                # Пересчитываем нормаль региона
                normal_sum = np.zeros(3, dtype=np.float64)
                for v in region_set:
                    if v in surface_voxels:
                        normal_sum += surface_voxels[v][0]
                norm = np.linalg.norm(normal_sum)
                if norm > 1e-6:
                    region_normals[region_idx] = (normal_sum / norm).astype(np.float32)

        # Собираем результат — пропускаем пустые регионы
        result: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
        empty_count = 0
        for idx in range(len(regions)):
            if len(region_sets[idx]) > 0:
                result.append((list(region_sets[idx]), region_normals[idx]))
            else:
                empty_count += 1

        print(f"PolygonBuilder: greedy absorption: {len(regions)} regions, "
              f"absorbed {total_absorbed} voxels, redistributed {total_pruned} hanging, "
              f"removed {empty_count} empty regions, result: {len(result)} regions")

        return result

    def _add_multi_normal_voxels_to_regions(
        self,
        regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
        surface_voxels: dict[tuple[int, int, int], list[np.ndarray]],
    ) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
        """
        Шаг 2.4: Воксели с несколькими нормалями добавляются во все совместимые регионы.

        Для каждого вокселя с len(normals) > 1:
        - Проверяем каждый регион
        - Если нормаль региона совместима с любой из нормалей вокселя — добавляем
        """
        threshold = self.config.normal_threshold

        # Собираем воксели с несколькими нормалями
        multi_normal_voxels = {
            v: normals for v, normals in surface_voxels.items()
            if len(normals) > 1
        }

        if not multi_normal_voxels:
            return regions

        # Преобразуем регионы в sets для быстрой проверки и модификации
        region_sets: list[set[tuple[int, int, int]]] = [set(voxels) for voxels, _ in regions]
        region_normals: list[np.ndarray] = [normal for _, normal in regions]

        added_count = 0

        for voxel, voxel_normals in multi_normal_voxels.items():
            for region_idx, region_normal in enumerate(region_normals):
                # Пропускаем если воксель уже в этом регионе
                if voxel in region_sets[region_idx]:
                    continue

                # Проверяем совместимость с любой из нормалей вокселя
                for vn in voxel_normals:
                    if np.dot(vn, region_normal) >= threshold:
                        region_sets[region_idx].add(voxel)
                        added_count += 1
                        break

        # Собираем результат
        result = [
            (list(region_sets[i]), region_normals[i])
            for i in range(len(regions))
        ]

        print(f"PolygonBuilder: added {added_count} multi-normal voxels to additional regions")

        return result

    def _expand_all_regions(
        self,
        regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
        surface_voxels: dict[tuple[int, int, int], list[np.ndarray]],
    ) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
        """
        Шаг 2.4: Расширение всех регионов на соседние воксели.

        Каждый регион принимает соседние воксели с подходящими нормалями.
        Воксель может участвовать в нескольких регионах одновременно.
        """
        threshold = self.config.normal_threshold

        # Преобразуем регионы в sets
        region_sets: list[set[tuple[int, int, int]]] = [set(voxels) for voxels, _ in regions]
        region_normals: list[np.ndarray] = [normal for _, normal in regions]

        total_added = 0
        iteration = 0

        # Итеративно расширяем пока есть изменения
        changed = True
        while changed:
            changed = False
            iteration += 1

            for region_idx in range(len(region_sets)):
                region_set = region_sets[region_idx]
                region_normal = region_normals[region_idx]

                # Собираем соседей всех вокселей региона
                candidates: set[tuple[int, int, int]] = set()
                for vx, vy, vz in region_set:
                    for dx, dy, dz in NEIGHBORS_26:
                        neighbor = (vx + dx, vy + dy, vz + dz)
                        # Сосед должен быть surface voxel и не в этом регионе
                        if neighbor in surface_voxels and neighbor not in region_set:
                            candidates.add(neighbor)

                # Проверяем каждого кандидата
                for candidate in candidates:
                    candidate_normals = surface_voxels[candidate]
                    # Проверяем совместимость с любой нормалью кандидата
                    for cn in candidate_normals:
                        if np.dot(cn, region_normal) >= threshold:
                            region_set.add(candidate)
                            total_added += 1
                            changed = True
                            break

        # Собираем результат
        result = [
            (list(region_sets[i]), region_normals[i])
            for i in range(len(regions))
        ]

        print(f"PolygonBuilder: expand_all_regions: {iteration} iterations, added {total_added} voxels")

        return result

    def _filter_hanging_voxels(
        self,
        regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
    ) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
        """
        Шаг 2.6: Фильтрация "висячих" вокселей.

        Для каждого региона независимо:
        - Воксели с <=1 соседом из ЭТОГО региона (по 26-связности) выселяются
        - Воксель может остаться в других регионах, где у него достаточно соседей

        Процесс повторяется итеративно для каждого региона.
        """
        result: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []

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

                # Выселяем помеченные воксели (без создания новых регионов)
                for voxel in to_evict:
                    region_set.discard(voxel)
                    changed = True

                # Если регион стал слишком маленьким — прекращаем
                if len(region_set) <= 2:
                    break

            # Добавляем оставшиеся воксели как регион
            if region_set:
                result.append((list(region_set), region_normal))

        return result

    def _share_boundary_voxels(
        self,
        regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
    ) -> tuple[list[tuple[list[tuple[int, int, int]], np.ndarray]], set[tuple[int, int, int]]]:
        """
        Шаг 2.7: Граничные воксели становятся общими для соседних регионов.

        Для каждого вокселя V в регионе R с индексом i:
        - Если сосед N принадлежит региону S с индексом j > i
        - То V добавляется в регион S

        Это создаёт тонкую (1 воксель) общую границу между регионами.
        Угловые воксели (на стыке 3+ регионов) будут принадлежать всем смежным регионам.

        Returns:
            (обновлённые регионы, множество граничных вокселей)
        """
        # Строим mapping воксель -> множество регионов
        voxel_to_regions: dict[tuple[int, int, int], set[int]] = {}
        for idx, (voxels, _) in enumerate(regions):
            for v in voxels:
                if v not in voxel_to_regions:
                    voxel_to_regions[v] = set()
                voxel_to_regions[v].add(idx)

        # Находим граничные воксели и добавляем их в соседние регионы
        boundary_voxels: set[tuple[int, int, int]] = set()
        # to_add[region_idx] = set of voxels to add
        to_add: dict[int, set[tuple[int, int, int]]] = {i: set() for i in range(len(regions))}

        for region_idx, (region_voxels, _) in enumerate(regions):
            for voxel in region_voxels:
                vx, vy, vz = voxel
                for dx, dy, dz in NEIGHBORS_26:
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor in voxel_to_regions:
                        neighbor_regions = voxel_to_regions[neighbor]
                        for other_idx in neighbor_regions:
                            # Если сосед в регионе с большим индексом — добавляем туда текущий воксель
                            if other_idx > region_idx:
                                to_add[other_idx].add(voxel)
                                boundary_voxels.add(voxel)

        # Децимация границы — удаляем избыточные воксели
        boundary_voxels = self._decimate_boundary(boundary_voxels)

        # Применяем добавления (только оставшиеся после децимации)
        result: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
        for idx, (voxels, normal) in enumerate(regions):
            # Добавляем только те boundary воксели, что остались после децимации
            filtered_to_add = to_add[idx] & boundary_voxels
            new_voxels = set(voxels) | filtered_to_add
            result.append((list(new_voxels), normal))

        print(f"PolygonBuilder: shared {len(boundary_voxels)} boundary voxels between regions")
        return result, boundary_voxels

    def _decimate_boundary(
        self,
        boundary: set[tuple[int, int, int]],
    ) -> set[tuple[int, int, int]]:
        """
        Децимация границы — удаляем избыточные воксели.

        Воксель считается избыточным, если его соседи (из boundary)
        связаны между собой и без него.
        """
        result = set(boundary)
        changed = True
        iteration = 0

        while changed:
            changed = False
            iteration += 1
            to_remove: set[tuple[int, int, int]] = set()

            for voxel in result:
                # Находим соседей этого вокселя, которые тоже в boundary
                # и ещё не помечены на удаление в этой итерации
                vx, vy, vz = voxel
                neighbors_in_boundary: list[tuple[int, int, int]] = []
                for dx, dy, dz in NEIGHBORS_26:
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor in result and neighbor not in to_remove:
                        neighbors_in_boundary.append(neighbor)

                # Концевой воксель (< 2 соседей) — однозначно лишний
                if len(neighbors_in_boundary) < 2:
                    to_remove.add(voxel)
                    continue

                # Проверяем, связаны ли соседи между собой без этого вокселя
                if self._are_connected_26(neighbors_in_boundary):
                    to_remove.add(voxel)

            for voxel in to_remove:
                result.discard(voxel)
                changed = True

        print(f"PolygonBuilder: boundary decimation: {len(boundary)} -> {len(result)} ({iteration} iterations)")
        return result

    def _are_connected_26(self, voxels: list[tuple[int, int, int]]) -> bool:
        """
        Проверить, связаны ли все воксели между собой по 26-связности.
        """
        if len(voxels) <= 1:
            return True

        voxel_set = set(voxels)
        visited: set[tuple[int, int, int]] = set()
        queue = [voxels[0]]
        visited.add(voxels[0])

        while queue:
            current = queue.pop()
            vx, vy, vz = current
            for dx, dy, dz in NEIGHBORS_26:
                neighbor = (vx + dx, vy + dy, vz + dz)
                if neighbor in voxel_set and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return len(visited) == len(voxels)

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

    # =========== Contour Extraction ===========

    def extract_ordered_contours(
        self,
        region_voxels: list[tuple[int, int, int]],
        region_normal: np.ndarray,
        cell_size: float,
        origin: np.ndarray,
        simplify_epsilon: float = 0.0,
    ) -> tuple[np.ndarray, list[np.ndarray]]:
        """
        Извлечь упорядоченные контуры региона как 3D координаты.

        Args:
            region_voxels: Список вокселей региона.
            region_normal: Нормаль региона.
            cell_size: Размер вокселя.
            origin: Начало координат сетки.
            simplify_epsilon: Параметр Douglas-Peucker (0 = без упрощения).

        Returns:
            (outer_vertices, holes_vertices):
                outer_vertices: np.ndarray shape (N, 3) — вершины внешнего контура
                holes_vertices: список np.ndarray — вершины дырок
        """
        # Получаем упорядоченные воксельные контуры
        outer_voxels, holes_voxels = self.extract_contours_from_region(
            region_voxels, region_normal, cell_size, origin
        )

        if not outer_voxels:
            return np.array([]).reshape(0, 3), []

        # Строим плоскость региона
        u_axis, v_axis = self._build_2d_basis(region_normal)
        region_normal = region_normal / np.linalg.norm(region_normal)

        # Центроид региона
        centers_3d = np.array([
            origin + (np.array(v) + 0.5) * cell_size
            for v in region_voxels
        ], dtype=np.float32)
        centroid = centers_3d.mean(axis=0)

        def project_to_plane(voxels: list[tuple[int, int, int]]) -> np.ndarray:
            """Проецировать центры вокселей на плоскость региона."""
            if not voxels:
                return np.array([]).reshape(0, 3)

            vertices = []
            for vx, vy, vz in voxels:
                # Центр вокселя в мировых координатах
                world_pos = origin + (np.array([vx, vy, vz]) + 0.5) * cell_size

                # Проецируем на плоскость региона
                to_point = world_pos - centroid
                distance_to_plane = np.dot(to_point, region_normal)
                projected = world_pos - distance_to_plane * region_normal

                vertices.append(projected)

            return np.array(vertices, dtype=np.float32)

        # Проецируем контуры на плоскость
        outer_vertices = project_to_plane(outer_voxels)
        holes_vertices = [project_to_plane(h) for h in holes_voxels]

        # Применяем Douglas-Peucker если нужно
        if simplify_epsilon > 0:
            outer_vertices = self._douglas_peucker_3d(outer_vertices, simplify_epsilon)
            holes_vertices = [
                self._douglas_peucker_3d(h, simplify_epsilon)
                for h in holes_vertices
            ]

        return outer_vertices, holes_vertices

    def _douglas_peucker_3d(
        self,
        points: np.ndarray,
        epsilon: float,
    ) -> np.ndarray:
        """
        Упростить 3D полилинию алгоритмом Douglas-Peucker.

        Args:
            points: np.ndarray shape (N, 3) — вершины полилинии.
            epsilon: Максимальное отклонение.

        Returns:
            Упрощённая полилиния.
        """
        if len(points) <= 2:
            return points

        # Находим точку с максимальным отклонением от линии start-end
        start = points[0]
        end = points[-1]
        line_vec = end - start
        line_len = np.linalg.norm(line_vec)

        if line_len < 1e-10:
            return points[[0]]

        line_dir = line_vec / line_len

        max_dist = 0.0
        max_idx = 0

        for i in range(1, len(points) - 1):
            # Расстояние от точки до линии
            to_point = points[i] - start
            proj_len = np.dot(to_point, line_dir)
            proj_point = start + proj_len * line_dir
            dist = np.linalg.norm(points[i] - proj_point)

            if dist > max_dist:
                max_dist = dist
                max_idx = i

        if max_dist > epsilon:
            # Рекурсивно упрощаем обе части
            left = self._douglas_peucker_3d(points[:max_idx + 1], epsilon)
            right = self._douglas_peucker_3d(points[max_idx:], epsilon)
            return np.vstack([left[:-1], right])
        else:
            return points[[0, -1]]

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
        u_axis, v_axis = self._build_2d_basis(region_normal)

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
                            line_cells = self._bresenham_line(u1, v1, u2, v2)

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
        outer_2d, holes_2d = self._extract_contours_from_mask(mask)

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

    def _bresenham_line(
        self, x0: int, y0: int, x1: int, y1: int
    ) -> list[tuple[int, int]]:
        """Алгоритм Брезенхема для рисования линии между двумя точками."""
        cells: list[tuple[int, int]] = []

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        x, y = x0, y0
        while True:
            cells.append((x, y))
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

        return cells

    def _build_2d_basis(self, normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Построить ортонормированный базис для плоскости с заданной нормалью.

        Returns:
            (u_axis, v_axis) - два ортогональных вектора в плоскости.
        """
        normal = normal / np.linalg.norm(normal)

        # Выбираем ось, наименее параллельную нормали
        abs_n = np.abs(normal)
        if abs_n[0] <= abs_n[1] and abs_n[0] <= abs_n[2]:
            arbitrary = np.array([1.0, 0.0, 0.0])
        elif abs_n[1] <= abs_n[2]:
            arbitrary = np.array([0.0, 1.0, 0.0])
        else:
            arbitrary = np.array([0.0, 0.0, 1.0])

        u_axis = np.cross(normal, arbitrary)
        u_axis = u_axis / np.linalg.norm(u_axis)

        v_axis = np.cross(normal, u_axis)
        v_axis = v_axis / np.linalg.norm(v_axis)

        return u_axis, v_axis

    def _extract_contours_from_mask(
        self, mask: np.ndarray
    ) -> tuple[list[tuple[int, int]], list[list[tuple[int, int]]]]:
        """
        Извлечь внешний и внутренние контуры из бинарной маски.

        Алгоритм:
        1. Flood fill от края — помечаем "внешнюю пустоту"
        2. Граничные ячейки = заполненные с пустым соседом
        3. Outer = граничные, соседствующие с внешней пустотой
        4. Inner = граничные, соседствующие с внутренней пустотой
        5. Разделить inner на связные компоненты

        Args:
            mask: 2D массив (height, width), 1 = занято, 0 = пусто.

        Returns:
            (outer_contour, holes) - внешний контур и список дырок.
        """
        height, width = mask.shape

        # 8-связность
        directions = [
            (1, 0), (1, 1), (0, 1), (-1, 1),
            (-1, 0), (-1, -1), (0, -1), (1, -1)
        ]

        # Шаг 1: Flood fill от края — помечаем внешнюю пустоту
        external = np.zeros_like(mask, dtype=np.uint8)
        queue = deque()

        # Добавляем все пустые ячейки на краях
        for u in range(width):
            if mask[0, u] == 0:
                queue.append((u, 0))
                external[0, u] = 1
            if mask[height - 1, u] == 0:
                queue.append((u, height - 1))
                external[height - 1, u] = 1
        for v in range(height):
            if mask[v, 0] == 0:
                queue.append((0, v))
                external[v, 0] = 1
            if mask[v, width - 1] == 0:
                queue.append((width - 1, v))
                external[v, width - 1] = 1

        # Flood fill
        while queue:
            u, v = queue.popleft()
            for du, dv in directions:
                nu, nv = u + du, v + dv
                if 0 <= nu < width and 0 <= nv < height:
                    if mask[nv, nu] == 0 and external[nv, nu] == 0:
                        external[nv, nu] = 1
                        queue.append((nu, nv))

        # Шаг 2-4: Классифицируем граничные ячейки
        outer_cells: list[tuple[int, int]] = []
        inner_cells: list[tuple[int, int]] = []

        for v in range(height):
            for u in range(width):
                if mask[v, u] == 0:
                    continue

                has_external_neighbor = False
                has_internal_neighbor = False

                for du, dv in directions:
                    nu, nv = u + du, v + dv
                    if nu < 0 or nu >= width or nv < 0 or nv >= height:
                        has_external_neighbor = True
                    elif mask[nv, nu] == 0:
                        if external[nv, nu] == 1:
                            has_external_neighbor = True
                        else:
                            has_internal_neighbor = True

                if has_external_neighbor:
                    outer_cells.append((u, v))
                elif has_internal_neighbor:
                    inner_cells.append((u, v))

        # Шаг 5: Разделить inner на связные компоненты
        holes: list[list[tuple[int, int]]] = []
        if inner_cells:
            inner_set = set(inner_cells)
            visited: set[tuple[int, int]] = set()

            for start in inner_cells:
                if start in visited:
                    continue

                # BFS для связной компоненты
                component: list[tuple[int, int]] = []
                q = deque([start])
                visited.add(start)

                while q:
                    u, v = q.popleft()
                    component.append((u, v))

                    for du, dv in directions:
                        neighbor = (u + du, v + dv)
                        if neighbor in inner_set and neighbor not in visited:
                            visited.add(neighbor)
                            q.append(neighbor)

                if component:
                    holes.append(component)

        # Шаг 6: Упорядочить контуры (обход по/против часовой)
        outer_ordered = self._order_contour(outer_cells, directions)
        holes_ordered = [self._order_contour(h, directions) for h in holes]

        return outer_ordered, holes_ordered

    def _order_contour(
        self,
        cells: list[tuple[int, int]],
        directions: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """
        Упорядочить ячейки контура обходом по периметру.

        Args:
            cells: Неупорядоченный список ячеек контура.
            directions: Направления для 8-связности.

        Returns:
            Упорядоченный список ячеек (обход по часовой стрелке).
        """
        if len(cells) <= 2:
            return cells

        cell_set = set(cells)

        # Начинаем с самой верхней-левой ячейки
        start = min(cells, key=lambda c: (c[1], c[0]))
        ordered: list[tuple[int, int]] = [start]
        visited: set[tuple[int, int]] = {start}

        current = start
        # Начинаем поиск с востока (индекс 0)
        last_dir = 4  # Пришли с запада

        while True:
            found = False
            # Ищем следующего соседа по часовой стрелке
            # Начинаем с направления "назад + 2" (против часовой от направления прихода)
            search_start = (last_dir + 5) % 8

            for i in range(8):
                dir_idx = (search_start + i) % 8
                du, dv = directions[dir_idx]
                neighbor = (current[0] + du, current[1] + dv)

                if neighbor in cell_set and neighbor not in visited:
                    ordered.append(neighbor)
                    visited.add(neighbor)
                    current = neighbor
                    last_dir = dir_idx
                    found = True
                    break

            if not found:
                # Проверяем, можем ли вернуться к старту
                for i in range(8):
                    dir_idx = (search_start + i) % 8
                    du, dv = directions[dir_idx]
                    neighbor = (current[0] + du, current[1] + dv)
                    if neighbor == start:
                        break
                break

        return ordered

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
        outer_voxels, holes_voxels = self.extract_contours_from_region(
            region_voxels, region_normal, cell_size, origin
        )

        if len(outer_voxels) < 3:
            return np.array([]).reshape(0, 3), np.array([]).reshape(0, 3).astype(np.int32)

        # Шаг 2: Проекция на плоскость и переход в 2D
        u_axis, v_axis = self._build_2d_basis(region_normal)
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
            outer_2d = self._douglas_peucker_2d(outer_2d, simplify_epsilon)
            holes_2d = [self._douglas_peucker_2d(h, simplify_epsilon) for h in holes_2d if len(h) >= 3]

        # Удаляем слишком маленькие дырки после упрощения
        holes_2d = [h for h in holes_2d if len(h) >= 3]

        if len(outer_2d) < 3:
            return np.array([]).reshape(0, 3), np.array([]).reshape(0, 3).astype(np.int32)

        # Шаг 4: Bridge (объединение дырок с внешним контуром)
        if holes_2d:
            merged_2d = self._merge_holes_with_bridges(outer_2d, holes_2d)
        else:
            merged_2d = outer_2d

        if len(merged_2d) < 3:
            return np.array([]).reshape(0, 3), np.array([]).reshape(0, 3).astype(np.int32)

        # Шаг 5: Ear Clipping в 2D
        triangles = self._ear_clip(merged_2d)

        if len(triangles) == 0:
            return np.array([]).reshape(0, 3), np.array([]).reshape(0, 3).astype(np.int32)

        # Шаг 6: Преобразование вершин обратно в 3D
        vertices_3d = self._transform_to_3d(merged_2d, centroid, u_axis, v_axis)

        return vertices_3d, np.array(triangles, dtype=np.int32)

    def _douglas_peucker_2d(
        self,
        points: np.ndarray,
        epsilon: float,
    ) -> np.ndarray:
        """
        Упростить 2D полилинию алгоритмом Douglas-Peucker.

        Args:
            points: np.ndarray shape (N, 2) — вершины полилинии.
            epsilon: Максимальное отклонение.

        Returns:
            Упрощённая полилиния shape (M, 2).
        """
        if len(points) <= 2:
            return points

        # Для замкнутого контура: находим две самые далёкие точки
        # и разбиваем на две части
        n = len(points)

        # Находим точку с максимальным отклонением от линии start-end
        start = points[0]
        end = points[-1]
        line_vec = end - start
        line_len = np.linalg.norm(line_vec)

        if line_len < 1e-10:
            return points[[0]]

        line_dir = line_vec / line_len

        max_dist = 0.0
        max_idx = 0

        for i in range(1, n - 1):
            # Расстояние от точки до линии
            to_point = points[i] - start
            proj_len = np.dot(to_point, line_dir)
            proj_point = start + proj_len * line_dir
            dist = np.linalg.norm(points[i] - proj_point)

            if dist > max_dist:
                max_dist = dist
                max_idx = i

        if max_dist > epsilon:
            # Рекурсивно упрощаем обе части
            left = self._douglas_peucker_2d(points[:max_idx + 1], epsilon)
            right = self._douglas_peucker_2d(points[max_idx:], epsilon)
            return np.vstack([left[:-1], right])
        else:
            return points[[0, -1]]

    def _merge_holes_with_bridges(
        self,
        outer: np.ndarray,
        holes: list[np.ndarray],
    ) -> np.ndarray:
        """
        Объединить дырки с внешним контуром через bridge edges.

        Алгоритм:
        1. Сортируем дырки по максимальному X (правая вершина)
        2. Для каждой дырки:
           a) Находим вершину с максимальным X
           b) Ищем видимую вершину на внешнем контуре
           c) Вставляем дырку в контур через мост

        Args:
            outer: Внешний контур shape (N, 2), CCW ориентация.
            holes: Список дырок, каждая shape (M, 2), CW ориентация.

        Returns:
            Объединённый контур shape (K, 2).
        """
        if not holes:
            return outer

        # Копируем контур для модификации
        result = list(outer)

        # Сортируем дырки по максимальному X (обрабатываем справа налево)
        sorted_holes = sorted(
            holes,
            key=lambda h: max(p[0] for p in h),
            reverse=True
        )

        for hole in sorted_holes:
            if len(hole) < 3:
                continue

            # Находим вершину дырки с максимальным X
            hole_list = list(hole)
            max_x_idx = max(range(len(hole_list)), key=lambda i: hole_list[i][0])
            bridge_hole_vertex = hole_list[max_x_idx]

            # Ищем видимую вершину на внешнем контуре
            bridge_outer_idx = self._find_bridge_vertex(
                result, bridge_hole_vertex, hole_list
            )

            if bridge_outer_idx is None:
                continue

            # Вставляем дырку в контур
            # Outer CCW, hole нужно пройти CW (в обратном направлении)
            new_contour = []

            # Часть внешнего контура до bridge vertex (включительно)
            for i in range(bridge_outer_idx + 1):
                new_contour.append(result[i])

            # Дырка в обратном порядке, начиная с max_x_idx
            # Если hole дан как CCW, проходим его CW: max_x, max_x-1, ..., 0, n-1, ..., max_x+1
            for i in range(len(hole_list)):
                idx = (max_x_idx - i) % len(hole_list)
                new_contour.append(hole_list[idx])

            # Возврат к bridge vertex (замыкаем мост)
            new_contour.append(hole_list[max_x_idx])
            new_contour.append(result[bridge_outer_idx])

            # Остаток внешнего контура
            for i in range(bridge_outer_idx + 1, len(result)):
                new_contour.append(result[i])

            result = new_contour

        return np.array(result, dtype=np.float32)

    def _find_bridge_vertex(
        self,
        contour: list,
        hole_point: np.ndarray,
        hole: list,
    ) -> int | None:
        """
        Найти вершину контура для моста с точкой дырки.

        Упрощённый алгоритм:
        1. Находим все вершины контура, видимые из hole_point
        2. Среди видимых выбираем ближайшую

        Args:
            contour: Список вершин контура [(x, y), ...].
            hole_point: Точка дырки (x, y).
            hole: Список вершин дырки для проверки пересечений.

        Returns:
            Индекс вершины контура или None.
        """
        n = len(contour)
        hx, hy = hole_point[0], hole_point[1]

        # Находим все видимые вершины и их расстояния
        visible_vertices = []

        for i in range(n):
            if self._is_vertex_visible(contour, i, hole_point, hole):
                dx = contour[i][0] - hx
                dy = contour[i][1] - hy
                dist = dx * dx + dy * dy
                visible_vertices.append((dist, i))

        if not visible_vertices:
            # Ни одна вершина не видима - берём ближайшую
            min_dist = float('inf')
            best_idx = 0
            for i in range(n):
                dx = contour[i][0] - hx
                dy = contour[i][1] - hy
                dist = dx * dx + dy * dy
                if dist < min_dist:
                    min_dist = dist
                    best_idx = i
            return best_idx

        # Возвращаем ближайшую видимую вершину
        visible_vertices.sort(key=lambda x: x[0])
        return visible_vertices[0][1]

    def _is_vertex_visible(
        self,
        contour: list,
        vertex_idx: int,
        point: np.ndarray,
        hole: list,
    ) -> bool:
        """
        Проверить, видима ли вершина контура из точки.

        Args:
            contour: Список вершин контура.
            vertex_idx: Индекс вершины.
            point: Точка, из которой проверяем видимость.
            hole: Список вершин дырки (для проверки пересечений).

        Returns:
            True если вершина видима.
        """
        vertex = contour[vertex_idx]
        n = len(contour)

        # Проверяем пересечение отрезка (point, vertex) со всеми рёбрами контура
        for i in range(n):
            if i == vertex_idx or (i + 1) % n == vertex_idx:
                continue  # Пропускаем смежные рёбра

            if i == (vertex_idx - 1) % n:
                continue

            p1 = contour[i]
            p2 = contour[(i + 1) % n]

            if self._segments_intersect_strict(point, vertex, p1, p2):
                return False

        # Проверяем пересечение с рёбрами дырки
        m = len(hole)
        for i in range(m):
            p1 = hole[i]
            p2 = hole[(i + 1) % m]

            if self._segments_intersect_strict(point, vertex, p1, p2):
                return False

        return True

    def _segments_intersect_strict(
        self,
        a1: np.ndarray,
        a2: np.ndarray,
        b1: np.ndarray,
        b2: np.ndarray,
    ) -> bool:
        """
        Проверить строгое пересечение двух отрезков (без касания в точках).

        Args:
            a1, a2: Концы первого отрезка.
            b1, b2: Концы второго отрезка.

        Returns:
            True если отрезки пересекаются строго (не в концах).
        """
        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        d1 = cross(b1, b2, a1)
        d2 = cross(b1, b2, a2)
        d3 = cross(a1, a2, b1)
        d4 = cross(a1, a2, b2)

        if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
           ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
            return True

        return False

    def _ear_clip(self, polygon: np.ndarray) -> list[tuple[int, int, int]]:
        """
        Триангулировать простой полигон методом Ear Clipping.

        Args:
            polygon: np.ndarray shape (N, 2) — вершины полигона.

        Returns:
            Список треугольников [(i, j, k), ...].
        """
        n = len(polygon)
        if n < 3:
            return []

        if n == 3:
            return [(0, 1, 2)]

        # Определяем ориентацию полигона (CCW = положительная площадь)
        area = self._signed_area_2d(polygon)
        ccw = area > 0

        # Создаём связный список индексов
        indices = list(range(n))
        triangles = []

        # Пытаемся найти и отрезать уши
        max_iterations = n * n  # Защита от бесконечного цикла
        iteration = 0

        while len(indices) > 3 and iteration < max_iterations:
            iteration += 1
            found_ear = False

            for i in range(len(indices)):
                prev_i = (i - 1) % len(indices)
                next_i = (i + 1) % len(indices)

                prev_idx = indices[prev_i]
                curr_idx = indices[i]
                next_idx = indices[next_i]

                prev_p = polygon[prev_idx]
                curr_p = polygon[curr_idx]
                next_p = polygon[next_idx]

                # Проверяем выпуклость вершины
                if not self._is_convex_2d(prev_p, curr_p, next_p, ccw):
                    continue

                # Проверяем, что треугольник не содержит других вершин
                is_ear = True
                for j in range(len(indices)):
                    if j == prev_i or j == i or j == next_i:
                        continue

                    test_idx = indices[j]
                    test_p = polygon[test_idx]

                    # Пропускаем вершины, совпадающие с вершинами треугольника
                    # (могут появиться при bridge для дырок)
                    eps = 1e-10
                    if (abs(test_p[0] - prev_p[0]) < eps and abs(test_p[1] - prev_p[1]) < eps):
                        continue
                    if (abs(test_p[0] - curr_p[0]) < eps and abs(test_p[1] - curr_p[1]) < eps):
                        continue
                    if (abs(test_p[0] - next_p[0]) < eps and abs(test_p[1] - next_p[1]) < eps):
                        continue

                    if self._point_in_triangle_2d(test_p, prev_p, curr_p, next_p):
                        is_ear = False
                        break

                if is_ear:
                    # Добавляем треугольник
                    triangles.append((prev_idx, curr_idx, next_idx))
                    # Удаляем вершину
                    indices.pop(i)
                    found_ear = True
                    break

            if not found_ear:
                # Не удалось найти ухо - полигон может быть самопересекающимся
                break

        # Добавляем последний треугольник
        if len(indices) == 3:
            triangles.append((indices[0], indices[1], indices[2]))

        return triangles

    def _signed_area_2d(self, polygon: np.ndarray) -> float:
        """Вычислить знаковую площадь полигона (положительная для CCW)."""
        n = len(polygon)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += polygon[i][0] * polygon[j][1]
            area -= polygon[j][0] * polygon[i][1]
        return area / 2.0

    def _is_convex_2d(
        self,
        prev_p: np.ndarray,
        curr_p: np.ndarray,
        next_p: np.ndarray,
        ccw: bool,
    ) -> bool:
        """Проверить, является ли вершина выпуклой."""
        cross = (curr_p[0] - prev_p[0]) * (next_p[1] - curr_p[1]) - \
                (curr_p[1] - prev_p[1]) * (next_p[0] - curr_p[0])

        if ccw:
            return cross > 0
        else:
            return cross < 0

    def _point_in_triangle_2d(
        self,
        p: np.ndarray,
        a: np.ndarray,
        b: np.ndarray,
        c: np.ndarray,
    ) -> bool:
        """Проверить, находится ли точка внутри треугольника (строго)."""
        def sign(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

        d1 = sign(p, a, b)
        d2 = sign(p, b, c)
        d3 = sign(p, c, a)

        has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)

        return not (has_neg and has_pos)

    def _transform_to_3d(
        self,
        points_2d: np.ndarray,
        origin: np.ndarray,
        u_axis: np.ndarray,
        v_axis: np.ndarray,
    ) -> np.ndarray:
        """
        Преобразовать 2D точки обратно в 3D.

        Args:
            points_2d: np.ndarray shape (N, 2).
            origin: Центр плоскости в 3D.
            u_axis: U ось плоскости.
            v_axis: V ось плоскости.

        Returns:
            np.ndarray shape (N, 3).
        """
        n = len(points_2d)
        points_3d = np.zeros((n, 3), dtype=np.float32)

        for i in range(n):
            u, v = points_2d[i]
            points_3d[i] = origin + u * u_axis + v * v_axis

        return points_3d

