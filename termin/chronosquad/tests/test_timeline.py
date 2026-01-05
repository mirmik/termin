"""Tests for Timeline."""

import pytest
from termin.chronosquad.core import (
    Timeline,
    ObjectOfTimeline,
    Vec3,
    Pose,
    LinearMoveAnimatronic,
    GAME_FREQUENCY,
)


class TestTimeline:
    def test_create(self):
        tl = Timeline("Test")
        assert tl.name == "Test"
        assert tl.current_step == 0
        assert tl.current_time == 0.0
        assert len(tl.objects) == 0

    def test_add_object(self):
        tl = Timeline("Test")
        obj = ObjectOfTimeline("Player")
        tl.add_object(obj)

        assert len(tl.objects) == 1
        assert tl.get_object("Player") is obj
        assert tl.has_object("Player")
        assert obj.timeline is tl

    def test_add_duplicate_object_raises(self):
        tl = Timeline("Test")
        obj1 = ObjectOfTimeline("Player")
        obj2 = ObjectOfTimeline("Player")

        tl.add_object(obj1)
        with pytest.raises(ValueError):
            tl.add_object(obj2)

    def test_remove_object(self):
        tl = Timeline("Test")
        obj = ObjectOfTimeline("Player")
        tl.add_object(obj)
        tl.remove_object(obj)

        assert len(tl.objects) == 0
        assert tl.get_object("Player") is None
        assert obj.timeline is None

    def test_promote_forward(self):
        tl = Timeline("Test")
        tl.promote(100)

        assert tl.current_step == 100
        assert tl.current_time == pytest.approx(1.0)  # 100 steps / 100 freq

    def test_promote_backward(self):
        tl = Timeline("Test")
        tl.promote(100)
        tl.promote(50)

        assert tl.current_step == 50
        assert tl.current_time == pytest.approx(0.5)

    def test_promote_delta(self):
        tl = Timeline("Test")
        tl.promote_delta(1.0)  # 1 second

        assert tl.current_step == int(GAME_FREQUENCY)

    def test_is_present_past(self):
        tl = Timeline("Test")
        tl.promote(100)

        assert tl.is_present()
        assert not tl.is_past()

        tl.promote(50)
        assert tl.is_past()
        assert not tl.is_present()

    def test_drop_to_current(self):
        tl = Timeline("Test")
        obj = ObjectOfTimeline("Player")
        tl.add_object(obj)

        # Add animatronic
        move = LinearMoveAnimatronic(
            0, 100,
            Pose(Vec3(0, 0, 0), obj.pose.rotation),
            Pose(Vec3(10, 0, 0), obj.pose.rotation),
        )
        obj.add_animatronic(move)

        # Go to step 50 and drop
        tl.promote(50)
        tl.drop_to_current()

        # Now step 50 should be "present"
        assert tl.is_present()

    def test_copy(self):
        tl = Timeline("Main")
        obj = ObjectOfTimeline("Player")
        obj.set_position(Vec3(5, 0, 0))
        tl.add_object(obj)
        tl.promote(50)

        # Create copy
        copy = tl.copy("Branch")

        assert copy.name == "Branch"
        assert copy.current_step == 50
        assert len(copy.objects) == 1

        copy_obj = copy.get_object("Player")
        assert copy_obj is not obj
        assert copy_obj.position.x == pytest.approx(5.0)

    def test_copy_independence(self):
        tl = Timeline("Main")
        obj = ObjectOfTimeline("Player")
        tl.add_object(obj)

        move = LinearMoveAnimatronic(
            0, 100,
            Pose(Vec3(0, 0, 0), obj.pose.rotation),
            Pose(Vec3(10, 0, 0), obj.pose.rotation),
        )
        obj.add_animatronic(move)

        tl.promote(50)
        copy = tl.copy("Branch")

        # Move timelines independently
        tl.promote(100)
        copy.promote(0)

        main_obj = tl.get_object("Player")
        copy_obj = copy.get_object("Player")

        assert main_obj.position.x == pytest.approx(10.0)
        assert copy_obj.position.x == pytest.approx(0.0)

    def test_info(self):
        tl = Timeline("Test")
        obj = ObjectOfTimeline("Player")
        tl.add_object(obj)
        tl.promote(50)

        info = tl.info()
        assert "Test" in info
        assert "50" in info
        assert "Objects: 1" in info
