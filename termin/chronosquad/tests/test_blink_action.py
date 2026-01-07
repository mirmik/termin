"""
Tests for BlinkActionComponent and ActionServerComponent.
"""

import pytest
from termin.geombase import Vec3

from termin.chronosquad.core import (
    Timeline,
    ObjectOfTimeline,
    BlinkAbility,
)
from termin.chronosquad.controllers import (
    ActionServerComponent,
    ActionSpec,
    ActionSpecType,
    ClickInfo,
    BlinkActionComponent,
)


class TestActionServerComponent:
    """Tests for ActionServerComponent."""

    def setup_method(self):
        """Reset instance before each test."""
        ActionServerComponent._instance = None

    def teardown_method(self):
        """Clean up after each test."""
        ActionServerComponent._instance = None

    def test_initially_not_charged(self):
        """ActionServerComponent starts uncharged."""
        server = ActionServerComponent()
        ActionServerComponent._instance = server

        assert not server.is_charged()
        assert server.current_action is None
        assert server.current_spec is None


class TestBlinkAbility:
    """Tests for BlinkAbility."""

    def test_create(self):
        """Test BlinkAbility creation."""
        ability = BlinkAbility(blink_time_lapse=0.5, cooldown=3.0)
        assert ability.blink_time_lapse == 0.5
        assert ability.cooldown_time == 3.0

    def test_teleport(self):
        """Test teleportation via BlinkAbility."""
        tl = Timeline("Test")
        obj = ObjectOfTimeline("Player")
        obj.set_local_position(Vec3(0, 0, 0))
        tl.add_object(obj)

        # Add ability
        ability = BlinkAbility(cooldown=3.0)
        obj.add_ability(ability)

        # Use ability
        target = Vec3(10, 5, 0)
        ability.use_on_environment(target, tl, obj.ability_list)

        # Check position changed
        assert abs(obj.local_position.x - 10) < 0.01
        assert abs(obj.local_position.y - 5) < 0.01

    def test_cooldown(self):
        """Test cooldown after use."""
        tl = Timeline("Test")
        obj = ObjectOfTimeline("Player")
        tl.add_object(obj)

        ability = BlinkAbility(cooldown=3.0)
        obj.add_ability(ability)

        # Initially can use
        assert ability.can_use(tl, obj.ability_list)

        # Use ability
        ability.use_on_environment(Vec3(5, 0, 0), tl, obj.ability_list)

        # Update cooldowns
        obj.ability_list.promote_cooldowns()

        # Now on cooldown
        assert not ability.can_use(tl, obj.ability_list)
