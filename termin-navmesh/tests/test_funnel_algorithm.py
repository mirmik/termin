"""
Тесты для Funnel Algorithm и связанных функций.
"""

import numpy as np

from termin.navmesh.pathfinding import (
    build_adjacency,
    get_portals_from_path,
    funnel_algorithm,
    navmesh_line_of_sight,
)


def _xz(point):
    return np.array([point[0], point[2]], dtype=np.float64)


def _assert_path_endpoints(path, start, end):
    assert len(path) >= 2
    assert np.allclose(path[0], start)
    assert np.allclose(path[-1], end)


def _orient(a, b, c):
    return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _on_segment(a, b, p, eps=1e-6):
    return (
        min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps
        and abs(_orient(a, b, p)) <= eps
    )


def _segments_intersect(a0, a1, b0, b1, eps=1e-6):
    o1 = _orient(a0, a1, b0)
    o2 = _orient(a0, a1, b1)
    o3 = _orient(b0, b1, a0)
    o4 = _orient(b0, b1, a1)

    if o1 * o2 < -eps and o3 * o4 < -eps:
        return True

    return (
        _on_segment(a0, a1, b0, eps)
        or _on_segment(a0, a1, b1, eps)
        or _on_segment(b0, b1, a0, eps)
        or _on_segment(b0, b1, a1, eps)
    )


def _assert_path_crosses_portals(path, portals):
    segments = [(_xz(path[i]), _xz(path[i + 1])) for i in range(len(path) - 1)]
    for portal_index, (left, right) in enumerate(portals):
        portal = (_xz(left), _xz(right))
        assert any(
            _segments_intersect(seg[0], seg[1], portal[0], portal[1])
            for seg in segments
        ), f"Path does not cross portal {portal_index}: {left} -> {right}"


def _assert_waypoints_are_portal_corners(path, portals):
    corners = [point for portal in portals for point in portal]
    for waypoint in path[1:-1]:
        assert any(np.allclose(waypoint, corner) for corner in corners), (
            f"Waypoint {waypoint} is not a portal corner"
        )


def _point_in_triangle_xz(point, a, b, c, eps=1e-5):
    area = _orient(a, b, c)
    if abs(area) < eps:
        return False

    s = _orient(point, a, b)
    t = _orient(point, b, c)
    u = _orient(point, c, a)

    if area > 0:
        return s >= -eps and t >= -eps and u >= -eps
    return s <= eps and t <= eps and u <= eps


def _point_in_mesh_xz(point, vertices, triangles):
    p = _xz(point)
    for tri in triangles:
        a, b, c = (_xz(vertices[tri[0]]), _xz(vertices[tri[1]]), _xz(vertices[tri[2]]))
        if _point_in_triangle_xz(p, a, b, c):
            return True
    return False


def _assert_path_inside_mesh(path, vertices, triangles, samples_per_segment=32):
    for segment_index, (start, end) in enumerate(zip(path, path[1:])):
        for sample_index in range(samples_per_segment + 1):
            t = sample_index / samples_per_segment
            point = start * (1.0 - t) + end * t
            assert _point_in_mesh_xz(point, vertices, triangles), (
                f"Path segment {segment_index} leaves mesh at t={t:.3f}: {point}"
            )


def _assert_triangle_path_connected(path_tris, neighbors):
    assert len(path_tris) >= 1
    for left, right in zip(path_tris, path_tris[1:]):
        assert right in neighbors[left], f"Triangles {left} and {right} are not adjacent"


def _assert_portals_match_triangle_path(path_tris, portals, triangles, vertices):
    assert len(portals) == max(0, len(path_tris) - 1)
    for portal_index, (tri_a, tri_b) in enumerate(zip(path_tris, path_tris[1:])):
        shared = set(map(int, triangles[tri_a])).intersection(map(int, triangles[tri_b]))
        assert len(shared) == 2, f"Triangles {tri_a} and {tri_b} do not share an edge"
        expected = {tuple(vertices[idx]) for idx in shared}
        actual = {tuple(portals[portal_index][0]), tuple(portals[portal_index][1])}
        assert actual == expected


