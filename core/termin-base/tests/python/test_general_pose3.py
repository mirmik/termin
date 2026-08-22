"""Tests for GeneralPose3 - pose with scale."""

import math
import numpy as np
import pytest

from termin.geombase import GeneralPose3, Pose3, Vec3, Quat
from termin.geombase._geom_native import lerp_general_pose3


def assert_vec3_approx(actual: Vec3, expected: tuple, eps=1e-6):
    """Helper to assert Vec3 is approximately equal to expected tuple."""
    assert abs(actual.x - expected[0]) < eps, f"x: {actual.x} != {expected[0]}"
    assert abs(actual.y - expected[1]) < eps, f"y: {actual.y} != {expected[1]}"
    assert abs(actual.z - expected[2]) < eps, f"z: {actual.z} != {expected[2]}"


def assert_quat_approx(actual: Quat, expected: Quat, eps=1e-6):
    assert actual.x == pytest.approx(expected.x, abs=eps)
    assert actual.y == pytest.approx(expected.y, abs=eps)
    assert actual.z == pytest.approx(expected.z, abs=eps)
    assert actual.w == pytest.approx(expected.w, abs=eps)


class TestGeneralPose3Basics:
    """Basic GeneralPose3 functionality."""

    def test_identity(self):
        gp = GeneralPose3.identity()
        assert_vec3_approx(gp.lin, (0, 0, 0))
        assert gp.ang.x == pytest.approx(0)
        assert gp.ang.y == pytest.approx(0)
        assert gp.ang.z == pytest.approx(0)
        assert gp.ang.w == pytest.approx(1)
        assert_vec3_approx(gp.scale, (1, 1, 1))

    def test_default_constructor(self):
        gp = GeneralPose3()
        assert_vec3_approx(gp.lin, (0, 0, 0))
        assert gp.ang.w == pytest.approx(1)
        assert_vec3_approx(gp.scale, (1, 1, 1))

    def test_constructor_with_scale(self):
        gp = GeneralPose3(lin=Vec3(1, 2, 3), ang=Quat(0, 0, 0, 1), scale=Vec3(2, 3, 4))
        assert_vec3_approx(gp.lin, (1, 2, 3))
        assert_vec3_approx(gp.scale, (2, 3, 4))

    def test_normalized_rejects_degenerate_rotation(self):
        gp = GeneralPose3(ang=Quat(0.0, 0.0, 0.0, 0.0))

        with pytest.raises(ValueError, match="GeneralPose3 rotation cannot be normalized"):
            gp.normalized()

    def test_copy(self):
        gp = GeneralPose3(lin=Vec3(1, 2, 3), scale=Vec3(2, 2, 2))
        gp_copy = gp.copy()

        # Check copy has same values
        assert_vec3_approx(gp_copy.lin, (1, 2, 3))
        assert gp_copy.ang.x == pytest.approx(0)
        assert gp_copy.ang.y == pytest.approx(0)
        assert gp_copy.ang.z == pytest.approx(0)
        assert gp_copy.ang.w == pytest.approx(1)
        assert_vec3_approx(gp_copy.scale, (2, 2, 2))

    def test_semantic_operations_accept_scaled_rotation_without_mutating_pose(self):
        unit_rotation = GeneralPose3.rotate_z(math.pi / 2).ang
        factor = 1.0e300
        scaled_rotation = Quat(
            unit_rotation.x * factor,
            unit_rotation.y * factor,
            unit_rotation.z * factor,
            unit_rotation.w * factor,
        )
        pose = GeneralPose3(
            ang=scaled_rotation,
            lin=Vec3(1.0, 2.0, 3.0),
            scale=Vec3(2.0, 3.0, 4.0),
        )
        reference = GeneralPose3(ang=unit_rotation, lin=pose.lin, scale=pose.scale)
        point = Vec3(2.0, -1.0, 0.5)

        transformed = reference.transform_point(point)
        assert_vec3_approx(
            pose.transform_point(point),
            (transformed.x, transformed.y, transformed.z),
        )
        recovered = pose.inverse_transform_point(transformed)
        assert_vec3_approx(recovered, (point.x, point.y, point.z))
        direction = pose.transform_direction(Vec3.unit_x())
        reference_direction = reference.transform_direction(Vec3.unit_x())
        assert_vec3_approx(
            direction,
            (reference_direction.x, reference_direction.y, reference_direction.z),
        )

        inverse = pose.inverse_trs_projected()
        reference_inverse = reference.inverse_trs_projected()
        assert_quat_approx(inverse.ang, reference_inverse.ang)
        assert_vec3_approx(
            inverse.lin,
            (reference_inverse.lin.x, reference_inverse.lin.y, reference_inverse.lin.z),
        )
        assert_vec3_approx(
            inverse.scale,
            (reference_inverse.scale.x, reference_inverse.scale.y, reference_inverse.scale.z),
        )

        np.testing.assert_allclose(pose.rotation_matrix(), reference.rotation_matrix())
        np.testing.assert_allclose(pose.as_matrix(), reference.as_matrix())
        np.testing.assert_allclose(pose.inverse_matrix(), reference.inverse_matrix())

        assert pose.ang.x == scaled_rotation.x
        assert pose.ang.y == scaled_rotation.y
        assert pose.ang.z == scaled_rotation.z
        assert pose.ang.w == scaled_rotation.w

    def test_semantic_operations_reject_invalid_rotations(self):
        invalid_rotations = (
            Quat(0.0, 0.0, 0.0, 0.0),
            Quat(math.nan, 0.0, 0.0, 1.0),
            Quat(math.inf, 0.0, 0.0, 1.0),
        )
        for rotation in invalid_rotations:
            pose = GeneralPose3(ang=rotation)
            operations = (
                pose.inverse_trs_projected,
                lambda pose=pose: pose.transform_point(Vec3.unit_x()),
                lambda pose=pose: pose.transform_direction(Vec3.unit_x()),
                pose.rotation_matrix,
                pose.as_matrix,
                pose.inverse_matrix,
                lambda pose=pose: pose.compose_trs_projected(GeneralPose3.identity()),
            )
            for operation in operations:
                with pytest.raises(ValueError, match="GeneralPose3 rotation"):
                    operation()

    def test_axis_angle_factories_reject_invalid_inputs(self):
        with pytest.raises(ValueError, match="GeneralPose3 axis"):
            GeneralPose3.rotation(Vec3.zero(), 0.5)
        with pytest.raises(ValueError, match="GeneralPose3 axis"):
            GeneralPose3.rotation(Vec3.unit_z(), math.nan)
        with pytest.raises(ValueError, match="GeneralPose3 axis"):
            GeneralPose3.rotate_x(math.inf)

    def test_semantic_operations_cover_full_range_rotation_intermediates(self):
        largest = float.fromhex("0x1.fffffffffffffp+1023")
        rotation = Quat(0.0, 0.0, largest, 0.0)
        pose = GeneralPose3(ang=rotation, scale=Vec3(1.0, 1.0, 1.0))
        vector = Vec3(largest, 0.0, 0.0)

        assert_vec3_approx(pose.transform_vector(vector), (-largest, 0.0, 0.0))
        assert_vec3_approx(pose.inverse_transform_vector(vector), (-largest, 0.0, 0.0))
        assert_vec3_approx(pose.right_in_global(largest), (-largest, 0.0, 0.0))
        assert_vec3_approx(pose.global_right_in_local(largest), (-largest, 0.0, 0.0))

        child = GeneralPose3(lin=vector)
        composed = pose.compose_trs_projected(child)
        assert_vec3_approx(composed.lin, (-largest, 0.0, 0.0))

        inverse = GeneralPose3(ang=rotation, lin=vector).inverse_trs_projected()
        assert_vec3_approx(inverse.lin, (largest, 0.0, 0.0))

        with pytest.raises(ValueError, match="distance must be finite"):
            pose.right_in_global(math.inf)
        with pytest.raises(ValueError, match="GeneralPose3 rotation"):
            GeneralPose3(ang=Quat(0.0, 0.0, 0.0, 0.0)).right_in_global()


