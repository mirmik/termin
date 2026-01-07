"""
BlinkAbility - instant teleportation ability.

Matches original C# BlinkAbility:
- Instantly teleports actor to target position
- Has cooldown
- Uses BlinkCommand for execution
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.geombase import Vec3

from .ability import Ability

if TYPE_CHECKING:
    from termin.chronosquad.core.object_of_timeline import ObjectOfTimeline
    from termin.chronosquad.core.timeline import Timeline
    from termin.chronosquad.core.ability.ability import AbilityList


class BlinkAbility(Ability):
    """
    Instant teleportation ability.

    Teleports the actor to the target position using BlinkCommand.
    """

    def __init__(self, blink_time_lapse: float = 0.5, cooldown: float = 3.0):
        """
        Initialize blink ability.

        Args:
            blink_time_lapse: Visual effect duration
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

        Matches original BlinkAbility.UseOnEnvironmentImpl():
        - Creates BlinkCommand
        - Adds it to actor's command buffer
        """
        from termin.chronosquad.core.commands.blink_command import BlinkCommand

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

        # Create BlinkCommand
        command = BlinkCommand(
            target_pos,
            self._blink_time_lapse,
            actor.local_step + 1,
        )

        # Add command to actor
        actor.command_buffer.add_command(command)

    def info(self) -> str:
        return f"BlinkAbility(cooldown={self.cooldown_time:.1f}s, lapse={self._blink_time_lapse:.1f}s)"
