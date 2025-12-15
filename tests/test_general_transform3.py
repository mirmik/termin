"""Tests for GeneralTransform3 - transform hierarchy with scale inheritance."""

import math
import numpy as np
import pytest

from termin.geombase import GeneralPose3, Pose3
from termin.kinematic import GeneralTransform3


class TestGeneralTransform3Basics:
    """Basic GeneralTransform3 functionality."""

    def test_create_default(self):
        t = GeneralTransform3()
        pose = t.local_pose()
        np.testing.assert_array_equal(pose.lin, [0, 0, 0])
        np.testing.assert_array_equal(pose.scale, [1, 1, 1])

    def test_create_with_pose(self):
        pose = GeneralPose3(
            lin=np.array([1, 2, 3]),
            scale=np.array([2, 2, 2])
        )
        t = GeneralTransform3(pose)
        np.testing.assert_array_equal(t.local_pose().lin, [1, 2, 3])
        np.testing.assert_array_equal(t.local_pose().scale, [2, 2, 2])

    def test_global_pose_no_parent(self):
        pose = GeneralPose3(lin=np.array([1, 2, 3]), scale=np.array([2, 2, 2]))
        t = GeneralTransform3(pose)

        global_pose = t.global_pose()
        np.testing.assert_array_equal(global_pose.lin, [1, 2, 3])
        np.testing.assert_array_equal(global_pose.scale, [2, 2, 2])


class TestGeneralTransform3ScaleInheritance:
    """Test scale inheritance through hierarchy."""

    def test_child_inherits_parent_scale(self):
        """Child's global scale = parent scale * child local scale."""
        parent = GeneralTransform3(GeneralPose3(scale=np.array([2, 2, 2])))
        child = GeneralTransform3(GeneralPose3(scale=np.array([1, 1, 1])))
        parent.add_child(child)

        child_global = child.global_pose()
        np.testing.assert_array_almost_equal(child_global.scale, [2, 2, 2])

    def test_scale_multiplies_through_hierarchy(self):
        """Scales multiply: grandchild scale = parent * child * grandchild."""
        parent = GeneralTransform3(GeneralPose3(scale=np.array([2, 2, 2])))
        child = GeneralTransform3(GeneralPose3(scale=np.array([3, 3, 3])))
        grandchild = GeneralTransform3(GeneralPose3(scale=np.array([1, 1, 1])))

        parent.add_child(child)
        child.add_child(grandchild)

        grandchild_global = grandchild.global_pose()
        np.testing.assert_array_almost_equal(grandchild_global.scale, [6, 6, 6])

    def test_non_uniform_scale_inheritance(self):
        """Non-uniform scales inherit correctly."""
        parent = GeneralTransform3(GeneralPose3(scale=np.array([2, 3, 4])))
        child = GeneralTransform3(GeneralPose3(scale=np.array([1, 2, 0.5])))
        parent.add_child(child)

        child_global = child.global_pose()
        np.testing.assert_array_almost_equal(child_global.scale, [2, 6, 2])


class TestGeneralTransform3PositionWithScale:
    """Test that parent scale affects child global position."""

    def test_parent_scale_affects_child_position(self):
        """Child at local [1,0,0] with parent scale [2,2,2] -> global [2,0,0]."""
        parent = GeneralTransform3(GeneralPose3(scale=np.array([2, 2, 2])))
        child = GeneralTransform3(GeneralPose3(lin=np.array([1, 0, 0])))
        parent.add_child(child)

        child_global = child.global_pose()
        np.testing.assert_array_almost_equal(child_global.lin, [2, 0, 0])

    def test_non_uniform_scale_affects_position(self):
        """Non-uniform parent scale affects child position per axis."""
        parent = GeneralTransform3(GeneralPose3(scale=np.array([2, 3, 4])))
        child = GeneralTransform3(GeneralPose3(lin=np.array([1, 1, 1])))
        parent.add_child(child)

        child_global = child.global_pose()
        np.testing.assert_array_almost_equal(child_global.lin, [2, 3, 4])

    def test_parent_translation_and_scale(self):
        """Parent at [10,0,0] with scale [2,2,2], child at local [1,0,0]."""
        parent = GeneralTransform3(GeneralPose3(
            lin=np.array([10, 0, 0]),
            scale=np.array([2, 2, 2])
        ))
        child = GeneralTransform3(GeneralPose3(lin=np.array([1, 0, 0])))
        parent.add_child(child)

        child_global = child.global_pose()
        # child [1,0,0] scaled by 2 -> [2,0,0], then parent adds [10,0,0] -> [12,0,0]
        np.testing.assert_array_almost_equal(child_global.lin, [12, 0, 0])

    def test_three_level_hierarchy_position(self):
        """Three-level hierarchy with scale at each level."""
        root = GeneralTransform3(GeneralPose3(scale=np.array([2, 2, 2])))
        middle = GeneralTransform3(GeneralPose3(
            lin=np.array([1, 0, 0]),
            scale=np.array([3, 3, 3])
        ))
        leaf = GeneralTransform3(GeneralPose3(lin=np.array([1, 0, 0])))

        root.add_child(middle)
        middle.add_child(leaf)

        # Leaf position calculation:
        # leaf local [1,0,0] scaled by middle scale [3,3,3] -> [3,0,0]
        # middle local [1,0,0] + [3,0,0] = [4,0,0]
        # [4,0,0] scaled by root scale [2,2,2] -> [8,0,0]
        leaf_global = leaf.global_pose()
        np.testing.assert_array_almost_equal(leaf_global.lin, [8, 0, 0])
        np.testing.assert_array_almost_equal(leaf_global.scale, [6, 6, 6])


