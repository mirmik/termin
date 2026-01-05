"""Tests for ObjectOfTimeline."""

import pytest
from termin.chronosquad.core import (
    ObjectOfTimeline,
    Vec3,
    Pose3,
    Quat,
    LinearMoveAnimatronic,
    CubicMoveAnimatronic,
    StaticAnimatronic,
)


class TestVec3:
    def test_create(self):
        v = Vec3(1, 2, 3)
        assert v.x == 1
        assert v.y == 2
        assert v.z == 3

    def test_add(self):
        a = Vec3(1, 2, 3)
        b = Vec3(4, 5, 6)
        c = a + b
        assert c.x == 5
        assert c.y == 7
        assert c.z == 9

    def test_sub(self):
        a = Vec3(4, 5, 6)
        b = Vec3(1, 2, 3)
        c = a - b
        assert c.x == 3
        assert c.y == 3
        assert c.z == 3

    def test_mul(self):
        v = Vec3(1, 2, 3)
        r = v * 2
        assert r.x == 2
        assert r.y == 4
        assert r.z == 6


class TestPose3:
    def test_identity(self):
        p = Pose3.identity()
        assert p.lin.x == 0
        assert p.lin.y == 0
        assert p.lin.z == 0
        assert p.ang.w == 1

    def test_lerp(self):
        a = Pose3(Quat.identity(), Vec3(0, 0, 0))
        b = Pose3(Quat.identity(), Vec3(10, 0, 0))

        mid = Pose3.lerp(a, b, 0.5)
        assert mid.lin.x == pytest.approx(5)


class TestObjectOfTimeline:
    def test_create(self):
        obj = ObjectOfTimeline("Player")
        assert obj.name == "Player"
        assert obj.timeline is None
        assert obj.local_step == 0

    def test_set_position(self):
        obj = ObjectOfTimeline("Player")
        obj.set_local_position(Vec3(5, 10, 15))

        assert obj.local_position.x == 5
        assert obj.local_position.y == 10
        assert obj.local_position.z == 15

    def test_add_animatronic(self):
        obj = ObjectOfTimeline("Player")
        anim = StaticAnimatronic(0, Pose3.identity())
        obj.add_animatronic(anim)

        # Promote to activate
        obj.promote(0)
        assert obj._current_animatronic is anim

    def test_linear_movement(self):
        obj = ObjectOfTimeline("Player")
        move = LinearMoveAnimatronic(
            0, 100,
            Pose3(Quat.identity(), Vec3(0, 0, 0)),
            Pose3(Quat.identity(), Vec3(10, 0, 0)),
        )
        obj.add_animatronic(move)

        obj.promote(0)
        assert obj.local_position.x == pytest.approx(0)

        obj.promote(50)
        assert obj.local_position.x == pytest.approx(5)

        obj.promote(100)
        assert obj.local_position.x == pytest.approx(10)

    def test_sequential_animatronics(self):
        obj = ObjectOfTimeline("Player")

        # First move: X from 0 to 5
        move1 = LinearMoveAnimatronic(
            0, 50,
            Pose3(Quat.identity(), Vec3(0, 0, 0)),
            Pose3(Quat.identity(), Vec3(5, 0, 0)),
        )

        # Second move: Y from 0 to 5
        move2 = LinearMoveAnimatronic(
            50, 100,
            Pose3(Quat.identity(), Vec3(5, 0, 0)),
            Pose3(Quat.identity(), Vec3(5, 5, 0)),
        )

        obj.add_animatronic(move1)
        obj.add_animatronic(move2)

        obj.promote(25)
        assert obj.local_position.x == pytest.approx(2.5)
        assert obj.local_position.y == pytest.approx(0)

        obj.promote(75)
        assert obj.local_position.x == pytest.approx(5)
        assert obj.local_position.y == pytest.approx(2.5)

    def test_copy(self):
        obj = ObjectOfTimeline("Player")
        obj.set_local_position(Vec3(5, 10, 15))

        move = LinearMoveAnimatronic(
            0, 100,
            Pose3(Quat.identity(), Vec3(0, 0, 0)),
            Pose3(Quat.identity(), Vec3(10, 0, 0)),
        )
        obj.add_animatronic(move)

        copy = obj.copy(None)
        assert copy.name == "Player"
        assert copy.local_position.x == pytest.approx(5)
        assert len(copy._animatronics) == 1

        # Modifying copy shouldn't affect original
        copy.set_local_position(Vec3(0, 0, 0))
        assert obj.local_position.x == pytest.approx(5)

    def test_drop_to_current(self):
        obj = ObjectOfTimeline("Player")

        # Add animatronic starting in future
        move = LinearMoveAnimatronic(
            100, 200,
            Pose3(Quat.identity(), Vec3(0, 0, 0)),
            Pose3(Quat.identity(), Vec3(10, 0, 0)),
        )
        obj.add_animatronic(move)

        obj.promote(50)
        obj.drop_to_current()

        # Future animatronic should be removed
        assert len(obj._animatronics) == 0
