"""Tests for navmesh pathfinding."""

import unittest
import numpy as np

from termin.navmesh.pathfinding import (
    RegionGraph,
    build_adjacency,
    compute_centroids,
    find_triangle_containing_point,
    point_in_triangle_2d,
    astar_triangles,
)


class BuildAdjacencyTest(unittest.TestCase):
    """Тесты для build_adjacency."""

    def test_single_triangle(self):
        """Один треугольник — нет соседей."""
        triangles = np.array([[0, 1, 2]], dtype=np.int32)
        neighbors = build_adjacency(triangles)

        self.assertEqual(neighbors.shape, (1, 3))
        self.assertTrue(np.all(neighbors == -1))

    def test_two_adjacent_triangles(self):
        """Два треугольника с общим ребром."""
        # Треугольник 0: (0, 1, 2)
        # Треугольник 1: (1, 3, 2) — общее ребро (1, 2)
        triangles = np.array([
            [0, 1, 2],
            [1, 3, 2],
        ], dtype=np.int32)
        neighbors = build_adjacency(triangles)

        self.assertEqual(neighbors.shape, (2, 3))
        # Треугольник 0: ребро 1 (вершины 1-2) соседствует с треугольником 1
        self.assertEqual(neighbors[0, 1], 1)
        # Треугольник 1: ребро 2 (вершины 2-1) соседствует с треугольником 0
        self.assertEqual(neighbors[1, 2], 0)

    def test_three_triangles_fan(self):
        """Три треугольника веером из одной вершины."""
        #     1
        #    /|\
        #   / | \
        #  0--+--2
        #   \ | /
        #    \|/
        #     3
        triangles = np.array([
            [0, 1, 2],  # верхний
            [0, 2, 3],  # правый
            [0, 3, 1],  # левый (замыкает)
        ], dtype=np.int32)
        neighbors = build_adjacency(triangles)

        # Каждый треугольник должен иметь 2 соседа (через вершину 0)
        # Но соседство по РЕБРУ, не по вершине!
        # Треугольники 0 и 1 имеют общее ребро (0, 2)
        # Треугольники 1 и 2 имеют общее ребро (0, 3)
        # Треугольники 0 и 2 имеют общее ребро (0, 1)

        # Проверяем что каждый треугольник имеет ровно 2 соседа
        for tri_idx in range(3):
            neighbor_count = np.sum(neighbors[tri_idx] >= 0)
            self.assertEqual(neighbor_count, 2, f"Triangle {tri_idx} should have 2 neighbors")


class PointInTriangleTest(unittest.TestCase):
    """Тесты для point_in_triangle_2d."""

    def test_point_inside(self):
        """Точка внутри треугольника."""
        self.assertTrue(point_in_triangle_2d(
            0.5, 0.5,
            0.0, 0.0,
            1.0, 0.0,
            0.5, 1.0,
        ))

    def test_point_outside(self):
        """Точка снаружи треугольника."""
        self.assertFalse(point_in_triangle_2d(
            2.0, 2.0,
            0.0, 0.0,
            1.0, 0.0,
            0.5, 1.0,
        ))

    def test_point_on_edge(self):
        """Точка на ребре — считается внутри."""
        self.assertTrue(point_in_triangle_2d(
            0.5, 0.0,
            0.0, 0.0,
            1.0, 0.0,
            0.5, 1.0,
        ))


class FindTriangleTest(unittest.TestCase):
    """Тесты для find_triangle_containing_point."""

    def test_find_in_single_triangle(self):
        """Найти точку в единственном треугольнике."""
        vertices = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 0.0, 1.0],
        ], dtype=np.float32)
        triangles = np.array([[0, 1, 2]], dtype=np.int32)

        # Точка в центре (XZ проекция)
        point = np.array([0.5, 0.0, 0.3])
        result = find_triangle_containing_point(point, vertices, triangles)
        self.assertEqual(result, 0)

    def test_point_not_found(self):
        """Точка вне всех треугольников."""
        vertices = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 0.0, 1.0],
        ], dtype=np.float32)
        triangles = np.array([[0, 1, 2]], dtype=np.int32)

        point = np.array([5.0, 0.0, 5.0])
        result = find_triangle_containing_point(point, vertices, triangles)
        self.assertEqual(result, -1)