class TestGeneralTransform3RotationWithScale:
    """Test rotation combined with scale."""

    def test_parent_rotation_then_scale(self):
        """Parent rotates then scales child position."""
        # Parent: rotate 90 degrees around Z, scale by 2
        parent_pose = GeneralPose3(
            ang=GeneralPose3.rotateZ(math.pi / 2).ang,
            scale=np.array([2, 2, 2])
        )
        parent = GeneralTransform3(parent_pose)
        child = GeneralTransform3(GeneralPose3(lin=np.array([1, 0, 0])))
        parent.add_child(child)

        child_global = child.global_pose()
        # Child [1,0,0] scaled by 2 -> [2,0,0], rotated 90 around Z -> [0,2,0]
        np.testing.assert_array_almost_equal(child_global.lin, [0, 2, 0], decimal=5)

    def test_child_rotated_parent_scaled(self):
        """Parent scaled, child rotated."""
        parent = GeneralTransform3(GeneralPose3(scale=np.array([2, 2, 2])))
        child_pose = GeneralPose3(
            lin=np.array([1, 0, 0]),
            ang=GeneralPose3.rotateZ(math.pi / 2).ang
        )
        child = GeneralTransform3(child_pose)
        parent.add_child(child)

        child_global = child.global_pose()
        # Child position [1,0,0] scaled by parent -> [2,0,0]
        np.testing.assert_array_almost_equal(child_global.lin, [2, 0, 0], decimal=5)


class TestGeneralTransform3Relocate:
    """Test relocate methods."""

    def test_relocate_with_pose3(self):
        """relocate() accepts Pose3 and preserves scale."""
        t = GeneralTransform3(GeneralPose3(scale=np.array([2, 2, 2])))

        t.relocate(Pose3(lin=np.array([5, 5, 5])))

        pose = t.local_pose()
        np.testing.assert_array_almost_equal(pose.lin, [5, 5, 5])
        np.testing.assert_array_almost_equal(pose.scale, [2, 2, 2])  # scale preserved

    def test_relocate_with_general_pose3(self):
        """relocate() with GeneralPose3 updates everything."""
        t = GeneralTransform3(GeneralPose3(scale=np.array([2, 2, 2])))

        t.relocate(GeneralPose3(lin=np.array([5, 5, 5]), scale=np.array([3, 3, 3])))

        pose = t.local_pose()
        np.testing.assert_array_almost_equal(pose.lin, [5, 5, 5])
        np.testing.assert_array_almost_equal(pose.scale, [3, 3, 3])

    def test_relocate_global_with_pose3(self):
        """relocate_global() with Pose3 preserves scale."""
        parent = GeneralTransform3(GeneralPose3(lin=np.array([10, 0, 0])))
        child = GeneralTransform3(GeneralPose3(scale=np.array([2, 2, 2])))
        parent.add_child(child)

        child.relocate_global(Pose3(lin=np.array([15, 0, 0])))

        # Global position should be [15,0,0], so local should be [5,0,0]
        np.testing.assert_array_almost_equal(child.local_pose().lin, [5, 0, 0])
        np.testing.assert_array_almost_equal(child.local_pose().scale, [2, 2, 2])  # preserved

    def test_relocate_updates_children(self):
        """Relocating parent updates children's global pose."""
        parent = GeneralTransform3(GeneralPose3(scale=np.array([2, 2, 2])))
        child = GeneralTransform3(GeneralPose3(lin=np.array([1, 0, 0])))
        parent.add_child(child)

        # Initial child global position
        initial = child.global_pose().lin.copy()
        np.testing.assert_array_almost_equal(initial, [2, 0, 0])

        # Move parent
        parent.relocate(GeneralPose3(lin=np.array([10, 0, 0]), scale=np.array([2, 2, 2])))

        # Child should update
        updated = child.global_pose()
        np.testing.assert_array_almost_equal(updated.lin, [12, 0, 0])


