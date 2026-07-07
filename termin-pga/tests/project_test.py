from termin.geomalgo.project import (
    project_point_on_aabb,
    project_segment_on_aabb,
    project_point_on_plane,
    project_point_on_line
)
import unittest
from termin.geombase import AABB, Vec3
from termin.geomalgo.project import closest_of_aabb_and_capsule
import numpy as np


class TestProjectPointOnAABB(unittest.TestCase):
    """Тесты для функции project_point_on_aabb"""
    
    def test_point_projection_cases(self):
        """Точки внутри, на границе и вне AABB проецируются ожидаемо"""
        cases = [
            ("inside", [0.5, 0.5, 0.5], [0, 0, 0], [2, 2, 2], [0.5, 0.5, 0.5]),
            ("outside_corner", [3, 3, 3], [0, 0, 0], [2, 2, 2], [2, 2, 2]),
            ("boundary", [2, 1, 1], [0, 0, 0], [2, 2, 2], [2, 1, 1]),
            ("outside_one_axis", [1, 1, 3], [0, 0, 0], [2, 2, 2], [1, 1, 2]),
            ("asymmetric_bounds", [3, 0, 0], [-1, -0.5, -0.25], [1, 0.5, 0.25], [1, 0, 0]),
        ]

        for name, point, aabb_min, aabb_max, expected in cases:
            with self.subTest(name=name):
                result = project_point_on_aabb(point, aabb_min, aabb_max)
                np.testing.assert_allclose(result, expected)


class TestProjectSegmentOnAABB(unittest.TestCase):
    """Тесты для функции project_segment_on_aabb"""
    
    def test_segment_completely_inside_aabb(self):
        """Отрезок полностью внутри AABB - расстояние должно быть 0"""
        seg_start = [0.5, 0.5, 0.5]
        seg_end = [1.5, 1.5, 1.5]
        aabb_min = [0, 0, 0]
        aabb_max = [2, 2, 2]
        result = project_segment_on_aabb(seg_start, seg_end, aabb_min, aabb_max)
        self.assertAlmostEqual(result[2], 0.0, places=6)
        # Точки должны совпадать
        np.testing.assert_allclose(result[0], result[1])
    
    def test_segment_completely_outside_aabb(self):
        """Отрезок полностью вне AABB"""
        seg_start = [3, 3, 3]
        seg_end = [4, 4, 4]
        aabb_min = [0, 0, 0]
        aabb_max = [2, 2, 2]
        result = project_segment_on_aabb(seg_start, seg_end, aabb_min, aabb_max)
        expected_distance = np.sqrt(3)  # От [3,3,3] до [2,2,2]
        self.assertAlmostEqual(result[2], expected_distance, places=6)
    
    def test_segment_intersects_aabb(self):
        """Отрезок пересекает AABB - расстояние должно быть 0"""
        seg_start = [-1, 1, 1]
        seg_end = [3, 1, 1]
        aabb_min = [0, 0, 0]
        aabb_max = [2, 2, 2]
        result = project_segment_on_aabb(seg_start, seg_end, aabb_min, aabb_max)
        self.assertAlmostEqual(result[2], 0.0, places=6)
    
    def test_degenerate_point_inside_aabb(self):
        """Вырожденный случай: точка (отрезок нулевой длины) внутри AABB"""
        seg_start = [0.5, 0.5, 0.5]
        seg_end = [0.5, 0.5, 0.5]
        aabb_min = [0, 0, 0]
        aabb_max = [2, 2, 2]
        result = project_segment_on_aabb(seg_start, seg_end, aabb_min, aabb_max)
        self.assertAlmostEqual(result[2], 0.0, places=6)
        np.testing.assert_allclose(result[0], seg_start)
        np.testing.assert_allclose(result[1], seg_start)
    
    def test_degenerate_point_outside_aabb(self):
        """Вырожденный случай: точка вне AABB"""
        seg_start = [3, 3, 3]
        seg_end = [3, 3, 3]
        aabb_min = [0, 0, 0]
        aabb_max = [2, 2, 2]
        result = project_segment_on_aabb(seg_start, seg_end, aabb_min, aabb_max)
        expected_distance = np.sqrt(3)
        self.assertAlmostEqual(result[2], expected_distance, places=6)
    
    def test_segment_parallel_to_face_outside(self):
        """Отрезок параллелен грани AABB (снаружи)"""
        seg_start = [3, 0, 0]
        seg_end = [3, 2, 0]
        aabb_min = [0, 0, 0]
        aabb_max = [2, 2, 2]
        result = project_segment_on_aabb(seg_start, seg_end, aabb_min, aabb_max)
        self.assertAlmostEqual(result[2], 1.0, places=6)
    
    def test_segment_touches_corner(self):
        """Отрезок касается угла AABB"""
        seg_start = [0, 0, -1]
        seg_end = [0, 0, 3]
        aabb_min = [0, 0, 0]
        aabb_max = [2, 2, 2]
        result = project_segment_on_aabb(seg_start, seg_end, aabb_min, aabb_max)
        self.assertAlmostEqual(result[2], 0.0, places=6)
    
    def test_segment_diagonal_through_aabb(self):
        """Отрезок проходит по диагонали через весь AABB"""
        seg_start = [-1, -1, -1]
        seg_end = [3, 3, 3]
        aabb_min = [0, 0, 0]
        aabb_max = [2, 2, 2]
        result = project_segment_on_aabb(seg_start, seg_end, aabb_min, aabb_max)
        self.assertAlmostEqual(result[2], 0.0, places=6)


