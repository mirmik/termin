"""Tests for GeneralPose3 - pose with scale."""

import math
import numpy as np
import pytest

from termin.geombase import GeneralPose3, Pose3


class TestGeneralPose3Basics:
    """Basic GeneralPose3 functionality."""

    def test_identity(self):
        gp = GeneralPose3.identity()
        np.testing.assert_array_equal(gp.lin, [0, 0, 0])
        np.testing.assert_array_equal(gp.ang, [0, 0, 0, 1])
        np.testing.assert_array_equal(gp.scale, [1, 1, 1])

    def test_default_constructor(self):
        gp = GeneralPose3()
        np.testing.assert_array_equal(gp.lin, [0, 0, 0])
        np.testing.assert_array_equal(gp.ang, [0, 0, 0, 1])
        np.testing.assert_array_equal(gp.scale, [1, 1, 1])

    def test_constructor_with_scale(self):
        gp = GeneralPose3(
            lin=np.array([1, 2, 3]),
            ang=np.array([0, 0, 0, 1]),
            scale=np.array([2, 3, 4])
        )
        np.testing.assert_array_equal(gp.lin, [1, 2, 3])
        np.testing.assert_array_equal(gp.scale, [2, 3, 4])

    def test_copy(self):
        gp = GeneralPose3(
            lin=np.array([1, 2, 3]),
            scale=np.array([2, 2, 2])
        )
        gp_copy = gp.copy()

        # Modify original
        gp.lin[0] = 100
        gp.scale[0] = 100

        # Copy should be unchanged
        assert gp_copy.lin[0] == 1
        assert gp_copy.scale[0] == 2


class TestGeneralPose3Composition:
    """Test pose composition with scale."""

    def test_composition_identity(self):
        """Identity * pose = pose."""
        identity = GeneralPose3.identity()
        gp = GeneralPose3(
            lin=np.array([1, 2, 3]),
            scale=np.array([2, 2, 2])
        )
        result = identity * gp
        np.testing.assert_array_almost_equal(result.lin, gp.lin)
        np.testing.assert_array_almost_equal(result.scale, gp.scale)

    def test_composition_scale_affects_child_position(self):
        """Parent scale affects child's global position."""
        parent = GeneralPose3(scale=np.array([2, 2, 2]))
        child = GeneralPose3(lin=np.array([1, 0, 0]))

        result = parent * child

        # Child at [1,0,0] with parent scale [2,2,2] -> global [2,0,0]
        np.testing.assert_array_almost_equal(result.lin, [2, 0, 0])

    def test_composition_scale_multiplies(self):
        """Scales multiply element-wise."""
        parent = GeneralPose3(scale=np.array([2, 3, 4]))
        child = GeneralPose3(scale=np.array([5, 6, 7]))

        result = parent * child

        np.testing.assert_array_almost_equal(result.scale, [10, 18, 28])

    def test_composition_non_uniform_scale(self):
        """Non-uniform scale affects position correctly."""
        parent = GeneralPose3(scale=np.array([2, 1, 3]))
        child = GeneralPose3(lin=np.array([1, 1, 1]))

        result = parent * child

        # Each axis scaled independently
        np.testing.assert_array_almost_equal(result.lin, [2, 1, 3])

    def test_composition_rotation_then_scale(self):
        """Parent rotation + scale affects child position."""
        # Parent: rotate 90 degrees around Z, then scale by 2
        parent = GeneralPose3.rotateZ(math.pi / 2)
        parent = parent.with_scale(np.array([2, 2, 2]))

        child = GeneralPose3(lin=np.array([1, 0, 0]))

        result = parent * child

        # Child [1,0,0] rotated 90 around Z -> [0,1,0], then scaled by 2 -> [0,2,0]
        np.testing.assert_array_almost_equal(result.lin, [0, 2, 0], decimal=5)

    def test_composition_translation_scale_child(self):
        """Parent translation + child with scale."""
        parent = GeneralPose3(lin=np.array([10, 0, 0]))
        child = GeneralPose3(lin=np.array([1, 0, 0]), scale=np.array([3, 3, 3]))

        result = parent * child

        # Parent translation + child position (no scale on parent)
        np.testing.assert_array_almost_equal(result.lin, [11, 0, 0])
        np.testing.assert_array_almost_equal(result.scale, [3, 3, 3])

    def test_composition_full_transform(self):
        """Full transform: translation + rotation + scale."""
        parent = GeneralPose3(
            lin=np.array([10, 0, 0]),
            ang=GeneralPose3.rotateZ(math.pi / 2).ang,
            scale=np.array([2, 2, 2])
        )
        child = GeneralPose3(lin=np.array([1, 0, 0]))

        result = parent * child

        # Child [1,0,0] scaled by 2 -> [2,0,0], rotated 90 around Z -> [0,2,0],
        # then translated by [10,0,0] -> [10,2,0]
        np.testing.assert_array_almost_equal(result.lin, [10, 2, 0], decimal=5)

    def test_composition_chain_three_levels(self):
        """Chain of three transforms with scale."""
        level1 = GeneralPose3(scale=np.array([2, 2, 2]))
        level2 = GeneralPose3(lin=np.array([1, 0, 0]), scale=np.array([3, 3, 3]))
        level3 = GeneralPose3(lin=np.array([1, 0, 0]))

        result = level1 * level2 * level3

        # level3 [1,0,0] scaled by level2 scale [3,3,3] -> [3,0,0]
        # level2 position [1,0,0] + [3,0,0] = [4,0,0]
        # level2 result scaled by level1 scale [2,2,2] -> [8,0,0]
        # Final scale = [2,2,2] * [3,3,3] * [1,1,1] = [6,6,6]
        np.testing.assert_array_almost_equal(result.lin, [8, 0, 0])
        np.testing.assert_array_almost_equal(result.scale, [6, 6, 6])