class TestGeneralTransform3TransformPoint:
    """Test point transformation."""

    def test_transform_point_with_scale(self):
        """transform_point applies scale."""
        t = GeneralTransform3(GeneralPose3(scale=np.array([2, 3, 4])))

        result = t.transform_point(np.array([1, 1, 1]))

        np.testing.assert_array_almost_equal(result, [2, 3, 4])

    def test_transform_point_hierarchy(self):
        """transform_point uses global pose."""
        parent = GeneralTransform3(GeneralPose3(scale=np.array([2, 2, 2])))
        child = GeneralTransform3(GeneralPose3(lin=np.array([5, 0, 0])))
        parent.add_child(child)

        # Transform point [1,0,0] through child
        result = child.transform_point(np.array([1, 0, 0]))

        # Child global: position [10,0,0] (5 * 2), scale [2,2,2]
        # Point [1,0,0] scaled by 2 -> [2,0,0], then translated by [10,0,0] -> [12,0,0]
        np.testing.assert_array_almost_equal(result, [12, 0, 0])


class TestGeneralTransform3DirectionVectors:
    """Test direction helper methods."""

    def test_forward_with_scale(self):
        """forward() returns scaled vector."""
        t = GeneralTransform3(GeneralPose3(scale=np.array([2, 3, 4])))

        # Y-forward convention
        result = t.forward()

        # forward is [0, 1, 0] * scale = [0, 3, 0]
        np.testing.assert_array_almost_equal(result, [0, 3, 0])

    def test_right_with_scale(self):
        """right() returns scaled vector."""
        t = GeneralTransform3(GeneralPose3(scale=np.array([2, 3, 4])))

        result = t.right()

        # right is [1, 0, 0] * scale = [2, 0, 0]
        np.testing.assert_array_almost_equal(result, [2, 0, 0])

    def test_up_with_scale(self):
        """up() returns scaled vector."""
        t = GeneralTransform3(GeneralPose3(scale=np.array([2, 3, 4])))

        result = t.up()

        # up is [0, 0, 1] * scale = [0, 0, 4]
        np.testing.assert_array_almost_equal(result, [0, 0, 4])


class TestGeneralTransform3WorldMatrix:
    """Test world_matrix method."""

    def test_world_matrix_identity(self):
        t = GeneralTransform3()
        mat = t.world_matrix()
        np.testing.assert_array_almost_equal(mat, np.eye(4))

    def test_world_matrix_with_scale(self):
        t = GeneralTransform3(GeneralPose3(scale=np.array([2, 3, 4])))
        mat = t.world_matrix()

        # Diagonal should have scale values
        assert mat[0, 0] == pytest.approx(2)
        assert mat[1, 1] == pytest.approx(3)
        assert mat[2, 2] == pytest.approx(4)

    def test_world_matrix_inherits_scale(self):
        """World matrix includes inherited scale."""
        parent = GeneralTransform3(GeneralPose3(scale=np.array([2, 2, 2])))
        child = GeneralTransform3(GeneralPose3(scale=np.array([3, 3, 3])))
        parent.add_child(child)

        mat = child.world_matrix()

        # Child global scale = 2 * 3 = 6
        assert mat[0, 0] == pytest.approx(6)
        assert mat[1, 1] == pytest.approx(6)
        assert mat[2, 2] == pytest.approx(6)


class TestGeneralTransform3EdgeCases:
    """Test edge cases."""

    def test_zero_scale_component(self):
        """Handle zero in scale (degenerate case)."""
        t = GeneralTransform3(GeneralPose3(scale=np.array([1, 0, 1])))

        # Should not crash
        mat = t.world_matrix()
        assert mat[1, 1] == pytest.approx(0)

    def test_very_small_scale(self):
        """Handle very small scale values."""
        t = GeneralTransform3(GeneralPose3(scale=np.array([1e-10, 1e-10, 1e-10])))

        result = t.transform_point(np.array([1, 1, 1]))
        np.testing.assert_array_almost_equal(result, [1e-10, 1e-10, 1e-10])

    def test_very_large_scale(self):
        """Handle very large scale values."""
        t = GeneralTransform3(GeneralPose3(scale=np.array([1e10, 1e10, 1e10])))

        result = t.transform_point(np.array([1, 1, 1]))
        np.testing.assert_array_almost_equal(result, [1e10, 1e10, 1e10])

    def test_negative_scale(self):
        """Handle negative scale (mirror)."""
        t = GeneralTransform3(GeneralPose3(scale=np.array([-1, 1, 1])))

        result = t.transform_point(np.array([1, 0, 0]))
        np.testing.assert_array_almost_equal(result, [-1, 0, 0])

    def test_reparenting_updates_global(self):
        """Reparenting child updates its global pose."""
        parent1 = GeneralTransform3(GeneralPose3(scale=np.array([2, 2, 2])))
        parent2 = GeneralTransform3(GeneralPose3(scale=np.array([3, 3, 3])))
        child = GeneralTransform3(GeneralPose3(lin=np.array([1, 0, 0])))

        parent1.add_child(child)
        np.testing.assert_array_almost_equal(child.global_pose().lin, [2, 0, 0])

        parent2.add_child(child)  # reparent
        np.testing.assert_array_almost_equal(child.global_pose().lin, [3, 0, 0])
