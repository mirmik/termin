"""
BlinkAbility - instant teleportation ability.

Matches original C# BlinkAbility:
- Instantly teleports actor to target position
- Has cooldown
- Uses ReferencedPoint for time-stable positioning
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.geombase import Vec3, Pose3

from .ability import Ability
from termin.chronosquad.core.animatronic import StaticAnimatronic

if TYPE_CHECKING:
    from termin.chronosquad.core.object_of_timeline import ObjectOfTimeline
    from termin.chronosquad.core.timeline import Timeline
    from termin.chronosquad.core.ability.ability import AbilityList


class BlinkAbility(Ability):
    """
    Instant teleportation ability.

    Teleports the actor to the target position instantly.
    Creates a StaticAnimatronic at the destination.
    """

    def __init__(self, blink_time_lapse: float = 0.5, cooldown: float = 3.0):
        """
        Initialize blink ability.

        Args:
            blink_time_lapse: Visual effect duration (not used in core logic)
            cooldown: Cooldown time in seconds
        """
        super().__init__(cooldown)
        self._blink_time_lapse = blink_time_lapse

    @property
    def blink_time_lapse(self) -> float:
        """Visual effect duration."""
        return self._blink_time_lapse

    def use_on_environment_impl(
        self,
        target_position,  # ReferencedPoint or Vec3
        timeline: Timeline,
        ability_list: AbilityList,
        private_parameters=None,
    ) -> None:
        """
        Teleport actor to target position.

        Matches original BlinkAbility.UseOnEnvironmentImpl().
        """
        actor = ability_list.actor

        # Get target position (handle both ReferencedPoint and Vec3)
        if hasattr(target_position, 'to_global_position'):
            # ReferencedPoint
            target_pos = target_position.to_global_position(timeline)
        elif isinstance(target_position, Vec3):
            target_pos = target_position
        else:
            # Assume it has x, y, z attributes
            target_pos = Vec3(target_position.x, target_position.y, target_position.z)

        # Create new pose at target (keep rotation)
        new_pose = Pose3(actor.local_rotation, target_pos)

        # Create static animatronic at new position
        # This "snaps" the actor to the new position
        local_step = actor.local_step
        static_anim = StaticAnimatronic(
            pose=new_pose,
            start_step=local_step,
            finish_step=local_step + 1,  # Single step
        )
        actor.add_animatronic(static_anim)

        # Directly set pose for immediate effect
        actor.set_local_pose(new_pose)

    def info(self) -> str:
        return f"BlinkAbility(cooldown={self.cooldown_time:.1f}s, lapse={self._blink_time_lapse:.1f}s)"