class TestProjectPointOnPlane(unittest.TestCase):
    """Тесты для функции project_point_on_plane"""
    
    def test_point_projection_cases(self):
        """Точки на плоскости и по обе стороны от неё проецируются на плоскость"""
        cases = [
            ("on_plane", [1, 1, 0], [1, 1, 0]),
            ("above", [1, 1, 5], [1, 1, 0]),
            ("below", [1, 1, -3], [1, 1, 0]),
        ]

        for name, point, expected in cases:
            with self.subTest(name=name):
                result = project_point_on_plane(point, [0, 0, 0], [0, 0, 1])
                np.testing.assert_allclose(result, expected)


class TestProjectPointOnLine(unittest.TestCase):
    """Тесты для функции project_point_on_line"""
    
    def test_point_projection_cases(self):
        """Точки на осевой и произвольной линии проецируются ожидаемо"""
        cases = [
            ("on_axis_line", [2, 0, 0], [0, 0, 0], [1, 0, 0], [2, 0, 0]),
            ("perpendicular_to_axis", [1, 5, 0], [0, 0, 0], [1, 0, 0], [1, 0, 0]),
            ("arbitrary_direction", [3, 4, 5], [0, 0, 0], [1, 1, 1], [4, 4, 4]),
        ]

        for name, point, line_point, line_direction, expected in cases:
            with self.subTest(name=name):
                result = project_point_on_line(point, line_point, line_direction)
                np.testing.assert_allclose(result, expected)


class TestClosestOfAABBAndCapsule(unittest.TestCase):
    """Тесты для функции closest_of_aabb_and_capsule"""
    def test_closest_of_aabb_and_capsule(self):
        aabb = AABB(Vec3(0.0, 0.0, 0.0), Vec3(1.0, 1.0, 1.0))
        capsule_start = np.array([2.0, 0.5, 0.5])
        capsule_end = np.array([3.0, 0.5, 0.5])
        capsule_radius = 0.2

        closest_aabb_point, closest_capsule_point, distance = closest_of_aabb_and_capsule(
            aabb.min_point, aabb.max_point, capsule_start, capsule_end, capsule_radius
        )

        expected_closest_aabb_point = np.array([1.0, 0.5, 0.5])
        expected_closest_capsule_point = np.array([1.8, 0.5, 0.5])
        expected_distance = 0.8

        np.testing.assert_array_almost_equal(closest_aabb_point, expected_closest_aabb_point)
        np.testing.assert_array_almost_equal(closest_capsule_point, expected_closest_capsule_point)
        self.assertAlmostEqual(distance, expected_distance)
