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
) -> bool:
    """Проверить, является ли вершина выпуклой."""
    cross = (curr_p[0] - prev_p[0]) * (next_p[1] - curr_p[1]) - \
            (curr_p[1] - prev_p[1]) * (next_p[0] - curr_p[0])

    if ccw:
        return cross > 0
    else:
        return cross < 0


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
            if not is_convex_2d(prev_p, curr_p, next_p, ccw):
                continue

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
            break

    # Добавляем последний треугольник
    if len(indices) == 3:
        triangles.append((indices[0], indices[1], indices[2]))

    return triangles


def ear_clipping(vertices: np.ndarray) -> np.ndarray:
    """
    Триангулировать простой полигон методом Ear Clipping.

    Обёртка над ear_clip(), возвращающая np.ndarray.

    Args:
        vertices: 2D координаты вершин полигона (CCW), shape (N, 2).

    Returns:
        Треугольники (индексы вершин), shape (N-2, 3).
    """
    triangles = ear_clip(vertices)
    if not triangles:
        return np.array([], dtype=np.int32).reshape(0, 3)
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

        # Дырка в обратном порядке, начиная с bridge_hole_idx
        for i in range(len(hole_list)):
            idx = (bridge_hole_idx - i) % len(hole_list)
            new_contour.append(hole_list[idx])

        # Возврат к bridge vertex (замыкаем мост)
        new_contour.append(hole_list[bridge_hole_idx])
        new_contour.append(result[bridge_outer_idx])

        # Остаток внешнего контура
        for i in range(bridge_outer_idx + 1, len(result)):
            new_contour.append(result[i])

        result = new_contour

    return np.array(result, dtype=np.float32)


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
