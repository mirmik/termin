"""
Pathfinding на основе графа треугольников.

Иерархическая структура:
- RegionGraph: граф треугольников внутри одного региона
- NavMeshGraph: граф регионов + порталы между ними
"""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import numpy as np


@dataclass
class RegionGraph:
    """Граф треугольников для одного региона."""

    region_id: int
    vertices: np.ndarray      # (N, 3) — вершины
    triangles: np.ndarray     # (M, 3) — индексы вершин треугольников
    neighbors: np.ndarray     # (M, 3) — соседи по каждому ребру, -1 = нет соседа
    centroids: np.ndarray     # (M, 3) — центры треугольников

    @classmethod
    def from_mesh(
        cls,
        vertices: np.ndarray,
        triangles: np.ndarray,
        region_id: int = 0,
    ) -> RegionGraph:
        """Построить граф из меша."""
        neighbors = build_adjacency(triangles)
        centroids = compute_centroids(vertices, triangles)
        return cls(
            region_id=region_id,
            vertices=vertices,
            triangles=triangles,
            neighbors=neighbors,
            centroids=centroids,
        )

    def find_triangle(self, point: np.ndarray) -> int:
        """Найти треугольник, содержащий точку. Возвращает -1 если не найден."""
        return find_triangle_containing_point(point, self.vertices, self.triangles)

    def find_path(self, start: np.ndarray, end: np.ndarray) -> list[int] | None:
        """
        Найти путь между двумя точками.

        Returns:
            Список индексов треугольников от старта до финиша, или None.
        """
        start_tri = self.find_triangle(start)
        end_tri = self.find_triangle(end)

        if start_tri < 0 or end_tri < 0:
            return None

        if start_tri == end_tri:
            return [start_tri]

        return astar_triangles(
            start_tri, end_tri, self.neighbors, self.centroids,
            self.triangles, self.vertices
        )


@dataclass
class Portal:
    """Связь между двумя регионами."""

    region_a: int
    region_b: int
    tri_a: int              # треугольник в регионе A
    tri_b: int              # треугольник в регионе B
    edge: tuple[int, int]   # общее ребро (индексы вершин)


@dataclass
class NavMeshGraph:
    """Глобальный граф навигации."""

    regions: list[RegionGraph] = field(default_factory=list)
    portals: list[Portal] = field(default_factory=list)

    def add_region(self, region: RegionGraph) -> None:
        """Добавить регион."""
        self.regions.append(region)

    def add_portal(self, portal: Portal) -> None:
        """Добавить портал между регионами."""
        self.portals.append(portal)

    def find_region(self, point: np.ndarray) -> int:
        """Найти регион, содержащий точку. Возвращает -1 если не найден."""
        for i, region in enumerate(self.regions):
            if region.find_triangle(point) >= 0:
                return i
        return -1

    def find_path(self, start: np.ndarray, end: np.ndarray) -> list[tuple[int, int]] | None:
        """
        Найти путь между двумя точками.

        Returns:
            Список (region_id, triangle_id) от старта до финиша, или None.
        """
        start_region = self.find_region(start)
        end_region = self.find_region(end)

        if start_region < 0 or end_region < 0:
            return None

        if start_region == end_region:
            # Путь внутри одного региона
            region = self.regions[start_region]
            path = region.find_path(start, end)
            if path is None:
                return None
            return [(start_region, tri) for tri in path]

        # TODO: межрегиональный поиск через порталы
        return None