class TestGeneralPose3Composition:
    """Test explicitly projected TRS composition with scale."""

    def test_composition_accepts_scaled_parent_and_child_rotations(self):
        parent_rotation = GeneralPose3.rotate_x(0.25).ang
        child_rotation = GeneralPose3.rotate_z(-0.5).ang
        parent = GeneralPose3(
            ang=Quat(
                parent_rotation.x * 8.0,
                parent_rotation.y * 8.0,
                parent_rotation.z * 8.0,
                parent_rotation.w * 8.0,
            ),
            lin=Vec3(1.0, 2.0, 3.0),
            scale=Vec3(2.0, 3.0, 4.0),
        )
        child = GeneralPose3(
            ang=Quat(
                child_rotation.x * 3.0,
                child_rotation.y * 3.0,
                child_rotation.z * 3.0,
                child_rotation.w * 3.0,
            ),
            lin=Vec3(-2.0, 1.0, 0.5),
            scale=Vec3(0.5, 2.0, 1.5),
        )
        reference_parent = GeneralPose3(ang=parent_rotation, lin=parent.lin, scale=parent.scale)
        reference_child = GeneralPose3(ang=child_rotation, lin=child.lin, scale=child.scale)

        actual = parent.compose_trs_projected(child)
        expected = reference_parent.compose_trs_projected(reference_child)
        assert_quat_approx(actual.ang, expected.ang)
        assert_vec3_approx(actual.lin, (expected.lin.x, expected.lin.y, expected.lin.z))
        assert_vec3_approx(actual.scale, (expected.scale.x, expected.scale.y, expected.scale.z))

        pose_child = Pose3(ang=child.ang, lin=child.lin)
        reference_pose_child = Pose3(ang=child_rotation, lin=child.lin)
        actual_pose_child = parent.compose_trs_projected(pose_child)
        expected_pose_child = reference_parent.compose_trs_projected(reference_pose_child)
        assert_quat_approx(actual_pose_child.ang, expected_pose_child.ang)
        assert_vec3_approx(
            actual_pose_child.lin,
            (expected_pose_child.lin.x, expected_pose_child.lin.y, expected_pose_child.lin.z),
        )

    def test_composition_identity(self):
        """Identity * pose = pose."""
        identity = GeneralPose3.identity()
        gp = GeneralPose3(lin=Vec3(1, 2, 3), scale=Vec3(2, 2, 2))
        result = identity.compose_trs_projected(gp)
        assert_vec3_approx(result.lin, (1, 2, 3))
        assert_vec3_approx(result.scale, (2, 2, 2))

    def test_composition_scale_affects_child_position(self):
        """Parent scale affects child's global position."""
        parent = GeneralPose3(scale=Vec3(2, 2, 2))
        child = GeneralPose3(lin=Vec3(1, 0, 0))

        result = parent.compose_trs_projected(child)

        # Child at [1,0,0] with parent scale [2,2,2] -> global [2,0,0]
        assert_vec3_approx(result.lin, (2, 0, 0))

    def test_composition_scale_multiplies(self):
        """Scales multiply element-wise."""
        parent = GeneralPose3(scale=Vec3(2, 3, 4))
        child = GeneralPose3(scale=Vec3(5, 6, 7))

        result = parent.compose_trs_projected(child)

        assert_vec3_approx(result.scale, (10, 18, 28))

    def test_composition_non_uniform_scale(self):
        """Non-uniform scale affects position correctly."""
        parent = GeneralPose3(scale=Vec3(2, 1, 3))
        child = GeneralPose3(lin=Vec3(1, 1, 1))

        result = parent.compose_trs_projected(child)

        # Each axis scaled independently
        assert_vec3_approx(result.lin, (2, 1, 3))

    def test_composition_rotation_then_scale(self):
        """Parent rotation + scale affects child position."""
        # Parent: rotate 90 degrees around Z, then scale by 2
        parent = GeneralPose3.rotateZ(math.pi / 2)
        parent = parent.with_scale(Vec3(2, 2, 2))

        child = GeneralPose3(lin=Vec3(1, 0, 0))

        result = parent.compose_trs_projected(child)

        # Child [1,0,0] rotated 90 around Z -> [0,1,0], then scaled by 2 -> [0,2,0]
        assert_vec3_approx(result.lin, (0, 2, 0), eps=1e-5)

    def test_composition_translation_scale_child(self):
        """Parent translation + child with scale."""
        parent = GeneralPose3(lin=Vec3(10, 0, 0))
        child = GeneralPose3(lin=Vec3(1, 0, 0), scale=Vec3(3, 3, 3))

        result = parent.compose_trs_projected(child)

        # Parent translation + child position (no scale on parent)
        assert_vec3_approx(result.lin, (11, 0, 0))
        assert_vec3_approx(result.scale, (3, 3, 3))

    def test_composition_full_transform(self):
        """Full transform: translation + rotation + scale."""
        parent = GeneralPose3(lin=Vec3(10, 0, 0), ang=GeneralPose3.rotateZ(math.pi / 2).ang, scale=Vec3(2, 2, 2))
        child = GeneralPose3(lin=Vec3(1, 0, 0))

        result = parent.compose_trs_projected(child)

        # Child [1,0,0] scaled by 2 -> [2,0,0], rotated 90 around Z -> [0,2,0],
        # then translated by [10,0,0] -> [10,2,0]
        assert_vec3_approx(result.lin, (10, 2, 0), eps=1e-5)

    def test_composition_chain_three_levels(self):
        """Chain of three transforms with scale."""
        level1 = GeneralPose3(scale=Vec3(2, 2, 2))
        level2 = GeneralPose3(lin=Vec3(1, 0, 0), scale=Vec3(3, 3, 3))
        level3 = GeneralPose3(lin=Vec3(1, 0, 0))

        result = level1.compose_trs_projected(level2.compose_trs_projected(level3))

        # level3 [1,0,0] scaled by level2 scale [3,3,3] -> [3,0,0]
        # level2 position [1,0,0] + [3,0,0] = [4,0,0]
        # level2 result scaled by level1 scale [2,2,2] -> [8,0,0]
        # Final scale = [2,2,2] * [3,3,3] * [1,1,1] = [6,6,6]
        assert_vec3_approx(result.lin, (8, 0, 0))
        assert_vec3_approx(result.scale, (6, 6, 6))


