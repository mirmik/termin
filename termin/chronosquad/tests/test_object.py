"""Tests for ObjectOfTimeline."""

import pytest
from termin.chronosquad.core import (
    ObjectOfTimeline,
    Vec3,
    Pose,
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

    def test_lerp(self):
        a = Vec3(0, 0, 0)
        b = Vec3(10, 20, 30)

        mid = a.lerp(b, 0.5)
        assert mid.x == pytest.approx(5)
        assert mid.y == pytest.approx(10)
        assert mid.z == pytest.approx(15)

    def test_distance_to(self):
        a = Vec3(0, 0, 0)
        b = Vec3(3, 4, 0)
        assert a.distance_to(b) == pytest.approx(5.0)

    def test_copy(self):
        v = Vec3(1, 2, 3)
        c = v.copy()
        c.x = 10
        assert v.x == 1


class TestPose:
    def test_identity(self):
        p = Pose.identity()
        assert p.position.x == 0
        assert p.position.y == 0
        assert p.position.z == 0
        assert p.rotation.w == 1

    def test_lerp(self):
        a = Pose(Vec3(0, 0, 0), Quat.identity())
        b = Pose(Vec3(10, 0, 0), Quat.identity())

        mid = a.lerp(b, 0.5)
        assert mid.position.x == pytest.approx(5)


class TestObjectOfTimeline:
    def test_create(self):
        obj = ObjectOfTimeline("Player")
        assert obj.name == "Player"
        assert obj.timeline is None
        assert obj.local_step == 0

    def test_set_position(self):
        obj = ObjectOfTimeline("Player")
        obj.set_position(Vec3(5, 10, 15))

        assert obj.position.x == 5
        assert obj.position.y == 10
        assert obj.position.z == 15

    def test_add_animatronic(self):
        obj = ObjectOfTimeline("Player")
        anim = StaticAnimatronic(0, Pose.identity())
        obj.add_animatronic(anim)

        # Promote to activate
        obj.promote(0)
        assert obj._current_animatronic is anim

    def test_linear_movement(self):
        obj = ObjectOfTimeline("Player")
        move = LinearMoveAnimatronic(
            0, 100,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(10, 0, 0), Quat.identity()),
        )
        obj.add_animatronic(move)

        obj.promote(0)
        assert obj.position.x == pytest.approx(0)

        obj.promote(50)
        assert obj.position.x == pytest.approx(5)

        obj.promote(100)
        assert obj.position.x == pytest.approx(10)

    def test_sequential_animatronics(self):
        obj = ObjectOfTimeline("Player")

        # First move: X from 0 to 5
        move1 = LinearMoveAnimatronic(
            0, 50,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(5, 0, 0), Quat.identity()),
        )

        # Second move: Y from 0 to 5
        move2 = LinearMoveAnimatronic(
            50, 100,
            Pose(Vec3(5, 0, 0), Quat.identity()),
            Pose(Vec3(5, 5, 0), Quat.identity()),
        )

        obj.add_animatronic(move1)
        obj.add_animatronic(move2)

        obj.promote(25)
        assert obj.position.x == pytest.approx(2.5)
        assert obj.position.y == pytest.approx(0)

        obj.promote(75)
        assert obj.position.x == pytest.approx(5)
        assert obj.position.y == pytest.approx(2.5)

    def test_copy(self):
        obj = ObjectOfTimeline("Player")
        obj.set_position(Vec3(5, 10, 15))

        move = LinearMoveAnimatronic(
            0, 100,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(10, 0, 0), Quat.identity()),
        )
        obj.add_animatronic(move)

        copy = obj.copy(None)
        assert copy.name == "Player"
        assert copy.position.x == pytest.approx(5)
        assert len(copy._animatronics) == 1

        # Modifying copy shouldn't affect original
        copy.set_position(Vec3(0, 0, 0))
        assert obj.position.x == pytest.approx(5)

    def test_drop_to_current(self):
        obj = ObjectOfTimeline("Player")

        # Add animatronic starting in future
        move = LinearMoveAnimatronic(
            100, 200,
            Pose(Vec3(0, 0, 0), Quat.identity()),
            Pose(Vec3(10, 0, 0), Quat.identity()),
        )
        obj.add_animatronic(move)

        obj.promote(50)
        obj.drop_to_current()

        # Future animatronic should be removed
        assert len(obj._animatronics) == 0