class AStarTest(unittest.TestCase):
    """Тесты для A* поиска."""

    def test_same_triangle(self):
        """Старт и финиш в одном треугольнике."""
        triangles = np.array([[0, 1, 2]], dtype=np.int32)
        neighbors = np.array([[-1, -1, -1]], dtype=np.int32)
        centroids = np.array([[0.5, 0.0, 0.5]], dtype=np.float32)

        path = astar_triangles(0, 0, neighbors, centroids)
        self.assertEqual(path, [0])

    def test_two_triangles(self):
        """Путь через два соседних треугольника."""
        triangles = np.array([
            [0, 1, 2],
            [1, 3, 2],
        ], dtype=np.int32)
        neighbors = np.array([
            [-1, 1, -1],  # tri 0: сосед 1 по ребру 1
            [-1, -1, 0],  # tri 1: сосед 0 по ребру 2
        ], dtype=np.int32)
        centroids = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
        ], dtype=np.float32)

        path = astar_triangles(0, 1, neighbors, centroids)
        self.assertEqual(path, [0, 1])

    def test_no_path(self):
        """Нет пути между несвязанными треугольниками."""
        neighbors = np.array([
            [-1, -1, -1],
            [-1, -1, -1],
        ], dtype=np.int32)
        centroids = np.array([
            [0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0],
        ], dtype=np.float32)

        path = astar_triangles(0, 1, neighbors, centroids)
        self.assertIsNone(path)

    def test_path_through_multiple_triangles(self):
        """Путь через несколько треугольников."""
        # Линейная цепочка: 0 -- 1 -- 2 -- 3
        neighbors = np.array([
            [-1, 1, -1],
            [0, 2, -1],
            [1, 3, -1],
            [2, -1, -1],
        ], dtype=np.int32)
        centroids = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
        ], dtype=np.float32)

        path = astar_triangles(0, 3, neighbors, centroids)
        self.assertEqual(path, [0, 1, 2, 3])


class RegionGraphTest(unittest.TestCase):
    """Тесты для RegionGraph."""

    def test_from_mesh(self):
        """Создание RegionGraph из меша."""
        vertices = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 0.0, 1.0],
            [1.5, 0.0, 0.5],
        ], dtype=np.float32)
        triangles = np.array([
            [0, 1, 2],
            [1, 3, 2],
        ], dtype=np.int32)

        graph = RegionGraph.from_mesh(vertices, triangles, region_id=42)

        self.assertEqual(graph.region_id, 42)
        self.assertEqual(len(graph.triangles), 2)
        self.assertEqual(len(graph.centroids), 2)
        self.assertEqual(graph.neighbors.shape, (2, 3))

    def test_find_path(self):
        """Поиск пути через RegionGraph."""
        vertices = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 0.0, 1.0],
            [1.5, 0.0, 0.5],
        ], dtype=np.float32)
        triangles = np.array([
            [0, 1, 2],
            [1, 3, 2],
        ], dtype=np.int32)

        graph = RegionGraph.from_mesh(vertices, triangles)

        # Точка в первом треугольнике
        start = np.array([0.3, 0.0, 0.3])
        # Точка во втором треугольнике
        end = np.array([1.2, 0.0, 0.4])

        path = graph.find_path(start, end)
        self.assertIsNotNone(path)
        self.assertEqual(path, [0, 1])