class TestGeneralPose3ProjectedInverse:
    """Test explicitly projected TRS inverse with scale."""

    def test_inverse_identity(self):
        gp = GeneralPose3.identity()
        inv = gp.inverse_trs_projected()
        assert_vec3_approx(inv.lin, (0, 0, 0))
        assert_vec3_approx(inv.scale, (1, 1, 1))

    def test_inverse_translation_only(self):
        gp = GeneralPose3(lin=Vec3(1, 2, 3))
        inv = gp.inverse_trs_projected()
        assert_vec3_approx(inv.lin, (-1, -2, -3))

    def test_inverse_scale_only(self):
        gp = GeneralPose3(scale=Vec3(2, 4, 8))
        inv = gp.inverse_trs_projected()
        assert_vec3_approx(inv.scale, (0.5, 0.25, 0.125))

    def test_inverse_roundtrip(self):
        """pose * inverse(pose) = identity (works for any scale)."""
        gp = GeneralPose3(
            lin=Vec3(1, 2, 3),
            ang=GeneralPose3.rotateZ(0.5).ang,
            scale=Vec3(2, 3, 4),  # non-uniform scale OK for right multiplication
        )
        result = gp.compose_trs_projected(gp.inverse_trs_projected())

        assert_vec3_approx(result.lin, (0, 0, 0), eps=1e-5)
        assert_vec3_approx(result.scale, (1, 1, 1), eps=1e-5)

    def test_inverse_roundtrip_reverse_uniform_scale(self):
        """inverse(pose) * pose = identity (uniform scale only).

        Note: Non-uniform scale with rotation doesn't form a closed group.
        TRS inverse is S^-1 R^-1 T^-1 which isn't representable as TRS
        when scale is non-uniform and rotation is present.
        """
        gp = GeneralPose3(
            lin=Vec3(1, 2, 3),
            ang=GeneralPose3.rotateZ(0.5).ang,
            scale=Vec3(2, 2, 2),  # uniform scale
        )
        result = gp.inverse_trs_projected().compose_trs_projected(gp)

        assert_vec3_approx(result.lin, (0, 0, 0), eps=1e-5)
        assert_vec3_approx(result.scale, (1, 1, 1), eps=1e-5)

    def test_inverse_roundtrip_reverse_no_rotation(self):
        """inverse(pose) * pose = identity (no rotation case).

        Works with non-uniform scale when there's no rotation.
        """
        gp = GeneralPose3(
            lin=Vec3(1, 2, 3),
            scale=Vec3(2, 3, 4),  # non-uniform, but no rotation
        )
        result = gp.inverse_trs_projected().compose_trs_projected(gp)

        assert_vec3_approx(result.lin, (0, 0, 0), eps=1e-5)
        assert_vec3_approx(result.scale, (1, 1, 1), eps=1e-5)

    def test_exact_looking_algebra_is_not_exposed(self):
        gp = GeneralPose3.identity()

        with pytest.raises(TypeError):
            gp * gp
        with pytest.raises(TypeError):
            gp @ gp
        assert "inverse" not in dir(gp)


