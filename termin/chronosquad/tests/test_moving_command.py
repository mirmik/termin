"""Tests for MovingCommand and command interruption."""

import math
import pytest
from termin.chronosquad.core import (
    Timeline,
    ObjectOfTimeline,
    Vec3,
    Quat,
    Pose3,
    GAME_FREQUENCY,
)
from termin.chronosquad.core.commands.moving_command import MovingCommand, WalkingType, _look_rotation


class TestLookRotation:
    """Tests for the _look_rotation helper function."""

    def test_look_positive_y(self):
        """Looking along +Y should give identity rotation (forward is +Y)."""
        rot = _look_rotation(Vec3(0, 1, 0))
        # Identity quaternion or close to it
        forward = rot.rotate(Vec3(0, 1, 0))
        assert forward.x == pytest.approx(0, abs=0.001)
        assert forward.y == pytest.approx(1, abs=0.001)

    def test_look_positive_x(self):
        """Looking along +X should rotate 90 degrees around Z."""
        rot = _look_rotation(Vec3(1, 0, 0))
        forward = rot.rotate(Vec3(0, 1, 0))
        assert forward.x == pytest.approx(1, abs=0.001)
        assert forward.y == pytest.approx(0, abs=0.001)

    def test_look_negative_y(self):
        """Looking along -Y should rotate 180 degrees around Z."""
        rot = _look_rotation(Vec3(0, -1, 0))
        forward = rot.rotate(Vec3(0, 1, 0))
        assert forward.x == pytest.approx(0, abs=0.001)
        assert forward.y == pytest.approx(-1, abs=0.001)

    def test_look_negative_x(self):
        """Looking along -X should rotate -90 degrees around Z."""
        rot = _look_rotation(Vec3(-1, 0, 0))
        forward = rot.rotate(Vec3(0, 1, 0))
        assert forward.x == pytest.approx(-1, abs=0.001)
        assert forward.y == pytest.approx(0, abs=0.001)

    def test_look_diagonal(self):
        """Looking diagonally should rotate 45 degrees."""
        rot = _look_rotation(Vec3(1, 1, 0))
        forward = rot.rotate(Vec3(0, 1, 0))
        # Should point toward (1, 1, 0) normalized
        expected = 1.0 / math.sqrt(2)
        assert forward.x == pytest.approx(expected, abs=0.01)
        assert forward.y == pytest.approx(expected, abs=0.01)

    def test_zero_direction_returns_identity(self):
        """Zero direction should return identity."""
        rot = _look_rotation(Vec3(0, 0, 0))
        assert rot.x == pytest.approx(0)
        assert rot.y == pytest.approx(0)
        assert rot.z == pytest.approx(0)
        assert rot.w == pytest.approx(1)


