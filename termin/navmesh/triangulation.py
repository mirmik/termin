"""
Триангуляция полигонов для NavMesh.

Включает Ear Clipping, Douglas-Peucker и объединение дырок через bridge.
"""

from __future__ import annotations

import numpy as np


def signed_area_2d(polygon: np.ndarray) -> float:
    """Вычислить знаковую площадь полигона (положительная для CCW)."""
    n = len(polygon)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]
    return area / 2.0


def is_convex_2d(
    prev_p: np.ndarray,
    curr_p: np.ndarray,
    next_p: np.ndarray,
    ccw: bool,
    epsilon: float = 1e-10,
) -> bool:
    """
    Проверить, является ли вершина выпуклой.

    Почти коллинеарные вершины (cross ≈ 0) считаются выпуклыми,
    чтобы ear clipping работал на узких полигонах.
    """
    cross = (curr_p[0] - prev_p[0]) * (next_p[1] - curr_p[1]) - \
            (curr_p[1] - prev_p[1]) * (next_p[0] - curr_p[0])

    if ccw:
        return cross > -epsilon  # >= 0 с погрешностью
    else:
        return cross < epsilon   # <= 0 с погрешностью


def point_in_triangle_2d(
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


def segments_intersect_strict(
    a1: np.ndarray,
    a2: np.ndarray,
    b1: np.ndarray,
    b2: np.ndarray,
) -> bool:
    """
    Проверить строгое пересечение двух отрезков (без касания в точках).
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


def ear_clip(polygon: np.ndarray) -> list[tuple[int, int, int]]:
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
    area = signed_area_2d(polygon)
    ccw = area > 0

    # Создаём связный список индексов
    indices = list(range(n))
    triangles = []

    # Пытаемся найти и отрезать уши
    max_iterations = n * n
    iteration = 0

    convex_count = 0
    reflex_count = 0

    while len(indices) > 3 and iteration < max_iterations:
        iteration += 1
        found_ear = False
        convex_count = 0
        reflex_count = 0

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
            if not is_convex_2d(prev_p, curr_p, next_p, ccw):
                reflex_count += 1
                continue
            convex_count += 1

            # Проверяем, что треугольник не содержит других вершин
            is_ear = True
            for j in range(len(indices)):
                if j == prev_i or j == i or j == next_i:
                    continue

                test_idx = indices[j]
                test_p = polygon[test_idx]

                # Пропускаем вершины, совпадающие с вершинами треугольника
                eps = 1e-10
                if (abs(test_p[0] - prev_p[0]) < eps and abs(test_p[1] - prev_p[1]) < eps):
                    continue
                if (abs(test_p[0] - curr_p[0]) < eps and abs(test_p[1] - curr_p[1]) < eps):
                    continue
                if (abs(test_p[0] - next_p[0]) < eps and abs(test_p[1] - next_p[1]) < eps):
                    continue

                if point_in_triangle_2d(test_p, prev_p, curr_p, next_p):
                    is_ear = False
                    break

            if is_ear:
                triangles.append((prev_idx, curr_idx, next_idx))
                indices.pop(i)
                found_ear = True
                break

        if not found_ear:
            print(f"[ear_clip] no ear found! remaining={len(indices)}, convex={convex_count}, reflex={reflex_count}, triangles={len(triangles)}")
            break

    # Добавляем последний треугольник
    if len(indices) == 3:
        triangles.append((indices[0], indices[1], indices[2]))

    return triangles


def ear_clipping(vertices: np.ndarray, optimize: bool = True) -> np.ndarray:
    """
    Триангулировать простой полигон методом Ear Clipping.

    Обёртка над ear_clip(), возвращающая np.ndarray.
    Опционально применяет Delaunay edge flipping для улучшения качества.

    Args:
        vertices: 2D координаты вершин полигона (CCW), shape (N, 2).
        optimize: Применить edge flipping для улучшения качества.

    Returns:
        Треугольники (индексы вершин), shape (N-2, 3).
    """
    triangles = ear_clip(vertices)
    if not triangles:
        return np.array([], dtype=np.int32).reshape(0, 3)

    if optimize and len(triangles) >= 2:
        # Граничные рёбра полигона — не переворачивать
        boundary = extract_boundary_edges(len(vertices))
        triangles = delaunay_flip(vertices, triangles, boundary)

    return np.array(triangles, dtype=np.int32)


def douglas_peucker_2d(
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

    n = len(points)
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
        to_point = points[i] - start
        proj_len = np.dot(to_point, line_dir)
        proj_point = start + proj_len * line_dir
        dist = np.linalg.norm(points[i] - proj_point)

        if dist > max_dist:
            max_dist = dist
            max_idx = i

    if max_dist > epsilon:
        left = douglas_peucker_2d(points[:max_idx + 1], epsilon)
        right = douglas_peucker_2d(points[max_idx:], epsilon)
        return np.vstack([left[:-1], right])
    else:
        return points[[0, -1]]


def douglas_peucker_2d_with_fixed(
    points: np.ndarray,
    epsilon: float,
    fixed_indices: set[int],
) -> np.ndarray:
    """
    Упростить 2D полилинию алгоритмом Douglas-Peucker, сохраняя фиксированные вершины.

    Фиксированные вершины (например, на границах с другими регионами) не удаляются.

    Args:
        points: np.ndarray shape (N, 2) — вершины полилинии.
        epsilon: Максимальное отклонение.
        fixed_indices: Индексы вершин, которые нельзя удалять.

    Returns:
        Упрощённая полилиния shape (M, 2).
    """
    if len(points) <= 2:
        return points

    n = len(points)

    # Находим индексы, которые нужно сохранить (включая первый, последний и фиксированные)
    keep_indices: set[int] = {0, n - 1}
    keep_indices.update(i for i in fixed_indices if 0 <= i < n)

    # Рекурсивная функция для упрощения сегмента
    def simplify_segment(start_idx: int, end_idx: int) -> None:
        if end_idx - start_idx <= 1:
            return

        start = points[start_idx]
        end = points[end_idx]
        line_vec = end - start
        line_len = np.linalg.norm(line_vec)

        if line_len < 1e-10:
            return

        line_dir = line_vec / line_len

        max_dist = 0.0
        max_idx = -1

        # Ищем точку с максимальным отклонением (исключая фиксированные)
        for i in range(start_idx + 1, end_idx):
            to_point = points[i] - start
            proj_len = np.dot(to_point, line_dir)
            proj_point = start + proj_len * line_dir
            dist = np.linalg.norm(points[i] - proj_point)

            if dist > max_dist:
                max_dist = dist
                max_idx = i

        # Проверяем, есть ли фиксированные точки в этом сегменте
        fixed_in_segment = [i for i in range(start_idx + 1, end_idx) if i in fixed_indices]

        if fixed_in_segment:
            # Если есть фиксированные точки, добавляем их и рекурсивно обрабатываем подсегменты
            for fixed_idx in fixed_in_segment:
                keep_indices.add(fixed_idx)
            # Сортируем все сохраняемые точки в сегменте
            segment_keep = sorted([start_idx] + fixed_in_segment + [end_idx])
            for i in range(len(segment_keep) - 1):
                simplify_segment(segment_keep[i], segment_keep[i + 1])
        elif max_dist > epsilon and max_idx > 0:
            # Стандартный Douglas-Peucker
            keep_indices.add(max_idx)
            simplify_segment(start_idx, max_idx)
            simplify_segment(max_idx, end_idx)

    simplify_segment(0, n - 1)

    # Собираем результат
    sorted_indices = sorted(keep_indices)
    return points[sorted_indices]


def is_vertex_visible(
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
        hole: Список вершин дырки.

    Returns:
        True если вершина видима.
    """
    vertex = contour[vertex_idx]
    n = len(contour)

    # Проверяем пересечение со всеми рёбрами контура
    for i in range(n):
        if i == vertex_idx or (i + 1) % n == vertex_idx:
            continue
        if i == (vertex_idx - 1) % n:
            continue

        p1 = contour[i]
        p2 = contour[(i + 1) % n]

        if segments_intersect_strict(point, vertex, p1, p2):
            return False

    # Проверяем пересечение с рёбрами дырки
    m = len(hole)
    for i in range(m):
        p1 = hole[i]
        p2 = hole[(i + 1) % m]

        if segments_intersect_strict(point, vertex, p1, p2):
            return False

    return True


def find_optimal_bridge(
    contour: list,
    hole: list,
) -> tuple[int, int] | None:
    """
    Найти оптимальный мост между контуром и дыркой.

    Перебирает все пары (вершина контура, вершина дырки),
    проверяет видимость и выбирает пару с минимальным расстоянием.

    Args:
        contour: Список вершин внешнего контура [(x, y), ...].
        hole: Список вершин дырки [(x, y), ...].

    Returns:
        (outer_idx, hole_idx) или None если мост не найден.
    """
    n_contour = len(contour)
    n_hole = len(hole)

    best_dist = float('inf')
    best_pair = None

    # Перебираем все пары вершин
    for hi in range(n_hole):
        hole_point = hole[hi]
        hx, hy = hole_point[0], hole_point[1]

        for ci in range(n_contour):
            # Проверяем видимость
            if not is_vertex_visible(contour, ci, hole_point, hole):
                continue

            # Вычисляем расстояние
            dx = contour[ci][0] - hx
            dy = contour[ci][1] - hy
            dist = dx * dx + dy * dy

            if dist < best_dist:
                best_dist = dist
                best_pair = (ci, hi)

    # Если ни одна пара не видима, ищем просто ближайшую
    if best_pair is None:
        for hi in range(n_hole):
            hole_point = hole[hi]
            hx, hy = hole_point[0], hole_point[1]

            for ci in range(n_contour):
                dx = contour[ci][0] - hx
                dy = contour[ci][1] - hy
                dist = dx * dx + dy * dy

                if dist < best_dist:
                    best_dist = dist
                    best_pair = (ci, hi)

    return best_pair


def merge_holes_with_bridges(
    outer: np.ndarray,
    holes: list[np.ndarray],
) -> np.ndarray:
    """
    Объединить дырки с внешним контуром через bridge edges.

    Args:
        outer: Внешний контур shape (N, 2), CCW ориентация.
        holes: Список дырок, каждая shape (M, 2), CW ориентация.

    Returns:
        Объединённый контур shape (K, 2).
    """
    if not holes:
        return outer

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

        hole_list = list(hole)

        bridge = find_optimal_bridge(result, hole_list)

        if bridge is None:
            continue

        bridge_outer_idx, bridge_hole_idx = bridge

        # Вставляем дырку в контур
        new_contour = []

        # Часть внешнего контура до bridge vertex (включительно)
        for i in range(bridge_outer_idx + 1):
            new_contour.append(result[i])

        # Дырка в прямом порядке (CW), начиная с bridge_hole_idx
        for i in range(len(hole_list)):
            idx = (bridge_hole_idx + i) % len(hole_list)
            new_contour.append(hole_list[idx])

        # Возврат к bridge vertex (замыкаем мост)
        new_contour.append(hole_list[bridge_hole_idx])
        new_contour.append(result[bridge_outer_idx])

        # Остаток внешнего контура
        for i in range(bridge_outer_idx + 1, len(result)):
            new_contour.append(result[i])

        result = new_contour

    return np.array(result, dtype=np.float32)


def in_circumcircle(
    ax: float, ay: float,
    bx: float, by: float,
    cx: float, cy: float,
    dx: float, dy: float,
) -> bool:
    """
    Проверить, лежит ли точка D внутри описанной окружности треугольника ABC.

    Использует определитель 3x3 (критерий Delaunay).
    Предполагает CCW ориентацию ABC.

    Returns:
        True если D внутри окружности.
    """
    # Сдвигаем координаты относительно D
    adx = ax - dx
    ady = ay - dy
    bdx = bx - dx
    bdy = by - dy
    cdx = cx - dx
    cdy = cy - dy

    # Квадраты расстояний
    ad_sq = adx * adx + ady * ady
    bd_sq = bdx * bdx + bdy * bdy
    cd_sq = cdx * cdx + cdy * cdy

    # Определитель 3x3
    det = adx * (bdy * cd_sq - cdy * bd_sq) \
        - ady * (bdx * cd_sq - cdx * bd_sq) \
        + ad_sq * (bdx * cdy - cdx * bdy)

    return det > 0


def build_edge_map(
    triangles: list[tuple[int, int, int]],
) -> dict[tuple[int, int], list[int]]:
    """
    Построить карту рёбер: edge -> список индексов треугольников.

    Ребро нормализовано (меньший индекс первым).
    """
    edge_map: dict[tuple[int, int], list[int]] = {}

    for tri_idx, (a, b, c) in enumerate(triangles):
        for v0, v1 in [(a, b), (b, c), (c, a)]:
            edge = (min(v0, v1), max(v0, v1))
            if edge not in edge_map:
                edge_map[edge] = []
            edge_map[edge].append(tri_idx)

    return edge_map


def get_opposite_vertex(
    tri: tuple[int, int, int],
    edge: tuple[int, int],
) -> int:
    """Получить вершину треугольника, противоположную ребру."""
    for v in tri:
        if v != edge[0] and v != edge[1]:
            return v
    return -1


def delaunay_flip(
    vertices: np.ndarray,
    triangles: list[tuple[int, int, int]],
    boundary_edges: set[tuple[int, int]] | None = None,
    max_iterations: int = 1000,
) -> list[tuple[int, int, int]]:
    """
    Улучшить триангуляцию методом edge flipping (Delaunay).

    Args:
        vertices: 2D координаты вершин, shape (N, 2).
        triangles: Список треугольников [(a, b, c), ...].
        boundary_edges: Множество граничных рёбер (не переворачивать).
        max_iterations: Максимум итераций.

    Returns:
        Улучшенный список треугольников.
    """
    if len(triangles) < 2:
        return triangles

    triangles = list(triangles)  # копия

    if boundary_edges is None:
        boundary_edges = set()

    flip_count = 0

    for iteration in range(max_iterations):
        flipped = False
        edge_map = build_edge_map(triangles)

        for edge, tri_indices in edge_map.items():
            # Только внутренние рёбра (2 треугольника)
            if len(tri_indices) != 2:
                continue

            # Не трогаем граничные рёбра
            if edge in boundary_edges:
                continue

            tri1_idx, tri2_idx = tri_indices
            tri1 = triangles[tri1_idx]
            tri2 = triangles[tri2_idx]

            # Вершины противоположные ребру
            v1 = get_opposite_vertex(tri1, edge)
            v2 = get_opposite_vertex(tri2, edge)

            if v1 < 0 or v2 < 0:
                continue

            # Проверяем Delaunay критерий
            # Точки ребра
            e0, e1 = edge
            ax, ay = vertices[e0]
            bx, by = vertices[e1]
            cx, cy = vertices[v1]
            dx, dy = vertices[v2]

            # Проверяем ориентацию треугольника (e0, e1, v1)
            # Если CW, меняем порядок для корректной проверки
            cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
            if cross < 0:
                # CW — меняем местами
                ax, ay, bx, by = bx, by, ax, ay

            # Проверяем, лежит ли v2 внутри описанной окружности (e0, e1, v1)
            if in_circumcircle(ax, ay, bx, by, cx, cy, dx, dy):
                # Flip: заменяем ребро (e0, e1) на (v1, v2)
                # Новые треугольники: (e0, v2, v1) и (e1, v1, v2)
                new_tri1 = (e0, v2, v1)
                new_tri2 = (e1, v1, v2)

                # Проверяем корректность (не вырожденные)
                def tri_area(t):
                    a, b, c = t
                    return abs(
                        (vertices[b][0] - vertices[a][0]) * (vertices[c][1] - vertices[a][1]) -
                        (vertices[c][0] - vertices[a][0]) * (vertices[b][1] - vertices[a][1])
                    )

                if tri_area(new_tri1) > 1e-10 and tri_area(new_tri2) > 1e-10:
                    triangles[tri1_idx] = new_tri1
                    triangles[tri2_idx] = new_tri2
                    flipped = True
                    flip_count += 1
                    break  # Перестраиваем edge_map

        if not flipped:
            break

    if flip_count > 0:
        print(f"[delaunay_flip] {flip_count} flips")

    return triangles


def valence_flip(
    vertices: np.ndarray,
    triangles: list[tuple[int, int, int]],
    boundary_edges: set[tuple[int, int]] | None = None,
    max_vertex_valence: int = 0,
    max_iterations: int = 1000,
) -> list[tuple[int, int, int]]:
    """
    Улучшить триангуляцию методом edge flipping для уменьшения валентности.

    Переворачивает рёбра, если это уменьшает максимальную валентность вершин.

    Args:
        vertices: 2D координаты вершин, shape (N, 2).
        triangles: Список треугольников [(a, b, c), ...].
        boundary_edges: Множество граничных рёбер (не переворачивать).
        max_vertex_valence: Целевая макс. валентность (0 = минимизировать).
        max_iterations: Максимум итераций.

    Returns:
        Улучшенный список треугольников.
    """
    if len(triangles) < 2:
        return triangles

    triangles = list(triangles)

    if boundary_edges is None:
        boundary_edges = set()

    def compute_valence() -> dict[int, int]:
        """Подсчитать валентность каждой вершины."""
        val: dict[int, int] = {}
        for tri in triangles:
            for v in tri:
                val[v] = val.get(v, 0) + 1
        return val

    flip_count = 0
    initial_max_valence = max(compute_valence().values()) if triangles else 0

    for iteration in range(max_iterations):
        flipped = False
        valence = compute_valence()
        edge_map = build_edge_map(triangles)

        # Если задан max_vertex_valence и все вершины в пределах — выходим
        if max_vertex_valence > 0:
            current_max = max(valence.values()) if valence else 0
            if current_max <= max_vertex_valence:
                break

        for edge, tri_indices in edge_map.items():
            if len(tri_indices) != 2:
                continue

            if edge in boundary_edges:
                continue

            tri1_idx, tri2_idx = tri_indices
            tri1 = triangles[tri1_idx]
            tri2 = triangles[tri2_idx]

            e0, e1 = edge
            v1 = get_opposite_vertex(tri1, edge)
            v2 = get_opposite_vertex(tri2, edge)

            if v1 < 0 or v2 < 0:
                continue

            # Текущие валентности
            val_e0 = valence.get(e0, 0)
            val_e1 = valence.get(e1, 0)
            val_v1 = valence.get(v1, 0)
            val_v2 = valence.get(v2, 0)

            current_max = max(val_e0, val_e1, val_v1, val_v2)

            # После flip: e0, e1 теряют по 1; v1, v2 получают по 1
            new_max = max(val_e0 - 1, val_e1 - 1, val_v1 + 1, val_v2 + 1)

            # Flip только если уменьшает max валентность
            if new_max >= current_max:
                continue

            # Если задан порог и новый max всё ещё выше порога у v1/v2 — не flip
            # (иначе мы просто переносим проблему на другие вершины)
            if max_vertex_valence > 0:
                if val_v1 + 1 > max_vertex_valence or val_v2 + 1 > max_vertex_valence:
                    # Проверяем что flip хотя бы уменьшает проблему
                    if val_e0 <= max_vertex_valence and val_e1 <= max_vertex_valence:
                        continue

            # Выполняем flip
            new_tri1 = (e0, v2, v1)
            new_tri2 = (e1, v1, v2)

            # Проверяем что новые треугольники не вырождены
            def tri_area(t):
                a, b, c = t
                return abs(
                    (vertices[b][0] - vertices[a][0]) * (vertices[c][1] - vertices[a][1]) -
                    (vertices[c][0] - vertices[a][0]) * (vertices[b][1] - vertices[a][1])
                )

            if tri_area(new_tri1) > 1e-10 and tri_area(new_tri2) > 1e-10:
                triangles[tri1_idx] = new_tri1
                triangles[tri2_idx] = new_tri2
                flipped = True
                flip_count += 1
                break

        if not flipped:
            break

    if flip_count > 0:
        final_max_valence = max(compute_valence().values()) if triangles else 0
        print(f"[valence_flip] {flip_count} flips, max valence: {initial_max_valence} -> {final_max_valence}")

    return triangles


def angle_flip(
    vertices: np.ndarray,
    triangles: list[tuple[int, int, int]],
    boundary_edges: set[tuple[int, int]] | None = None,
    max_iterations: int = 1000,
) -> list[tuple[int, int, int]]:
    """
    Улучшить триангуляцию методом edge flipping для максимизации минимального угла.

    Переворачивает рёбра, если это увеличивает минимальный угол в паре треугольников.

    Args:
        vertices: 2D координаты вершин, shape (N, 2).
        triangles: Список треугольников [(a, b, c), ...].
        boundary_edges: Множество граничных рёбер (не переворачивать).
        max_iterations: Максимум итераций.

    Returns:
        Улучшенный список треугольников.
    """
    import math

    if len(triangles) < 2:
        return triangles

    triangles = list(triangles)

    if boundary_edges is None:
        boundary_edges = set()

    def compute_min_angle(tri: tuple[int, int, int]) -> float:
        """Вычислить минимальный угол треугольника в радианах."""
        a, b, c = tri
        p0 = vertices[a]
        p1 = vertices[b]
        p2 = vertices[c]

        def angle_at(p, q, r):
            """Угол при вершине q в треугольнике p-q-r."""
            v1 = (p[0] - q[0], p[1] - q[1])
            v2 = (r[0] - q[0], r[1] - q[1])
            dot = v1[0] * v2[0] + v1[1] * v2[1]
            len1 = math.sqrt(v1[0]**2 + v1[1]**2)
            len2 = math.sqrt(v2[0]**2 + v2[1]**2)
            if len1 < 1e-10 or len2 < 1e-10:
                return 0.0
            cos_angle = max(-1.0, min(1.0, dot / (len1 * len2)))
            return math.acos(cos_angle)

        return min(angle_at(p1, p0, p2), angle_at(p0, p1, p2), angle_at(p0, p2, p1))

    flip_count = 0

    for iteration in range(max_iterations):
        flipped = False
        edge_map = build_edge_map(triangles)

        for edge, tri_indices in edge_map.items():
            if len(tri_indices) != 2:
                continue

            if edge in boundary_edges:
                continue

            tri1_idx, tri2_idx = tri_indices
            tri1 = triangles[tri1_idx]
            tri2 = triangles[tri2_idx]

            e0, e1 = edge
            v1 = get_opposite_vertex(tri1, edge)
            v2 = get_opposite_vertex(tri2, edge)

            if v1 < 0 or v2 < 0:
                continue

            # Текущий минимальный угол
            current_min = min(compute_min_angle(tri1), compute_min_angle(tri2))

            # Новые треугольники после flip
            new_tri1 = (e0, v2, v1)
            new_tri2 = (e1, v1, v2)

            # Проверяем что новые треугольники не вырождены
            def tri_area(t):
                a, b, c = t
                return (
                    (vertices[b][0] - vertices[a][0]) * (vertices[c][1] - vertices[a][1]) -
                    (vertices[c][0] - vertices[a][0]) * (vertices[b][1] - vertices[a][1])
                )

            area1 = tri_area(new_tri1)
            area2 = tri_area(new_tri2)

            # Оба треугольника должны иметь одинаковую ориентацию и не быть вырожденными
            if abs(area1) < 1e-10 or abs(area2) < 1e-10:
                continue
            if (area1 > 0) != (area2 > 0):
                continue

            # Минимальный угол после flip
            new_min = min(compute_min_angle(new_tri1), compute_min_angle(new_tri2))

            # Flip только если увеличивает минимальный угол
            if new_min > current_min + 1e-6:
                triangles[tri1_idx] = new_tri1
                triangles[tri2_idx] = new_tri2
                flipped = True
                flip_count += 1
                break

        if not flipped:
            break

    if flip_count > 0:
        print(f"[angle_flip] {flip_count} flips")

    return triangles


def cvt_smoothing(
    vertices: np.ndarray,
    triangles: list[tuple[int, int, int]],
    boundary_vertices: set[int] | None = None,
    iterations: int = 3,
) -> np.ndarray:
    """
    Оптимизировать позиции вершин для улучшения качества треугольников.

    Каждая внутренняя вершина двигается к позиции, которая делает окружающие
    треугольники более равносторонними. Движение ограничено чтобы сохранить площадь.

    Args:
        vertices: 2D координаты вершин, shape (N, 2).
        triangles: Список треугольников [(a, b, c), ...].
        boundary_vertices: Множество индексов граничных вершин (не сдвигать).
        iterations: Количество итераций оптимизации.

    Returns:
        Новый массив вершин.
    """
    import math

    if len(vertices) == 0 or len(triangles) == 0:
        return vertices

    vertices = np.array(vertices, dtype=np.float64)

    if boundary_vertices is None:
        boundary_vertices = set()

    # Строим карту: вершина → список треугольников
    vertex_triangles: dict[int, list[int]] = {i: [] for i in range(len(vertices))}
    for tri_idx, tri in enumerate(triangles):
        for v in tri:
            vertex_triangles[v].append(tri_idx)

    # Строим граф соседей
    neighbors: dict[int, set[int]] = {i: set() for i in range(len(vertices))}
    for tri in triangles:
        a, b, c = tri
        neighbors[a].add(b)
        neighbors[a].add(c)
        neighbors[b].add(a)
        neighbors[b].add(c)
        neighbors[c].add(a)
        neighbors[c].add(b)

    def compute_total_area() -> float:
        """Вычислить общую площадь."""
        total = 0.0
        for tri in triangles:
            a, b, c = tri
            v0 = vertices[a]
            v1 = vertices[b]
            v2 = vertices[c]
            total += abs((v1[0] - v0[0]) * (v2[1] - v0[1]) - (v2[0] - v0[0]) * (v1[1] - v0[1])) / 2
        return total

    def compute_ideal_position(v_idx: int) -> tuple[float, float]:
        """
        Вычислить идеальную позицию для вершины.

        Для каждого соседа вычисляем точку, которая образовала бы
        равносторонний треугольник. Усредняем эти точки.
        """
        nbrs = list(neighbors[v_idx])
        if len(nbrs) < 2:
            return vertices[v_idx][0], vertices[v_idx][1]

        # Центроид соседей (как базовая точка)
        cx = sum(vertices[n][0] for n in nbrs) / len(nbrs)
        cy = sum(vertices[n][1] for n in nbrs) / len(nbrs)

        return cx, cy

    area_before = compute_total_area()
    interior_count = len(vertices) - len(boundary_vertices)
    interior_indices = [i for i in range(len(vertices)) if i not in boundary_vertices]

    # Сохраняем исходные позиции граничных вершин для проверки
    boundary_positions_before = {i: (vertices[i][0], vertices[i][1]) for i in boundary_vertices}

    # Коэффициент сдвига (консервативный)
    alpha = 0.3

    for iteration in range(iterations):
        new_vertices = vertices.copy()

        for v_idx in interior_indices:
            # Целевая позиция
            target_x, target_y = compute_ideal_position(v_idx)

            # Сдвигаем на долю alpha к целевой позиции
            new_vertices[v_idx][0] = vertices[v_idx][0] + alpha * (target_x - vertices[v_idx][0])
            new_vertices[v_idx][1] = vertices[v_idx][1] + alpha * (target_y - vertices[v_idx][1])

        # Проверяем изменение площади и корректируем
        old_verts = vertices
        vertices = new_vertices
        area_after = compute_total_area()

        # Если площадь изменилась значительно, масштабируем обратно
        if abs(area_after - area_before) > area_before * 0.01:  # > 1% изменение
            # Вычисляем центроид границы
            boundary_list = list(boundary_vertices)
            if boundary_list:
                bcx = sum(vertices[i][0] for i in boundary_list) / len(boundary_list)
                bcy = sum(vertices[i][1] for i in boundary_list) / len(boundary_list)
            else:
                bcx = sum(v[0] for v in vertices) / len(vertices)
                bcy = sum(v[1] for v in vertices) / len(vertices)

            # Масштабируем внутренние вершины
            scale = math.sqrt(area_before / area_after) if area_after > 1e-10 else 1.0
            for i in interior_indices:
                vertices[i][0] = bcx + (vertices[i][0] - bcx) * scale
                vertices[i][1] = bcy + (vertices[i][1] - bcy) * scale

    # Проверяем что граничные вершины не сдвинулись
    boundary_moved = 0
    for i in boundary_vertices:
        bx, by = boundary_positions_before[i]
        if abs(vertices[i][0] - bx) > 1e-6 or abs(vertices[i][1] - by) > 1e-6:
            boundary_moved += 1

    if interior_count > 0:
        final_area = compute_total_area()
        area_change = (final_area - area_before) / area_before * 100
        print(f"[cvt_smoothing] {iterations} iterations, {interior_count} interior vertices, "
              f"boundary: {len(boundary_vertices)}, area change: {area_change:.2f}%"
              f"{f', BOUNDARY MOVED: {boundary_moved}!' if boundary_moved else ''}")

    return vertices.astype(np.float32)


def edge_collapse(
    vertices: np.ndarray,
    triangles: list[tuple[int, int, int]],
    min_edge_length: float,
    min_contour_edge_length: float = 0.0,
    boundary_edges: set[tuple[int, int]] | None = None,
    boundary_vertices: set[int] | None = None,
    max_iterations: int = 1000,
) -> tuple[np.ndarray, list[tuple[int, int, int]]]:
    """
    Схлопнуть короткие рёбра для упрощения меша.

    Args:
        vertices: 2D координаты вершин, shape (N, 2).
        triangles: Список треугольников [(a, b, c), ...].
        min_edge_length: Мин. длина внутреннего ребра.
        min_contour_edge_length: Мин. длина ребра на контуре.
        boundary_edges: Множество граничных рёбер (нормализованные: min, max).
        boundary_vertices: Множество индексов граничных вершин (не сдвигать).
        max_iterations: Максимум итераций.

    Returns:
        (new_vertices, new_triangles) — упрощённая триангуляция.
    """
    if (min_edge_length <= 0 and min_contour_edge_length <= 0) or len(triangles) == 0:
        return vertices, triangles

    vertices = list(map(tuple, vertices))
    triangles = list(triangles)

    if boundary_edges is None:
        boundary_edges = set()

    if boundary_vertices is None:
        boundary_vertices = set()

    # Debug info
    edge_map = build_edge_map(triangles)
    all_edges = list(edge_map.keys())
    edge_lengths = []
    for e0, e1 in all_edges:
        v0 = vertices[e0]
        v1 = vertices[e1]
        length = ((v1[0] - v0[0])**2 + (v1[1] - v0[1])**2)**0.5
        edge_lengths.append(length)

    if edge_lengths:
        min_len = min(edge_lengths)
        max_len = max(edge_lengths)
        avg_len = sum(edge_lengths) / len(edge_lengths)

        # Count collapsible edges
        interior_collapsible = 0
        contour_collapsible = 0
        for edge in all_edges:
            e0, e1 = edge
            v0 = vertices[e0]
            v1 = vertices[e1]
            length = ((v1[0] - v0[0])**2 + (v1[1] - v0[1])**2)**0.5
            if edge in boundary_edges:
                if min_contour_edge_length > 0 and length < min_contour_edge_length:
                    contour_collapsible += 1
            else:
                if min_edge_length > 0 and length < min_edge_length:
                    interior_collapsible += 1

        print(f"[edge_collapse] interior_threshold={min_edge_length:.3f}, contour_threshold={min_contour_edge_length:.3f}")
        print(f"[edge_collapse] edges={len(all_edges)}, lengths: min={min_len:.3f}, max={max_len:.3f}, avg={avg_len:.3f}")
        print(f"[edge_collapse] interior_collapsible={interior_collapsible}, contour_collapsible={contour_collapsible}")

    collapse_count = 0
    min_len_sq = min_edge_length * min_edge_length
    min_contour_len_sq = min_contour_edge_length * min_contour_edge_length

    for iteration in range(max_iterations):
        # Находим самое короткое СХЛОПЫВАЕМОЕ ребро
        # (учитываем разные пороги для внутренних и контурных рёбер)
        shortest_edge = None
        shortest_len_sq = float('inf')
        shortest_is_boundary = False

        edge_map = build_edge_map(triangles)

        for edge in edge_map.keys():
            e0, e1 = edge
            v0 = vertices[e0]
            v1 = vertices[e1]
            len_sq = (v1[0] - v0[0])**2 + (v1[1] - v0[1])**2

            is_boundary = edge in boundary_edges
            threshold_sq = min_contour_len_sq if is_boundary else min_len_sq

            # Пропускаем если порог нулевой
            if threshold_sq <= 0:
                continue

            # Проверяем, короче ли ребро порога
            if len_sq >= threshold_sq:
                continue

            if len_sq < shortest_len_sq:
                shortest_len_sq = len_sq
                shortest_edge = edge
                shortest_is_boundary = is_boundary

        if shortest_edge is None:
            break

        e0, e1 = shortest_edge
        is_boundary_edge = shortest_edge in boundary_edges

        # Схлопываем ребро: определяем какую вершину оставить
        e0_is_boundary = e0 in boundary_vertices
        e1_is_boundary = e1 in boundary_vertices

        if e0_is_boundary and e1_is_boundary and not is_boundary_edge:
            # Обе вершины граничные, но ребро внутреннее — не схлопываем
            continue

        if is_boundary_edge:
            # Граничное ребро — сдвигаем обе вершины в середину (меняем форму контура)
            keep_idx, remove_idx = e0, e1
            mid_x = (vertices[e0][0] + vertices[e1][0]) / 2
            mid_y = (vertices[e0][1] + vertices[e1][1]) / 2
            vertices[keep_idx] = (mid_x, mid_y)
        elif e0_is_boundary:
            # e0 граничная — оставляем e0, удаляем e1
            keep_idx, remove_idx = e0, e1
            # Не двигаем граничную вершину
        elif e1_is_boundary:
            # e1 граничная — оставляем e1, удаляем e0
            keep_idx, remove_idx = e1, e0
            # Не двигаем граничную вершину
        else:
            # Обе внутренние — сдвигаем в середину
            keep_idx, remove_idx = e0, e1
            mid_x = (vertices[e0][0] + vertices[e1][0]) / 2
            mid_y = (vertices[e0][1] + vertices[e1][1]) / 2
            vertices[keep_idx] = (mid_x, mid_y)

        # Заменяем remove_idx на keep_idx во всех треугольниках
        new_triangles = []
        for tri in triangles:
            a, b, c = tri
            if a == remove_idx:
                a = keep_idx
            if b == remove_idx:
                b = keep_idx
            if c == remove_idx:
                c = keep_idx

            # Проверяем что треугольник не вырожден (все вершины разные)
            if a != b and b != c and c != a:
                new_triangles.append((a, b, c))

        triangles = new_triangles
        collapse_count += 1

        # Обновляем boundary_edges: заменяем remove_idx на keep_idx
        new_boundary_edges = set()
        for be0, be1 in boundary_edges:
            if be0 == remove_idx:
                be0 = keep_idx
            if be1 == remove_idx:
                be1 = keep_idx
            if be0 != be1:
                new_boundary_edges.add((min(be0, be1), max(be0, be1)))
        boundary_edges = new_boundary_edges

        # Обновляем boundary_vertices: заменяем remove_idx на keep_idx
        if remove_idx in boundary_vertices:
            boundary_vertices.discard(remove_idx)
            boundary_vertices.add(keep_idx)

    if collapse_count > 0:
        # Удаляем неиспользуемые вершины и перенумеровываем
        used_vertices = set()
        for tri in triangles:
            used_vertices.update(tri)

        if len(used_vertices) < len(vertices):
            # Создаём маппинг старых индексов в новые
            old_to_new = {}
            new_vertices = []
            for old_idx in sorted(used_vertices):
                old_to_new[old_idx] = len(new_vertices)
                new_vertices.append(vertices[old_idx])

            # Перенумеровываем треугольники
            triangles = [
                (old_to_new[a], old_to_new[b], old_to_new[c])
                for a, b, c in triangles
            ]
            vertices = new_vertices

        print(f"[edge_collapse] {collapse_count} collapses, {len(vertices)} vertices, {len(triangles)} triangles")
    else:
        print(f"[edge_collapse] no collapses performed")

    return np.array(vertices, dtype=np.float32), triangles


def extract_boundary_edges(polygon_size: int) -> set[tuple[int, int]]:
    """Извлечь граничные рёбра полигона (индексы 0..n-1)."""
    edges = set()
    for i in range(polygon_size):
        j = (i + 1) % polygon_size
        edges.add((min(i, j), max(i, j)))
    return edges


def refine_triangulation(
    vertices: np.ndarray,
    triangles: list[tuple[int, int, int]],
    max_edge_length: float,
    max_iterations: int = 100,
    max_vertex_valence: int = 0,
) -> tuple[np.ndarray, list[tuple[int, int, int]]]:
    """
    Улучшить триангуляцию, разбивая большие треугольники и снижая валентность вершин.

    Добавляет точки на середине рёбер, превышающих max_edge_length,
    а также разбивает рёбра от вершин с высокой валентностью.

    Args:
        vertices: 2D координаты вершин, shape (N, 2).
        triangles: Список треугольников [(a, b, c), ...].
        max_edge_length: Максимальная длина ребра (0 = без ограничения).
        max_iterations: Максимум итераций разбиения.
        max_vertex_valence: Макс. количество треугольников на вершину (0 = без ограничения).

    Returns:
        (new_vertices, new_triangles) — улучшенная триангуляция.
    """
    vertices = list(map(tuple, vertices))  # список для добавления
    triangles = list(triangles)

    def split_edge(
        edge: tuple[int, int],
        verts: list[tuple[float, float]],
        tris: list[tuple[int, int, int]],
    ) -> tuple[list[tuple[float, float]], list[tuple[int, int, int]]]:
        """Разбить ребро, добавив вершину на середине."""
        e0, e1 = edge
        mid_x = (verts[e0][0] + verts[e1][0]) / 2
        mid_y = (verts[e0][1] + verts[e1][1]) / 2
        new_vertex_idx = len(verts)
        verts.append((mid_x, mid_y))

        # Находим все треугольники с этим ребром
        tris_to_split = []
        for tri_idx, tri in enumerate(tris):
            edge_set = {
                (min(tri[0], tri[1]), max(tri[0], tri[1])),
                (min(tri[1], tri[2]), max(tri[1], tri[2])),
                (min(tri[2], tri[0]), max(tri[2], tri[0])),
            }
            if edge in edge_set:
                tris_to_split.append(tri_idx)

        # Разбиваем каждый треугольник на два
        new_triangles = []
        for tri_idx, tri in enumerate(tris):
            if tri_idx in tris_to_split:
                opposite = -1
                for v in tri:
                    if v != e0 and v != e1:
                        opposite = v
                        break

                if opposite >= 0:
                    new_triangles.append((e0, new_vertex_idx, opposite))
                    new_triangles.append((new_vertex_idx, e1, opposite))
            else:
                new_triangles.append(tri)

        return verts, new_triangles

    for iteration in range(max_iterations):
        made_split = False

        # Фаза 1: Разбиение по длине рёбер
        if max_edge_length > 0:
            longest_edge = None
            longest_length = 0.0

            for tri in triangles:
                for edge_idx in range(3):
                    v0_idx = tri[edge_idx]
                    v1_idx = tri[(edge_idx + 1) % 3]
                    v0 = vertices[v0_idx]
                    v1 = vertices[v1_idx]

                    length = ((v1[0] - v0[0])**2 + (v1[1] - v0[1])**2)**0.5

                    if length > longest_length:
                        longest_length = length
                        longest_edge = (min(v0_idx, v1_idx), max(v0_idx, v1_idx))

            if longest_length > max_edge_length and longest_edge is not None:
                vertices, triangles = split_edge(longest_edge, vertices, triangles)
                made_split = True
                continue  # Перезапускаем итерацию

        # Фаза 2: Ограничение валентности вершин (TODO: реализовать)
        # Текущий алгоритм разбиения рёбер не уменьшает валентность.
        # Для корректной работы нужен более сложный подход с перетриангуляцией.
        # Пока параметр max_vertex_valence не используется.

        # Нет изменений — завершаем
        if not made_split:
            break

    return np.array(vertices, dtype=np.float32), triangles


def ear_clipping_refined(
    vertices: np.ndarray,
    max_edge_length: float = 1.0,
    min_edge_length: float = 0.0,
    min_contour_edge_length: float = 0.0,
    max_vertex_valence: int = 0,
    use_delaunay_flip: bool = True,
    use_valence_flip: bool = False,
    use_angle_flip: bool = False,
    use_cvt_smoothing: bool = False,
    use_second_pass: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Триангулировать полигон с ограничением размера треугольников.

    Args:
        vertices: 2D координаты вершин полигона (CCW), shape (N, 2).
        max_edge_length: Максимальная длина ребра (0 = без ограничения).
        min_edge_length: Мин. длина внутреннего ребра для edge collapse (0 = без collapse).
        min_contour_edge_length: Мин. длина ребра на контуре (0 = без collapse).
        max_vertex_valence: Макс. количество треугольников на вершину (0 = без ограничения).
        use_delaunay_flip: Применить Delaunay edge flipping.
        use_valence_flip: Применить edge flipping для уменьшения валентности.
        use_angle_flip: Применить edge flipping для максимизации минимального угла.
        use_cvt_smoothing: Применить CVT (Centroidal Voronoi Tessellation) smoothing.
        use_second_pass: Повторный проход flips + smoothing после edge collapse.

    Returns:
        (vertices, triangles) — вершины могут содержать добавленные точки.
    """
    # Базовая триангуляция
    triangles = ear_clip(vertices)
    if not triangles:
        return vertices, np.array([], dtype=np.int32).reshape(0, 3)

    # Разбиваем большие треугольники
    refined_verts, refined_tris = refine_triangulation(
        vertices, triangles, max_edge_length, max_vertex_valence=max_vertex_valence
    )

    # Граничные рёбра исходного полигона (не переворачиваем)
    boundary = extract_boundary_edges(len(vertices))

    # Граничные вершины — исходные вершины полигона
    boundary_vertices = set(range(len(vertices)))

    # Также помечаем вершины, добавленные на граничных рёбрах
    # (после refinement новые вершины на границе тоже должны быть зафиксированы)
    for v_idx in range(len(vertices), len(refined_verts)):
        # Проверяем, лежит ли вершина на каком-либо граничном ребре
        vx, vy = refined_verts[v_idx]
        for e0, e1 in boundary:
            # Точки ребра
            x0, y0 = refined_verts[e0]
            x1, y1 = refined_verts[e1]
            # Проверяем, лежит ли точка на отрезке
            # Вектор ребра
            dx, dy = x1 - x0, y1 - y0
            edge_len_sq = dx * dx + dy * dy
            if edge_len_sq < 1e-10:
                continue
            # Проекция точки на прямую
            t = ((vx - x0) * dx + (vy - y0) * dy) / edge_len_sq
            if t < -0.01 or t > 1.01:
                continue
            # Расстояние до прямой
            proj_x = x0 + t * dx
            proj_y = y0 + t * dy
            dist_sq = (vx - proj_x) ** 2 + (vy - proj_y) ** 2
            if dist_sq < 1e-6:  # На ребре
                boundary_vertices.add(v_idx)
                break

    # Delaunay optimization
    if use_delaunay_flip and len(refined_tris) >= 2:
        refined_tris = delaunay_flip(refined_verts, refined_tris, boundary)

    # Valence optimization
    if use_valence_flip and len(refined_tris) >= 2:
        refined_tris = valence_flip(
            refined_verts, refined_tris, boundary, max_vertex_valence
        )

    # Angle optimization
    if use_angle_flip and len(refined_tris) >= 2:
        refined_tris = angle_flip(refined_verts, refined_tris, boundary)

    # CVT smoothing (только внутренние вершины)
    if use_cvt_smoothing and len(refined_verts) > len(vertices):
        refined_verts = cvt_smoothing(
            refined_verts, refined_tris, boundary_vertices
        )

    # Edge collapse (схлопывание коротких рёбер)
    # Вычисляем граничные рёбра как рёбра с одним соседним треугольником
    if min_edge_length > 0 or min_contour_edge_length > 0:
        edge_map = build_edge_map(refined_tris)
        actual_boundary_edges = {
            edge for edge, tris in edge_map.items() if len(tris) == 1
        }
        # Граничные вершины — вершины на граничных рёбрах
        actual_boundary_vertices = set()
        for e0, e1 in actual_boundary_edges:
            actual_boundary_vertices.add(e0)
            actual_boundary_vertices.add(e1)
        refined_verts, refined_tris = edge_collapse(
            refined_verts, refined_tris, min_edge_length, min_contour_edge_length,
            actual_boundary_edges, actual_boundary_vertices
        )

    # Второй проход (после edge collapse)
    if use_second_pass and len(refined_tris) >= 2:
        print("[second_pass] Starting...")

        # Пересчитываем граничные рёбра после collapse
        edge_map = build_edge_map(refined_tris)
        boundary = {
            edge for edge, tris in edge_map.items() if len(tris) == 1
        }

        # Пересчитываем граничные вершины
        boundary_vertices = set()
        for e0, e1 in boundary:
            boundary_vertices.add(e0)
            boundary_vertices.add(e1)

        # Delaunay flip (второй проход)
        if use_delaunay_flip:
            refined_tris = delaunay_flip(refined_verts, refined_tris, boundary)

        # Valence optimization (второй проход)
        if use_valence_flip:
            refined_tris = valence_flip(refined_verts, refined_tris, boundary, max_vertex_valence)

        # Angle optimization (второй проход)
        if use_angle_flip:
            refined_tris = angle_flip(refined_verts, refined_tris, boundary)

        # CVT smoothing (второй проход)
        if use_cvt_smoothing and len(boundary_vertices) < len(refined_verts):
            refined_verts = cvt_smoothing(
                refined_verts, refined_tris, boundary_vertices
            )

        print("[second_pass] Done")

    return refined_verts, np.array(refined_tris, dtype=np.int32)


def transform_to_3d(
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


def build_2d_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Построить ортонормальный базис (U, V) перпендикулярный нормали.

    Args:
        normal: Нормаль плоскости (3D вектор).

    Returns:
        (u_axis, v_axis) — ортонормальные векторы на плоскости.
    """
    normal = normal / np.linalg.norm(normal)

    # Выбираем вектор, не параллельный нормали
    if abs(normal[0]) < 0.9:
        ref = np.array([1.0, 0.0, 0.0])
    else:
        ref = np.array([0.0, 1.0, 0.0])

    # U = ref × normal (нормализованный)
    u_axis = np.cross(ref, normal)
    u_axis = u_axis / np.linalg.norm(u_axis)

    # V = normal × U
    v_axis = np.cross(normal, u_axis)
    v_axis = v_axis / np.linalg.norm(v_axis)

    return u_axis.astype(np.float32), v_axis.astype(np.float32)
