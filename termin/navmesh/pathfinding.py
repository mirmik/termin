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
) -> int:
    """
    Найти треугольник, содержащий точку (2D проекция на XZ).

    Args:
        point: (3,) — точка в 3D.
        vertices: (N, 3) — вершины.
        triangles: (M, 3) — треугольники.

    Returns:
        Индекс треугольника или -1.
    """
    px, pz = point[0], point[2]

    for tri_idx in range(len(triangles)):
        t = triangles[tri_idx]
        v0 = vertices[t[0]]
        v1 = vertices[t[1]]
        v2 = vertices[t[2]]

        # Проверка point-in-triangle в XZ плоскости
        if point_in_triangle_2d(px, pz, v0[0], v0[2], v1[0], v1[2], v2[0], v2[2]):
            return tri_idx

    return -1


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