class TestGeneralPose3Inverse:
    """Test inverse with scale."""

    def test_inverse_identity(self):
        gp = GeneralPose3.identity()
        inv = gp.inverse()
        np.testing.assert_array_almost_equal(inv.lin, [0, 0, 0])
        np.testing.assert_array_almost_equal(inv.scale, [1, 1, 1])

    def test_inverse_translation_only(self):
        gp = GeneralPose3(lin=np.array([1, 2, 3]))
        inv = gp.inverse()
        np.testing.assert_array_almost_equal(inv.lin, [-1, -2, -3])

    def test_inverse_scale_only(self):
        gp = GeneralPose3(scale=np.array([2, 4, 8]))
        inv = gp.inverse()
        np.testing.assert_array_almost_equal(inv.scale, [0.5, 0.25, 0.125])

    def test_inverse_roundtrip(self):
        """pose * inverse(pose) = identity (works for any scale)."""
        gp = GeneralPose3(
            lin=np.array([1, 2, 3]),
            ang=GeneralPose3.rotateZ(0.5).ang,
            scale=np.array([2, 3, 4])  # non-uniform scale OK for right multiplication
        )
        result = gp * gp.inverse()

        np.testing.assert_array_almost_equal(result.lin, [0, 0, 0], decimal=5)
        np.testing.assert_array_almost_equal(result.scale, [1, 1, 1], decimal=5)

    def test_inverse_roundtrip_reverse_uniform_scale(self):
        """inverse(pose) * pose = identity (uniform scale only).

        Note: Non-uniform scale with rotation doesn't form a closed group.
        TRS inverse is S^-1 R^-1 T^-1 which isn't representable as TRS
        when scale is non-uniform and rotation is present.
        """
        gp = GeneralPose3(
            lin=np.array([1, 2, 3]),
            ang=GeneralPose3.rotateZ(0.5).ang,
            scale=np.array([2, 2, 2])  # uniform scale
        )
        result = gp.inverse() * gp

        np.testing.assert_array_almost_equal(result.lin, [0, 0, 0], decimal=5)
        np.testing.assert_array_almost_equal(result.scale, [1, 1, 1], decimal=5)

    def test_inverse_roundtrip_reverse_no_rotation(self):
        """inverse(pose) * pose = identity (no rotation case).

        Works with non-uniform scale when there's no rotation.
        """
        gp = GeneralPose3(
            lin=np.array([1, 2, 3]),
            scale=np.array([2, 3, 4])  # non-uniform, but no rotation
        )
        result = gp.inverse() * gp

        np.testing.assert_array_almost_equal(result.lin, [0, 0, 0], decimal=5)
        np.testing.assert_array_almost_equal(result.scale, [1, 1, 1], decimal=5)


class TestGeneralPose3TransformPoint:
    """Test point transformation with scale."""

    def test_transform_point_identity(self):
        gp = GeneralPose3.identity()
        point = np.array([1, 2, 3])
        result = gp.transform_point(point)
        np.testing.assert_array_almost_equal(result, point)

    def test_transform_point_scale_only(self):
        gp = GeneralPose3(scale=np.array([2, 3, 4]))
        point = np.array([1, 1, 1])
        result = gp.transform_point(point)
        np.testing.assert_array_almost_equal(result, [2, 3, 4])

    def test_transform_point_translation_and_scale(self):
        gp = GeneralPose3(
            lin=np.array([10, 20, 30]),
            scale=np.array([2, 2, 2])
        )
        point = np.array([1, 1, 1])
        result = gp.transform_point(point)
        # scale first: [2,2,2], then translate: [12, 22, 32]
        np.testing.assert_array_almost_equal(result, [12, 22, 32])

    def test_inverse_transform_point_roundtrip(self):
        gp = GeneralPose3(
            lin=np.array([1, 2, 3]),
            ang=GeneralPose3.rotateZ(0.5).ang,
            scale=np.array([2, 3, 4])
        )
        point = np.array([5, 6, 7])

        transformed = gp.transform_point(point)
        recovered = gp.inverse_transform_point(transformed)

        np.testing.assert_array_almost_equal(recovered, point, decimal=5)


