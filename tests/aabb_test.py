from termin.kinematic import Transform
from termin.geombase import Pose3, AABB, TransformAABB
import unittest
import numpy

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
        aabb1 = AABB(numpy.array([0.0, 0.0, 0.0]), numpy.array([1.0, 1.0, 1.0]))
        aabb2 = AABB(numpy.array([0.5, 0.5, 0.5]), numpy.array([2.0, 2.0, 2.0]))

        merged_aabb = aabb1.merge(aabb2)
        expected_min = numpy.array([0.0, 0.0, 0.0])
        expected_max = numpy.array([2.0, 2.0, 2.0])

        numpy.testing.assert_array_equal(merged_aabb.min_point, expected_min)
        numpy.testing.assert_array_equal(merged_aabb.max_point, expected_max)

    def test_intersects(self):
        aabb1 = AABB(numpy.array([0.0, 0.0]), numpy.array([1.0, 1.0]))
        aabb2 = AABB(numpy.array([0.5, 0.5]), numpy.array([1.5, 1.5]))
        aabb3 = AABB(numpy.array([2.0, 2.0]), numpy.array([3.0, 3.0]))

        self.assertTrue(aabb1.intersects(aabb2))
        self.assertFalse(aabb1.intersects(aabb3))

        aabb4 = AABB(numpy.array([-0.5, 0.5]), numpy.array([0.5, 1.5]))
        self.assertTrue(aabb1.intersects(aabb4))

    def test_transform_aabb(self):
        transform = Transform(Pose3.identity())
        aabb = AABB(numpy.array([-1.0, -1.0, -1.0]), numpy.array([1.0, 1.0, 1.0]))
        taabb = TransformAABB(transform, aabb)

        compiled_aabb = taabb.compile_tree_aabb()
        numpy.testing.assert_array_equal(compiled_aabb.min_point, aabb.min_point)
        numpy.testing.assert_array_equal(compiled_aabb.max_point, aabb.max_point)

    def test_transform_aabb_with_children(self):
        parent_transform = Transform(Pose3.identity())
        child_transform = Transform(Pose3.identity(), parent=parent_transform)

        parent_aabb = AABB(numpy.array([-2.0, -2.0, -2.0]), numpy.array([2.0, 2.0, 2.0]))
        child_aabb = AABB(numpy.array([-1.0, -1.0, -1.0]), numpy.array([1.0, 1.0, 1.0]))

        parent_taabb = TransformAABB(parent_transform, parent_aabb)
        child_taabb = TransformAABB(child_transform, child_aabb)

        compiled_aabb = parent_taabb.compile_tree_aabb()
        expected_min = numpy.array([-2.0, -2.0, -2.0])
        expected_max = numpy.array([2.0, 2.0, 2.0])

        numpy.testing.assert_array_equal(compiled_aabb.min_point, expected_min)
        numpy.testing.assert_array_equal(compiled_aabb.max_point, expected_max)
        numpy.testing.assert_array_equal(compiled_aabb.max_point, expected_max)

    def test_transform_aabb_with_children_with_latest_relocation(self):
        parent_transform = Transform(Pose3.identity())
        child_transform = Transform(Pose3.identity(), parent=parent_transform)

        self.assertEqual(parent_transform._version_for_walking_to_distal, 1)
        self.assertEqual(parent_transform._version_only_my, 0)
        self.assertEqual(parent_transform._version_for_walking_to_proximal, 0)
        self.assertEqual(child_transform._version_for_walking_to_distal, 1)
        self.assertEqual(child_transform._version_only_my, 1)
        self.assertEqual(child_transform._version_for_walking_to_proximal, 1)

        parent_aabb = AABB(numpy.array([-2.0, -2.0, -2.0]), numpy.array([2.0, 2.0, 2.0]))
        child_aabb = AABB(numpy.array([-1.0, -1.0, -1.0]), numpy.array([1.0, 1.0, 1.0]))

        parent_taabb = TransformAABB(parent_transform, parent_aabb)
        child_taabb = TransformAABB(child_transform, child_aabb)

        self.assertEqual(parent_taabb._last_tree_inspected_version, -1)
        # Initial compilation
        compiled_aabb = parent_taabb.compile_tree_aabb()

        self.assertEqual(parent_taabb._last_tree_inspected_version, 1)

        numpy.testing.assert_array_equal(compiled_aabb.min_point, numpy.array([-2.0, -2.0, -2.0]))
        numpy.testing.assert_array_equal(compiled_aabb.max_point, numpy.array([2.0, 2.0, 2.0]))

        # Move child transform
        child_transform.relocate(Pose3(
            ang=numpy.array([0.0, 0.0, 0.0, 1.0]),
            lin=numpy.array([3.0, 0.0, 0.0])
        ))

        # check versions of transforms
        self.assertEqual(parent_transform._version_for_walking_to_distal, 2)
        self.assertEqual(parent_transform._version_only_my, 0)
        self.assertEqual(parent_transform._version_for_walking_to_proximal, 0)
        self.assertEqual(child_transform._version_for_walking_to_distal, 2)
        self.assertEqual(child_transform._version_only_my, 2)
        self.assertEqual(child_transform._version_for_walking_to_proximal, 2)

        child_world_aabb = child_taabb.get_world_aabb()
        numpy.testing.assert_array_equal(child_world_aabb.min_point, numpy.array([2.0, -1.0, -1.0]))
        numpy.testing.assert_array_equal(child_world_aabb.max_point, numpy.array([4.0, 1.0, 1.0]))

        # Recompile after relocation
        compiled_aabb_after_move = parent_taabb.compile_tree_aabb()
        expected_min_after_move = numpy.array([-2.0, -2.0, -2.0])
        expected_max_after_move = numpy.array([4.0, 2.0, 2.0])

        numpy.testing.assert_array_equal(compiled_aabb_after_move.min_point, expected_min_after_move)
        numpy.testing.assert_array_equal(compiled_aabb_after_move.max_point, expected_max_after_move)
