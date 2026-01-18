"""
Region Growing алгоритмы для построения NavMesh.

Группировка поверхностных вокселей в регионы по схожести нормалей.
"""

from __future__ import annotations

from collections import deque
import numpy as np

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


def collect_surface_voxels(
    grid: VoxelGrid,
    max_slope_cos: float = 0.0,
    up_axis: np.ndarray | None = None,
) -> dict[tuple[int, int, int], list[np.ndarray]]:
    """
    Шаг 1: Собрать поверхностные воксели с нормалями.

    Args:
        grid: Воксельная сетка.
        max_slope_cos: Косинус максимального угла наклона (0 = без фильтрации).
                       Например: cos(45°) ≈ 0.707, cos(60°) = 0.5.
        up_axis: Вектор "вверх" для проверки наклона. По умолчанию (0, 0, 1).

    Returns:
        {(vx, vy, vz): [normal, ...]} для всех проходимых поверхностных вокселей.
    """
    if up_axis is None:
        up_axis = np.array([0.0, 0.0, 1.0], dtype=np.float32)

    result: dict[tuple[int, int, int], list[np.ndarray]] = {}

    for coord, normals_list in grid.surface_normals.items():
        if grid.get(*coord) != 0 and normals_list:
            # Фильтрация по углу наклона
            if max_slope_cos > 0:
                # Проверяем первую нормаль (основную)
                normal = normals_list[0]
                dot = float(np.dot(normal, up_axis))
                if dot < max_slope_cos:
                    # Слишком крутой склон — непроходим
                    continue
            result[coord] = normals_list

    return result


def region_growing_basic(
    surface_voxels: dict[tuple[int, int, int], list[np.ndarray]],
    normal_threshold: float,
) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
    """
    Шаг 2: Группировка вокселей методом Region Growing.

    Использует первую нормаль из списка для начального роста региона.

    Args:
        surface_voxels: {(vx, vy, vz): [normal, ...]}
        normal_threshold: Порог dot product для совместимости нормалей.

    Returns:
        Список (список вокселей, усреднённая нормаль).
    """
    remaining = set(surface_voxels.keys())
    regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []

    while remaining:
        seed = next(iter(remaining))
        seed_normal = surface_voxels[seed][0]

        region: list[tuple[int, int, int]] = []
        normal_sum = np.zeros(3, dtype=np.float64)

        queue: deque[tuple[int, int, int]] = deque([seed])
        remaining.remove(seed)

        while queue:
            current = queue.popleft()
            current_normal = surface_voxels[current][0]

            dot = np.dot(seed_normal, current_normal)
            if dot < normal_threshold:
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


def greedy_absorption(
    regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
    surface_voxels: dict[tuple[int, int, int], list[np.ndarray]],
    normal_threshold: float,
) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
    """
    Шаг 2.3: Жадное поглощение — большие регионы поглощают воксели меньших.

    Args:
        regions: Список (воксели, нормаль).
        surface_voxels: {(vx, vy, vz): [normal, ...]}.
        normal_threshold: Порог совместимости нормалей.

    Returns:
        Обновлённый список регионов.
    """
    if len(regions) <= 1:
        return regions

    region_sets: list[set[tuple[int, int, int]]] = [set(voxels) for voxels, _ in regions]
    region_normals: list[np.ndarray] = [normal.copy() for _, normal in regions]

    voxel_to_region: dict[tuple[int, int, int], int] = {}
    for idx, voxel_set in enumerate(region_sets):
        for v in voxel_set:
            voxel_to_region[v] = idx

    sorted_indices = sorted(range(len(regions)), key=lambda i: len(region_sets[i]), reverse=True)

    total_absorbed = 0
    total_pruned = 0

    for rank, region_idx in enumerate(sorted_indices):
        region_normal = region_normals[region_idx]
        region_set = region_sets[region_idx]

        if len(region_set) == 0:
            continue

        current_size = len(region_set)
        changed = True
        absorbed_this_region = 0

        while changed:
            changed = False

            boundary_neighbors: set[tuple[int, int, int]] = set()
            for vx, vy, vz in region_set:
                for dx, dy, dz in NEIGHBORS_26:
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor not in region_set and neighbor in surface_voxels:
                        boundary_neighbors.add(neighbor)

            to_absorb: list[tuple[int, int, int]] = []

            for neighbor in boundary_neighbors:
                if neighbor in voxel_to_region:
                    neighbor_region_idx = voxel_to_region[neighbor]
                    neighbor_region_size = len(region_sets[neighbor_region_idx])
                    if neighbor_region_size >= current_size:
                        continue

                neighbor_normals = surface_voxels[neighbor]
                compatible = False
                for normal in neighbor_normals:
                    dot = np.dot(region_normal, normal)
                    if dot >= normal_threshold:
                        compatible = True
                        break

                if compatible:
                    to_absorb.append(neighbor)

            for voxel in to_absorb:
                if voxel in voxel_to_region:
                    old_region_idx = voxel_to_region[voxel]
                    region_sets[old_region_idx].discard(voxel)
                region_set.add(voxel)
                voxel_to_region[voxel] = region_idx
                changed = True
                absorbed_this_region += 1

        total_absorbed += absorbed_this_region

        # Перераспределение висячих вокселей
        redistributed_this_region = 0
        redistribute_changed = True
        while redistribute_changed and len(region_set) > 1:
            redistribute_changed = False
            to_redistribute: list[tuple[tuple[int, int, int], int]] = []

            for voxel in list(region_set):
                vx, vy, vz = voxel
                neighbors_in_current = 0
                for dx, dy, dz in NEIGHBORS_26:
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor in region_set:
                        neighbors_in_current += 1

                if neighbors_in_current < 2:
                    neighbor_counts: dict[int, int] = {}
                    for dx, dy, dz in NEIGHBORS_26:
                        neighbor = (vx + dx, vy + dy, vz + dz)
                        if neighbor in voxel_to_region:
                            other_idx = voxel_to_region[neighbor]
                            if other_idx != region_idx:
                                neighbor_counts[other_idx] = neighbor_counts.get(other_idx, 0) + 1

                    best_region = None
                    best_count = neighbors_in_current
                    voxel_normals = surface_voxels.get(voxel, [])

                    for other_idx, count in neighbor_counts.items():
                        if count > best_count:
                            other_normal = region_normals[other_idx]
                            for vn in voxel_normals:
                                if np.dot(vn, other_normal) >= normal_threshold:
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

        total_pruned += redistributed_this_region

        if absorbed_this_region > 0 or redistributed_this_region > 0:
            normal_sum = np.zeros(3, dtype=np.float64)
            for v in region_set:
                if v in surface_voxels:
                    normal_sum += surface_voxels[v][0]
            norm = np.linalg.norm(normal_sum)
            if norm > 1e-6:
                region_normals[region_idx] = (normal_sum / norm).astype(np.float32)

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