class TestMovingCommandPosition:
    """Tests for position behavior during movement."""

    def test_basic_movement(self):
        """Object should move from start to target."""
        tl = Timeline()
        obj = ObjectOfTimeline('test')
        tl.add_object(obj)
        obj.set_local_position(Vec3(0, 0, 0))

        cmd = MovingCommand(Vec3(10, 0, 0), WalkingType.RUN, 0)
        obj.command_buffer.add_command(cmd)

        # Advance to end
        for step in range(300):
            tl.promote(step)

        pos = obj.current_position()
        assert pos.x == pytest.approx(10, abs=0.1)
        assert pos.y == pytest.approx(0, abs=0.1)

    def test_position_continuity_on_interrupt(self):
        """Position should not jump when command is interrupted."""
        tl = Timeline()
        obj = ObjectOfTimeline('test')
        tl.add_object(obj)
        obj.set_local_position(Vec3(0, 0, 0))

        # First command: move to (10, 0, 0)
        cmd1 = MovingCommand(Vec3(10, 0, 0), WalkingType.RUN, 0)
        obj.command_buffer.add_command(cmd1)

        # Advance part way
        for step in range(30):
            tl.promote(step)

        pos_before_interrupt = obj.current_position()

        # Second command: change direction
        cmd2 = MovingCommand(Vec3(0, 10, 0), WalkingType.RUN, 30)
        obj.command_buffer.add_command(cmd2)

        # Advance one more step
        tl.promote(30)
        pos_after_interrupt = obj.current_position()

        # Position should be continuous (no teleport)
        dist = math.sqrt(
            (pos_after_interrupt.x - pos_before_interrupt.x) ** 2 +
            (pos_after_interrupt.y - pos_before_interrupt.y) ** 2 +
            (pos_after_interrupt.z - pos_before_interrupt.z) ** 2
        )
        # Allow small movement from one frame of new animatronic
        max_frame_movement = 5.0 / GAME_FREQUENCY  # RUN speed = 5 m/s
        assert dist < max_frame_movement * 2, f"Position jumped {dist} units"

    def test_no_teleport_on_multiple_interrupts(self):
        """Multiple interrupts should all maintain position continuity."""
        tl = Timeline()
        obj = ObjectOfTimeline('test')
        tl.add_object(obj)
        obj.set_local_position(Vec3(0, 0, 0))

        targets = [
            (30, Vec3(10, 0, 0)),
            (60, Vec3(10, 10, 0)),
            (90, Vec3(0, 10, 0)),
            (120, Vec3(0, 0, 0)),
        ]

        # Initial command
        cmd = MovingCommand(targets[0][1], WalkingType.RUN, 0)
        obj.command_buffer.add_command(cmd)

        prev_pos = Vec3(0, 0, 0)
        max_jump = 0.0

        for step in range(150):
            tl.promote(step)

            # Add interrupt commands at specified steps
            for interrupt_step, target in targets:
                if step == interrupt_step:
                    cmd = MovingCommand(target, WalkingType.RUN, step)
                    obj.command_buffer.add_command(cmd)

            # Check position continuity
            pos = obj.current_position()
            dist = math.sqrt(
                (pos.x - prev_pos.x) ** 2 +
                (pos.y - prev_pos.y) ** 2 +
                (pos.z - prev_pos.z) ** 2
            )
            max_jump = max(max_jump, dist)
            prev_pos = Vec3(pos.x, pos.y, pos.z)

        # Max frame-to-frame movement should be bounded by speed
        max_expected = 8.0 / GAME_FREQUENCY * 1.5  # SPRINT speed with margin
        assert max_jump < max_expected, f"Max position jump was {max_jump}"


