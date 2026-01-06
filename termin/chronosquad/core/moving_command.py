"""
MovingCommand - command for moving an actor to a target position.

Simplified version without pathfinding - creates a linear movement animatronic.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING

from termin.geombase import Vec3, Quat, Pose3

from .actor_command import ActorCommand
from .animatronic import LinearMoveAnimatronic, AnimationType
from .timeline import GAME_FREQUENCY

if TYPE_CHECKING:
    from .object_of_timeline import ObjectOfTimeline
    from .timeline import Timeline
    from .command_buffer import CommandBuffer


def _look_rotation(direction: Vec3) -> Quat:
    """
    Create a rotation that looks in the given direction.

    Convention: Forward = +Y, Up = +Z.
    Returns identity if direction is zero.
    """
    length = direction.norm()
    if length < 0.001:
        return Quat.identity()

    # Normalize direction (in XY plane)
    dx = direction.x / length
    dy = direction.y / length

    # Calculate angle from +Y axis (forward direction)
    # atan2(dx, dy) gives angle from +Y
    angle = math.atan2(dx, dy)

    # Rotation around Z axis
    return Quat.from_axis_angle(Vec3(0, 0, 1), angle)


class WalkingType(Enum):
    """Type of walking animation/speed."""
    WALK = "walk"
    RUN = "run"
    CROUCH = "crouch"
    SPRINT = "sprint"


# Speed in units per second for each walking type
WALKING_SPEEDS = {
    WalkingType.WALK: 1.5,
    WalkingType.RUN: 5.0,
    WalkingType.CROUCH: 0.8,
    WalkingType.SPRINT: 8.0,
}


class MovingCommand(ActorCommand):
    """
    Command that moves an actor to a target position.

    Creates a LinearMoveAnimatronic when first executed.
    Completes when the actor reaches the target or animatronic finishes.
    """

    def __init__(
        self,
        target_position: Vec3,
        walking_type: WalkingType,
        start_step: int,
    ):
        super().__init__(start_step)
        self._target_position = target_position
        self._walking_type = walking_type

    @property
    def target_position(self) -> Vec3:
        return self._target_position

    @property
    def walking_type(self) -> WalkingType:
        return self._walking_type

    def execute_first_time(self, actor: ObjectOfTimeline, timeline: Timeline) -> bool:
        """
        Create movement animatronic.

        Called when command first becomes active.
        """
        if timeline.is_past:
            actor.drop_to_current()

        # Get current position and calculate path
        current_pos = actor.current_position()
        target = self._target_position

        # Calculate direction and distance
        dx = target.x - current_pos.x
        dy = target.y - current_pos.y
        dz = target.z - current_pos.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        if distance < 0.01:
            return True  # Already at target

        # Calculate target rotation (look in movement direction)
        direction = Vec3(dx, dy, 0)  # Horizontal direction only
        if direction.norm() > 0.001:
            target_rot = _look_rotation(direction)
        else:
            target_rot = actor.local_rotation

        # Calculate duration based on walking speed
        speed = WALKING_SPEEDS.get(self._walking_type, 5.0)
        duration_seconds = distance / speed
        duration_steps = max(1, int(duration_seconds * GAME_FREQUENCY))

        # Create animatronic
        start_pose = Pose3(actor.local_rotation, current_pos)
        end_pose = Pose3(target_rot, target)

        end_step = self._start_step + duration_steps
        anim = LinearMoveAnimatronic(self._start_step, end_step, start_pose, end_pose)

        # Set animation type based on walking type
        if self._walking_type == WalkingType.RUN:
            anim.set_animation_type(AnimationType.RUN)
        elif self._walking_type == WalkingType.CROUCH:
            anim.set_animation_type(AnimationType.CROUCH_WALK)
        else:
            anim.set_animation_type(AnimationType.WALK)

        actor.add_animatronic(anim)

        return False  # Not finished yet

    def execute(self, actor: ObjectOfTimeline, timeline: Timeline) -> bool:
        """
        Check if movement is complete.

        Returns True when actor reaches target.
        """
        # Check if animatronic is done
        current_anim = actor.current_animatronic
        if current_anim is None:
            return True

        if isinstance(current_anim, LinearMoveAnimatronic):
            if current_anim.finish_step <= actor.local_step:
                return True

        # Check distance to target
        current_pos = actor.current_position()
        dx = self._target_position.x - current_pos.x
        dy = self._target_position.y - current_pos.y
        dz = self._target_position.z - current_pos.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        if distance < 0.05:  # Allowed error
            return True

        return False

    def cancel_handler(self, command_buffer: CommandBuffer) -> None:
        """Called when command is cancelled."""
        pass

    def clone(self) -> MovingCommand:
        """Create a copy of this command."""
        cmd = MovingCommand(
            Vec3(self._target_position.x, self._target_position.y, self._target_position.z),
            self._walking_type,
            self._start_step,
        )
        cmd._finish_step = self._finish_step
        return cmd

    def hash_code(self) -> int:
        """Hash for deduplication."""
        return hash((
            "MovingCommand",
            self._start_step,
            round(self._target_position.x, 3),
            round(self._target_position.y, 3),
            round(self._target_position.z, 3),
            self._walking_type,
        ))

    def info(self) -> str:
        return (
            f"MovingCommand(start={self._start_step}, "
            f"target={self._target_position}, type={self._walking_type.value})"
        )
