from termin.geomalgo.project import (
    project_point_on_aabb,
    project_segment_on_aabb,
    project_point_on_plane,
    project_point_on_line
)
import unittest
from termin.geombase import AABB
from termin.geomalgo.project import closest_of_aabb_and_capsule
import numpy as np
import numpy


class TestProjectPointOnAABB(unittest.TestCase):
    """Тесты для функции project_point_on_aabb"""
    
    def test_point_inside_aabb(self):
        """Точка внутри AABB должна проецироваться в саму себя"""
        point = [0.5, 0.5, 0.5]
        aabb_min = [0, 0, 0]
        aabb_max = [2, 2, 2]
        result = project_point_on_aabb(point, aabb_min, aabb_max)
        np.testing.assert_allclose(result, point)
    
    def test_point_outside_aabb(self):
        """Точка вне AABB должна проецироваться на угол"""
        point = [3, 3, 3]
        aabb_min = [0, 0, 0]
        aabb_max = [2, 2, 2]
        result = project_point_on_aabb(point, aabb_min, aabb_max)
        np.testing.assert_allclose(result, [2, 2, 2])
    
    def test_point_on_aabb_boundary(self):
        """Точка на границе AABB должна остаться на месте"""
        point = [2, 1, 1]
        aabb_min = [0, 0, 0]
        aabb_max = [2, 2, 2]
        result = project_point_on_aabb(point, aabb_min, aabb_max)
        np.testing.assert_allclose(result, point)
    
    def test_point_outside_one_dimension(self):
        """Точка вне только по одной координате"""
        point = [1, 1, 3]
        aabb_min = [0, 0, 0]
        aabb_max = [2, 2, 2]
        result = project_point_on_aabb(point, aabb_min, aabb_max)
        np.testing.assert_allclose(result, [1, 1, 2])


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
    
    def test_point_on_plane(self):
        """Точка на плоскости должна остаться на месте"""
        point = [1, 1, 0]
        plane_point = [0, 0, 0]
        plane_normal = [0, 0, 1]
        result = project_point_on_plane(point, plane_point, plane_normal)
        np.testing.assert_allclose(result, point)
    
    def test_point_above_plane(self):
        """Точка над плоскостью должна проецироваться вниз"""
        point = [1, 1, 5]
        plane_point = [0, 0, 0]
        plane_normal = [0, 0, 1]
        result = project_point_on_plane(point, plane_point, plane_normal)
        np.testing.assert_allclose(result, [1, 1, 0])
    
    def test_point_below_plane(self):
        """Точка под плоскостью должна проецироваться вверх"""
        point = [1, 1, -3]
        plane_point = [0, 0, 0]
        plane_normal = [0, 0, 1]
        result = project_point_on_plane(point, plane_point, plane_normal)
        np.testing.assert_allclose(result, [1, 1, 0])


class TestProjectPointOnLine(unittest.TestCase):
    """Тесты для функции project_point_on_line"""
    
    def test_point_on_line(self):
        """Точка на линии должна остаться на месте"""
        point = [2, 0, 0]
        line_point = [0, 0, 0]
        line_direction = [1, 0, 0]
        result = project_point_on_line(point, line_point, line_direction)
        np.testing.assert_allclose(result, point)
    
    def test_point_perpendicular_to_line(self):
        """Точка перпендикулярно линии"""
        point = [1, 5, 0]
        line_point = [0, 0, 0]
        line_direction = [1, 0, 0]
        result = project_point_on_line(point, line_point, line_direction)
        np.testing.assert_allclose(result, [1, 0, 0])
    
    def test_point_arbitrary_position(self):
        """Точка в произвольной позиции относительно линии"""
        point = [3, 4, 5]
        line_point = [0, 0, 0]
        line_direction = [1, 1, 1]
        result = project_point_on_line(point, line_point, line_direction)
        # Проекция точки [3,4,5] на линию через начало координат в направлении [1,1,1]
        # должна дать точку [4,4,4] (т.к. dot([3,4,5], [1,1,1])/|[1,1,1]|^2 = 12/3 = 4)
        expected = [4, 4, 4]
        np.testing.assert_allclose(result, expected)


class TestClosestOfAABBAndCapsule(unittest.TestCase):
    """Тесты для функции closest_of_aabb_and_capsule"""
    def test_closest_of_aabb_and_capsule(self):
        aabb = AABB(numpy.array([0.0, 0.0, 0.0]), numpy.array([1.0, 1.0, 1.0]))
        capsule_start = numpy.array([2.0, 0.5, 0.5])
        capsule_end = numpy.array([3.0, 0.5, 0.5])
        capsule_radius = 0.2

        closest_aabb_point, closest_capsule_point, distance = closest_of_aabb_and_capsule(
            aabb.min_point, aabb.max_point, capsule_start, capsule_end, capsule_radius
        )

        expected_closest_aabb_point = numpy.array([1.0, 0.5, 0.5])
        expected_closest_capsule_point = numpy.array([1.8, 0.5, 0.5])
        expected_distance = 0.8

        numpy.testing.assert_array_almost_equal(closest_aabb_point, expected_closest_aabb_point)
        numpy.testing.assert_array_almost_equal(closest_capsule_point, expected_closest_capsule_point)
        self.assertAlmostEqual(distance, expected_distance)

    def test_project_point_on_aabb(self):
        aabb = AABB(numpy.array([-1.0, -0.5, -0.25]), numpy.array([1.0, 0.5, 0.25]))
        point = numpy.array([3.0, 0.0, 0.0])
        projected_point = project_point_on_aabb(point, aabb.min_point, aabb.max_point)
        expected_point = numpy.array([1.0, 0.0, 0.0])
        numpy.testing.assert_array_almost_equal(projected_point, expected_point)