import math

import pytest

from termin.geombase import Pose3, Quat, Vec3, qslerp
from termin.geombase import _geom_native


def _components(q: Quat) -> tuple[float, float, float, float]:
    return q.x, q.y, q.z, q.w


def _same_rotation(lhs: Quat, rhs: Quat, epsilon: float = 1.0e-12) -> bool:
    lhs_unit = lhs.try_normalized(0.0)
    rhs_unit = rhs.try_normalized(0.0)
    assert lhs_unit is not None
    assert rhs_unit is not None
    return abs(abs(lhs_unit.dot(rhs_unit)) - 1.0) <= epsilon


def test_quat_is_a_raw_xyzw_value_with_checked_normalization() -> None:
    value = Quat(1.0, -2.0, 3.0, 4.0)
    other = Quat(-0.5, 0.25, 2.0, -1.0)

    assert value.dot(other) == pytest.approx(1.0)
    assert value.norm_squared() == pytest.approx(30.0)
    assert value.norm() == pytest.approx(math.sqrt(30.0))
    assert value.is_finite()
    assert not Quat(math.nan, 0.0, 0.0, 1.0).is_finite()
    assert math.isfinite(Quat(float.fromhex("0x1.fffffffffffffp+1023"), 0.0, 0.0, 0.0).norm())

    normalized = value.try_normalized()
    assert normalized is not None
    assert normalized.norm() == pytest.approx(1.0)
    assert _components(Quat(0.0, 0.0, 0.0, 7.0).normalized()) == pytest.approx((0.0, 0.0, 0.0, 1.0))


@pytest.mark.parametrize(
    ("value", "epsilon"),
    [
        (Quat(0.0, 0.0, 0.0, 0.0), 0.0),
        (Quat(math.nan, 0.0, 0.0, 1.0), 0.0),
        (Quat(math.inf, 0.0, 0.0, 1.0), 0.0),
        (Quat.identity(), -1.0),
        (Quat.identity(), math.nan),
        (Quat.identity(), math.inf),
        (Quat.identity(), 1.0),
    ],
)
def test_quat_checked_normalization_rejects_invalid_values(value: Quat, epsilon: float) -> None:
    assert value.try_normalized(epsilon) is None
    fallback = Quat(4.0, 3.0, 2.0, 1.0)
    assert _components(value.normalized_or(fallback, epsilon)) == _components(fallback)
    with pytest.raises(ValueError):
        value.normalized(epsilon)


def test_quat_inverse_is_true_for_non_unit_values() -> None:
    value = Quat(1.0, -2.0, 3.0, 4.0)
    inverse = value.try_inverse()
    assert inverse is not None
    assert _components(value * inverse) == pytest.approx((0.0, 0.0, 0.0, 1.0), abs=1.0e-15)
    assert _components(inverse * value) == pytest.approx((0.0, 0.0, 0.0, 1.0), abs=1.0e-15)
    assert _components(Quat(0.0, 0.0, 0.0, 2.0).inverse()) == pytest.approx((0.0, 0.0, 0.0, 0.5))

    largest_finite = Quat(float.fromhex("0x1.fffffffffffffp+1023"), 0.0, 0.0, 0.0)
    large_inverse = largest_finite.try_inverse(0.0)
    assert large_inverse is not None
    assert math.isfinite(large_inverse.x) and large_inverse.x < 0.0
    assert _components(largest_finite * large_inverse) == pytest.approx((0.0, 0.0, 0.0, 1.0), abs=1.0e-15)

    partial_underflow = Quat(2.0e-162, 2.0e-162, 0.0, 0.0)
    normalized = partial_underflow.try_normalized(0.0)
    assert normalized is not None
    assert normalized.norm() == pytest.approx(1.0, abs=1.0e-15)
    inverse = partial_underflow.try_inverse(0.0)
    assert inverse is not None
    assert _components(partial_underflow * inverse) == pytest.approx((0.0, 0.0, 0.0, 1.0), abs=1.0e-15)

    smallest_subnormal = float.fromhex("0x0.0000000000001p-1022")
    subnormal = Quat(smallest_subnormal, 0.0, 0.0, 0.0)
    assert _components(subnormal.normalized(0.0)) == (1.0, 0.0, 0.0, 0.0)
    assert subnormal.try_inverse(0.0) is None
    with pytest.raises(ValueError):
        subnormal.inverse(0.0)

    largest = float.fromhex("0x1.fffffffffffffp+1023")
    multi_max = Quat(largest, largest, largest, largest)
    multi_normalized = multi_max.try_normalized(0.0)
    assert multi_normalized is not None
    assert _components(multi_normalized) == (0.5, 0.5, 0.5, 0.5)
    assert math.isinf(multi_max.norm())
    assert math.isinf(multi_max.norm_squared())
    multi_inverse = multi_max.try_inverse(0.0)
    assert multi_inverse is not None
    assert all(math.isfinite(component) for component in _components(multi_inverse))
    assert _components(multi_max * multi_inverse) == pytest.approx((0.0, 0.0, 0.0, 1.0), abs=2.0e-15)


