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

        return astar_triangles(start_tri, end_tri, self.neighbors, self.centroids)


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
) -> bool:
    """Проверить, находится ли точка внутри треугольника (2D)."""
    def sign(px, py, x1, y1, x2, y2):
        return (px - x2) * (y1 - y2) - (x1 - x2) * (py - y2)

    d1 = sign(px, py, x0, y0, x1, y1)
    d2 = sign(px, py, x1, y1, x2, y2)
    d3 = sign(px, py, x2, y2, x0, y0)

    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)

    return not (has_neg and has_pos)


def get_portals_from_path(
    path: list[int],
    triangles: np.ndarray,
    vertices: np.ndarray,
    neighbors: np.ndarray,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    Извлечь порталы (рёбра между смежными треугольниками) из пути.

    Args:
        path: Список индексов треугольников.
        triangles: (M, 3) — индексы вершин треугольников.
        vertices: (N, 3) — вершины.
        neighbors: (M, 3) — соседи по каждому ребру.

    Returns:
        Список порталов (left, right) — координаты концов общего ребра.
    """
    portals: list[tuple[np.ndarray, np.ndarray]] = []

    for i in range(len(path) - 1):
        tri_a = path[i]
        tri_b = path[i + 1]

        # Найти общее ребро между tri_a и tri_b
        for edge_idx in range(3):
            if neighbors[tri_a, edge_idx] == tri_b:
                # Ребро edge_idx: вершины (edge_idx, edge_idx+1)
                v0_idx = triangles[tri_a, edge_idx]
                v1_idx = triangles[tri_a, (edge_idx + 1) % 3]
                left = vertices[v0_idx].copy()
                right = vertices[v1_idx].copy()
                portals.append((left, right))
                break

    return portals


def funnel_algorithm(
    start: np.ndarray,
    end: np.ndarray,
    portals: list[tuple[np.ndarray, np.ndarray]],
) -> list[np.ndarray]:
    """
    Funnel Algorithm (Simple Stupid Funnel Algorithm).

    Оптимизирует путь через порталы, "натягивая верёвку".

    Args:
        start: Начальная точка.
        end: Конечная точка.
        portals: Список порталов (left, right).

    Returns:
        Оптимизированный список точек пути.
    """
    if len(portals) == 0:
        return [start.copy(), end.copy()]

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

    def triarea2(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        """Удвоенная площадь треугольника (знаковая, 2D на плоскости XY или XZ)."""
        # Используем X и Z (горизонтальная плоскость)
        ax = b[0] - a[0]
        az = b[2] - a[2]
        bx = c[0] - a[0]
        bz = c[2] - a[2]
        return ax * bz - az * bx

    i = 1
    while i < len(portals):
        portal_left = portals[i][0]
        portal_right = portals[i][1]

        # Обновляем правую границу
        if triarea2(apex, right, portal_right) <= 0.0:
            if np.allclose(apex, right) or triarea2(apex, left, portal_right) > 0.0:
                # Сужаем воронку справа
                right = portal_right.copy()
                right_index = i
            else:
                # Правая граница пересекла левую — добавляем left в путь
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
        if triarea2(apex, left, portal_left) >= 0.0:
            if np.allclose(apex, left) or triarea2(apex, right, portal_left) < 0.0:
                # Сужаем воронку слева
                left = portal_left.copy()
                left_index = i
            else:
                # Левая граница пересекла правую — добавляем right в путь
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
    direction = end - start
    dir_len = float(np.linalg.norm(direction))
    if dir_len < 1e-8:
        return True

    current_tri = start_tri
    visited: set[int] = set()
    max_iterations = len(triangles) * 2  # защита от бесконечного цикла

    for _ in range(max_iterations):
        if current_tri in visited:
            return False
        visited.add(current_tri)

        # Проверяем, находится ли end в текущем треугольнике
        tri = triangles[current_tri]
        v0 = vertices[tri[0]]
        v1 = vertices[tri[1]]
        v2 = vertices[tri[2]]

        if _point_in_triangle_3d(end, v0, v1, v2):
            return True

        # Ищем ребро, которое пересекает луч start->end
        best_edge = -1
        best_t = float('inf')

        for edge_idx in range(3):
            e0 = vertices[tri[edge_idx]]
            e1 = vertices[tri[(edge_idx + 1) % 3]]

            t = _ray_edge_intersection_2d(start, direction, e0, e1)
            if t is not None and 0.0 < t <= 1.0:
                if t < best_t:
                    best_t = t
                    best_edge = edge_idx

        if best_edge < 0:
            return False  # Нет пересечения — что-то не так

        neighbor = neighbors[current_tri, best_edge]
        if neighbor < 0:
            return False  # Граничное ребро — нет прямой видимости

        current_tri = neighbor

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


def _ray_edge_intersection_2d(
    origin: np.ndarray,
    direction: np.ndarray,
    e0: np.ndarray,
    e1: np.ndarray,
) -> float | None:
    """
    Пересечение луча с ребром в 2D (XZ плоскость).

    Returns:
        Параметр t вдоль direction, или None.
    """
    # Проецируем на XZ
    ox, oz = origin[0], origin[2]
    dx, dz = direction[0], direction[2]

    e0x, e0z = e0[0], e0[2]
    e1x, e1z = e1[0], e1[2]

    ex = e1x - e0x
    ez = e1z - e0z

    denom = dx * ez - dz * ex
    if abs(denom) < 1e-10:
        return None  # Параллельны

    diff_x = e0x - ox
    diff_z = e0z - oz

    t = (diff_x * ez - diff_z * ex) / denom
    s = (diff_x * dz - diff_z * dx) / denom

    if 0.0 <= s <= 1.0 and t > 1e-8:
        return t

    return None


def astar_triangles(
    start_tri: int,
    end_tri: int,
    neighbors: np.ndarray,
    centroids: np.ndarray,
) -> list[int] | None:
    """
    A* поиск пути по графу треугольников.

    Args:
        start_tri: индекс стартового треугольника.
        end_tri: индекс целевого треугольника.
        neighbors: (M, 3) — массив соседей.
        centroids: (M, 3) — центры треугольников.

    Returns:
        Список индексов треугольников от старта до финиша, или None.
    """
    goal = centroids[end_tri]

    def heuristic(tri: int) -> float:
        return float(np.linalg.norm(centroids[tri] - goal))

    # (f_score, counter, triangle_idx)
    counter = 0
    open_set: list[tuple[float, int, int]] = [(heuristic(start_tri), counter, start_tri)]
    came_from: dict[int, int] = {}
    g_score: dict[int, float] = {start_tri: 0.0}

    while open_set:
        _, _, current = heapq.heappop(open_set)

        if current == end_tri:
            # Восстанавливаем путь
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return path[::-1]

        for edge_idx in range(3):
            neighbor = neighbors[current, edge_idx]
            if neighbor < 0:
                continue

            # Расстояние между центроидами
            dist = float(np.linalg.norm(centroids[current] - centroids[neighbor]))
            tentative_g = g_score[current] + dist

            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + heuristic(neighbor)
                counter += 1
                heapq.heappush(open_set, (f, counter, neighbor))

    return None
