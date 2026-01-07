"""
BlinkActionComponent - action component for instant teleportation.

Attach to entity with ObjectController to enable blink ability.
"""

from __future__ import annotations

from termin._native import log
from termin.editor.inspect_field import InspectField
from termin.chronosquad.core.ability.blink_ability import BlinkAbility
from termin.chronosquad.core import Ability
from termin.visualization.platform.backends.base import Key

from termin.chronosquad.controllers.action.action_component import ActionComponent, ActionSpec, ActionSpecType, ClickInfo


class BlinkActionComponent(ActionComponent):
    """
    Action component for instant teleportation (blink).

    Visualization: Line from actor to target point.
    Effect: Teleport actor to clicked position.
    """

    inspect_fields = {
        "cooldown": InspectField(
            path="cooldown",
            label="Cooldown",
            kind="float",
        ),
        "max_distance": InspectField(
            path="max_distance",
            label="Max Distance",
            kind="float",
        ),
        "blink_time_lapse": InspectField(
            path="blink_time_lapse",
            label="Blink Time Lapse",
            kind="float",
        ),
    }

    # Visual settings
    LINE_COLOR = (0.0, 0.8, 1.0, 0.8)  # Cyan-ish
    LINE_WIDTH = 0.05

    def __init__(
        self,
        enabled: bool = True,
        cooldown: float = 3.0,
        max_distance: float = 15.0,
        blink_time_lapse: float = 0.5,
    ):
        super().__init__(enabled=enabled)
        self.cooldown: float = cooldown
        self.max_distance: float = max_distance
        self.blink_time_lapse: float = blink_time_lapse
        self.shortcut_key: Key = Key.B  # Default key for blink action

    def create_ability(self) -> Ability | None:
        """Create BlinkAbility."""
        return BlinkAbility(
            blink_time_lapse=self.blink_time_lapse,
            cooldown=self.cooldown,
        )

    def get_spec(self) -> ActionSpec:
        """
        Return visualization spec.

        BlinkAction uses a LINE from actor to cursor with max distance constraint.
        """
        return ActionSpec(
            spec_type=ActionSpecType.LINE,
            color=self.LINE_COLOR,
            line_width=self.LINE_WIDTH,
            max_distance=self.max_distance,
            require_navmesh=True,  # Blink target should be walkable
        )

    def on_apply(self, click: ClickInfo) -> bool:
        """
        Apply blink to target position.
        """
        ability = self.ability
        if ability is None:
            log.warning("[BlinkActionComponent] No ability")
            return False

        chrono_obj = self.chrono_object
        if chrono_obj is None:
            log.warning("[BlinkActionComponent] No chrono object")
            return False

        timeline = chrono_obj.timeline
        if timeline is None:
            log.warning("[BlinkActionComponent] No timeline")
            return False

        # Use ability on environment (target position)
        ability.use_on_environment(
            click.world_position,
            timeline,
            chrono_obj.ability_list,
            None,  # private_parameters
            False,  # ignore_cooldown
        )

        log.info(f"[BlinkActionComponent] Blinked to {click.world_position}")
        return True

    def get_tooltip(self) -> str:
        """Get tooltip text."""
        return "Blink: Instantly teleport to target position"