def add_multi_normal_voxels_to_regions(
    regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
    surface_voxels: dict[tuple[int, int, int], list[np.ndarray]],
    normal_threshold: float,
) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
    """
    Шаг 2.4: Воксели с несколькими нормалями добавляются во все совместимые регионы.
    """
    multi_normal_voxels = {
        v: normals for v, normals in surface_voxels.items()
        if len(normals) > 1
    }

    if not multi_normal_voxels:
        return regions

    region_sets: list[set[tuple[int, int, int]]] = [set(voxels) for voxels, _ in regions]
    region_normals: list[np.ndarray] = [normal for _, normal in regions]

    added_count = 0

    for voxel, voxel_normals in multi_normal_voxels.items():
        for region_idx, region_normal in enumerate(region_normals):
            if voxel in region_sets[region_idx]:
                continue

            for vn in voxel_normals:
                if np.dot(vn, region_normal) >= normal_threshold:
                    region_sets[region_idx].add(voxel)
                    added_count += 1
                    break

    result = [
        (list(region_sets[i]), region_normals[i])
        for i in range(len(regions))
    ]

    print(f"PolygonBuilder: added {added_count} multi-normal voxels to additional regions")

    return result


def expand_all_regions(
    regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
    surface_voxels: dict[tuple[int, int, int], list[np.ndarray]],
    normal_threshold: float,
) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
    """
    Шаг 2.4: Расширение всех регионов на соседние воксели.
    """
    region_sets: list[set[tuple[int, int, int]]] = [set(voxels) for voxels, _ in regions]
    region_normals: list[np.ndarray] = [normal for _, normal in regions]

    total_added = 0
    iteration = 0

    changed = True
    while changed:
        changed = False
        iteration += 1

        for region_idx in range(len(region_sets)):
            region_set = region_sets[region_idx]
            region_normal = region_normals[region_idx]

            candidates: set[tuple[int, int, int]] = set()
            for vx, vy, vz in region_set:
                for dx, dy, dz in NEIGHBORS_26:
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor in surface_voxels and neighbor not in region_set:
                        candidates.add(neighbor)

            for candidate in candidates:
                candidate_normals = surface_voxels[candidate]
                for cn in candidate_normals:
                    if np.dot(cn, region_normal) >= normal_threshold:
                        region_set.add(candidate)
                        total_added += 1
                        changed = True
                        break

    result = [
        (list(region_sets[i]), region_normals[i])
        for i in range(len(regions))
    ]

    print(f"PolygonBuilder: expand_all_regions: {iteration} iterations, added {total_added} voxels")

    return result


