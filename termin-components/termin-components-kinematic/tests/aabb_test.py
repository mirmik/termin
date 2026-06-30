from termin.geombase import Pose3, AABB, TransformAABB
from termin.kinematic import Transform
import unittest
import numpy


def _pose_at(x: float, y: float = 0.0, z: float = 0.0) -> Pose3:
    return Pose3(
        ang=numpy.array([0.0, 0.0, 0.0, 1.0]),
        lin=numpy.array([x, y, z]),
    )


def _aabb(min_point, max_point) -> AABB:
    return AABB(numpy.array(min_point), numpy.array(max_point))


def _assert_aabb(testcase: unittest.TestCase, aabb: AABB, min_point, max_point):
    testcase.assertIsNotNone(aabb)
    numpy.testing.assert_array_equal(aabb.min_point, numpy.array(min_point))
    numpy.testing.assert_array_equal(aabb.max_point, numpy.array(max_point))


class AABBTest(unittest.TestCase):
    def test_aabb_creation(self):
        points = numpy.array([
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [-1.0, -2.0, -3.0]
        ])
        aabb = AABB.from_points(points)
        expected_min = numpy.array([-1.0, -2.0, -3.0])
        expected_max = numpy.array([4.0, 5.0, 6.0])

        numpy.testing.assert_array_equal(aabb.min_point, expected_min)
        numpy.testing.assert_array_equal(aabb.max_point, expected_max)

    def test_aabb_merge(self):
        aabb1 = _aabb([0.0, 0.0, 0.0], [1.0, 1.0, 1.0])
        aabb2 = _aabb([0.5, 0.5, 0.5], [2.0, 2.0, 2.0])

        merged_aabb = aabb1.merge(aabb2)
        expected_min = numpy.array([0.0, 0.0, 0.0])
        expected_max = numpy.array([2.0, 2.0, 2.0])

        numpy.testing.assert_array_equal(merged_aabb.min_point, expected_min)
        numpy.testing.assert_array_equal(merged_aabb.max_point, expected_max)

    def test_intersects(self):
        aabb1 = _aabb([0.0, 0.0, 0.0], [1.0, 1.0, 1.0])
        aabb2 = _aabb([0.5, 0.5, 0.5], [1.5, 1.5, 1.5])
        aabb3 = _aabb([2.0, 2.0, 2.0], [3.0, 3.0, 3.0])

        self.assertTrue(aabb1.intersects(aabb2))
        self.assertFalse(aabb1.intersects(aabb3))

        aabb4 = _aabb([-0.5, 0.5, 0.0], [0.5, 1.5, 1.0])
        self.assertTrue(aabb1.intersects(aabb4))

    def test_transform_aabb(self):
        transform = Transform(Pose3.identity())
        aabb = _aabb([-1.0, -1.0, -1.0], [1.0, 1.0, 1.0])
        taabb = TransformAABB(transform, aabb)

        compiled_aabb = taabb.compile_tree_aabb()
        _assert_aabb(self, compiled_aabb, [-1.0, -1.0, -1.0], [1.0, 1.0, 1.0])

    def test_transform_aabb_with_children(self):
        parent_transform = Transform(Pose3.identity())
        child_transform = Transform(_pose_at(4.0), parent=parent_transform)

        parent_aabb = _aabb([-2.0, -2.0, -2.0], [2.0, 2.0, 2.0])
        child_aabb = _aabb([-1.0, -1.0, -1.0], [1.0, 1.0, 1.0])

        parent_taabb = TransformAABB(parent_transform, parent_aabb)
        _child_taabb = TransformAABB(child_transform, child_aabb)

        compiled_aabb = parent_taabb.compile_tree_aabb()
        _assert_aabb(self, compiled_aabb, [-2.0, -2.0, -2.0], [5.0, 2.0, 2.0])

    def test_transform_aabb_recompiles_after_child_relocation(self):
        parent_transform = Transform(Pose3.identity())
        child_transform = Transform(Pose3.identity(), parent=parent_transform)

        parent_aabb = _aabb([-2.0, -2.0, -2.0], [2.0, 2.0, 2.0])
        child_aabb = _aabb([-1.0, -1.0, -1.0], [1.0, 1.0, 1.0])

        parent_taabb = TransformAABB(parent_transform, parent_aabb)
        child_taabb = TransformAABB(child_transform, child_aabb)

        compiled_aabb = parent_taabb.compile_tree_aabb()
        _assert_aabb(self, compiled_aabb, [-2.0, -2.0, -2.0], [2.0, 2.0, 2.0])

        child_transform.relocate(_pose_at(3.0))

        child_world_aabb = child_taabb.get_world_aabb()
        _assert_aabb(self, child_world_aabb, [2.0, -1.0, -1.0], [4.0, 1.0, 1.0])

        compiled_aabb_after_move = parent_taabb.compile_tree_aabb()
        _assert_aabb(self, compiled_aabb_after_move, [-2.0, -2.0, -2.0], [4.0, 2.0, 2.0])

    def test_transform_aabb_recompiles_after_parent_relocation(self):
        parent_transform = Transform(Pose3.identity())
        child_transform = Transform(_pose_at(3.0), parent=parent_transform)

        parent_taabb = TransformAABB(parent_transform, _aabb([-1.0, -1.0, -1.0], [1.0, 1.0, 1.0]))
        TransformAABB(child_transform, _aabb([-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]))

        compiled_aabb = parent_taabb.compile_tree_aabb()
        _assert_aabb(self, compiled_aabb, [-1.0, -1.0, -1.0], [3.5, 1.0, 1.0])

        parent_transform.relocate(_pose_at(10.0))

        compiled_aabb_after_move = parent_taabb.compile_tree_aabb()
        _assert_aabb(self, compiled_aabb_after_move, [9.0, -1.0, -1.0], [13.5, 1.0, 1.0])