def build_adjacency(triangles: np.ndarray) -> np.ndarray:
    """
    Построить массив смежности треугольников.

    Args:
        triangles: (M, 3) — индексы вершин треугольников.

    Returns:
        neighbors: (M, 3) — для каждого треугольника, сосед по каждому ребру.
                   neighbors[t, e] = индекс соседнего треугольника по ребру e, или -1.
                   Ребро 0: вершины (0, 1), ребро 1: (1, 2), ребро 2: (2, 0).
    """
    m = len(triangles)
    neighbors = np.full((m, 3), -1, dtype=np.int32)

    # edge -> (triangle_idx, edge_idx)
    edge_to_tri: dict[tuple[int, int], tuple[int, int]] = {}

    for tri_idx in range(m):
        t = triangles[tri_idx]
        for edge_idx in range(3):
            v0 = int(t[edge_idx])
            v1 = int(t[(edge_idx + 1) % 3])
            # Нормализуем ребро (меньший индекс первым)
            edge = (min(v0, v1), max(v0, v1))

            if edge in edge_to_tri:
                # Нашли соседа
                other_tri, other_edge = edge_to_tri[edge]
                neighbors[tri_idx, edge_idx] = other_tri
                neighbors[other_tri, other_edge] = tri_idx
            else:
                edge_to_tri[edge] = (tri_idx, edge_idx)

    return neighbors


