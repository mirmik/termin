"""
Извлечение контуров из воксельных регионов.

Алгоритмы для нахождения внешнего контура и дырок.
"""

from __future__ import annotations

from collections import deque
import numpy as np

from termin.navmesh.triangulation import build_2d_basis


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