def filter_hanging_voxels(
    regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
    """
    Шаг 2.6: Фильтрация "висячих" вокселей.
    """
    result: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []

    for region_voxels, region_normal in regions:
        if len(region_voxels) <= 2:
            result.append((region_voxels, region_normal))
            continue

        region_set = set(region_voxels)
        changed = True

        while changed:
            changed = False
            to_evict: list[tuple[int, int, int]] = []

            for voxel in region_set:
                neighbor_count = 0
                vx, vy, vz = voxel
                for dx, dy, dz in NEIGHBORS_26:
                    neighbor = (vx + dx, vy + dy, vz + dz)
                    if neighbor in region_set:
                        neighbor_count += 1

                if neighbor_count <= 1:
                    to_evict.append(voxel)

            for voxel in to_evict:
                region_set.discard(voxel)
                changed = True

            if len(region_set) <= 2:
                break

        if region_set:
            result.append((list(region_set), region_normal))

    return result


def are_connected_26(voxels: list[tuple[int, int, int]]) -> bool:
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


def decimate_boundary(
    boundary: set[tuple[int, int, int]],
) -> set[tuple[int, int, int]]:
    """
    Децимация границы — удаляем избыточные воксели.
    """
    result = set(boundary)
    changed = True
    iteration = 0

    while changed:
        changed = False
        iteration += 1
        to_remove: set[tuple[int, int, int]] = set()

        for voxel in result:
            vx, vy, vz = voxel
            neighbors_in_boundary: list[tuple[int, int, int]] = []
            for dx, dy, dz in NEIGHBORS_26:
                neighbor = (vx + dx, vy + dy, vz + dz)
                if neighbor in result and neighbor not in to_remove:
                    neighbors_in_boundary.append(neighbor)

            if len(neighbors_in_boundary) < 2:
                to_remove.add(voxel)
                continue

            if are_connected_26(neighbors_in_boundary):
                to_remove.add(voxel)

        for voxel in to_remove:
            result.discard(voxel)
            changed = True

    print(f"PolygonBuilder: boundary decimation: {len(boundary)} -> {len(result)} ({iteration} iterations)")
    return result


def share_boundary_voxels(
    regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
) -> tuple[list[tuple[list[tuple[int, int, int]], np.ndarray]], set[tuple[int, int, int]]]:
    """
    Шаг 2.7: Граничные воксели становятся общими для соседних регионов.

    Returns:
        (обновлённые регионы, множество граничных вокселей)
    """
    voxel_to_regions: dict[tuple[int, int, int], set[int]] = {}
    for idx, (voxels, _) in enumerate(regions):
        for v in voxels:
            if v not in voxel_to_regions:
                voxel_to_regions[v] = set()
            voxel_to_regions[v].add(idx)

    boundary_voxels: set[tuple[int, int, int]] = set()
    to_add: dict[int, set[tuple[int, int, int]]] = {i: set() for i in range(len(regions))}

    for region_idx, (region_voxels, _) in enumerate(regions):
        for voxel in region_voxels:
            vx, vy, vz = voxel
            for dx, dy, dz in NEIGHBORS_26:
                neighbor = (vx + dx, vy + dy, vz + dz)
                if neighbor in voxel_to_regions:
                    neighbor_regions = voxel_to_regions[neighbor]
                    for other_idx in neighbor_regions:
                        if other_idx > region_idx:
                            to_add[other_idx].add(voxel)
                            boundary_voxels.add(voxel)

    boundary_voxels = decimate_boundary(boundary_voxels)

    result: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
    for idx, (voxels, normal) in enumerate(regions):
        filtered_to_add = to_add[idx] & boundary_voxels
        new_voxels = set(voxels) | filtered_to_add
        result.append((list(new_voxels), normal))

    print(f"PolygonBuilder: shared {len(boundary_voxels)} boundary voxels between regions")
    return result, boundary_voxels


def expand_regions(
    regions: list[tuple[list[tuple[int, int, int]], np.ndarray]],
    surface_voxels: dict[tuple[int, int, int], list[np.ndarray]],
    normal_threshold: float,
) -> list[tuple[list[tuple[int, int, int]], np.ndarray]]:
    """
    Шаг 2.5: Расширить регионы, добавляя граничные воксели с подходящими нормалями.
    """
    expanded_regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []

    for region_voxels, region_normal in regions:
        region_set = set(region_voxels)
        expanded = list(region_voxels)

        boundary: set[tuple[int, int, int]] = set()
        for vx, vy, vz in region_voxels:
            for dx, dy, dz in NEIGHBORS_26:
                neighbor = (vx + dx, vy + dy, vz + dz)
                if neighbor not in region_set and neighbor in surface_voxels:
                    boundary.add(neighbor)

        for neighbor in boundary:
            normals_list = surface_voxels[neighbor]
            for normal in normals_list:
                dot = np.dot(region_normal, normal)
                if dot >= normal_threshold:
                    expanded.append(neighbor)
                    break

        expanded_regions.append((expanded, region_normal))

    return expanded_regions