class TestGeneralPose3Matrix:
    """Test matrix conversion."""

    def test_as_matrix_identity(self):
        gp = GeneralPose3.identity()
        mat = gp.as_matrix()
        np.testing.assert_array_almost_equal(mat, np.eye(4))

    def test_as_matrix_scale(self):
        gp = GeneralPose3(scale=np.array([2, 3, 4]))
        mat = gp.as_matrix()

        # Scale should be in diagonal of rotation part
        assert mat[0, 0] == pytest.approx(2)
        assert mat[1, 1] == pytest.approx(3)
        assert mat[2, 2] == pytest.approx(4)

    def test_from_matrix_extracts_scale(self):
        # Create matrix with scale
        mat = np.array([
            [2, 0, 0, 1],
            [0, 3, 0, 2],
            [0, 0, 4, 3],
            [0, 0, 0, 1]
        ], dtype=float)

        gp = GeneralPose3.from_matrix(mat)

        np.testing.assert_array_almost_equal(gp.lin, [1, 2, 3])
        np.testing.assert_array_almost_equal(gp.scale, [2, 3, 4])

    def test_matrix_roundtrip(self):
        gp = GeneralPose3(
            lin=np.array([1, 2, 3]),
            ang=GeneralPose3.rotateZ(0.5).ang,
            scale=np.array([2, 3, 4])
        )
        mat = gp.as_matrix()
        gp2 = GeneralPose3.from_matrix(mat)

        np.testing.assert_array_almost_equal(gp2.lin, gp.lin, decimal=5)
        np.testing.assert_array_almost_equal(gp2.scale, gp.scale, decimal=5)


class TestGeneralPose3ToPose3:
    """Test conversion to Pose3."""

    def test_to_pose3_drops_scale(self):
        gp = GeneralPose3(
            lin=np.array([1, 2, 3]),
            ang=np.array([0, 0, 0, 1]),
            scale=np.array([2, 3, 4])
        )
        pose = gp.to_pose3()

        assert isinstance(pose, Pose3)
        np.testing.assert_array_equal(pose.lin, [1, 2, 3])
        np.testing.assert_array_equal(pose.ang, [0, 0, 0, 1])

    def test_pose3_to_general_pose3_roundtrip(self):
        pose = Pose3(
            lin=np.array([1, 2, 3]),
            ang=Pose3.rotateZ(0.5).ang
        )
        gp = pose.to_general_pose3(scale=np.array([2, 2, 2]))
        pose2 = gp.to_pose3()

        np.testing.assert_array_almost_equal(pose2.lin, pose.lin)
        np.testing.assert_array_almost_equal(pose2.ang, pose.ang)


class TestGeneralPose3Lerp:
    """Test interpolation with scale."""

    def test_lerp_position(self):
        gp1 = GeneralPose3(lin=np.array([0, 0, 0]))
        gp2 = GeneralPose3(lin=np.array([10, 20, 30]))

        result = GeneralPose3.lerp(gp1, gp2, 0.5)

        np.testing.assert_array_almost_equal(result.lin, [5, 10, 15])

    def test_lerp_scale(self):
        gp1 = GeneralPose3(scale=np.array([1, 1, 1]))
        gp2 = GeneralPose3(scale=np.array([3, 5, 7]))

        result = GeneralPose3.lerp(gp1, gp2, 0.5)

        np.testing.assert_array_almost_equal(result.scale, [2, 3, 4])

    def test_lerp_endpoints(self):
        gp1 = GeneralPose3(lin=np.array([0, 0, 0]), scale=np.array([1, 1, 1]))
        gp2 = GeneralPose3(lin=np.array([10, 10, 10]), scale=np.array([2, 2, 2]))

        result0 = GeneralPose3.lerp(gp1, gp2, 0.0)
        result1 = GeneralPose3.lerp(gp1, gp2, 1.0)

        np.testing.assert_array_almost_equal(result0.lin, gp1.lin)
        np.testing.assert_array_almost_equal(result0.scale, gp1.scale)
        np.testing.assert_array_almost_equal(result1.lin, gp2.lin)
        np.testing.assert_array_almost_equal(result1.scale, gp2.scale)
