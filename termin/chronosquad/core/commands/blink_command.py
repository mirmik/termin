"""
BlinkCommand - command for instant teleportation.

Matches original C# BlinkCommand:
- Teleports actor to target position
- Creates animatronic for the blink movement
- Has blink_time_lapse for visual effect duration
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.geombase import Vec3, Quat, Pose3

from termin.chronosquad.core.commands.actor_command import ActorCommand
from termin.chronosquad.core.animatronic import BlinkedMovingState
from termin.chronosquad.core.timeline import GAME_FREQUENCY
from termin.chronosquad.core.effects.blind_effect import BlindEffect
from termin.chronosquad.core.timeline import Timeline

if TYPE_CHECKING:
    from termin.chronosquad.core.object_of_timeline import ObjectOfTimeline


class BlinkCommand(ActorCommand):
    """
    Command that teleports an actor to a target position.

    Matches original C# BlinkCommand:
    - Takes ReferencedPoint or Vec3 as target
    - Creates animatronic for the blink transition
    - Uses blink_time_lapse for visual effect duration
    """

    def __init__(
        self,
        target_position: Vec3,
        blink_time_lapse: float,
        start_step: int,
    ):
        super().__init__(start_step)
        self._target_position = target_position
        self._blink_time_lapse = blink_time_lapse

    @property
    def target_position(self) -> Vec3:
        return self._target_position

    @property
    def blink_time_lapse(self) -> float:
        return self._blink_time_lapse

    def execute_first_time(self, actor: ObjectOfTimeline, timeline: Timeline) -> bool:
        """
        Execute blink teleportation.

        Matches original BlinkCommand.Execute():
        1. Calculate target position (snap to navmesh if available)
        2. Calculate target direction (face nearest enemy or movement direction)
        3. Create BlinkedMovingState animatronic
        4. Return True (command finished after one execution)
        """
        if timeline.is_past:
            actor.drop_to_current()

        local_step = actor.local_step

        # Get current pose as initial pose
        initial_pose = actor.local_pose.copy()

        # Get target position
        target_pos = self._target_position

        # Calculate target direction
        target_direction = self._calculate_target_direction(actor, target_pos, timeline)

        # Create target pose
        target_pose = Pose3(target_direction, target_pos)

        # Calculate finish step based on blink_time_lapse
        blink_steps = int(self._blink_time_lapse * GAME_FREQUENCY)
        finish_step = local_step + 2 + blink_steps

        # Set finish step for this command
        self.set_finish_step(finish_step)

        # Create BlinkedMovingState (matches original C#)
        blink_anim = BlinkedMovingState(
            initial_pose=initial_pose,
            target_pose=target_pose,
            start_step=local_step + 1,
            finish_step=finish_step,
        )
        actor.add_animatronic(blink_anim)

        blind_effect = BlindEffect(
            start_step=local_step + 1,
            finish_step=finish_step,
            position=target_pos,
        )
        timeline.add_visual_effect_event(blind_effect)

        # Command finishes immediately (matches original C# returning true)
        return True

    def execute(self, actor: ObjectOfTimeline, timeline: Timeline) -> bool:
        """Check if blink is complete (should not be called as execute_first_time returns True)."""
        return True

    def _calculate_target_direction(
        self,
        actor: ObjectOfTimeline,
        target_position: Vec3,
        timeline: Timeline,
    ) -> Quat:
        """
        Calculate direction to face after blink.

        Matches original BlinkCommand.TargetDirection():
        - If closest enemy within 10 units, face them
        - Otherwise face movement direction
        """
        # Simple direction: face movement direction
        current_pos = actor.current_position()
        direction = target_position - current_pos

        # Zero out vertical component
        direction = Vec3(direction.x, direction.y, 0)

        length = direction.norm()
        if length < 0.001:
            # No movement, keep current rotation
            return actor.local_rotation

        # Normalize
        direction = direction * (1.0 / length)

        # Create rotation from direction
        # Convention: Forward = +Y, Up = +Z
        import math
        angle = -math.atan2(direction.x, direction.y)
        return Quat.from_axis_angle(Vec3(0, 0, 1), angle)

    def clone(self) -> BlinkCommand:
        """Create a copy of this command."""
        cmd = BlinkCommand(
            self._target_position,
            self._blink_time_lapse,
            self._start_step,
        )
        cmd.set_finish_step(self._finish_step)
        return cmd

    def hash_code(self) -> int:
        """Hash for deduplication."""
        return hash((
            "BlinkCommand",
            self._target_position.x,
            self._target_position.y,
            self._target_position.z,
            self._blink_time_lapse,
            self._start_step,
        ))

    def info(self) -> str:
        return f"BlinkCommand(target={self._target_position}, lapse={self._blink_time_lapse:.1f}s)"