class TestGeneralPose3TransformPoint:
    """Test point transformation with scale."""

    def test_transform_point_identity(self):
        gp = GeneralPose3.identity()
        point = Vec3(1, 2, 3)
        result = gp.transform_point(point)
        assert_vec3_approx(result, (1, 2, 3))

    def test_transform_point_scale_only(self):
        gp = GeneralPose3(scale=Vec3(2, 3, 4))
        point = Vec3(1, 1, 1)
        result = gp.transform_point(point)
        assert_vec3_approx(result, (2, 3, 4))

    def test_transform_vector_applies_scale_but_transform_direction_does_not(self):
        gp = GeneralPose3(scale=Vec3(2, 3, 4))
        vector = Vec3(1, 1, 1)

        transformed_vector = gp.transform_vector(vector)
        transformed_direction = gp.transform_direction(vector)

        assert_vec3_approx(transformed_vector, (2, 3, 4))
        assert_vec3_approx(transformed_direction, (1, 1, 1))

    def test_direction_helpers_ignore_scale(self):
        gp = GeneralPose3(scale=Vec3(2, 3, 4))

        assert_vec3_approx(gp.forward_in_global(), (0, 1, 0))
        assert_vec3_approx(gp.right_in_global(), (1, 0, 0))
        assert_vec3_approx(gp.up_in_global(), (0, 0, 1))
        assert_vec3_approx(gp.forward_in_global(2.0), (0, 2, 0))

    def test_transform_point_translation_and_scale(self):
        gp = GeneralPose3(lin=Vec3(10, 20, 30), scale=Vec3(2, 2, 2))
        point = Vec3(1, 1, 1)
        result = gp.transform_point(point)
        # scale first: [2,2,2], then translate: [12, 22, 32]
        assert_vec3_approx(result, (12, 22, 32))

    def test_inverse_transform_point_roundtrip(self):
        gp = GeneralPose3(lin=Vec3(1, 2, 3), ang=GeneralPose3.rotateZ(0.5).ang, scale=Vec3(2, 3, 4))
        point = Vec3(5, 6, 7)

        transformed = gp.transform_point(point)
        recovered = gp.inverse_transform_point(transformed)

        assert_vec3_approx(recovered, (5, 6, 7), eps=1e-5)


