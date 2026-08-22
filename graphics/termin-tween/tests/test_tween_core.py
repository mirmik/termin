from __future__ import annotations

import math

import pytest

from termin.geombase import GeneralPose3, Quat, Vec3
from termin.tween import Ease, MoveTween, RotateTween, ScaleTween, TweenManager, TweenState
from termin.tween.ease import evaluate


class _Transform:
    def __init__(self, pose: GeneralPose3 | None = None) -> None:
        initial_pose = pose if pose is not None else GeneralPose3()
        self._pose = initial_pose.copy()

    def local_pose(self) -> GeneralPose3:
        return self._pose.copy()

    def relocate(self, pose: GeneralPose3) -> None:
        self._pose = pose.copy()


def _assert_vec3(actual: Vec3, expected: tuple[float, float, float]) -> None:
    assert tuple(actual) == pytest.approx(expected)


def _assert_same_rotation(actual: Quat, expected: Quat) -> None:
    assert abs(actual.dot(expected)) == pytest.approx(1.0, abs=1.0e-12)


def test_ease_linear_evaluates_endpoints() -> None:
    assert evaluate(Ease.LINEAR, 0.0) == 0.0
    assert evaluate(Ease.LINEAR, 1.0) == 1.0


def test_move_tween_accepts_sequence_and_preserves_rotation_and_scale() -> None:
    rotation = Quat.from_axis_angle(Vec3.unit_x(), 0.4)
    transform = _Transform(
        GeneralPose3(
            lin=Vec3.zero(),
            ang=rotation,
            scale=Vec3(2.0, 3.0, 4.0),
        )
    )
    tween = MoveTween(transform, (2.0, 4.0, 6.0), duration=2.0)

    assert isinstance(tween.target, Vec3)
    assert tween.update(1.0) is True
    pose = transform.local_pose()
    _assert_vec3(pose.lin, (1.0, 2.0, 3.0))
    _assert_same_rotation(pose.ang, rotation)
    _assert_vec3(pose.scale, (2.0, 3.0, 4.0))

    assert tween.update(1.0) is False
    _assert_vec3(transform.local_pose().lin, (2.0, 4.0, 6.0))
    assert tween.state == TweenState.COMPLETED


def test_move_tween_accepts_and_owns_canonical_target() -> None:
    transform = _Transform()
    target = Vec3(3.0, 5.0, 7.0)
    tween = MoveTween(transform, target, duration=1.0)
    target.x = 30.0

    tween.update(1.0)

    _assert_vec3(transform.local_pose().lin, (3.0, 5.0, 7.0))


def test_scale_tween_accepts_uniform_target_and_preserves_other_trs_parts() -> None:
    rotation = Quat.from_axis_angle(Vec3.unit_y(), -0.3)
    transform = _Transform(
        GeneralPose3(
            lin=Vec3(4.0, 5.0, 6.0),
            ang=rotation,
            scale=Vec3(1.0, 2.0, 3.0),
        )
    )
    tween = ScaleTween(transform, 3.0, duration=2.0)

    assert isinstance(tween.target, Vec3)
    tween.update(1.0)
    pose = transform.local_pose()
    _assert_vec3(pose.scale, (2.0, 2.5, 3.0))
    _assert_vec3(pose.lin, (4.0, 5.0, 6.0))
    _assert_same_rotation(pose.ang, rotation)


def test_scale_tween_accepts_and_owns_canonical_vector_target() -> None:
    transform = _Transform()
    target = Vec3(2.0, 4.0, 8.0)
    tween = ScaleTween(transform, target, duration=1.0)
    target.z = 80.0

    tween.update(1.0)

    _assert_vec3(transform.local_pose().scale, (2.0, 4.0, 8.0))