class TestMovingCommandRotation:
    """Tests for rotation/orientation during movement."""

    def test_faces_movement_direction(self):
        """Character should face the direction of movement."""
        tl = Timeline()
        obj = ObjectOfTimeline('test')
        tl.add_object(obj)
        obj.set_local_position(Vec3(0, 0, 0))
        obj.set_local_rotation(Quat.identity())

        # Move along +X
        cmd = MovingCommand(Vec3(10, 0, 0), WalkingType.RUN, 0)
        obj.command_buffer.add_command(cmd)

        # Advance past rotation phase
        for step in range(60):
            tl.promote(step)

        # Forward direction should point toward +X
        forward = obj.local_rotation.rotate(Vec3(0, 1, 0))
        assert forward.x == pytest.approx(1, abs=0.1), f"Forward.x = {forward.x}"
        assert forward.y == pytest.approx(0, abs=0.1), f"Forward.y = {forward.y}"

    def test_faces_negative_y(self):
        """Character should correctly face -Y direction."""
        tl = Timeline()
        obj = ObjectOfTimeline('test')
        tl.add_object(obj)
        obj.set_local_position(Vec3(0, 0, 0))
        obj.set_local_rotation(Quat.identity())

        # Move along -Y
        cmd = MovingCommand(Vec3(0, -10, 0), WalkingType.RUN, 0)
        obj.command_buffer.add_command(cmd)

        for step in range(60):
            tl.promote(step)

        forward = obj.local_rotation.rotate(Vec3(0, 1, 0))
        assert forward.x == pytest.approx(0, abs=0.1)
        assert forward.y == pytest.approx(-1, abs=0.1)

    def test_faces_diagonal(self):
        """Character should correctly face diagonal direction."""
        tl = Timeline()
        obj = ObjectOfTimeline('test')
        tl.add_object(obj)
        obj.set_local_position(Vec3(0, 0, 0))
        obj.set_local_rotation(Quat.identity())

        # Move diagonally
        cmd = MovingCommand(Vec3(10, 10, 0), WalkingType.RUN, 0)
        obj.command_buffer.add_command(cmd)

        for step in range(60):
            tl.promote(step)

        forward = obj.local_rotation.rotate(Vec3(0, 1, 0))
        expected = 1.0 / math.sqrt(2)
        assert forward.x == pytest.approx(expected, abs=0.1)
        assert forward.y == pytest.approx(expected, abs=0.1)

    def test_rotation_not_sideways(self):
        """Character should not run sideways - forward should match movement."""
        tl = Timeline()
        obj = ObjectOfTimeline('test')
        tl.add_object(obj)
        obj.set_local_position(Vec3(0, 0, 0))
        obj.set_local_rotation(Quat.identity())

        # Move along +X (perpendicular to initial forward +Y)
        cmd = MovingCommand(Vec3(10, 0, 0), WalkingType.RUN, 0)
        obj.command_buffer.add_command(cmd)

        # Check multiple frames during movement
        sideways_frames = 0
        for step in range(120):
            tl.promote(step)

            pos = obj.current_position()
            forward = obj.local_rotation.rotate(Vec3(0, 1, 0))

            # Calculate velocity direction
            if step > 0:
                vel_x = pos.x - prev_pos.x
                vel_y = pos.y - prev_pos.y
                vel_len = math.sqrt(vel_x * vel_x + vel_y * vel_y)

                if vel_len > 0.001:
                    # Normalize velocity
                    vel_x /= vel_len
                    vel_y /= vel_len

                    # Check if forward aligns with velocity (dot product close to 1)
                    dot = forward.x * vel_x + forward.y * vel_y

                    # Allow some rotation phase at start, but mostly should be aligned
                    if step > 30 and dot < 0.7:
                        sideways_frames += 1

            prev_pos = Vec3(pos.x, pos.y, pos.z)

        # Most frames should not be sideways
        assert sideways_frames < 10, f"Character ran sideways for {sideways_frames} frames"


class TestAnimatronicSelection:
    """Tests for correct animatronic selection when multiple exist."""

    def test_selects_latest_animatronic(self):
        """Should select the animatronic with highest start_step <= current_step."""
        tl = Timeline()
        obj = ObjectOfTimeline('test')
        tl.add_object(obj)
        obj.set_local_position(Vec3(0, 0, 0))

        # First command at step 0
        cmd1 = MovingCommand(Vec3(10, 0, 0), WalkingType.RUN, 0)
        obj.command_buffer.add_command(cmd1)

        for step in range(30):
            tl.promote(step)

        # Second command at step 30
        cmd2 = MovingCommand(Vec3(0, 10, 0), WalkingType.RUN, 30)
        obj.command_buffer.add_command(cmd2)

        tl.promote(30)

        # Current animatronic should be the second one
        assert obj._current_animatronic is not None
        assert obj._current_animatronic.start_step == 30

    def test_old_animatronics_preserved(self):
        """Old animatronics should be kept for reverse playback."""
        tl = Timeline()
        obj = ObjectOfTimeline('test')
        tl.add_object(obj)
        obj.set_local_position(Vec3(0, 0, 0))

        # First command
        cmd1 = MovingCommand(Vec3(10, 0, 0), WalkingType.RUN, 0)
        obj.command_buffer.add_command(cmd1)

        for step in range(30):
            tl.promote(step)

        # Second command
        cmd2 = MovingCommand(Vec3(0, 10, 0), WalkingType.RUN, 30)
        obj.command_buffer.add_command(cmd2)

        tl.promote(30)

        # Both animatronics should exist
        assert len(obj._animatronics) == 2
        assert obj._animatronics[0].start_step == 0
        assert obj._animatronics[1].start_step == 30