class TestGeneralPose3Matrix:
    """Test matrix conversion."""

    def test_as_matrix_identity(self):
        import numpy as np

        gp = GeneralPose3.identity()
        mat = np.asarray(gp.as_matrix())
        expected = np.eye(4)
        assert mat.shape == (4, 4)
        for i in range(4):
            for j in range(4):
                assert mat[i, j] == pytest.approx(expected[i, j])

    def test_as_matrix_scale(self):
        gp = GeneralPose3(scale=Vec3(2, 3, 4))
        mat = np.asarray(gp.as_matrix())

        # Scale should be in diagonal of rotation part
        assert mat[0, 0] == pytest.approx(2)
        assert mat[1, 1] == pytest.approx(3)
        assert mat[2, 2] == pytest.approx(4)

    def test_from_matrix_extracts_scale(self):
        source = GeneralPose3(lin=Vec3(1, 2, 3), scale=Vec3(2, 3, 4))
        gp = GeneralPose3.from_matrix(source.as_mat44())

        assert_vec3_approx(gp.lin, (1, 2, 3))
        assert_vec3_approx(gp.scale, (2, 3, 4))

    def test_matrix_roundtrip(self):
        gp = GeneralPose3(lin=Vec3(1, 2, 3), ang=GeneralPose3.rotateZ(0.5).ang, scale=Vec3(2, 3, 4))
        gp2 = GeneralPose3.from_matrix(gp.as_mat44())

        assert_vec3_approx(gp2.lin, (gp.lin.x, gp.lin.y, gp.lin.z), eps=1e-5)
        assert_vec3_approx(gp2.scale, (gp.scale.x, gp.scale.y, gp.scale.z), eps=1e-5)
        expected_point = gp.transform_point(Vec3(1, 2, 3))
        actual_point = gp2.transform_point(Vec3(1, 2, 3))
        assert_vec3_approx(actual_point, (expected_point.x, expected_point.y, expected_point.z), eps=1e-5)


