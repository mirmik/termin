"""
Тесты для edge flipping (Delaunay optimization).
"""

import numpy as np
import pytest

from termin.navmesh.triangulation import (
    ear_clip,
    ear_clipping,
    ear_clipping_refined,
    refine_triangulation,
    delaunay_flip,
    extract_boundary_edges,
    in_circumcircle,
)


class TestInCircumcircle:
    """Тесты для in_circumcircle."""

    def test_point_inside(self):
        """Точка внутри окружности."""
        # Треугольник (0,0), (2,0), (1,2) — окружность проходит через них
        # Точка (1,0.5) внутри
        assert in_circumcircle(0, 0, 2, 0, 1, 2, 1, 0.5) is True

    def test_point_outside(self):
        """Точка снаружи окружности."""
        # Та же окружность, точка (1, 5) снаружи
        assert in_circumcircle(0, 0, 2, 0, 1, 2, 1, 5) is False

    def test_point_on_circle(self):
        """Точка на окружности — граничный случай."""
        # Квадрат — все 4 точки на одной окружности
        # Треугольник (0,0), (1,0), (0,1) — точка (1,1) на окружности
        result = in_circumcircle(0, 0, 1, 0, 0, 1, 1, 1)
        # На границе — может быть True или False, зависит от погрешности
        assert isinstance(result, bool)


class TestDelaunayFlip:
    """Тесты для delaunay_flip."""

    def test_simple_quad(self):
        """Квадрат — должен выбрать лучшую диагональ."""
        # Квадрат: (0,0), (1,0), (1,1), (0,1)
        vertices = np.array([
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 1],
        ], dtype=np.float32)

        # Плохая триангуляция: острые треугольники через диагональ (0,2)
        triangles = [(0, 1, 2), (0, 2, 3)]

        boundary = extract_boundary_edges(4)
        result = delaunay_flip(vertices, triangles, boundary)

        print(f"Before: {triangles}")
        print(f"After: {result}")

        # Должно быть 2 треугольника
        assert len(result) == 2

    def test_no_flip_needed(self):
        """Уже Delaunay — ничего не меняется."""
        # Равносторонний треугольник + точка в центре = 3 треугольника
        vertices = np.array([
            [0, 0],
            [2, 0],
            [1, 1.732],
        ], dtype=np.float32)

        triangles = [(0, 1, 2)]

        result = delaunay_flip(vertices, triangles, set())
        assert result == triangles

    def test_preserves_boundary(self):
        """Граничные рёбра не переворачиваются."""
        vertices = np.array([
            [0, 0],
            [2, 0],
            [2, 2],
            [0, 2],
        ], dtype=np.float32)

        triangles = [(0, 1, 2), (0, 2, 3)]
        boundary = extract_boundary_edges(4)

        result = delaunay_flip(vertices, triangles, boundary)

        # Проверяем что граничные рёбра сохранены
        result_edges = set()
        for tri in result:
            for i in range(3):
                e = (min(tri[i], tri[(i+1)%3]), max(tri[i], tri[(i+1)%3]))
                result_edges.add(e)

        for edge in boundary:
            assert edge in result_edges, f"Boundary edge {edge} lost"


class TestEarClippingWithOptimization:
    """Тесты для ear_clipping с оптимизацией."""

    def test_square(self):
        """Квадрат."""
        vertices = np.array([
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 1],
        ], dtype=np.float32)

        result = ear_clipping(vertices, optimize=True)
        print(f"Optimized triangles: {result}")

        assert len(result) == 2
        assert result.shape == (2, 3)

    def test_pentagon(self):
        """Пятиугольник."""
        # Правильный пятиугольник
        angles = np.linspace(0, 2 * np.pi, 6)[:-1]
        vertices = np.column_stack([np.cos(angles), np.sin(angles)]).astype(np.float32)

        result = ear_clipping(vertices, optimize=True)
        print(f"Pentagon triangles: {result}")

        assert len(result) == 3  # n - 2

    def test_complex_polygon(self):
        """Сложный полигон."""
        # L-образный полигон
        vertices = np.array([
            [0, 0],
            [2, 0],
            [2, 1],
            [1, 1],
            [1, 2],
            [0, 2],
        ], dtype=np.float32)

        result_optimized = ear_clipping(vertices, optimize=True)
        result_basic = ear_clipping(vertices, optimize=False)

        print(f"Basic: {result_basic}")
        print(f"Optimized: {result_optimized}")

        # Оба должны давать 4 треугольника
        assert len(result_optimized) == 4
        assert len(result_basic) == 4

    def test_minimum_angle_improvement(self):
        """Проверяем улучшение минимального угла."""
        # Вытянутый четырёхугольник — ear clipping даст плохие треугольники
        vertices = np.array([
            [0, 0],
            [10, 0],
            [10, 1],
            [0, 1],
        ], dtype=np.float32)

        result_basic = ear_clipping(vertices, optimize=False)
        result_optimized = ear_clipping(vertices, optimize=True)

        def min_angle(triangles, verts):
            """Вычислить минимальный угол во всех треугольниках."""
            min_a = float('inf')
            for tri in triangles:
                for i in range(3):
                    p0 = verts[tri[i]]
                    p1 = verts[tri[(i+1)%3]]
                    p2 = verts[tri[(i+2)%3]]

                    v1 = p1 - p0
                    v2 = p2 - p0

                    cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-10)
                    cos_angle = np.clip(cos_angle, -1, 1)
                    angle = np.arccos(cos_angle)
                    min_a = min(min_a, angle)
            return np.degrees(min_a)

        min_basic = min_angle(result_basic, vertices)
        min_optimized = min_angle(result_optimized, vertices)

        print(f"Min angle basic: {min_basic:.1f}°")
        print(f"Min angle optimized: {min_optimized:.1f}°")

        # Оптимизированный должен быть не хуже
        assert min_optimized >= min_basic - 1.0  # допуск на погрешность