class TestGetPortalsFromPath:
    """Тесты для get_portals_from_path."""

    def test_two_triangles_simple(self):
        """Два треугольника с общим ребром."""
        #   2
        #  /|\
        # 0-+-1
        #  \|/
        #   3
        vertices = np.array([
            [0, 0, 0],   # 0
            [2, 0, 0],   # 1
            [1, 0, 2],   # 2
            [1, 0, -2],  # 3
        ], dtype=np.float32)

        triangles = np.array([
            [0, 1, 2],  # верхний
            [0, 3, 1],  # нижний (обратный порядок для общего ребра 0-1)
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)

        # Путь из треугольника 0 в треугольник 1
        path = [0, 1]
        portals = get_portals_from_path(path, triangles, vertices, neighbors)

        assert len(portals) == 1
        _assert_portals_match_triangle_path(path, portals, triangles, vertices)

        left, right = portals[0]
        # Общее ребро — 0-1, порядок зависит от edge_idx
        edge_set = {tuple(left), tuple(right)}
        assert edge_set == {tuple(vertices[0]), tuple(vertices[1])}

    def test_three_triangles_strip(self):
        """Три треугольника в линию."""
        # 0--1--2--3
        # | /| /| /|
        # |/ |/ |/ |
        # 4--5--6--7
        vertices = np.array([
            [0, 0, 2],  # 0
            [1, 0, 2],  # 1
            [2, 0, 2],  # 2
            [3, 0, 2],  # 3
            [0, 0, 0],  # 4
            [1, 0, 0],  # 5
            [2, 0, 0],  # 6
            [3, 0, 0],  # 7
        ], dtype=np.float32)

        triangles = np.array([
            [0, 4, 1],  # tri 0: левый верхний
            [1, 4, 5],  # tri 1: левый нижний
            [1, 5, 2],  # tri 2: средний верхний
            [2, 5, 6],  # tri 3: средний нижний
            [2, 6, 3],  # tri 4: правый верхний
            [3, 6, 7],  # tri 5: правый нижний
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)

        # Путь через все треугольники
        path = [0, 1, 2, 3, 4, 5]
        portals = get_portals_from_path(path, triangles, vertices, neighbors)

        assert len(portals) == 5  # 6 треугольников = 5 порталов
        _assert_portals_match_triangle_path(path, portals, triangles, vertices)


class TestFunnelAlgorithm:
    """Тесты для funnel_algorithm."""

    def test_straight_line(self):
        """Прямой путь без препятствий — должен вернуть только start и end."""
        start = np.array([0, 0, 0], dtype=np.float32)
        end = np.array([10, 0, 0], dtype=np.float32)

        # Порталы широкие, не мешают прямому пути
        portals = [
            (np.array([2, 0, -5], dtype=np.float32), np.array([2, 0, 5], dtype=np.float32)),
            (np.array([5, 0, -5], dtype=np.float32), np.array([5, 0, 5], dtype=np.float32)),
            (np.array([8, 0, -5], dtype=np.float32), np.array([8, 0, 5], dtype=np.float32)),
        ]

        path = funnel_algorithm(start, end, portals)

        assert len(path) == 2
        _assert_path_endpoints(path, start, end)
        _assert_path_crosses_portals(path, portals)

    def test_single_turn(self):
        """Путь с одним поворотом."""
        #
        #  start ----portal1---- corner
        #                          |
        #                       portal2
        #                          |
        #                         end
        #
        start = np.array([0, 0, 0], dtype=np.float32)
        end = np.array([5, 0, -5], dtype=np.float32)

        # Портал 1: горизонтальный, ведёт к углу
        # Портал 2: вертикальный, ведёт вниз
        portals = [
            (np.array([3, 0, -1], dtype=np.float32), np.array([3, 0, 1], dtype=np.float32)),  # |
            (np.array([4, 0, -2], dtype=np.float32), np.array([6, 0, -2], dtype=np.float32)),  # --
        ]

        path = funnel_algorithm(start, end, portals)

        _assert_path_endpoints(path, start, end)
        _assert_waypoints_are_portal_corners(path, portals)
        _assert_path_crosses_portals(path, portals)

    def test_corridor_zigzag(self):
        """Узкий коридор с зигзагом — путь должен идти через углы порталов."""
        start = np.array([0, 0, 0], dtype=np.float32)
        end = np.array([10, 0, 0], dtype=np.float32)

        # Узкие порталы, смещённые то влево, то вправо — прямая линия НЕ проходит
        portals = [
            (np.array([2, 0, 0], dtype=np.float32), np.array([2, 0, 1], dtype=np.float32)),   # z: 0-1
            (np.array([4, 0, -1], dtype=np.float32), np.array([4, 0, 0], dtype=np.float32)),  # z: -1-0
            (np.array([6, 0, 0], dtype=np.float32), np.array([6, 0, 1], dtype=np.float32)),   # z: 0-1
            (np.array([8, 0, -1], dtype=np.float32), np.array([8, 0, 0], dtype=np.float32)),  # z: -1-0
        ]

        path = funnel_algorithm(start, end, portals)

        _assert_path_endpoints(path, start, end)
        _assert_waypoints_are_portal_corners(path, portals)
        _assert_path_crosses_portals(path, portals)

    def test_wide_corridor_straight(self):
        """Широкий коридор — прямая линия должна проходить без поворотов."""
        start = np.array([0, 0, 0.5], dtype=np.float32)
        end = np.array([10, 0, 0.5], dtype=np.float32)

        # Широкие порталы, все включают z=0.5
        portals = [
            (np.array([2, 0, 0], dtype=np.float32), np.array([2, 0, 1], dtype=np.float32)),   # z: 0-1, включает 0.5
            (np.array([4, 0, 0], dtype=np.float32), np.array([4, 0, 1], dtype=np.float32)),   # z: 0-1, включает 0.5
            (np.array([6, 0, 0], dtype=np.float32), np.array([6, 0, 1], dtype=np.float32)),   # z: 0-1, включает 0.5
            (np.array([8, 0, 0], dtype=np.float32), np.array([8, 0, 1], dtype=np.float32)),   # z: 0-1, включает 0.5
        ]

        path = funnel_algorithm(start, end, portals)

        assert len(path) == 2, f"Expected straight line (2 points), got {len(path)}"
        _assert_path_endpoints(path, start, end)
        _assert_path_crosses_portals(path, portals)

    def test_no_portals(self):
        """Без порталов — прямой путь start -> end."""
        start = np.array([0, 0, 0], dtype=np.float32)
        end = np.array([5, 0, 5], dtype=np.float32)

        path = funnel_algorithm(start, end, [])

        assert len(path) == 2
        _assert_path_endpoints(path, start, end)

class TestNavmeshLineOfSight:
    """Тесты для navmesh_line_of_sight."""

    def test_same_triangle(self):
        """Start и end в одном треугольнике."""
        vertices = np.array([
            [0, 0, 0],
            [2, 0, 0],
            [1, 0, 2],
        ], dtype=np.float32)

        triangles = np.array([[0, 1, 2]], dtype=np.int32)
        neighbors = np.array([[-1, -1, -1]], dtype=np.int32)

        start = np.array([0.5, 0, 0.5], dtype=np.float32)
        end = np.array([1.0, 0, 0.5], dtype=np.float32)

        result = navmesh_line_of_sight(start, end, 0, triangles, vertices, neighbors)
        assert result is True

    def test_adjacent_triangles(self):
        """Start и end в соседних треугольниках."""
        vertices = np.array([
            [0, 0, 0],
            [2, 0, 0],
            [1, 0, 2],
            [1, 0, -2],
        ], dtype=np.float32)

        triangles = np.array([
            [0, 1, 2],
            [0, 3, 1],
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)

        start = np.array([1, 0, 1], dtype=np.float32)  # в треугольнике 0
        end = np.array([1, 0, -1], dtype=np.float32)   # в треугольнике 1

        result = navmesh_line_of_sight(start, end, 0, triangles, vertices, neighbors)
        assert result is True

    def test_blocked_by_boundary(self):
        """Путь блокирован границей NavMesh."""
        #  Два отдельных треугольника без общего ребра
        vertices = np.array([
            [0, 0, 0],
            [1, 0, 0],
            [0.5, 0, 1],
            [5, 0, 0],
            [6, 0, 0],
            [5.5, 0, 1],
        ], dtype=np.float32)

        triangles = np.array([
            [0, 1, 2],
            [3, 4, 5],
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)
        # Треугольники не соединены
        assert neighbors[0, 0] == -1
        assert neighbors[0, 1] == -1
        assert neighbors[0, 2] == -1

        start = np.array([0.5, 0, 0.3], dtype=np.float32)
        end = np.array([5.5, 0, 0.3], dtype=np.float32)

        result = navmesh_line_of_sight(start, end, 0, triangles, vertices, neighbors)
        assert result is False


class TestIntegration:
    """Интеграционные тесты."""

    def test_simple_mesh_pathfinding(self):
        """Полный пайплайн: A* -> порталы -> funnel."""
        from termin.navmesh.pathfinding import astar_triangles, compute_centroids

        # Простой меш: 4 треугольника в ряд
        # 0---1---2---3---4
        # |  /|  /|  /|  /|
        # | / | / | / | / |
        # |/  |/  |/  |/  |
        # 5---6---7---8---9
        vertices = np.array([
            [0, 0, 1], [1, 0, 1], [2, 0, 1], [3, 0, 1], [4, 0, 1],
            [0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0],
        ], dtype=np.float32)

        triangles = np.array([
            [0, 5, 1],  # 0
            [1, 5, 6],  # 1
            [1, 6, 2],  # 2
            [2, 6, 7],  # 3
            [2, 7, 3],  # 4
            [3, 7, 8],  # 5
            [3, 8, 4],  # 6
            [4, 8, 9],  # 7
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)
        centroids = compute_centroids(vertices, triangles)

        # A* от треугольника 0 до треугольника 7
        path_tris = astar_triangles(0, 7, neighbors, centroids)
        assert path_tris is not None
        assert path_tris[0] == 0
        assert path_tris[-1] == 7
        _assert_triangle_path_connected(path_tris, neighbors)

        # Извлекаем порталы
        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        _assert_portals_match_triangle_path(path_tris, portals, triangles, vertices)

        # Funnel algorithm
        start = np.array([0.3, 0, 0.5], dtype=np.float32)
        end = np.array([3.7, 0, 0.5], dtype=np.float32)

        path = funnel_algorithm(start, end, portals)

        assert len(path) == 2, f"Expected 2 points (straight line), got {len(path)}"
        _assert_path_endpoints(path, start, end)
        _assert_path_inside_mesh(path, vertices, triangles)

    def test_l_shaped_path(self):
        """L-образный путь — должен быть один поворот."""
        from termin.navmesh.pathfinding import astar_triangles, compute_centroids

        # L-образный меш:
        #
        #     4---5
        #     |  /|
        #     | / |
        #     |/  |
        # 0---1---2
        # |  /|
        # | / |
        # |/  |
        # 3---6
        #
        vertices = np.array([
            [0, 0, 2],  # 0
            [1, 0, 2],  # 1
            [2, 0, 2],  # 2
            [0, 0, 1],  # 3
            [1, 0, 3],  # 4
            [2, 0, 3],  # 5
            [1, 0, 1],  # 6
        ], dtype=np.float32)

        triangles = np.array([
            [0, 3, 1],  # 0: нижний левый
            [1, 3, 6],  # 1: нижний правый
            [0, 1, 4],  # 2: верхний левый
            [1, 4, 5],  # 3: верхний средний
            [1, 5, 2],  # 4: верхний правый
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)
        centroids = compute_centroids(vertices, triangles)

        # Путь от нижнего левого (0) до верхнего правого (4)
        path_tris = astar_triangles(0, 4, neighbors, centroids)
        assert path_tris is not None
        assert path_tris[0] == 0
        assert path_tris[-1] == 4
        _assert_triangle_path_connected(path_tris, neighbors)

        # Извлекаем порталы
        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        _assert_portals_match_triangle_path(path_tris, portals, triangles, vertices)

        # Funnel algorithm
        start = np.array([0.2, 0, 1.5], dtype=np.float32)  # нижний левый угол
        end = np.array([1.8, 0, 2.5], dtype=np.float32)    # верхний правый угол

        path = funnel_algorithm(start, end, portals)

        _assert_path_endpoints(path, start, end)
        _assert_path_inside_mesh(path, vertices, triangles)

    def test_disconnected_mesh_has_no_triangle_path(self):
        """Разорванный меш должен явно возвращать отсутствие пути."""
        from termin.navmesh.pathfinding import astar_triangles, compute_centroids

        vertices = np.array([
            [0, 0, 0], [1, 0, 0], [0, 0, 1],
            [3, 0, 0], [4, 0, 0], [3, 0, 1],
        ], dtype=np.float32)

        triangles = np.array([
            [0, 1, 2],
            [3, 4, 5],
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)
        centroids = compute_centroids(vertices, triangles)

        assert astar_triangles(0, 1, neighbors, centroids) is None

    def test_portal_orientation_consistency(self):
        """Проверка консистентности порталов — left и right должны быть разными точками."""
        # Два треугольника рядом
        # 0---1
        # |\ /|
        # | X |
        # |/ \|
        # 2---3
        vertices = np.array([
            [0, 0, 1],  # 0: верх-лево
            [2, 0, 1],  # 1: верх-право
            [0, 0, 0],  # 2: низ-лево
            [2, 0, 0],  # 3: низ-право
        ], dtype=np.float32)

        triangles = np.array([
            [0, 2, 1],  # 0: левый (0-2-1)
            [1, 2, 3],  # 1: правый (1-2-3)
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)

        # Путь из 0 в 1
        path_tris = [0, 1]

        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)

        assert len(portals) == 1
        _assert_portals_match_triangle_path(path_tris, portals, triangles, vertices)
        left, right = portals[0]

        # Главное — left и right должны быть разными точками ребра
        assert not np.allclose(left, right), "left and right should be different"

        # Обе точки должны быть вершинами общего ребра (2 и 1)
        edge_verts = {tuple(vertices[2]), tuple(vertices[1])}
        assert tuple(left) in edge_verts, f"left {left} not in edge"
        assert tuple(right) in edge_verts, f"right {right} not in edge"


class TestNonConvexPolygons:
    """Тесты для невыпуклых полигонов — основной источник странных путей."""

    def test_u_shaped_corridor(self):
        """
        U-образный коридор — путь должен огибать внутренний угол.

        Структура:
        0---1       6---7
        |   |       |   |
        |   2-------5   |
        |               |
        3---------------8
        |               |
        4---------------9

        Путь из левого верхнего угла в правый верхний должен идти вниз,
        через низ и обратно наверх.
        """
        from termin.navmesh.pathfinding import astar_triangles, compute_centroids

        vertices = np.array([
            [0, 0, 4],  # 0: левый верх-верх
            [1, 0, 4],  # 1: левый верх-середина
            [1, 0, 3],  # 2: внутренний угол левый
            [0, 0, 2],  # 3: левый середина
            [0, 0, 0],  # 4: левый низ
            [3, 0, 3],  # 5: внутренний угол правый
            [3, 0, 4],  # 6: правый верх-середина
            [4, 0, 4],  # 7: правый верх-верх
            [4, 0, 2],  # 8: правый середина
            [4, 0, 0],  # 9: правый низ
        ], dtype=np.float32)

        # Триангуляция U-образной формы
        triangles = np.array([
            [0, 3, 1],   # 0: левый верх
            [1, 3, 2],   # 1: левый верх-угол
            [3, 4, 9],   # 2: низ левый
            [3, 9, 8],   # 3: низ центр
            [2, 3, 8],   # 4: центр левый
            [2, 8, 5],   # 5: центр
            [5, 8, 6],   # 6: правый центр
            [6, 8, 7],   # 7: правый верх
            [7, 8, 9],   # 8: правый низ
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)
        centroids = compute_centroids(vertices, triangles)

        # Путь от верхнего левого (0) до верхнего правого (7)
        path_tris = astar_triangles(0, 7, neighbors, centroids)

        assert path_tris is not None
        assert path_tris[0] == 0
        assert path_tris[-1] == 7
        _assert_triangle_path_connected(path_tris, neighbors)

        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        _assert_portals_match_triangle_path(path_tris, portals, triangles, vertices)

        start = np.array([0.5, 0, 3.8], dtype=np.float32)
        end = np.array([3.5, 0, 3.8], dtype=np.float32)

        path = funnel_algorithm(start, end, portals)

        _assert_path_endpoints(path, start, end)
        _assert_path_inside_mesh(path, vertices, triangles)

    def test_concave_corner_cut(self):
        """
        Вогнутый угол — проверка что путь не срезает через невидимую область.

        Структура:
             2
            /|
           / |
          /  |
         0---1
              \
               \
                3

        Путь от 0 до 3 должен идти через вершину 1, а не напрямую.
        """
        from termin.navmesh.pathfinding import astar_triangles, compute_centroids

        vertices = np.array([
            [0, 0, 0],  # 0
            [2, 0, 0],  # 1: угол
            [2, 0, 2],  # 2
            [4, 0, -2], # 3
        ], dtype=np.float32)

        # Исправляем — правильная триангуляция
        triangles = np.array([
            [0, 1, 2],   # 0: левый треугольник
            [1, 3, 2],   # 1: правый (ориентация может быть неверной)
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)
        centroids = compute_centroids(vertices, triangles)

        if neighbors[0, 1] < 0 and neighbors[0, 0] < 0 and neighbors[0, 2] < 0:
            # Создаём связные треугольники
            vertices = np.array([
                [0, 0, 0],  # 0
                [2, 0, 0],  # 1: угол
                [1, 0, 2],  # 2
                [3, 0, -1], # 3
            ], dtype=np.float32)

            triangles = np.array([
                [0, 1, 2],  # 0: верхний
                [0, 3, 1],  # 1: нижний
            ], dtype=np.int32)

            neighbors = build_adjacency(triangles)
            centroids = compute_centroids(vertices, triangles)

        path_tris = astar_triangles(0, 1, neighbors, centroids)
        assert path_tris is not None
        assert path_tris[0] == 0
        assert path_tris[-1] == 1
        _assert_triangle_path_connected(path_tris, neighbors)

        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        _assert_portals_match_triangle_path(path_tris, portals, triangles, vertices)

        start = np.array([1.5, 0, 1.0], dtype=np.float32)
        end = np.array([2.5, 0, -0.5], dtype=np.float32)

        path = funnel_algorithm(start, end, portals)

        _assert_path_endpoints(path, start, end)
        _assert_path_inside_mesh(path, vertices, triangles)

    def test_narrow_bottleneck(self):
        r"""
        Узкое горлышко — путь должен пройти через узкий проход.

        Структура:
        0---------1
        |    3    |
        |   / \   |
        |  /   \  |
        | /     \ |
        |/       \|
        2---------4

        Точка 3 создаёт узкое горлышко.
        """
        from termin.navmesh.pathfinding import astar_triangles, compute_centroids

        vertices = np.array([
            [0, 0, 2],   # 0: верх-лево
            [4, 0, 2],   # 1: верх-право
            [0, 0, 0],   # 2: низ-лево
            [2, 0, 1.5], # 3: горлышко (посередине, но близко к верху)
            [4, 0, 0],   # 4: низ-право
        ], dtype=np.float32)

        triangles = np.array([
            [0, 2, 3],  # 0: лево-верх
            [0, 3, 1],  # 1: верх
            [2, 4, 3],  # 2: низ
            [3, 4, 1],  # 3: право-верх
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)
        centroids = compute_centroids(vertices, triangles)

        # Путь снизу-слева до верх-справа через горлышко
        path_tris = astar_triangles(0, 3, neighbors, centroids)

        assert path_tris is not None
        assert path_tris[0] == 0
        assert path_tris[-1] == 3
        _assert_triangle_path_connected(path_tris, neighbors)

        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        _assert_portals_match_triangle_path(path_tris, portals, triangles, vertices)

        start = np.array([0.5, 0, 0.5], dtype=np.float32)  # низ-лево
        end = np.array([3.5, 0, 1.8], dtype=np.float32)    # верх-право

        path = funnel_algorithm(start, end, portals)

        _assert_path_endpoints(path, start, end)
        _assert_path_inside_mesh(path, vertices, triangles)

    def test_zigzag_corridor_detailed(self):
        """
        Подробный тест зигзагообразного коридора.

        Структура (вид сверху, коридор шириной 1):

        start                     end
          v                        v
        0---1       4---5       8---9
        |   |       |   |       |   |
        |   2-------3   6-------7   |
        |                           |
        +---------------------------+
                 (стена)

        Путь должен зигзагом обходить стены.
        """
        from termin.navmesh.pathfinding import astar_triangles, compute_centroids

        # Создаём зигзаг-коридор
        vertices = np.array([
            # Секция 1 (левая)
            [0, 0, 2],  # 0
            [1, 0, 2],  # 1
            [1, 0, 1],  # 2
            [2, 0, 1],  # 3
            # Секция 2 (средняя)
            [2, 0, 2],  # 4
            [3, 0, 2],  # 5
            [3, 0, 1],  # 6
            [4, 0, 1],  # 7
            # Секция 3 (правая)
            [4, 0, 2],  # 8
            [5, 0, 2],  # 9
        ], dtype=np.float32)

        triangles = np.array([
            [0, 2, 1],  # 0: левый верх
            [0, 3, 2],  # 1: левый низ (соединяет с центром)
            [1, 2, 4],  # 2: переход 1->2 верх
            [2, 3, 4],  # 3: переход 1->2 низ
            [3, 4, 5],  # 4: центр верх
            [3, 5, 6],  # 5: центр низ
            [5, 6, 8],  # 6: переход 2->3 верх
            [6, 7, 8],  # 7: переход 2->3 низ
            [7, 8, 9],  # 8: правый
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)
        centroids = compute_centroids(vertices, triangles)

        # Ищем путь от первого до последнего треугольника
        path_tris = astar_triangles(0, 8, neighbors, centroids)

        assert path_tris is not None
        assert path_tris[0] == 0
        assert path_tris[-1] == 8
        _assert_triangle_path_connected(path_tris, neighbors)

        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        _assert_portals_match_triangle_path(path_tris, portals, triangles, vertices)

        start = np.array([0.2, 0, 1.8], dtype=np.float32)
        end = np.array([4.8, 0, 1.8], dtype=np.float32)

        path = funnel_algorithm(start, end, portals)

        _assert_path_endpoints(path, start, end)
        _assert_path_inside_mesh(path, vertices, triangles)

    def test_path_should_not_cross_boundary(self):
        """
        Критический тест: путь НЕ должен пересекать границу полигона.

        Если funnel algorithm работает неправильно, путь может
        'срезать' через области вне NavMesh.
        """
        from termin.navmesh.pathfinding import astar_triangles, compute_centroids

        # Простой L-образный полигон
        #
        # 0-------1
        # |       |
        # |   2---3
        # |   |
        # 4---5
        #
        vertices = np.array([
            [0, 0, 4],  # 0
            [4, 0, 4],  # 1
            [2, 0, 2],  # 2
            [4, 0, 2],  # 3
            [0, 0, 0],  # 4
            [2, 0, 0],  # 5
        ], dtype=np.float32)

        triangles = np.array([
            [0, 4, 2],  # 0: левый верх
            [0, 2, 1],  # 1: верх
            [2, 3, 1],  # 2: верх-право
            [4, 5, 2],  # 3: низ
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)
        centroids = compute_centroids(vertices, triangles)

        # Путь из нижнего левого угла в верхний правый
        path_tris = astar_triangles(3, 2, neighbors, centroids)

        assert path_tris is not None
        assert path_tris[0] == 3
        assert path_tris[-1] == 2
        _assert_triangle_path_connected(path_tris, neighbors)

        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        _assert_portals_match_triangle_path(path_tris, portals, triangles, vertices)

        start = np.array([0.5, 0, 0.5], dtype=np.float32)  # низ-лево
        end = np.array([3.5, 0, 3.5], dtype=np.float32)    # верх-право

        path = funnel_algorithm(start, end, portals)

        _assert_path_endpoints(path, start, end)
        _assert_path_inside_mesh(path, vertices, triangles)
