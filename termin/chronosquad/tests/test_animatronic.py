"""Tests for Animatronics."""

import pytest
from termin.chronosquad.core import (
    Vec3,
    Pose,
    Quat,
    StaticAnimatronic,
    LinearMoveAnimatronic,
    CubicMoveAnimatronic,
    WaypointAnimatronic,
)


class TestStaticAnimatronic:
    def test_evaluate(self):
        pose = Pose(Vec3(5, 10, 15), Quat.identity())
        anim = StaticAnimatronic(0, pose)

        result = anim.evaluate(0)
        assert result.position.x == pytest.approx(5)
        assert result.position.y == pytest.approx(10)

        result = anim.evaluate(1000)
        assert result.position.x == pytest.approx(5)

    def test_copy(self):
        pose = Pose(Vec3(5, 10, 15), Quat.identity())
        anim = StaticAnimatronic(0, pose)
        copy = anim.copy()

        assert copy.start_step == 0
        assert copy.pose.position.x == pytest.approx(5)


class TestLinearMoveAnimatronic:
    def test_evaluate_start(self):
        anim = LinearMoveAnimatronic(
            0, 100,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(10, 0, 0), Quat.identity()),
        )

        result = anim.evaluate(0)
        assert result.position.x == pytest.approx(0)

    def test_evaluate_middle(self):
        anim = LinearMoveAnimatronic(
            0, 100,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(10, 0, 0), Quat.identity()),
        )

        result = anim.evaluate(50)
        assert result.position.x == pytest.approx(5)

    def test_evaluate_end(self):
        anim = LinearMoveAnimatronic(
            0, 100,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(10, 0, 0), Quat.identity()),
        )

        result = anim.evaluate(100)
        assert result.position.x == pytest.approx(10)

    def test_is_active_at(self):
        anim = LinearMoveAnimatronic(
            10, 20,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(10, 0, 0), Quat.identity()),
        )

        assert not anim.is_active_at(9)
        assert anim.is_active_at(10)
        assert anim.is_active_at(15)
        assert anim.is_active_at(20)
        assert not anim.is_active_at(21)

    def test_progress(self):
        anim = LinearMoveAnimatronic(
            0, 100,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(10, 0, 0), Quat.identity()),
        )

        assert anim.progress(0) == pytest.approx(0.0)
        assert anim.progress(50) == pytest.approx(0.5)
        assert anim.progress(100) == pytest.approx(1.0)

    def test_copy(self):
        anim = LinearMoveAnimatronic(
            0, 100,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(10, 0, 0), Quat.identity()),
        )
        copy = anim.copy()

        assert copy.start_step == 0
        assert copy.finish_step == 100
        assert copy.start_pose.position.x == pytest.approx(0)
        assert copy.end_pose.position.x == pytest.approx(10)


class TestCubicMoveAnimatronic:
    def test_smooth_acceleration(self):
        anim = CubicMoveAnimatronic(
            0, 100,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(10, 0, 0), Quat.identity()),
        )

        # At start, should accelerate slowly
        pos_10 = anim.evaluate(10).position.x
        pos_20 = anim.evaluate(20).position.x

        # Early velocity should be lower
        early_velocity = pos_10 / 10
        later_velocity = (pos_20 - pos_10) / 10
        assert later_velocity > early_velocity

    def test_smooth_deceleration(self):
        anim = CubicMoveAnimatronic(
            0, 100,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(10, 0, 0), Quat.identity()),
        )

        # At end, should decelerate
        pos_80 = anim.evaluate(80).position.x
        pos_90 = anim.evaluate(90).position.x
        pos_100 = anim.evaluate(100).position.x

        late_velocity = (pos_100 - pos_90) / 10
        mid_velocity = (pos_90 - pos_80) / 10
        assert late_velocity < mid_velocity

    def test_endpoints(self):
        anim = CubicMoveAnimatronic(
            0, 100,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(10, 0, 0), Quat.identity()),
        )

        assert anim.evaluate(0).position.x == pytest.approx(0)
        assert anim.evaluate(100).position.x == pytest.approx(10)


class TestWaypointAnimatronic:
    def test_single_waypoint(self):
        anim = WaypointAnimatronic(0, [
            (0, Pose(Vec3(5, 0, 0), Quat.identity())),
        ])

        result = anim.evaluate(0)
        assert result.position.x == pytest.approx(5)

    def test_two_waypoints(self):
        anim = WaypointAnimatronic(0, [
            (0, Pose(Vec3(0, 0, 0), Quat.identity())),
            (100, Pose(Vec3(10, 0, 0), Quat.identity())),
        ])

        assert anim.evaluate(0).position.x == pytest.approx(0)
        assert anim.evaluate(50).position.x == pytest.approx(5)
        assert anim.evaluate(100).position.x == pytest.approx(10)

    def test_multiple_waypoints(self):
        anim = WaypointAnimatronic(0, [
            (0, Pose(Vec3(0, 0, 0), Quat.identity())),
            (50, Pose(Vec3(5, 0, 0), Quat.identity())),
            (100, Pose(Vec3(5, 5, 0), Quat.identity())),
        ])

        # First segment
        assert anim.evaluate(25).position.x == pytest.approx(2.5)
        assert anim.evaluate(25).position.y == pytest.approx(0)

        # At waypoint
        assert anim.evaluate(50).position.x == pytest.approx(5)
        assert anim.evaluate(50).position.y == pytest.approx(0)

        # Second segment
        assert anim.evaluate(75).position.x == pytest.approx(5)
        assert anim.evaluate(75).position.y == pytest.approx(2.5)

    def test_unsorted_waypoints(self):
        # Waypoints should be sorted internally
        anim = WaypointAnimatronic(0, [
            (100, Pose(Vec3(10, 0, 0), Quat.identity())),
            (0, Pose(Vec3(0, 0, 0), Quat.identity())),
            (50, Pose(Vec3(5, 0, 0), Quat.identity())),
        ])

        assert anim.evaluate(25).position.x == pytest.approx(2.5)
        assert anim.evaluate(75).position.x == pytest.approx(7.5)

    def test_empty_waypoints_raises(self):
        with pytest.raises(ValueError):
            WaypointAnimatronic(0, [])

    def test_copy(self):
        anim = WaypointAnimatronic(0, [
            (0, Pose(Vec3(0, 0, 0), Quat.identity())),
            (100, Pose(Vec3(10, 0, 0), Quat.identity())),
        ])
        copy = anim.copy()

        assert len(copy.waypoints) == 2
        assert copy.evaluate(50).position.x == pytest.approx(5)