class TestGeneralPose3ToPose3:
    """Test conversion to Pose3."""

    def test_to_pose3_drops_scale(self):
        gp = GeneralPose3(lin=Vec3(1, 2, 3), ang=Quat(0, 0, 0, 1), scale=Vec3(2, 3, 4))
        pose = gp.to_pose3()

        assert isinstance(pose, Pose3)
        assert_vec3_approx(pose.lin, (1, 2, 3))
        assert pose.ang.x == pytest.approx(0)
        assert pose.ang.y == pytest.approx(0)
        assert pose.ang.z == pytest.approx(0)
        assert pose.ang.w == pytest.approx(1)

    def test_pose3_to_general_pose3_roundtrip(self):
        pose = Pose3(lin=Vec3(1, 2, 3), ang=Pose3.rotateZ(0.5).ang)
        gp = pose.to_general_pose3(scale=Vec3(2, 2, 2))
        pose2 = gp.to_pose3()

        assert_vec3_approx(pose2.lin, (pose.lin.x, pose.lin.y, pose.lin.z))
        assert pose2.ang.x == pytest.approx(pose.ang.x)
        assert pose2.ang.y == pytest.approx(pose.ang.y)
        assert pose2.ang.z == pytest.approx(pose.ang.z)
        assert pose2.ang.w == pytest.approx(pose.ang.w)


