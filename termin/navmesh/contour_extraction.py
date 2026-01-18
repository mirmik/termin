"""
Извлечение контуров из воксельных регионов.

Алгоритмы для нахождения внешнего контура и дырок.
Алгоритмы для вычисления distance field.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import numpy as np

from termin.navmesh.triangulation import build_2d_basis


def compute_distance_field_2d(
    mask: np.ndarray,
) -> np.ndarray:
    """
    Вычислить distance field для 2D бинарной маски.

    Расстояние = кратчайший путь до границы через заполненные ячейки.
    Использует Dijkstra с весами рёбер.

    Args:
        mask: 2D массив (height, width), 1 = занято, 0 = пусто.

    Returns:
        2D массив той же формы с расстояниями (float32).
        Пустые ячейки имеют distance = 0.
        Граничные заполненные ячейки имеют distance = 0.
        Внутренние ячейки имеют distance > 0.
    """
    import heapq
    import math

    height, width = mask.shape
    distance = np.full((height, width), np.inf, dtype=np.float32)
    distance[mask == 0] = 0.0

    # 8-связность с весами
    sqrt2 = math.sqrt(2)
    directions = [
        # (du, dv, weight)
        (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, sqrt2), (1, -1, sqrt2), (-1, 1, sqrt2), (-1, -1, sqrt2),
    ]

    # 4-связность для определения границы
    cardinal = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    # Priority queue: (distance, u, v)
    heap: list[tuple[float, int, int]] = []

    # Находим граничные ячейки (заполненные с пустым соседом)
    for v in range(height):
        for u in range(width):
            if mask[v, u] == 0:
                continue

            is_boundary = False
            for du, dv in cardinal:
                nu, nv = u + du, v + dv
                if nu < 0 or nu >= width or nv < 0 or nv >= height:
                    is_boundary = True
                    break
                if mask[nv, nu] == 0:
                    is_boundary = True
                    break

            if is_boundary:
                distance[v, u] = 0.0
                heapq.heappush(heap, (0.0, u, v))

    # Dijkstra от границы внутрь
    while heap:
        dist, u, v = heapq.heappop(heap)

        for du, dv, weight in directions:
            nu, nv = u + du, v + dv
            if 0 <= nu < width and 0 <= nv < height:
                if mask[nv, nu] == 0:
                    continue

                new_dist = dist + weight

                if new_dist < distance[nv, nu]:
                    distance[nv, nu] = new_dist
                    heapq.heappush(heap, (new_dist, nu, nv))

    # Заменяем inf на 0 для незаполненных ячеек
    distance[np.isinf(distance)] = 0.0

    return distance


def smooth_distance_field_2d(
    distance_field: np.ndarray,
    mask: np.ndarray,
    iterations: int = 1,
) -> np.ndarray:
    """
    Сгладить distance field усреднением по соседям.

    Применяет mean filter только к заполненным ячейкам.
    Сглаживание убирает мелкие локальные максимумы на хребтах.

    Args:
        distance_field: 2D массив расстояний.
        mask: 2D бинарная маска (1 = занято).
        iterations: Количество итераций сглаживания.

    Returns:
        Сглаженный distance field.
    """
    height, width = distance_field.shape
    result = distance_field.copy()

    # 8-связность
    directions = [
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    ]

    for _ in range(int(iterations)):
        new_result = result.copy()

        for v in range(height):
            for u in range(width):
                if mask[v, u] == 0:
                    continue

                # Собираем значения соседей
                total = result[v, u]
                count = 1

                for du, dv in directions:
                    nu, nv = u + du, v + dv
                    if 0 <= nu < width and 0 <= nv < height:
                        if mask[nv, nu] == 1:
                            total += result[nv, nu]
                            count += 1

                new_result[v, u] = total / count

        result = new_result

    return result


def find_distance_field_peaks_2d(
    distance_field: np.ndarray,
    debug: bool = False,
) -> tuple[set[tuple[int, int]], list[tuple[int, int]]]:
    """
    Найти локальные максимумы в 2D distance field.

    Пик — это ячейка, значение которой >= всех 8 соседей.
    Для plateau выбирается один представитель (центр масс).

    Args:
        distance_field: 2D массив расстояний (float).
        debug: Выводить отладочную информацию.

    Returns:
        (all_local_maxima, plateau_peaks):
            all_local_maxima: Все локальные максимумы (до фильтрации плато).
            plateau_peaks: По одному пику на каждое плато.
    """
    height, width = distance_field.shape

    # 8-связность
    directions = [
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    ]

    # Находим все ячейки, которые являются локальными максимумами или частью plateau
    peak_candidates: set[tuple[int, int]] = set()

    for v in range(height):
        for u in range(width):
            dist = distance_field[v, u]
            if dist <= 0:
                continue

            is_peak = True
            for du, dv in directions:
                nu, nv = u + du, v + dv
                if 0 <= nu < width and 0 <= nv < height:
                    if distance_field[nv, nu] > dist:
                        is_peak = False
                        break

            if is_peak:
                peak_candidates.add((u, v))

    if debug:
        print(f"    peaks: candidates={len(peak_candidates)}")

    if not peak_candidates:
        return set(), []

    # Группируем соседние peak_candidates с близким distance (plateaus)
    # Порог для "одинакового" distance — разница меньше 0.5 ячейки
    visited: set[tuple[int, int]] = set()
    peaks: list[tuple[int, int]] = []

    for start in peak_candidates:
        if start in visited:
            continue

        # BFS для нахождения plateau
        plateau: list[tuple[int, int]] = []
        queue = deque([start])
        visited.add(start)
        plateau_dist = distance_field[start[1], start[0]]

        while queue:
            u, v = queue.popleft()
            plateau.append((u, v))

            for du, dv in directions:
                nu, nv = u + du, v + dv
                neighbor = (nu, nv)
                if neighbor in peak_candidates and neighbor not in visited:
                    # Близкий distance (часть того же plateau)
                    if abs(distance_field[nv, nu] - plateau_dist) < 0.5:
                        visited.add(neighbor)
                        queue.append(neighbor)

        # Выбираем центр масс plateau как представителя
        if plateau:
            center_u = sum(p[0] for p in plateau) // len(plateau)
            center_v = sum(p[1] for p in plateau) // len(plateau)
            # Находим ближайшую ячейку plateau к центру
            best = min(plateau, key=lambda p: (p[0] - center_u) ** 2 + (p[1] - center_v) ** 2)
            peaks.append(best)

            if debug:
                print(f"    plateau: size={len(plateau)}, dist={plateau_dist:.2f}, peak={best}")

    if debug:
        print(f"    peaks: final={len(peaks)}")

    return peak_candidates, peaks


@dataclass
class Watershed2DResult:
    """Результат watershed в 2D."""
    labels: np.ndarray
    num_regions: int
    smoothed_distance_field: np.ndarray
    all_local_maxima: set[tuple[int, int]]
    peaks: list[tuple[int, int]]


def watershed_split_2d(
    mask: np.ndarray,
    distance_field: np.ndarray,
    smoothing: int = 0,
) -> Watershed2DResult:
    """
    Разбить 2D маску на под-регионы с помощью watershed.

    Args:
        mask: 2D бинарная маска (1 = занято, 0 = пусто).
        distance_field: 2D distance field для маски (float).
        smoothing: Количество итераций сглаживания distance field.

    Returns:
        Watershed2DResult с labels, smoothed_df, peaks и т.д.
    """
    height, width = mask.shape
    labels = np.zeros((height, width), dtype=np.int32)

    # Сглаживание distance field для устранения ложных пиков на хребтах
    if smoothing > 0:
        smoothed_df = smooth_distance_field_2d(distance_field, mask, smoothing)
    else:
        smoothed_df = distance_field.copy()

    print(f"  watershed: mask {width}x{height}, smoothing={smoothing}")

    # Находим пики
    all_local_maxima, peaks = find_distance_field_peaks_2d(smoothed_df)
    print(f"  watershed: found {len(peaks)} peaks, {len(all_local_maxima)} local maxima")

    if not peaks:
        # Нет пиков — весь регион как один
        labels[mask == 1] = 1
        return Watershed2DResult(
            labels=labels,
            num_regions=1,
            smoothed_distance_field=smoothed_df,
            all_local_maxima=all_local_maxima,
            peaks=peaks,
        )

    # Присваиваем пикам метки
    for idx, (pu, pv) in enumerate(peaks):
        labels[pv, pu] = idx + 1

    # 4-связность для flooding
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    # BFS для равномерного роста всех регионов
    # Все регионы растут на один слой за итерацию
    frontier: list[tuple[int, int]] = list(peaks)

    while frontier:
        next_frontier: list[tuple[int, int]] = []

        for u, v in frontier:
            current_label = labels[v, u]

            for du, dv in directions:
                nu, nv = u + du, v + dv
                if 0 <= nu < width and 0 <= nv < height:
                    if mask[nv, nu] == 1 and labels[nv, nu] == 0:
                        labels[nv, nu] = current_label
                        next_frontier.append((nu, nv))

        frontier = next_frontier

    # Перенумеруем метки
    unique_labels = sorted(set(labels.flat) - {0})

    if len(unique_labels) != len(peaks):
        print(f"  watershed: WARNING peaks={len(peaks)}, but unique_labels={len(unique_labels)}")
        for idx, (pu, pv) in enumerate(peaks):
            label = idx + 1
            count = int(np.sum(labels == label))
            print(f"    peak {idx}: ({pu}, {pv}) -> label {label}, count={count}")

    label_remap = {old: new for new, old in enumerate(unique_labels, 1)}
    label_remap[0] = 0

    new_labels = np.zeros_like(labels)
    for old, new in label_remap.items():
        new_labels[labels == old] = new

    return Watershed2DResult(
        labels=new_labels,
        num_regions=len(unique_labels),
        smoothed_distance_field=smoothed_df,
        all_local_maxima=all_local_maxima,
        peaks=peaks,
    )


@dataclass
class WatershedResult:
    """Результат watershed разбиения региона."""
    sub_regions: list[list[tuple[int, int, int]]]
    """Список под-регионов."""
    distance_field: dict[tuple[int, int, int], float]
    """Distance field (voxel -> distance). Сглаженный если smoothing > 0."""
    peaks: set[tuple[int, int, int]]
    """Пики (локальные максимумы после plateau фильтрации)."""
    all_local_maxima: set[tuple[int, int, int]]
    """Все локальные максимумы (до plateau фильтрации)."""


def watershed_split_region(
    region_voxels: list[tuple[int, int, int]],
    region_normal: np.ndarray,
    cell_size: float,
    origin: np.ndarray,
    smoothing: int = 0,
) -> WatershedResult:
    """
    Разбить регион на под-регионы с помощью watershed.

    Args:
        region_voxels: Список вокселей региона.
        region_normal: Нормаль региона.
        cell_size: Размер вокселя.
        origin: Начало координат.
        smoothing: Количество итераций сглаживания distance field.

    Returns:
        WatershedResult с под-регионами и промежуточными данными.
    """
    # Вспомогательная функция для конвертации 2D точек в 3D воксели
    def map_2d_to_3d(
        points_2d,
        grid_2d_to_voxels: dict[tuple[int, int], list[tuple[int, int, int]]],
        offset_u: int,
        offset_v: int,
    ) -> set[tuple[int, int, int]]:
        result: set[tuple[int, int, int]] = set()
        for (pu, pv) in points_2d:
            grid_u = pu - offset_u
            grid_v = pv - offset_v
            if (grid_u, grid_v) in grid_2d_to_voxels:
                for voxel in grid_2d_to_voxels[(grid_u, grid_v)]:
                    result.add(voxel)
        return result

    # Пустой результат для граничных случаев
    def empty_result() -> WatershedResult:
        return WatershedResult(
            sub_regions=[region_voxels],
            distance_field={v: 0.0 for v in region_voxels},
            peaks=set(),
            all_local_maxima=set(),
        )

    if len(region_voxels) < 2:
        return empty_result()

    # Строим 2D проекцию
    u_axis, v_axis = build_2d_basis(region_normal)

    centers_3d = np.array([
        origin + (np.array(v) + 0.5) * cell_size
        for v in region_voxels
    ], dtype=np.float32)
    centroid = centers_3d.mean(axis=0)

    # Проецируем воксели
    voxel_to_2d: dict[tuple[int, int, int], tuple[int, int]] = {}
    grid_2d_to_voxels: dict[tuple[int, int], list[tuple[int, int, int]]] = {}

    for voxel in region_voxels:
        vx, vy, vz = voxel
        world_pos = origin + (np.array([vx, vy, vz]) + 0.5) * cell_size
        rel_pos = world_pos - centroid
        u = float(np.dot(rel_pos, u_axis))
        v = float(np.dot(rel_pos, v_axis))
        grid_u = int(round(u / cell_size))
        grid_v = int(round(v / cell_size))
        voxel_to_2d[voxel] = (grid_u, grid_v)
        if (grid_u, grid_v) not in grid_2d_to_voxels:
            grid_2d_to_voxels[(grid_u, grid_v)] = []
        grid_2d_to_voxels[(grid_u, grid_v)].append(voxel)

    # Связность через Bresenham
    region_set = set(region_voxels)
    for voxel in region_voxels:
        vx, vy, vz = voxel
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor in region_set and neighbor > voxel:
                        u1, v1 = voxel_to_2d[voxel]
                        u2, v2 = voxel_to_2d[neighbor]
                        line_cells = bresenham_line(u1, v1, u2, v2)
                        for cell in line_cells:
                            if cell not in grid_2d_to_voxels:
                                grid_2d_to_voxels[cell] = [voxel]

    # Создаём маску
    all_2d = list(grid_2d_to_voxels.keys())
    if not all_2d:
        return empty_result()

    min_u = min(p[0] for p in all_2d)
    max_u = max(p[0] for p in all_2d)
    min_v = min(p[1] for p in all_2d)
    max_v = max(p[1] for p in all_2d)

    width = max_u - min_u + 3
    height = max_v - min_v + 3
    offset_u = -min_u + 1
    offset_v = -min_v + 1

    mask = np.zeros((height, width), dtype=np.uint8)
    for (gu, gv) in all_2d:
        mask[gv + offset_v, gu + offset_u] = 1

    # Distance field
    distance_field_2d = compute_distance_field_2d(mask)

    # Watershed (возвращает сглаженный df и пики)
    ws_result = watershed_split_2d(mask, distance_field_2d, smoothing)

    # Конвертируем 2D distance field в 3D
    distance_field_3d: dict[tuple[int, int, int], float] = {}
    for voxel in region_voxels:
        grid_u, grid_v = voxel_to_2d[voxel]
        mask_u = grid_u + offset_u
        mask_v = grid_v + offset_v
        if 0 <= mask_u < width and 0 <= mask_v < height:
            distance_field_3d[voxel] = float(ws_result.smoothed_distance_field[mask_v, mask_u])
        else:
            distance_field_3d[voxel] = 0.0

    # Конвертируем пики в 3D
    peaks_3d = map_2d_to_3d(ws_result.peaks, grid_2d_to_voxels, offset_u, offset_v)
    all_local_maxima_3d = map_2d_to_3d(ws_result.all_local_maxima, grid_2d_to_voxels, offset_u, offset_v)

    if ws_result.num_regions <= 1:
        return WatershedResult(
            sub_regions=[region_voxels],
            distance_field=distance_field_3d,
            peaks=peaks_3d,
            all_local_maxima=all_local_maxima_3d,
        )

    # Собираем воксели по меткам
    sub_regions: dict[int, list[tuple[int, int, int]]] = {i: [] for i in range(1, ws_result.num_regions + 1)}

    for voxel in region_voxels:
        grid_u, grid_v = voxel_to_2d[voxel]
        mask_u = grid_u + offset_u
        mask_v = grid_v + offset_v
        if 0 <= mask_u < width and 0 <= mask_v < height:
            label = ws_result.labels[mask_v, mask_u]
            if label > 0:
                sub_regions[label].append(voxel)

    result_regions = [voxels for voxels in sub_regions.values() if voxels]
    if not result_regions:
        result_regions = [region_voxels]

    return WatershedResult(
        sub_regions=result_regions,
        distance_field=distance_field_3d,
        peaks=peaks_3d,
        all_local_maxima=all_local_maxima_3d,
    )


def find_peaks_for_region(
    region_voxels: list[tuple[int, int, int]],
    region_normal: np.ndarray,
    cell_size: float,
    origin: np.ndarray,
    smoothing: int = 0,
    debug: bool = False,
) -> tuple[set[tuple[int, int, int]], set[tuple[int, int, int]]]:
    """
    Найти локальные максимумы distance field для региона.

    Возвращает два множества 3D вокселей.

    Args:
        region_voxels: Список вокселей региона.
        region_normal: Нормаль региона.
        cell_size: Размер вокселя.
        origin: Начало координат.
        smoothing: Количество итераций сглаживания distance field.

    Returns:
        (all_local_maxima, plateau_peaks):
            all_local_maxima: Все локальные максимумы.
            plateau_peaks: По одному на плато.
    """
    if len(region_voxels) < 1:
        return set(), set()

    # Строим локальную 2D систему координат
    u_axis, v_axis = build_2d_basis(region_normal)

    # Центроид региона
    centers_3d = np.array([
        origin + (np.array(v) + 0.5) * cell_size
        for v in region_voxels
    ], dtype=np.float32)
    centroid = centers_3d.mean(axis=0)

    # Проецируем воксели на 2D
    voxel_to_2d: dict[tuple[int, int, int], tuple[int, int]] = {}
    grid_2d_to_voxels: dict[tuple[int, int], list[tuple[int, int, int]]] = {}

    for voxel in region_voxels:
        vx, vy, vz = voxel
        world_pos = origin + (np.array([vx, vy, vz]) + 0.5) * cell_size
        rel_pos = world_pos - centroid
        u = float(np.dot(rel_pos, u_axis))
        v = float(np.dot(rel_pos, v_axis))
        grid_u = int(round(u / cell_size))
        grid_v = int(round(v / cell_size))
        voxel_to_2d[voxel] = (grid_u, grid_v)
        if (grid_u, grid_v) not in grid_2d_to_voxels:
            grid_2d_to_voxels[(grid_u, grid_v)] = []
        grid_2d_to_voxels[(grid_u, grid_v)].append(voxel)

    # Bresenham для связности
    region_set = set(region_voxels)
    for voxel in region_voxels:
        vx, vy, vz = voxel
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor in region_set and neighbor > voxel:
                        u1, v1 = voxel_to_2d[voxel]
                        u2, v2 = voxel_to_2d[neighbor]
                        line_cells = bresenham_line(u1, v1, u2, v2)
                        for cell in line_cells:
                            if cell not in grid_2d_to_voxels:
                                grid_2d_to_voxels[cell] = [voxel]

    # Создаём маску
    all_2d = list(grid_2d_to_voxels.keys())
    if not all_2d:
        return set(), set()

    min_u = min(p[0] for p in all_2d)
    max_u = max(p[0] for p in all_2d)
    min_v = min(p[1] for p in all_2d)
    max_v = max(p[1] for p in all_2d)

    width = max_u - min_u + 3
    height = max_v - min_v + 3
    offset_u = -min_u + 1
    offset_v = -min_v + 1

    mask = np.zeros((height, width), dtype=np.uint8)
    for (gu, gv) in all_2d:
        mask[gv + offset_v, gu + offset_u] = 1

    # Distance field в 2D
    distance_2d = compute_distance_field_2d(mask)

    # Сглаживание для устранения ложных пиков на хребтах
    if smoothing > 0:
        distance_2d = smooth_distance_field_2d(distance_2d, mask, smoothing)

    if debug:
        max_dist = float(np.max(distance_2d))
        print(f"  region: voxels={len(region_voxels)}, mask={width}x{height}, max_dist={max_dist:.2f}, smoothing={smoothing}")

    # Находим пики в 2D
    all_maxima_2d, plateau_peaks_2d = find_distance_field_peaks_2d(distance_2d, debug=debug)

    # Маппим пики обратно в 3D воксели
    def map_2d_to_3d(points_2d):
        result: set[tuple[int, int, int]] = set()
        for (pu, pv) in points_2d:
            grid_u = pu - offset_u
            grid_v = pv - offset_v
            if (grid_u, grid_v) in grid_2d_to_voxels:
                for voxel in grid_2d_to_voxels[(grid_u, grid_v)]:
                    result.add(voxel)
        return result

    all_maxima_voxels = map_2d_to_3d(all_maxima_2d)
    plateau_peaks_voxels = map_2d_to_3d(plateau_peaks_2d)

    return all_maxima_voxels, plateau_peaks_voxels


def compute_distance_field_for_region(
    region_voxels: list[tuple[int, int, int]],
    region_normal: np.ndarray,
    cell_size: float,
    origin: np.ndarray,
) -> dict[tuple[int, int, int], float]:
    """
    Вычислить distance field для региона.

    Проецирует регион на 2D, вычисляет distance field,
    и возвращает маппинг 3D воксель -> расстояние.

    Args:
        region_voxels: Список вокселей региона (vx, vy, vz).
        region_normal: Нормаль региона.
        cell_size: Размер вокселя.
        origin: Начало координат сетки.

    Returns:
        {(vx, vy, vz): distance} для каждого вокселя региона.
    """
    if len(region_voxels) < 1:
        return {}

    # Строим локальную 2D систему координат
    u_axis, v_axis = build_2d_basis(region_normal)

    # Центроид региона
    centers_3d = np.array([
        origin + (np.array(v) + 0.5) * cell_size
        for v in region_voxels
    ], dtype=np.float32)
    centroid = centers_3d.mean(axis=0)

    # Проецируем воксели на 2D
    voxel_to_2d: dict[tuple[int, int, int], tuple[int, int]] = {}
    grid_2d_to_voxels: dict[tuple[int, int], list[tuple[int, int, int]]] = {}

    for voxel in region_voxels:
        vx, vy, vz = voxel
        world_pos = origin + (np.array([vx, vy, vz]) + 0.5) * cell_size
        rel_pos = world_pos - centroid
        u = float(np.dot(rel_pos, u_axis))
        v = float(np.dot(rel_pos, v_axis))
        grid_u = int(round(u / cell_size))
        grid_v = int(round(v / cell_size))
        voxel_to_2d[voxel] = (grid_u, grid_v)
        if (grid_u, grid_v) not in grid_2d_to_voxels:
            grid_2d_to_voxels[(grid_u, grid_v)] = []
        grid_2d_to_voxels[(grid_u, grid_v)].append(voxel)

    # Находим соседей в 3D и рисуем линии Брезенхема в 2D
    region_set = set(region_voxels)

    for voxel in region_voxels:
        vx, vy, vz = voxel
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor in region_set and neighbor > voxel:
                        u1, v1 = voxel_to_2d[voxel]
                        u2, v2 = voxel_to_2d[neighbor]
                        line_cells = bresenham_line(u1, v1, u2, v2)

                        for cell in line_cells:
                            if cell not in grid_2d_to_voxels:
                                grid_2d_to_voxels[cell] = [voxel]

    # Создаём бинарную маску
    all_2d = list(grid_2d_to_voxels.keys())
    if not all_2d:
        return {}

    min_u = min(p[0] for p in all_2d)
    max_u = max(p[0] for p in all_2d)
    min_v = min(p[1] for p in all_2d)
    max_v = max(p[1] for p in all_2d)

    width = max_u - min_u + 3
    height = max_v - min_v + 3
    offset_u = -min_u + 1
    offset_v = -min_v + 1

    mask = np.zeros((height, width), dtype=np.uint8)
    for (gu, gv) in all_2d:
        mask[gv + offset_v, gu + offset_u] = 1

    # Вычисляем distance field в 2D
    distance_2d = compute_distance_field_2d(mask)

    # Конвертируем обратно в 3D
    result: dict[tuple[int, int, int], float] = {}

    for voxel in region_voxels:
        grid_u, grid_v = voxel_to_2d[voxel]
        mask_u = grid_u + offset_u
        mask_v = grid_v + offset_v
        if 0 <= mask_u < width and 0 <= mask_v < height:
            result[voxel] = float(distance_2d[mask_v, mask_u])
        else:
            result[voxel] = 0.0

    return result


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
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


def order_contour(
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
    last_dir = 4  # Пришли с запада

    while True:
        found = False
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
            for i in range(8):
                dir_idx = (search_start + i) % 8
                du, dv = directions[dir_idx]
                neighbor = (current[0] + du, current[1] + dv)
                if neighbor == start:
                    break
            break

    return ordered


def extract_contours_from_mask(
    mask: np.ndarray
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

    # 8-связность для обхода контура
    directions = [
        (1, 0), (1, 1), (0, 1), (-1, 1),
        (-1, 0), (-1, -1), (0, -1), (1, -1)
    ]

    # 4-связность для flood fill (чтобы диагональные проходы не "заливали" дырки)
    cardinal_directions_ff = [(1, 0), (0, 1), (-1, 0), (0, -1)]

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

    # Flood fill с 4-связностью
    while queue:
        u, v = queue.popleft()
        for du, dv in cardinal_directions_ff:
            nu, nv = u + du, v + dv
            if 0 <= nu < width and 0 <= nv < height:
                if mask[nv, nu] == 0 and external[nv, nu] == 0:
                    external[nv, nu] = 1
                    queue.append((nu, nv))

    # Шаг 2-4: Классифицируем граничные ячейки
    # Используем 4-связность для определения границы (только кардинальные направления)
    cardinal_directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]

    outer_cells: list[tuple[int, int]] = []
    inner_cells: list[tuple[int, int]] = []

    for v in range(height):
        for u in range(width):
            if mask[v, u] == 0:
                continue

            has_external_neighbor = False
            has_internal_neighbor = False

            for du, dv in cardinal_directions:
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

    # Шаг 6: Упорядочить контуры
    outer_ordered = order_contour(outer_cells, directions)
    holes_ordered = [order_contour(h, directions) for h in holes]

    return outer_ordered, holes_ordered


def extract_contours_from_region(
    region_voxels: list[tuple[int, int, int]],
    region_normal: np.ndarray,
    cell_size: float,
    origin: np.ndarray,
) -> tuple[list[tuple[int, int, int]], list[list[tuple[int, int, int]]]]:
    """
    Извлечь внешний и внутренние контуры из региона.

    Args:
        region_voxels: Список вокселей региона (vx, vy, vz).
        region_normal: Нормаль региона.
        cell_size: Размер вокселя.
        origin: Начало координат сетки.

    Returns:
        (outer_contour, holes) - внешний контур и список дырок.
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

    # Проецируем воксели на 2D
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

    # Находим соседей в 3D и рисуем линии Брезенхема в 2D
    region_set = set(region_voxels)

    for voxel in region_voxels:
        vx, vy, vz = voxel
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor in region_set and neighbor > voxel:
                        u1, v1 = voxel_to_2d[voxel]
                        u2, v2 = voxel_to_2d[neighbor]
                        line_cells = bresenham_line(u1, v1, u2, v2)

                        for cell in line_cells:
                            if cell not in grid_2d_to_voxels:
                                grid_2d_to_voxels[cell] = [voxel]

    # Создаём бинарную маску
    all_2d = list(grid_2d_to_voxels.keys())
    min_u = min(p[0] for p in all_2d)
    max_u = max(p[0] for p in all_2d)
    min_v = min(p[1] for p in all_2d)
    max_v = max(p[1] for p in all_2d)

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
