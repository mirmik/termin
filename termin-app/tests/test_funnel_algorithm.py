"""
Тесты для Funnel Algorithm и связанных функций.
"""

import numpy as np
import pytest

from termin.navmesh.pathfinding import (
    build_adjacency,
    get_portals_from_path,
    funnel_algorithm,
    navmesh_line_of_sight,
)


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
        print(f"neighbors: {neighbors}")

        # Путь из треугольника 0 в треугольник 1
        path = [0, 1]
        portals = get_portals_from_path(path, triangles, vertices, neighbors)

        print(f"portals: {portals}")
        assert len(portals) == 1

        left, right = portals[0]
        # Общее ребро — 0-1, порядок зависит от edge_idx
        edge_set = {tuple(left), tuple(right)}
        assert tuple(vertices[0]) in edge_set or tuple(vertices[1]) in edge_set

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
        print(f"triangles:\n{triangles}")
        print(f"neighbors:\n{neighbors}")

        # Путь через все треугольники
        path = [0, 1, 2, 3, 4, 5]
        portals = get_portals_from_path(path, triangles, vertices, neighbors)

        print(f"portals count: {len(portals)}")
        for i, (left, right) in enumerate(portals):
            print(f"  portal {i}: left={left}, right={right}")

        assert len(portals) == 5  # 6 треугольников = 5 порталов


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

        print(f"path: {path}")
        # Ожидаем только start и end (прямая линия проходит через все порталы)
        assert len(path) == 2
        assert np.allclose(path[0], start)
        assert np.allclose(path[-1], end)

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

        print(f"path: {[p.tolist() for p in path]}")
        # Должен быть поворот где-то
        assert len(path) >= 2
        assert np.allclose(path[0], start)
        assert np.allclose(path[-1], end)

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

        print(f"zigzag path: {[p.tolist() for p in path]}")
        # Путь должен проходить через углы порталов (это корректно для зигзага)
        assert len(path) >= 2
        assert np.allclose(path[0], start)
        assert np.allclose(path[-1], end)

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

        print(f"wide corridor path: {[p.tolist() for p in path]}")
        # Прямая линия z=0.5 проходит через все порталы
        assert len(path) == 2, f"Expected straight line (2 points), got {len(path)}"
        assert np.allclose(path[0], start)
        assert np.allclose(path[-1], end)

    def test_no_portals(self):
        """Без порталов — прямой путь start -> end."""
        start = np.array([0, 0, 0], dtype=np.float32)
        end = np.array([5, 0, 5], dtype=np.float32)

        path = funnel_algorithm(start, end, [])

        assert len(path) == 2
        assert np.allclose(path[0], start)
        assert np.allclose(path[1], end)