def test_rotate_tween_slerps_sequence_target_and_preserves_position_and_scale() -> None:
    transform = _Transform(
        GeneralPose3(
            lin=Vec3(4.0, 5.0, 6.0),
            scale=Vec3(2.0, 3.0, 4.0),
        )
    )
    target = Quat.from_axis_angle(Vec3.unit_z(), math.pi)
    non_unit_target = tuple(component * 4.0 for component in target)
    tween = RotateTween(transform, non_unit_target, duration=2.0)

    assert isinstance(tween.target, Quat)
    assert tween.target.norm() == pytest.approx(1.0)
    assert tween.update(1.0) is True
    pose = transform.local_pose()
    _assert_vec3(pose.ang.rotate(Vec3.unit_x()), (0.0, 1.0, 0.0))
    _assert_vec3(pose.lin, (4.0, 5.0, 6.0))
    _assert_vec3(pose.scale, (2.0, 3.0, 4.0))

    assert tween.update(1.0) is False
    _assert_same_rotation(transform.local_pose().ang, target)


def test_rotate_tween_owns_canonical_target_and_uses_shortest_path_for_q_and_minus_q() -> None:
    rotation = Quat.from_axis_angle(Vec3(1.0, 2.0, 3.0), 0.7)
    transform = _Transform(GeneralPose3(ang=rotation))
    target = Quat(-rotation.x, -rotation.y, -rotation.z, -rotation.w)
    tween = RotateTween(transform, target, duration=1.0)
    target.x = 0.0

    tween.update(0.5)

    _assert_same_rotation(transform.local_pose().ang, rotation)


@pytest.mark.parametrize(
    "target",
    [
        (0.0, 0.0, 0.0, 0.0),
        (math.nan, 0.0, 0.0, 1.0),
        (0.0, math.inf, 0.0, 1.0),
    ],
)
def test_rotate_tween_rejects_degenerate_or_non_finite_target(target) -> None:
    with pytest.raises(ValueError, match="finite, non-degenerate quaternion"):
        RotateTween(_Transform(), target, duration=1.0)


def test_rotate_tween_reports_invalid_current_rotation_without_relocating() -> None:
    transform = _Transform(GeneralPose3(ang=Quat(0.0, 0.0, 0.0, 0.0)))
    tween = RotateTween(transform, Quat.identity(), duration=1.0)

    with pytest.raises(ValueError, match="rotation start"):
        tween.update(0.5)

    assert tuple(transform.local_pose().ang) == (0.0, 0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    ("factory", "target"),
    [
        (MoveTween, (math.inf, 0.0, 0.0)),
        (ScaleTween, (1.0, math.nan, 1.0)),
    ],
)
def test_vector_tweens_reject_non_finite_targets(factory, target) -> None:
    with pytest.raises(ValueError, match="must contain only finite values"):
        factory(_Transform(), target, duration=1.0)


@pytest.mark.parametrize(
    ("factory", "target", "component_count"),
    [
        (MoveTween, (1.0, 2.0), 3),
        (MoveTween, (1.0, 2.0, 3.0, 4.0), 3),
        (ScaleTween, (1.0, 2.0), 3),
        (ScaleTween, (1.0, 2.0, 3.0, 4.0), 3),
        (RotateTween, (0.0, 0.0, 1.0), 4),
        (RotateTween, (0.0, 0.0, 0.0, 1.0, 2.0), 4),
    ],
)
def test_transform_tweens_reject_wrong_component_count(
    factory,
    target,
    component_count,
) -> None:
    with pytest.raises(
        ValueError,
        match=rf"must contain exactly {component_count} components",
    ):
        factory(_Transform(), target, duration=1.0)


def test_manager_removes_completed_tweens() -> None:
    transform = _Transform()
    manager = TweenManager()
    manager.add(ScaleTween(transform, 3.0, duration=0.5))

    manager.update(0.5)

    assert manager.count == 0
    _assert_vec3(transform.local_pose().scale, (3.0, 3.0, 3.0))


def test_manager_factories_accept_canonical_math_values() -> None:
    transform = _Transform()
    manager = TweenManager()

    move = manager.move(transform, Vec3(1.0, 2.0, 3.0), duration=1.0)
    rotate = manager.rotate(transform, Quat.identity(), duration=1.0)
    scale = manager.scale(transform, Vec3(2.0, 3.0, 4.0), duration=1.0)

    assert isinstance(move.target, Vec3)
    assert isinstance(rotate.target, Quat)
    assert isinstance(scale.target, Vec3)