class NavMeshGraphTest(unittest.TestCase):
    """Тесты для NavMeshGraph."""

    def test_single_region(self):
        """Поиск пути внутри одного региона."""
        from termin.navmesh.pathfinding import NavMeshGraph

        vertices = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 0.0, 1.0],
            [1.5, 0.0, 0.5],
        ], dtype=np.float32)
        triangles = np.array([
            [0, 1, 2],
            [1, 3, 2],
        ], dtype=np.int32)

        graph = NavMeshGraph()
        region = RegionGraph.from_mesh(vertices, triangles, region_id=0)
        graph.add_region(region)

        # Точка в первом треугольнике
        start = np.array([0.3, 0.0, 0.3])
        # Точка во втором треугольнике
        end = np.array([1.2, 0.0, 0.4])

        path = graph.find_path(start, end)
        self.assertIsNotNone(path)
        self.assertEqual(len(path), 2)
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[1], (0, 1))

    def test_find_region(self):
        """Поиск региона по точке."""
        from termin.navmesh.pathfinding import NavMeshGraph

        vertices = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 0.0, 1.0],
        ], dtype=np.float32)
        triangles = np.array([[0, 1, 2]], dtype=np.int32)

        graph = NavMeshGraph()
        region = RegionGraph.from_mesh(vertices, triangles, region_id=0)
        graph.add_region(region)

        # Точка внутри
        inside = np.array([0.5, 0.0, 0.3])
        self.assertEqual(graph.find_region(inside), 0)

        # Точка снаружи
        outside = np.array([5.0, 0.0, 5.0])
        self.assertEqual(graph.find_region(outside), -1)


class RayTriangleIntersectTest(unittest.TestCase):
    """Тесты для ray-triangle intersection."""

    def test_ray_hits_triangle(self):
        """Луч попадает в треугольник."""
        from termin.navmesh.pathfinding_world_component import _ray_triangle_intersect

        # Треугольник в плоскости Y=0
        v0 = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.5, 0.0, 1.0], dtype=np.float32)

        # Луч сверху вниз через центр треугольника
        origin = np.array([0.5, 5.0, 0.3], dtype=np.float32)
        direction = np.array([0.0, -1.0, 0.0], dtype=np.float32)

        t = _ray_triangle_intersect(origin, direction, v0, v1, v2)
        self.assertIsNotNone(t)
        self.assertAlmostEqual(t, 5.0, places=5)

    def test_ray_misses_triangle(self):
        """Луч не попадает в треугольник."""
        from termin.navmesh.pathfinding_world_component import _ray_triangle_intersect

        v0 = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.5, 0.0, 1.0], dtype=np.float32)

        # Луч мимо треугольника
        origin = np.array([5.0, 5.0, 5.0], dtype=np.float32)
        direction = np.array([0.0, -1.0, 0.0], dtype=np.float32)

        t = _ray_triangle_intersect(origin, direction, v0, v1, v2)
        self.assertIsNone(t)

    def test_ray_parallel_to_triangle(self):
        """Луч параллелен треугольнику."""
        from termin.navmesh.pathfinding_world_component import _ray_triangle_intersect

        v0 = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.5, 0.0, 1.0], dtype=np.float32)

        # Луч параллелен плоскости Y=0
        origin = np.array([0.5, 1.0, 0.3], dtype=np.float32)
        direction = np.array([1.0, 0.0, 0.0], dtype=np.float32)

        t = _ray_triangle_intersect(origin, direction, v0, v1, v2)
        self.assertIsNone(t)

    def test_ray_behind_origin(self):
        """Треугольник позади начала луча."""
        from termin.navmesh.pathfinding_world_component import _ray_triangle_intersect

        v0 = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.5, 0.0, 1.0], dtype=np.float32)

        # Луч направлен вверх, но треугольник ниже
        origin = np.array([0.5, 5.0, 0.3], dtype=np.float32)
        direction = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        t = _ray_triangle_intersect(origin, direction, v0, v1, v2)
        self.assertIsNone(t)


if __name__ == "__main__":
    unittest.main()
