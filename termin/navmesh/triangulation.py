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
                    break  # Перестраиваем edge_map

        if not flipped:
            break

    return triangles


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
    max_vertex_valence: int = 0,
    optimize: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Триангулировать полигон с ограничением размера треугольников.

    Args:
        vertices: 2D координаты вершин полигона (CCW), shape (N, 2).
        max_edge_length: Максимальная длина ребра (0 = без ограничения).
        max_vertex_valence: Макс. количество треугольников на вершину (0 = без ограничения).
        optimize: Применить Delaunay edge flipping.

    Returns:
        (vertices, triangles) — вершины могут содержать добавленные точки.
    """
    # Базовая триангуляция
    triangles = ear_clip(vertices)
    if not triangles:
        return vertices, np.array([], dtype=np.int32).reshape(0, 3)

    # Разбиваем большие треугольники и высоковалентные вершины
    refined_verts, refined_tris = refine_triangulation(
        vertices, triangles, max_edge_length, max_vertex_valence=max_vertex_valence
    )

    # Delaunay optimization
    if optimize and len(refined_tris) >= 2:
        # Граничные рёбра исходного полигона
        boundary = extract_boundary_edges(len(vertices))
        refined_tris = delaunay_flip(refined_verts, refined_tris, boundary)

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