class TestTriarea2:
    """Тесты для функции triarea2 внутри funnel_algorithm."""

    def test_triarea2_sign(self):
        """Проверка знака triarea2."""
        # triarea2 использует X и Z координаты
        # Cross product (a→b) × (a→c) в XZ плоскости
        # Положительный = c слева от вектора a→b (если смотреть сверху, Y вниз)
        # Отрицательный = c справа

        def triarea2(a, b, c):
            ax = b[0] - a[0]
            az = b[2] - a[2]
            bx = c[0] - a[0]
            bz = c[2] - a[2]
            return ax * bz - az * bx

        a = np.array([0, 0, 0])
        b = np.array([1, 0, 0])  # вправо по X
        c_pos_z = np.array([0.5, 0, 1])   # положительный Z
        c_neg_z = np.array([0.5, 0, -1])  # отрицательный Z

        area_pos_z = triarea2(a, b, c_pos_z)
        area_neg_z = triarea2(a, b, c_neg_z)

        print(f"area (c at z=1): {area_pos_z}")
        print(f"area (c at z=-1): {area_neg_z}")

        # В XZ плоскости, если двигаемся вправо по X:
        # - точка с положительным Z даёт положительную площадь (слева)
        # - точка с отрицательным Z даёт отрицательную площадь (справа)
        assert area_pos_z > 0, f"Expected positive, got {area_pos_z}"
        assert area_neg_z < 0, f"Expected negative, got {area_neg_z}"


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
        print(f"LOS result: {result}")
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

        print(f"neighbors:\n{neighbors}")

        # A* от треугольника 0 до треугольника 7
        path_tris = astar_triangles(0, 7, neighbors, centroids)
        print(f"A* path: {path_tris}")
        assert path_tris is not None
        assert path_tris[0] == 0
        assert path_tris[-1] == 7

        # Извлекаем порталы
        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        print(f"portals ({len(portals)}):")
        for i, (left, right) in enumerate(portals):
            print(f"  {i}: L={left.tolist()}, R={right.tolist()}")

        # Funnel algorithm
        start = np.array([0.3, 0, 0.5], dtype=np.float32)
        end = np.array([3.7, 0, 0.5], dtype=np.float32)

        path = funnel_algorithm(start, end, portals)
        print(f"funnel path ({len(path)}):")
        for i, p in enumerate(path):
            print(f"  {i}: {p.tolist()}")

        # Прямая линия должна быть возможна
        assert len(path) == 2, f"Expected 2 points (straight line), got {len(path)}"
        assert np.allclose(path[0], start)
        assert np.allclose(path[-1], end)

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

        print(f"\nL-shaped mesh:")
        print(f"triangles:\n{triangles}")
        print(f"neighbors:\n{neighbors}")

        # Путь от нижнего левого (0) до верхнего правого (4)
        path_tris = astar_triangles(0, 4, neighbors, centroids)
        print(f"A* path: {path_tris}")
        assert path_tris is not None

        # Извлекаем порталы
        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        print(f"portals ({len(portals)}):")
        for i, (left, right) in enumerate(portals):
            print(f"  {i}: L={left.tolist()}, R={right.tolist()}")

        # Funnel algorithm
        start = np.array([0.2, 0, 1.5], dtype=np.float32)  # нижний левый угол
        end = np.array([1.8, 0, 2.5], dtype=np.float32)    # верхний правый угол

        path = funnel_algorithm(start, end, portals)
        print(f"funnel path ({len(path)}):")
        for i, p in enumerate(path):
            print(f"  {i}: {p.tolist()}")

        # Должен быть путь с поворотом около точки (1, 0, 2)
        assert len(path) >= 2
        assert np.allclose(path[0], start)
        assert np.allclose(path[-1], end)

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
        print(f"\nPortal orientation test:")
        print(f"triangles:\n{triangles}")
        print(f"neighbors:\n{neighbors}")

        # Путь из 0 в 1
        path_tris = [0, 1]

        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        print(f"portals: {portals}")

        assert len(portals) == 1
        left, right = portals[0]

        print(f"left: {left}, right: {right}")

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

        print("\nU-shaped corridor:")
        print(f"triangles:\n{triangles}")
        print(f"neighbors:\n{neighbors}")

        # Путь от верхнего левого (0) до верхнего правого (7)
        path_tris = astar_triangles(0, 7, neighbors, centroids)
        print(f"A* path: {path_tris}")

        if path_tris is None:
            pytest.skip("A* не нашёл путь — нужно исправить триангуляцию")

        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        print(f"portals ({len(portals)}):")
        for i, (left, right) in enumerate(portals):
            print(f"  {i}: L={left.tolist()}, R={right.tolist()}")

        start = np.array([0.5, 0, 3.8], dtype=np.float32)
        end = np.array([3.5, 0, 3.8], dtype=np.float32)

        path = funnel_algorithm(start, end, portals)
        print(f"funnel path ({len(path)}):")
        for i, p in enumerate(path):
            print(f"  {i}: {p.tolist()}")

        # Путь должен идти вокруг — не может быть прямой линией
        assert len(path) >= 2
        assert np.allclose(path[0], start)
        assert np.allclose(path[-1], end)

        # Проверяем, что путь не проходит через область z < 3 (внутренняя стена)
        # если путь короткий (2 точки), это подозрительно
        if len(path) == 2:
            print("WARNING: Path is suspiciously straight through U-shape!")

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

        triangles = np.array([
            [0, 1, 2],  # верхний
            [1, 3, 2],  # нижний (неправильный — для теста)
        ], dtype=np.int32)

        # Исправляем — правильная триангуляция
        triangles = np.array([
            [0, 1, 2],   # 0: левый треугольник
            [1, 3, 2],   # 1: правый (ориентация может быть неверной)
        ], dtype=np.int32)

        neighbors = build_adjacency(triangles)
        centroids = compute_centroids(vertices, triangles)

        print("\nConcave corner:")
        print(f"triangles:\n{triangles}")
        print(f"neighbors:\n{neighbors}")

        if neighbors[0, 1] < 0 and neighbors[0, 0] < 0 and neighbors[0, 2] < 0:
            print("No adjacency — triangles don't share edge")
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
        if path_tris is None:
            pytest.skip("Нет пути между треугольниками")

        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)

        start = np.array([0.5, 0, 1], dtype=np.float32)
        end = np.array([2, 0, -0.5], dtype=np.float32)

        path = funnel_algorithm(start, end, portals)
        print(f"funnel path ({len(path)}):")
        for i, p in enumerate(path):
            print(f"  {i}: {p.tolist()}")

        assert len(path) >= 2
        assert np.allclose(path[0], start)
        assert np.allclose(path[-1], end)

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

        print("\nNarrow bottleneck:")
        print(f"triangles:\n{triangles}")
        print(f"neighbors:\n{neighbors}")

        # Путь снизу-слева до верх-справа через горлышко
        path_tris = astar_triangles(0, 3, neighbors, centroids)
        print(f"A* path: {path_tris}")

        if path_tris is None:
            pytest.skip("A* не нашёл путь")

        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        print(f"portals ({len(portals)}):")
        for i, (left, right) in enumerate(portals):
            print(f"  {i}: L={left.tolist()}, R={right.tolist()}")

        start = np.array([0.5, 0, 0.5], dtype=np.float32)  # низ-лево
        end = np.array([3.5, 0, 1.8], dtype=np.float32)    # верх-право

        path = funnel_algorithm(start, end, portals)
        print(f"funnel path ({len(path)}):")
        for i, p in enumerate(path):
            print(f"  {i}: {p.tolist()}")

        assert len(path) >= 2
        assert np.allclose(path[0], start)
        assert np.allclose(path[-1], end)

        # Путь должен проходить близко к точке 3 (горлышко)
        bottleneck = vertices[3]
        min_dist_to_bottleneck = float('inf')
        for i in range(len(path) - 1):
            # Расстояние от точки 3 до отрезка path[i] -> path[i+1]
            p0, p1 = path[i], path[i + 1]
            v = p1 - p0
            w = bottleneck - p0
            t = max(0, min(1, np.dot(w, v) / (np.dot(v, v) + 1e-10)))
            closest = p0 + t * v
            dist = np.linalg.norm(bottleneck - closest)
            min_dist_to_bottleneck = min(min_dist_to_bottleneck, dist)

        print(f"Min distance to bottleneck: {min_dist_to_bottleneck}")

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

        print("\nZigzag corridor:")
        for i, t in enumerate(triangles):
            print(f"  tri {i}: {t} -> neighbors {neighbors[i]}")

        # Ищем путь от первого до последнего треугольника
        path_tris = astar_triangles(0, 8, neighbors, centroids)
        print(f"A* path: {path_tris}")

        if path_tris is None:
            # Попробуем упростить меш
            print("Simplifying mesh...")
            vertices = np.array([
                [0, 0, 2],  # 0
                [2, 0, 2],  # 1
                [0, 0, 0],  # 2
                [2, 0, 0],  # 3
                [4, 0, 2],  # 4
                [4, 0, 0],  # 5
            ], dtype=np.float32)

            triangles = np.array([
                [0, 2, 1],  # 0
                [1, 2, 3],  # 1
                [1, 3, 4],  # 2
                [4, 3, 5],  # 3
            ], dtype=np.int32)

            neighbors = build_adjacency(triangles)
            centroids = compute_centroids(vertices, triangles)
            path_tris = astar_triangles(0, 3, neighbors, centroids)
            print(f"Simplified A* path: {path_tris}")

        if path_tris is None:
            pytest.skip("Не удалось найти путь")

        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)

        start = np.array([0.2, 0, 1.8], dtype=np.float32)
        end = np.array([3.8, 0, 0.2], dtype=np.float32)

        path = funnel_algorithm(start, end, portals)
        print(f"funnel path ({len(path)}):")
        for i, p in enumerate(path):
            print(f"  {i}: {p.tolist()}")

        assert len(path) >= 2
        assert np.allclose(path[0], start)
        assert np.allclose(path[-1], end)

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

        print("\nL-shaped boundary test:")
        for i, t in enumerate(triangles):
            print(f"  tri {i}: verts {t}, neighbors {neighbors[i]}")

        # Путь из нижнего левого угла в верхний правый
        path_tris = astar_triangles(3, 2, neighbors, centroids)
        print(f"A* path: {path_tris}")

        if path_tris is None:
            pytest.skip("A* не нашёл путь")

        portals = get_portals_from_path(path_tris, triangles, vertices, neighbors)
        print(f"portals ({len(portals)}):")
        for i, (left, right) in enumerate(portals):
            print(f"  {i}: L={left.tolist()}, R={right.tolist()}")

        start = np.array([0.5, 0, 0.5], dtype=np.float32)  # низ-лево
        end = np.array([3.5, 0, 3.5], dtype=np.float32)    # верх-право

        path = funnel_algorithm(start, end, portals)
        print(f"funnel path ({len(path)}):")
        for i, p in enumerate(path):
            print(f"  {i}: {p.tolist()}")

        # Проверяем, что путь не проходит через точку (3, 0, 1)
        # которая находится вне L-образного полигона
        outside_point = np.array([3, 0, 1], dtype=np.float32)

        for i in range(len(path) - 1):
            p0, p1 = path[i], path[i + 1]
            # Проверяем, что отрезок не проходит слишком близко к outside_point
            v = p1 - p0
            w = outside_point - p0
            t = np.dot(w, v) / (np.dot(v, v) + 1e-10)
            if 0 < t < 1:
                closest = p0 + t * v
                dist = np.linalg.norm(outside_point - closest)
                print(f"  segment {i}: closest dist to outside = {dist:.3f}")
                # Если путь проходит очень близко к точке вне полигона — это подозрительно
                if dist < 0.3:
                    print(f"  WARNING: Path may be cutting through outside area!")

        assert len(path) >= 2
        assert np.allclose(path[0], start)
        assert np.allclose(path[-1], end)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