@pytest.mark.parametrize(
    ("value", "epsilon"),
    [
        (Quat(0.0, 0.0, 0.0, 0.0), 0.0),
        (Quat(math.nan, 0.0, 0.0, 1.0), 0.0),
        (Quat(0.0, math.inf, 0.0, 1.0), 0.0),
        (Quat.identity(), -1.0),
        (Quat.identity(), math.nan),
        (Quat.identity(), 1.0),
    ],
)
def test_quat_checked_inverse_rejects_invalid_values(value: Quat, epsilon: float) -> None:
    assert value.try_inverse(epsilon) is None
    with pytest.raises(ValueError):
        value.inverse(epsilon)


def test_checked_rotate_inverse_rotate_and_matrix_accept_scaled_quaternions() -> None:
    quarter_turn = Quat.from_axis_angle(Vec3(0.0, 0.0, 7.0), math.pi / 2.0)
    scaled = Quat(
        quarter_turn.x * 9.0,
        quarter_turn.y * 9.0,
        quarter_turn.z * 9.0,
        quarter_turn.w * 9.0,
    )
    vector = Vec3(2.0, -3.0, 4.0)

    rotated = scaled.try_rotate(vector)
    assert rotated is not None
    assert tuple(rotated) == pytest.approx((3.0, 2.0, 4.0), abs=1.0e-14)
    assert tuple(scaled.rotate(vector)) == pytest.approx(tuple(rotated), abs=1.0e-14)

    recovered = scaled.try_inverse_rotate(rotated)
    assert recovered is not None
    assert tuple(recovered) == pytest.approx(tuple(vector), abs=1.0e-14)
    assert tuple(scaled.inverse_rotate(rotated)) == pytest.approx(tuple(vector), abs=1.0e-14)

    matrix = scaled.try_to_matrix()
    assert matrix is not None
    assert tuple(matrix.transform(vector)) == pytest.approx(tuple(rotated), abs=1.0e-14)
    assert tuple(scaled.to_matrix().transform(vector)) == pytest.approx(tuple(rotated), abs=1.0e-14)

    largest = float.fromhex("0x1.fffffffffffffp+1023")
    multi_max = Quat(largest, largest, largest, largest)
    max_rotated = multi_max.try_rotate(vector, 0.0)
    max_matrix = multi_max.try_to_matrix(0.0)
    assert max_rotated is not None
    assert max_matrix is not None
    assert tuple(max_matrix.transform(vector)) == pytest.approx(tuple(max_rotated), abs=1.0e-14)

    half_turn_z = Quat(0.0, 0.0, 1.0, 0.0)
    largest_vector = Vec3(largest, 0.0, 0.0)
    largest_rotated = half_turn_z.try_rotate(largest_vector, 0.0)
    largest_inverse_rotated = half_turn_z.try_inverse_rotate(largest_vector, 0.0)
    assert largest_rotated is not None
    assert largest_inverse_rotated is not None
    assert tuple(largest_rotated) == (-largest, 0.0, 0.0)
    assert tuple(largest_inverse_rotated) == (-largest, 0.0, 0.0)