class TestGeneralPose3Lerp:
    """Test interpolation with scale."""

    def test_lerp_position(self):
        gp1 = GeneralPose3(lin=Vec3(0, 0, 0))
        gp2 = GeneralPose3(lin=Vec3(10, 20, 30))

        result = GeneralPose3.lerp(gp1, gp2, 0.5)

        assert_vec3_approx(result.lin, (5, 10, 15))

    def test_lerp_scale(self):
        gp1 = GeneralPose3(scale=Vec3(1, 1, 1))
        gp2 = GeneralPose3(scale=Vec3(3, 5, 7))

        result = GeneralPose3.lerp(gp1, gp2, 0.5)

        assert_vec3_approx(result.scale, (2, 3, 4))

    def test_lerp_endpoints(self):
        gp1 = GeneralPose3(lin=Vec3(0, 0, 0), scale=Vec3(1, 1, 1))
        gp2 = GeneralPose3(lin=Vec3(10, 10, 10), scale=Vec3(2, 2, 2))

        result0 = GeneralPose3.lerp(gp1, gp2, 0.0)
        result1 = GeneralPose3.lerp(gp1, gp2, 1.0)

        assert_vec3_approx(result0.lin, (0, 0, 0))
        assert_vec3_approx(result0.scale, (1, 1, 1))
        assert_vec3_approx(result1.lin, (10, 10, 10))
        assert_vec3_approx(result1.scale, (2, 2, 2))

    def test_lerp_preserves_full_range_endpoints_and_midpoint(self):
        largest = float.fromhex("0x1.fffffffffffffp+1023")
        first = GeneralPose3(
            lin=Vec3(-largest, largest, -largest),
            scale=Vec3(-largest, largest, -largest),
        )
        second = GeneralPose3(
            lin=Vec3(largest, -largest, largest),
            scale=Vec3(largest, -largest, largest),
        )

        for interpolate in (GeneralPose3.lerp, lerp_general_pose3):
            at_first = interpolate(first, second, 0.0)
            at_second = interpolate(first, second, 1.0)
            midpoint = interpolate(first, second, 0.5)

            assert (at_first.lin.x, at_first.lin.y, at_first.lin.z) == (-largest, largest, -largest)
            assert (at_first.scale.x, at_first.scale.y, at_first.scale.z) == (-largest, largest, -largest)
            assert (at_second.lin.x, at_second.lin.y, at_second.lin.z) == (largest, -largest, largest)
            assert (at_second.scale.x, at_second.scale.y, at_second.scale.z) == (largest, -largest, largest)
            assert (midpoint.lin.x, midpoint.lin.y, midpoint.lin.z) == (0.0, 0.0, 0.0)
            assert (midpoint.scale.x, midpoint.scale.y, midpoint.scale.z) == (0.0, 0.0, 0.0)

    def test_lerp_accepts_scaled_rotations(self):
        first_rotation = GeneralPose3.rotate_x(0.25).ang
        second_rotation = GeneralPose3.rotate_z(-0.5).ang
        first = GeneralPose3(
            ang=Quat(
                first_rotation.x * 8.0,
                first_rotation.y * 8.0,
                first_rotation.z * 8.0,
                first_rotation.w * 8.0,
            ),
            lin=Vec3(1.0, 2.0, 3.0),
            scale=Vec3(2.0, 3.0, 4.0),
        )
        second = GeneralPose3(
            ang=Quat(
                second_rotation.x * 3.0,
                second_rotation.y * 3.0,
                second_rotation.z * 3.0,
                second_rotation.w * 3.0,
            ),
            lin=Vec3(-2.0, 1.0, 0.5),
            scale=Vec3(0.5, 2.0, 1.5),
        )
        reference_first = GeneralPose3(ang=first_rotation, lin=first.lin, scale=first.scale)
        reference_second = GeneralPose3(ang=second_rotation, lin=second.lin, scale=second.scale)
        expected = GeneralPose3.lerp(reference_first, reference_second, 0.35)

        for actual in (
            GeneralPose3.lerp(first, second, 0.35),
            lerp_general_pose3(first, second, 0.35),
        ):
            assert_quat_approx(actual.ang, expected.ang)
            assert_vec3_approx(actual.lin, (expected.lin.x, expected.lin.y, expected.lin.z))
            assert_vec3_approx(actual.scale, (expected.scale.x, expected.scale.y, expected.scale.z))

    def test_lerp_rejects_invalid_rotation_and_factor(self):
        invalid = GeneralPose3(ang=Quat(0.0, 0.0, 0.0, 0.0))
        valid = GeneralPose3.identity()

        for interpolate in (GeneralPose3.lerp, lerp_general_pose3):
            with pytest.raises(ValueError, match="GeneralPose3 rotation"):
                interpolate(invalid, valid, 0.5)
            with pytest.raises(ValueError, match="GeneralPose3 interpolation factor"):
                interpolate(valid, valid, math.nan)
            with pytest.raises(ValueError, match="GeneralPose3 interpolation translations"):
                interpolate(GeneralPose3(lin=Vec3(math.inf, 0.0, 0.0)), valid, 0.0)
            with pytest.raises(ValueError, match="GeneralPose3 interpolation scales"):
                interpolate(GeneralPose3(scale=Vec3(math.inf, 1.0, 1.0)), valid, 0.0)


def test_inverse_operations_reject_nonfinite_scale():
    pose = GeneralPose3(scale=Vec3(math.inf, 1.0, 1.0))

    for operation in (
        pose.inverse_trs_projected,
        lambda: pose.inverse_transform_point(Vec3(1.0, 2.0, 3.0)),
        lambda: pose.inverse_transform_vector(Vec3(1.0, 2.0, 3.0)),
    ):
        with pytest.raises(ValueError, match="GeneralPose3 scale must be finite"):
            operation()