def compute_centroids(vertices: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Вычислить центроиды треугольников."""
    v0 = vertices[triangles[:, 0]]
    v1 = vertices[triangles[:, 1]]
    v2 = vertices[triangles[:, 2]]
    return (v0 + v1 + v2) / 3.0


def find_triangle_containing_point(
    point: np.ndarray,
    vertices: np.ndarray,
    triangles: np.ndarray,
    tolerance: float = 0.5,
) -> int:
    """
    Найти треугольник, содержащий точку.

    Проецирует точку на плоскость каждого треугольника и проверяет:
    1. Расстояние до плоскости < tolerance
    2. Проекция внутри треугольника

    Args:
        point: (3,) — точка в 3D.
        vertices: (N, 3) — вершины.
        triangles: (M, 3) — треугольники.
        tolerance: максимальное расстояние до плоскости треугольника.

    Returns:
        Индекс треугольника или -1.
    """
    best_tri = -1
    best_dist = tolerance

    for tri_idx in range(len(triangles)):
        t = triangles[tri_idx]
        v0 = vertices[t[0]]
        v1 = vertices[t[1]]
        v2 = vertices[t[2]]

        # Рёбра треугольника
        edge1 = v1 - v0
        edge2 = v2 - v0

        # Нормаль треугольника
        normal = np.cross(edge1, edge2)
        normal_len = np.linalg.norm(normal)
        if normal_len < 1e-10:
            continue
        normal = normal / normal_len

        # Расстояние от точки до плоскости
        d = np.dot(point - v0, normal)
        abs_d = abs(d)
        if abs_d > tolerance:
            continue

        # Проекция точки на плоскость
        p_proj = point - d * normal

        # Локальная 2D система координат на плоскости
        u_axis = edge1 / np.linalg.norm(edge1)
        v_axis = np.cross(normal, u_axis)

        # Перевод в 2D
        rel = p_proj - v0
        p2d_u = np.dot(rel, u_axis)
        p2d_v = np.dot(rel, v_axis)

        b2d_u = np.dot(edge1, u_axis)
        b2d_v = np.dot(edge1, v_axis)

        c2d_u = np.dot(edge2, u_axis)
        c2d_v = np.dot(edge2, v_axis)

        # Проверка point_in_triangle_2d
        if point_in_triangle_2d(p2d_u, p2d_v, 0.0, 0.0, b2d_u, b2d_v, c2d_u, c2d_v):
            if abs_d < best_dist:
                best_dist = abs_d
                best_tri = tri_idx

    return best_tri


def point_in_triangle_2d(
    px: float, py: float,
    x0: float, y0: float,
    x1: float, y1: float,
    x2: float, y2: float,
    epsilon: float = 0.05,
) -> bool:
    """
    Проверить, находится ли точка внутри треугольника (2D).

    Args:
        epsilon: Допуск для точек на границе или чуть за ней.
                 Нормализуется относительно площади треугольника.
    """
    def signed_area(ax, ay, bx, by, cx, cy):
        return (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)

    # Площадь треугольника
    area = signed_area(x0, y0, x1, y1, x2, y2)
    if abs(area) < 1e-10:
        return False

    # Барицентрические координаты (не нормализованные)
    s = signed_area(px, py, x0, y0, x1, y1)
    t = signed_area(px, py, x1, y1, x2, y2)
    u = signed_area(px, py, x2, y2, x0, y0)

    # Порог пропорционален площади
    threshold = epsilon * abs(area)

    if area > 0:
        # CCW winding
        return s >= -threshold and t >= -threshold and u >= -threshold
    else:
        # CW winding
        return s <= threshold and t <= threshold and u <= threshold


def get_portals_from_path(
    path: list[int],
    triangles: np.ndarray,
    vertices: np.ndarray,
    neighbors: np.ndarray,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    Извлечь порталы (рёбра между смежными треугольниками) из пути.

    Left/right ориентированы консистентно: общие вершины соседних порталов
    остаются на той же стороне (left или right).

    Args:
        path: Список индексов треугольников.
        triangles: (M, 3) — индексы вершин треугольников.
        vertices: (N, 3) — вершины.
        neighbors: (M, 3) — соседи по каждому ребру.

    Returns:
        Список порталов (left, right) — координаты концов общего ребра.
    """
    portals: list[tuple[np.ndarray, np.ndarray]] = []

    from termin._native import log as _log

    # Храним индексы вершин для обеспечения консистентности
    prev_left_idx: int | None = None
    prev_right_idx: int | None = None

    for i in range(len(path) - 1):
        tri_a = path[i]
        tri_b = path[i + 1]

        tri_a_verts = triangles[tri_a]

        # Найти общее ребро между tri_a и tri_b
        found_edge = False
        for edge_idx in range(3):
            if neighbors[tri_a, edge_idx] == tri_b:
                v0_idx = triangles[tri_a, edge_idx]
                v1_idx = triangles[tri_a, (edge_idx + 1) % 3]
                p0 = vertices[v0_idx].copy()
                p1 = vertices[v1_idx].copy()

                # Определяем left/right
                if i == 0:
                    # Первый портал: определяем ориентацию по направлению движения
                    tri_b_verts = triangles[tri_b]
                    centroid_a = (vertices[tri_a_verts[0]] + vertices[tri_a_verts[1]] + vertices[tri_a_verts[2]]) / 3.0
                    centroid_b = (vertices[tri_b_verts[0]] + vertices[tri_b_verts[1]] + vertices[tri_b_verts[2]]) / 3.0
                    move_dir = centroid_b - centroid_a

                    # Нормаль треугольника A
                    va0 = vertices[tri_a_verts[0]]
                    va1 = vertices[tri_a_verts[1]]
                    va2 = vertices[tri_a_verts[2]]
                    normal = np.cross(va1 - va0, va2 - va0)
                    normal_len = np.linalg.norm(normal)
                    if normal_len > 1e-10:
                        normal = normal / normal_len

                    edge_vec = p1 - p0
                    cross = np.cross(move_dir, edge_vec)
                    sign = np.dot(cross, normal)

                    if sign >= 0:
                        left_idx, right_idx = v0_idx, v1_idx
                    else:
                        left_idx, right_idx = v1_idx, v0_idx
                else:
                    # Последующие порталы: сохраняем консистентность с предыдущим
                    # Если одна из вершин совпадает с предыдущей, она остаётся на той же стороне
                    if v0_idx == prev_left_idx or v1_idx == prev_right_idx:
                        left_idx, right_idx = v0_idx, v1_idx
                    elif v1_idx == prev_left_idx or v0_idx == prev_right_idx:
                        left_idx, right_idx = v1_idx, v0_idx
                    else:
                        # Нет общих вершин с предыдущим порталом — используем move_dir
                        tri_b_verts = triangles[tri_b]
                        centroid_a = (vertices[tri_a_verts[0]] + vertices[tri_a_verts[1]] + vertices[tri_a_verts[2]]) / 3.0
                        centroid_b = (vertices[tri_b_verts[0]] + vertices[tri_b_verts[1]] + vertices[tri_b_verts[2]]) / 3.0
                        move_dir = centroid_b - centroid_a

                        va0 = vertices[tri_a_verts[0]]
                        va1 = vertices[tri_a_verts[1]]
                        va2 = vertices[tri_a_verts[2]]
                        normal = np.cross(va1 - va0, va2 - va0)
                        normal_len = np.linalg.norm(normal)
                        if normal_len > 1e-10:
                            normal = normal / normal_len

                        edge_vec = p1 - p0
                        cross = np.cross(move_dir, edge_vec)
                        sign = np.dot(cross, normal)

                        if sign >= 0:
                            left_idx, right_idx = v0_idx, v1_idx
                        else:
                            left_idx, right_idx = v1_idx, v0_idx

                left = vertices[left_idx].copy()
                right = vertices[right_idx].copy()

                _log.info(f"[Portal {i}] tri {tri_a}->{tri_b}, left_idx={left_idx}, right_idx={right_idx}")
                _log.info(f"[Portal {i}] left={left}, right={right}")

                portals.append((left, right))
                prev_left_idx = left_idx
                prev_right_idx = right_idx
                found_edge = True
                break

        if not found_edge:
            _log.warn(f"[Portal {i}] NO SHARED EDGE between tri {tri_a} and {tri_b}!")
            _log.warn(f"[Portal {i}] neighbors[{tri_a}] = {neighbors[tri_a]}")

    return portals


def funnel_algorithm(
    start: np.ndarray,
    end: np.ndarray,
    portals: list[tuple[np.ndarray, np.ndarray]],
    normal: np.ndarray | None = None,
) -> list[np.ndarray]:
    """
    Funnel Algorithm (Simple Stupid Funnel Algorithm).

    Оптимизирует путь через порталы, "натягивая верёвку".

    Args:
        start: Начальная точка.
        end: Конечная точка.
        portals: Список порталов (left, right).
        normal: Нормаль плоскости региона. Если None, вычисляется из первого портала.

    Returns:
        Оптимизированный список точек пути.
    """
    from termin._native import log as _log

    if len(portals) == 0:
        return [start.copy(), end.copy()]

    _log.info(f"[Funnel] start={start}, end={end}, {len(portals)} portals")
    for pi, (pl, pr) in enumerate(portals):
        _log.info(f"[Funnel] portal {pi}: left={pl}, right={pr}")

    # Вычисляем нормаль из первого портала если не задана
    if normal is None:
        # Используем start, portal_left, portal_right для определения плоскости
        p_left, p_right = portals[0]
        v1 = p_left - start
        v2 = p_right - start
        normal = np.cross(v1, v2)
        n_len = np.linalg.norm(normal)
        if n_len > 1e-10:
            normal = normal / n_len
        else:
            # Fallback на Y-up
            normal = np.array([0.0, 1.0, 0.0], dtype=np.float64)

    # Добавляем конечную точку как "портал" с left=right=end
    portals = portals + [(end.copy(), end.copy())]

    path: list[np.ndarray] = [start.copy()]

    # Вершина воронки
    apex = start.copy()
    apex_index = 0

    # Левая и правая границы воронки
    left = portals[0][0].copy()
    right = portals[0][1].copy()
    left_index = 0
    right_index = 0

    _log.info(f"[Funnel] initial: apex={apex}, left={left}, right={right}")

    def triarea2(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        """
        Знаковая площадь треугольника в плоскости с заданной нормалью.

        Положительная = c слева от вектора a→b.
        Отрицательная = c справа.
        """
        ab = b - a
        ac = c - a
        cross = np.cross(ab, ac)
        return float(np.dot(cross, normal))

    i = 1
    max_iterations = len(portals) * 3  # Защита от бесконечного цикла
    iteration = 0
    while i < len(portals):
        iteration += 1
        if iteration > max_iterations:
            _log.warn(f"[Funnel] max iterations exceeded, breaking")
            break

        portal_left = portals[i][0]
        portal_right = portals[i][1]

        # Обновляем правую границу
        # Пропускаем если portal_right == right (граница не изменилась)
        if np.allclose(right, portal_right):
            pass  # Правая граница не изменилась
        elif triarea2(apex, right, portal_right) <= 0.0:
            # Проверяем пересечение с левой границей
            # Если apex == left или apex == right — воронка схлопнулась в точку,
            # нет границы для пересечения, просто сужаем
            apex_collapsed = np.allclose(apex, left) or np.allclose(apex, right)
            if apex_collapsed or triarea2(apex, left, portal_right) > 0.0:
                # Сужаем воронку справа
                right = portal_right.copy()
                right_index = i
            else:
                # Правая граница пересекла левую — добавляем left в путь
                _log.info(f"[Funnel] i={i}: right crossed left, adding waypoint left={left}")
                path.append(left.copy())
                apex = left.copy()
                apex_index = left_index

                # Перезапускаем воронку
                left = apex.copy()
                right = apex.copy()
                left_index = apex_index
                right_index = apex_index

                # Перезапускаем сканирование с apex
                i = apex_index + 1
                continue

        # Обновляем левую границу
        # Пропускаем если portal_left == left (граница не изменилась)
        if np.allclose(left, portal_left):
            pass  # Левая граница не изменилась
        elif triarea2(apex, left, portal_left) >= 0.0:
            # Проверяем пересечение с правой границей
            # Если apex == left или apex == right — воронка схлопнулась в точку,
            # нет границы для пересечения, просто сужаем
            apex_collapsed = np.allclose(apex, left) or np.allclose(apex, right)
            if apex_collapsed or triarea2(apex, right, portal_left) < 0.0:
                # Сужаем воронку слева
                left = portal_left.copy()
                left_index = i
            else:
                # Левая граница пересекла правую — добавляем right в путь
                _log.info(f"[Funnel] i={i}: left crossed right, adding waypoint right={right}")
                path.append(right.copy())
                apex = right.copy()
                apex_index = right_index

                # Перезапускаем воронку
                left = apex.copy()
                right = apex.copy()
                left_index = apex_index
                right_index = apex_index

                # Перезапускаем сканирование с apex
                i = apex_index + 1
                continue

        i += 1

    # Добавляем конечную точку
    if len(path) == 0 or not np.allclose(path[-1], end):
        path.append(end.copy())

    return path


def navmesh_line_of_sight(
    start: np.ndarray,
    end: np.ndarray,
    start_tri: int,
    triangles: np.ndarray,
    vertices: np.ndarray,
    neighbors: np.ndarray,
) -> bool:
    """
    Проверка прямой видимости на NavMesh.

    Идёт от start_tri к end по прямой, переходя через порталы.
    Возвращает True если можно дойти, не выходя за границы NavMesh.

    Args:
        start: Начальная точка.
        end: Конечная точка.
        start_tri: Индекс треугольника, содержащего start.
        triangles: (M, 3) — индексы вершин треугольников.
        vertices: (N, 3) — вершины.
        neighbors: (M, 3) — соседи.

    Returns:
        True если прямой путь возможен.
    """
    from termin._native import log as _log

    direction = end - start
    dir_len = float(np.linalg.norm(direction))
    if dir_len < 1e-8:
        return True

    current_tri = start_tri
    prev_tri = -1  # Предыдущий треугольник (чтобы не возвращаться)
    max_iterations = len(triangles) * 2  # защита от бесконечного цикла

    for iteration in range(max_iterations):
        # Проверяем, находится ли end в текущем треугольнике
        tri = triangles[current_tri]
        v0 = vertices[tri[0]]
        v1 = vertices[tri[1]]
        v2 = vertices[tri[2]]

        if _point_in_triangle_3d(end, v0, v1, v2):
            _log.info(f"[LOS] end found in tri {current_tri} after {iteration} iterations")
            return True

        # Вычисляем базис плоскости треугольника
        edge1 = v1 - v0
        edge2 = v2 - v0
        normal = np.cross(edge1, edge2)
        normal_len = np.linalg.norm(normal)
        if normal_len < 1e-10:
            _log.warn(f"[LOS] degenerate triangle {current_tri}")
            return False
        normal = normal / normal_len

        u_axis = edge1 / np.linalg.norm(edge1)
        v_axis = np.cross(normal, u_axis)

        # Ищем ребро, которое пересекает луч start->end
        # Исключаем ребро, через которое мы пришли (prev_tri)
        best_edge = -1
        best_t = float('inf')

        for edge_idx in range(3):
            neighbor = neighbors[current_tri, edge_idx]

            # Не возвращаемся назад
            if neighbor == prev_tri:
                continue

            e0 = vertices[tri[edge_idx]]
            e1 = vertices[tri[(edge_idx + 1) % 3]]

            t = _ray_edge_intersection_3d(start, direction, e0, e1, u_axis, v_axis)
            if t is not None and 0.0 < t <= 1.0:
                if t < best_t:
                    best_t = t
                    best_edge = edge_idx

        if best_edge < 0:
            _log.info(f"[LOS] no exit edge found in tri {current_tri}")
            return False  # Нет пересечения — луч не выходит через это ребро

        neighbor = neighbors[current_tri, best_edge]
        if neighbor < 0:
            _log.info(f"[LOS] hit boundary edge {best_edge} in tri {current_tri}")
            return False  # Граничное ребро — нет прямой видимости

        prev_tri = current_tri
        current_tri = neighbor

    _log.warn(f"[LOS] max iterations reached")
    return False


def _point_in_triangle_3d(
    point: np.ndarray,
    v0: np.ndarray,
    v1: np.ndarray,
    v2: np.ndarray,
    tolerance: float = 0.5,
) -> bool:
    """Проверить, находится ли точка в треугольнике (3D с проекцией)."""
    edge1 = v1 - v0
    edge2 = v2 - v0

    normal = np.cross(edge1, edge2)
    normal_len = np.linalg.norm(normal)
    if normal_len < 1e-10:
        return False
    normal = normal / normal_len

    d = np.dot(point - v0, normal)
    if abs(d) > tolerance:
        return False

    p_proj = point - d * normal

    u_axis = edge1 / np.linalg.norm(edge1)
    v_axis = np.cross(normal, u_axis)

    rel = p_proj - v0
    p2d_u = np.dot(rel, u_axis)
    p2d_v = np.dot(rel, v_axis)

    b2d_u = np.dot(edge1, u_axis)
    b2d_v = np.dot(edge1, v_axis)

    c2d_u = np.dot(edge2, u_axis)
    c2d_v = np.dot(edge2, v_axis)

    return point_in_triangle_2d(p2d_u, p2d_v, 0.0, 0.0, b2d_u, b2d_v, c2d_u, c2d_v)


def _ray_edge_intersection_3d(
    origin: np.ndarray,
    direction: np.ndarray,
    e0: np.ndarray,
    e1: np.ndarray,
    u_axis: np.ndarray,
    v_axis: np.ndarray,
) -> float | None:
    """
    Пересечение луча с ребром в плоскости треугольника.

    Args:
        origin: Начало луча (3D).
        direction: Направление луча (3D).
        e0, e1: Концы ребра (3D).
        u_axis, v_axis: Базис плоскости треугольника.

    Returns:
        Параметр t вдоль direction, или None.
    """
    # Проецируем на плоскость треугольника
    ou = float(np.dot(origin, u_axis))
    ov = float(np.dot(origin, v_axis))
    du = float(np.dot(direction, u_axis))
    dv = float(np.dot(direction, v_axis))

    e0u = float(np.dot(e0, u_axis))
    e0v = float(np.dot(e0, v_axis))
    e1u = float(np.dot(e1, u_axis))
    e1v = float(np.dot(e1, v_axis))

    eu = e1u - e0u
    ev = e1v - e0v

    denom = du * ev - dv * eu
    if abs(denom) < 1e-10:
        return None  # Параллельны

    diff_u = e0u - ou
    diff_v = e0v - ov

    t = (diff_u * ev - diff_v * eu) / denom
    s = (diff_u * dv - diff_v * du) / denom

    if 0.0 <= s <= 1.0 and t > 1e-8:
        return t

    return None


def astar_triangles(
    start_tri: int,
    end_tri: int,
    neighbors: np.ndarray,
    centroids: np.ndarray,
    triangles: np.ndarray | None = None,
    vertices: np.ndarray | None = None,
    start_pos: np.ndarray | None = None,
    end_pos: np.ndarray | None = None,
) -> list[int] | None:
    """
    A* поиск пути по графу треугольников.

    Args:
        start_tri: индекс стартового треугольника.
        end_tri: индекс целевого треугольника.
        neighbors: (M, 3) — массив соседей.
        centroids: (M, 3) — центры треугольников.
        triangles: (M, 3) — индексы вершин (опционально, для расчёта по рёбрам).
        vertices: (N, 3) — вершины (опционально, для расчёта по рёбрам).
        start_pos: Реальная начальная точка (опционально).
        end_pos: Реальная конечная точка (опционально).

    Returns:
        Список индексов треугольников от старта до финиша, или None.
    """
    use_edge_centers = triangles is not None and vertices is not None

    # Используем реальные позиции если заданы, иначе центроиды
    actual_start = start_pos if start_pos is not None else centroids[start_tri]
    actual_goal = end_pos if end_pos is not None else centroids[end_tri]

    def get_edge_center(tri_idx: int, edge_idx: int) -> np.ndarray:
        """Получить центр ребра треугольника."""
        v0_idx = triangles[tri_idx, edge_idx]
        v1_idx = triangles[tri_idx, (edge_idx + 1) % 3]
        return (vertices[v0_idx] + vertices[v1_idx]) * 0.5

    def heuristic_from_pos(pos: np.ndarray) -> float:
        """Эвристика: расстояние от текущей позиции до цели."""
        return float(np.linalg.norm(pos - actual_goal))

    # Начальная позиция
    initial_pos = actual_start.copy()

    # (f_score, counter, triangle_idx)
    counter = 0
    open_set: list[tuple[float, int, int]] = [(heuristic_from_pos(initial_pos), counter, start_tri)]
    came_from: dict[int, int] = {}
    # g_score хранит (расстояние, последняя точка на пути)
    g_score: dict[int, tuple[float, np.ndarray]] = {
        start_tri: (0.0, initial_pos)
    }

    from termin._native import log as _astar_log

    while open_set:
        f_val, _, current = heapq.heappop(open_set)
        current_g, current_pos = g_score[current]
        _astar_log.info(f"[A*] pop tri={current}, g={current_g:.2f}, f={f_val:.2f}, pos={current_pos}")

        if current == end_tri:
            # Восстанавливаем путь
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return path[::-1]

        current_g, current_pos = g_score[current]

        for edge_idx in range(3):
            neighbor = neighbors[current, edge_idx]
            if neighbor < 0:
                continue

            if use_edge_centers:
                # Расстояние через центр общего ребра
                edge_center = get_edge_center(current, edge_idx)
                dist = float(np.linalg.norm(current_pos - edge_center))
                next_pos = edge_center
            else:
                # Fallback: расстояние между центроидами
                dist = float(np.linalg.norm(centroids[current] - centroids[neighbor]))
                next_pos = centroids[neighbor].copy()

            tentative_g = current_g + dist

            if neighbor not in g_score or tentative_g < g_score[neighbor][0]:
                came_from[neighbor] = current
                g_score[neighbor] = (tentative_g, next_pos)
                h = heuristic_from_pos(next_pos)
                f = tentative_g + h
                _astar_log.info(f"[A*]   -> tri={neighbor}, dist={dist:.2f}, g={tentative_g:.2f}, h={h:.2f}, f={f:.2f}")
                counter += 1
                heapq.heappush(open_set, (f, counter, neighbor))

    return None