@pytest.mark.parametrize(
    ("value", "vector", "epsilon"),
    [
        (Quat(0.0, 0.0, 0.0, 0.0), Vec3(1.0, 2.0, 3.0), 0.0),
        (Quat(math.nan, 0.0, 0.0, 1.0), Vec3(1.0, 2.0, 3.0), 0.0),
        (Quat(0.0, math.inf, 0.0, 1.0), Vec3(1.0, 2.0, 3.0), 0.0),
        (Quat.identity(), Vec3(1.0, 2.0, 3.0), -1.0),
        (Quat.identity(), Vec3(1.0, 2.0, 3.0), math.nan),
        (Quat.identity(), Vec3(1.0, 2.0, 3.0), 1.0),
    ],
)
def test_checked_rotate_and_matrix_reject_invalid_values(value: Quat, vector: Vec3, epsilon: float) -> None:
    assert value.try_rotate(vector, epsilon) is None
    assert value.try_inverse_rotate(vector, epsilon) is None
    assert value.try_to_matrix(epsilon) is None
    with pytest.raises(ValueError):
        value.rotate(vector, epsilon)
    with pytest.raises(ValueError):
        value.inverse_rotate(vector, epsilon)
    with pytest.raises(ValueError):
        value.to_matrix(epsilon)


def test_checked_rotate_rejects_invalid_vector_without_affecting_matrix() -> None:
    value = Quat.identity()
    vector = Vec3(math.nan, 0.0, 0.0)

    assert value.try_rotate(vector, 0.0) is None
    assert value.try_inverse_rotate(vector, 0.0) is None
    assert value.try_to_matrix(0.0) is not None
    with pytest.raises(ValueError):
        value.rotate(vector, 0.0)
    with pytest.raises(ValueError):
        value.inverse_rotate(vector, 0.0)
    value.to_matrix(0.0)


def test_checked_rotate_rejects_unrepresentable_result_transactionally() -> None:
    largest = float.fromhex("0x1.fffffffffffffp+1023")
    value = Quat.from_axis_angle(Vec3.unit_z(), math.pi / 4.0)
    vector = Vec3(largest, largest, 0.0)

    assert value.try_rotate(vector, 0.0) is None
    assert value.try_inverse_rotate(vector, 0.0) is None
    with pytest.raises(ValueError):
        value.rotate(vector, 0.0)
    with pytest.raises(ValueError):
        value.inverse_rotate(vector, 0.0)


def test_axis_angle_normalizes_full_range_axes_and_rejects_invalid_values() -> None:
    largest = float.fromhex("0x1.fffffffffffffp+1023")
    large_axis = Quat.try_from_axis_angle(Vec3(largest, largest, 0.0), 0.73, 0.0)
    assert large_axis is not None
    assert large_axis.norm() == pytest.approx(1.0, abs=1.0e-15)
    assert _same_rotation(large_axis, Quat.from_axis_angle(Vec3(7.0, 7.0, 0.0), 0.73))

    invalid_cases = [
        (Vec3.zero(), 0.5, 0.0),
        (Vec3(math.nan, 0.0, 0.0), 0.5, 0.0),
        (Vec3(0.0, math.inf, 0.0), 0.5, 0.0),
        (Vec3.unit_x(), math.nan, 0.0),
        (Vec3.unit_x(), math.inf, 0.0),
        (Vec3.unit_x(), 0.5, -1.0),
        (Vec3.unit_x(), 0.5, math.nan),
    ]
    for axis, angle, epsilon in invalid_cases:
        assert Quat.try_from_axis_angle(axis, angle, epsilon) is None
        with pytest.raises(ValueError):
            Quat.from_axis_angle(axis, angle, epsilon)


def test_slerp_normalizes_inputs_uses_shortest_path_and_allows_extrapolation() -> None:
    identity_scaled = Quat(0.0, 0.0, 0.0, 2.0)
    quarter_turn = Quat.from_axis_angle(Vec3.unit_z(), math.pi / 2.0)
    quarter_turn_scaled = Quat(
        quarter_turn.x * 3.0,
        quarter_turn.y * 3.0,
        quarter_turn.z * 3.0,
        quarter_turn.w * 3.0,
    )

    halfway = Quat.slerp(identity_scaled, quarter_turn_scaled, 0.5)
    assert halfway.norm() == pytest.approx(1.0)
    assert _same_rotation(halfway, Quat.from_axis_angle(Vec3.unit_z(), math.pi / 4.0))

    antipodal = Quat.try_slerp(identity_scaled, Quat(0.0, 0.0, 0.0, -5.0), 0.37)
    assert antipodal is not None
    assert _same_rotation(antipodal, Quat.identity())

    near = Quat.from_axis_angle(Vec3.unit_x(), 1.0e-5)
    assert _same_rotation(Quat.slerp(Quat.identity(), near, 0.25), Quat.from_axis_angle(Vec3.unit_x(), 2.5e-6))

    assert _same_rotation(
        Quat.slerp(Quat.identity(), quarter_turn_scaled, 1.5),
        Quat.from_axis_angle(Vec3.unit_z(), 3.0 * math.pi / 4.0),
    )
    assert _same_rotation(
        Quat.slerp(Quat.identity(), quarter_turn_scaled, -0.5),
        Quat.from_axis_angle(Vec3.unit_z(), -math.pi / 4.0),
    )
    assert _same_rotation(Quat.slerp(quarter_turn_scaled, quarter_turn_scaled, 7.0), quarter_turn)
    assert _same_rotation(qslerp(identity_scaled, quarter_turn_scaled, 0.5), halfway)


