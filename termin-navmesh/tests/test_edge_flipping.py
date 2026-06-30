"""
Тесты для edge flipping (Delaunay optimization).
"""

import numpy as np

from termin.navmesh.triangulation import (
    ear_clipping,
    ear_clipping_refined,
    refine_triangulation,
    delaunay_flip,
    extract_boundary_edges,
    in_circumcircle,
)


def _triangle_area(vertices, triangle):
    a, b, c = vertices[list(triangle)]
    cross = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    return abs(float(cross)) * 0.5


def _polygon_area(vertices):
    shifted = np.roll(vertices, -1, axis=0)
    cross = vertices[:, 0] * shifted[:, 1] - shifted[:, 0] * vertices[:, 1]
    return abs(float(np.sum(cross))) * 0.5


def _edge_counts(triangles):
    counts = {}
    for tri in triangles:
        for i in range(3):
            edge = tuple(sorted((int(tri[i]), int(tri[(i + 1) % 3]))))
            counts[edge] = counts.get(edge, 0) + 1
    return counts


def _assert_triangle_indices_valid(vertices, triangles):
    assert np.asarray(triangles).ndim == 2
    assert np.asarray(triangles).shape[1] == 3
    assert np.min(triangles) >= 0
    assert np.max(triangles) < len(vertices)


def _assert_non_degenerate(vertices, triangles):
    for tri in triangles:
        assert _triangle_area(vertices, tri) > 1e-6, f"Degenerate triangle: {tri}"


def _assert_manifold_edges(triangles):
    for edge, count in _edge_counts(triangles).items():
        assert count <= 2, f"Non-manifold edge {edge}: used {count} times"


def _assert_boundary_edges(triangles, expected_boundary):
    boundary = {edge for edge, count in _edge_counts(triangles).items() if count == 1}
    assert boundary == expected_boundary


def _assert_triangulates_polygon(vertices, triangles):
    _assert_triangle_indices_valid(vertices, triangles)
    _assert_non_degenerate(vertices, triangles)
    _assert_manifold_edges(triangles)
    assert len(triangles) == len(vertices) - 2
    assert np.isclose(
        sum(_triangle_area(vertices, tri) for tri in triangles),
        _polygon_area(vertices),
        atol=1e-5,
    )
    _assert_boundary_edges(triangles, extract_boundary_edges(len(vertices)))


def _assert_refinement_preserves_mesh(
    original_vertices,
    original_triangles,
    new_vertices,
    new_triangles,
):
    _assert_triangle_indices_valid(new_vertices, new_triangles)
    _assert_non_degenerate(new_vertices, new_triangles)
    _assert_manifold_edges(new_triangles)
    assert np.allclose(new_vertices[:len(original_vertices)], original_vertices)
    assert np.isclose(
        sum(_triangle_area(new_vertices, tri) for tri in new_triangles),
        sum(_triangle_area(original_vertices, tri) for tri in original_triangles),
        atol=1e-4,
    )


def _assert_all_edges_within(vertices, triangles, max_edge_length):
    for tri in triangles:
        for i in range(3):
            v0 = vertices[tri[i]]
            v1 = vertices[tri[(i + 1) % 3]]
            length = np.linalg.norm(v1 - v0)
            assert length <= max_edge_length + 0.01, f"Edge too long: {length}"


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

class TestDelaunayFlip:
    """Тесты для delaunay_flip."""

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

        _assert_triangulates_polygon(vertices, result)

    def test_pentagon(self):
        """Пятиугольник."""
        # Правильный пятиугольник
        angles = np.linspace(0, 2 * np.pi, 6)[:-1]
        vertices = np.column_stack([np.cos(angles), np.sin(angles)]).astype(np.float32)

        result = ear_clipping(vertices, optimize=True)

        _assert_triangulates_polygon(vertices, result)

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

        _assert_triangulates_polygon(vertices, result_optimized)
        _assert_triangulates_polygon(vertices, result_basic)

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
        _assert_refinement_preserves_mesh(vertices, triangles, new_verts, new_tris)

    def test_single_split(self):
        """Один большой треугольник — разбивается."""
        vertices = np.array([
            [0, 0],
            [10, 0],
            [5, 5],
        ], dtype=np.float32)

        triangles = [(0, 1, 2)]

        new_verts, new_tris = refine_triangulation(vertices, triangles, max_edge_length=5.0)

        assert len(new_tris) > 1
        assert len(new_verts) > 3
        _assert_refinement_preserves_mesh(vertices, triangles, new_verts, new_tris)
        _assert_all_edges_within(new_verts, new_tris, max_edge_length=5.0)

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

        # Длинные рёбра (10 единиц) должны быть разбиты
        assert len(new_tris) > 2

        _assert_refinement_preserves_mesh(vertices, triangles, new_verts, new_tris)
        _assert_all_edges_within(new_verts, new_tris, max_edge_length=2.0)


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

        assert len(triangles) > 2
        _assert_refinement_preserves_mesh(
            vertices,
            ear_clipping(vertices, optimize=True),
            new_verts,
            triangles,
        )
        _assert_all_edges_within(new_verts, triangles, max_edge_length=3.0)

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

        _assert_refinement_preserves_mesh(
            vertices,
            ear_clipping(vertices, optimize=True),
            new_verts,
            triangles,
        )
        _assert_all_edges_within(new_verts, triangles, max_edge_length=2.0)