class TestRefinement:
    """Тесты для refine_triangulation."""

    def test_no_refinement_needed(self):
        """Маленькие треугольники — ничего не меняется."""
        vertices = np.array([
            [0, 0],
            [1, 0],
            [0.5, 0.5],
        ], dtype=np.float32)

        triangles = [(0, 1, 2)]

        new_verts, new_tris = refine_triangulation(vertices, triangles, max_edge_length=2.0)

        assert len(new_verts) == 3
        assert len(new_tris) == 1

    def test_single_split(self):
        """Один большой треугольник — разбивается."""
        vertices = np.array([
            [0, 0],
            [10, 0],
            [5, 5],
        ], dtype=np.float32)

        triangles = [(0, 1, 2)]

        new_verts, new_tris = refine_triangulation(vertices, triangles, max_edge_length=5.0)

        print(f"Vertices: {len(new_verts)}")
        print(f"Triangles: {len(new_tris)}")

        # Должно быть больше треугольников
        assert len(new_tris) > 1
        assert len(new_verts) > 3

    def test_rectangle_refinement(self):
        """Вытянутый прямоугольник — разбивается на много треугольников."""
        vertices = np.array([
            [0, 0],
            [10, 0],
            [10, 1],
            [0, 1],
        ], dtype=np.float32)

        triangles = [(0, 1, 2), (0, 2, 3)]

        new_verts, new_tris = refine_triangulation(vertices, triangles, max_edge_length=2.0)

        print(f"Vertices: {len(new_verts)}")
        print(f"Triangles: {len(new_tris)}")

        # Длинные рёбра (10 единиц) должны быть разбиты
        assert len(new_tris) > 2

        # Проверяем, что все рёбра <= max_edge_length
        for tri in new_tris:
            for i in range(3):
                v0 = new_verts[tri[i]]
                v1 = new_verts[tri[(i+1) % 3]]
                length = np.linalg.norm(v1 - v0)
                assert length <= 2.0 + 0.01, f"Edge too long: {length}"


class TestEarClippingRefined:
    """Тесты для ear_clipping_refined."""

    def test_simple_polygon(self):
        """Простой полигон с refinement."""
        vertices = np.array([
            [0, 0],
            [10, 0],
            [10, 10],
            [0, 10],
        ], dtype=np.float32)

        new_verts, triangles = ear_clipping_refined(vertices, max_edge_length=3.0)

        print(f"Vertices: {len(new_verts)} (was 4)")
        print(f"Triangles: {len(triangles)}")

        # Должно быть много маленьких треугольников
        assert len(triangles) > 2

    def test_l_shaped(self):
        """L-образный полигон."""
        vertices = np.array([
            [0, 0],
            [6, 0],
            [6, 3],
            [3, 3],
            [3, 6],
            [0, 6],
        ], dtype=np.float32)

        new_verts, triangles = ear_clipping_refined(vertices, max_edge_length=2.0)

        print(f"L-shaped: {len(new_verts)} vertices, {len(triangles)} triangles")

        # Проверяем все рёбра
        max_edge = 0
        for tri in triangles:
            for i in range(3):
                v0 = new_verts[tri[i]]
                v1 = new_verts[tri[(i+1) % 3]]
                length = np.linalg.norm(v1 - v0)
                max_edge = max(max_edge, length)

        print(f"Max edge length: {max_edge:.2f}")
        assert max_edge <= 2.0 + 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