@pytest.mark.parametrize(
    ("a", "b", "t", "epsilon"),
    [
        (Quat(0.0, 0.0, 0.0, 0.0), Quat.identity(), 0.5, 0.0),
        (Quat.identity(), Quat(math.nan, 0.0, 0.0, 1.0), 0.5, 0.0),
        (Quat.identity(), Quat(0.0, math.inf, 0.0, 1.0), 0.5, 0.0),
        (Quat.identity(), Quat.identity(), math.nan, 0.0),
        (Quat.identity(), Quat.identity(), math.inf, 0.0),
        (Quat.identity(), Quat.identity(), 0.5, -1.0),
        (Quat.identity(), Quat.identity(), 0.5, math.nan),
        (Quat.identity(), Quat.identity(), 0.5, 1.0),
    ],
)
def test_checked_slerp_rejects_invalid_values(a: Quat, b: Quat, t: float, epsilon: float) -> None:
    assert Quat.try_slerp(a, b, t, epsilon) is None
    with pytest.raises(ValueError):
        Quat.slerp(a, b, t, epsilon)


def test_euler_xyz_is_typed_compositional_and_round_trips() -> None:
    euler = Vec3(0.37, -0.42, 0.81)
    from_euler = Quat.from_euler(euler)
    composed = (
        Quat.from_axis_angle(Vec3.unit_z(), euler.z)
        * Quat.from_axis_angle(Vec3.unit_y(), euler.y)
        * Quat.from_axis_angle(Vec3.unit_x(), euler.x)
    )
    assert _same_rotation(from_euler, composed)

    scaled = Quat(from_euler.x * 7.0, from_euler.y * 7.0, from_euler.z * 7.0, from_euler.w * 7.0)
    recovered = scaled.to_euler()
    assert (recovered.x, recovered.y, recovered.z) == pytest.approx((euler.x, euler.y, euler.z), abs=1.0e-14)

    pose = Pose3.from_euler(euler)
    assert _same_rotation(pose.ang, from_euler)
    assert tuple(pose.to_euler()) == pytest.approx(tuple(euler), abs=1.0e-14)


@pytest.mark.parametrize("pitch", [math.pi / 2.0, -math.pi / 2.0])
def test_euler_gimbal_policy_sets_roll_to_zero_and_preserves_rotation(pitch: float) -> None:
    source = Vec3(0.4, pitch, -0.7)
    orientation = Quat.from_euler(source)
    recovered = orientation.to_euler()

    assert recovered.x == 0.0
    assert recovered.y == pytest.approx(pitch, abs=1.0e-15)
    assert _same_rotation(Quat.from_euler(recovered), orientation)


def test_euler_checked_and_convenience_failures_are_explicit() -> None:
    invalid_euler = Vec3(math.nan, 0.0, 0.0)
    assert Quat.try_from_euler(invalid_euler) is None
    with pytest.raises(ValueError):
        Quat.from_euler(invalid_euler)
    with pytest.raises(ValueError):
        Pose3.from_euler(invalid_euler)

    zero = Quat(0.0, 0.0, 0.0, 0.0)
    assert zero.try_to_euler(0.0) is None
    with pytest.raises(ValueError):
        zero.to_euler(0.0)
    assert Quat.identity().try_to_euler(-1.0) is None
    assert Quat.identity().try_to_euler(math.nan) is None
    with pytest.raises(ValueError):
        Quat.identity().to_euler(-1.0)


def test_native_module_has_no_duplicate_module_level_slerp() -> None:
    assert not hasattr(_geom_native, "slerp")
