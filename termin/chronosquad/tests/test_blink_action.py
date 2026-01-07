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

        # Use ability (at step 0)
        target = Vec3(10, 5, 0)
        ability.use_on_environment(target, tl, obj.ability_list)

        # BlinkedMovingState returns initial_pose in first half, target_pose in second half
        # With default blink_time_lapse=0.5s: finish_step = 0 + 2 + 50 = 52
        # center = (2 + 52) / 2 = 27
        # Need to advance past center to see target position
        tl.promote(30)

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


class TestBlinkReproducibility:
    """Tests for time-reversal reproducibility with blink."""

    def test_move_blink_move_rewind(self):
        """
        Test that movement and blink are reproducible on time rewind.

        Scenario:
        1. Object at (0,0,0)
        2. Move to (5,0,0)
        3. Blink to (10,5,0)
        4. Move to (15,5,0)
        5. Rewind to start
        6. Replay and verify positions match
        """
        from termin.chronosquad.core.commands.moving_command import MovingCommand, WalkingType

        tl = Timeline("Test")
        obj = ObjectOfTimeline("Player")
        obj.set_local_position(Vec3(0, 0, 0))
        tl.add_object(obj)

        # Add blink ability
        ability = BlinkAbility(cooldown=3.0, blink_time_lapse=0.1)
        obj.add_ability(ability)

        # Record positions at each step during forward pass
        forward_positions: list[Vec3] = []

        # Step 0: Start position
        forward_positions.append(Vec3(obj.local_position.x, obj.local_position.y, obj.local_position.z))

        # Issue move command to (5, 0, 0)
        obj.move_to(Vec3(5, 0, 0), speed=5.0)

        # Advance timeline until movement completes (approximately)
        for step in range(1, 100):
            tl.promote(step)
            forward_positions.append(Vec3(obj.local_position.x, obj.local_position.y, obj.local_position.z))

            # Check if reached first destination
            if abs(obj.local_position.x - 5) < 0.1 and abs(obj.local_position.y) < 0.1:
                break

        first_move_end_step = tl.current_step

        # Blink to (10, 5, 0)
        ability.use_on_environment(Vec3(10, 5, 0), tl, obj.ability_list)

        # Advance timeline for blink to complete
        blink_steps = 20  # Enough for blink animation
        for i in range(blink_steps):
            step = first_move_end_step + i + 1
            tl.promote(step)
            forward_positions.append(Vec3(obj.local_position.x, obj.local_position.y, obj.local_position.z))

        blink_end_step = tl.current_step

        # Verify blink happened
        assert abs(obj.local_position.x - 10) < 0.1, f"Expected x=10, got {obj.local_position.x}"
        assert abs(obj.local_position.y - 5) < 0.1, f"Expected y=5, got {obj.local_position.y}"

        # Issue second move command to (15, 5, 0)
        obj.move_to(Vec3(15, 5, 0), speed=5.0)

        # Advance timeline for second movement
        # Need ~100 steps to move 5 units at 5 units/sec with 100 steps/sec
        for i in range(150):
            step = blink_end_step + i + 1
            tl.promote(step)
            forward_positions.append(Vec3(obj.local_position.x, obj.local_position.y, obj.local_position.z))

            # Check if reached second destination
            if abs(obj.local_position.x - 15) < 0.1:
                break

        final_step = tl.current_step
        total_steps = len(forward_positions)

        # Verify final position
        assert abs(obj.local_position.x - 15) < 0.5, f"Expected x≈15, got {obj.local_position.x}"

        # =====================================================================
        # REWIND: Go back to step 0
        # =====================================================================
        tl.promote(0)

        # Verify we're back at start
        assert abs(obj.local_position.x) < 0.1, f"After rewind, expected x=0, got {obj.local_position.x}"
        assert abs(obj.local_position.y) < 0.1, f"After rewind, expected y=0, got {obj.local_position.y}"

        # =====================================================================
        # REPLAY: Go forward and verify positions match
        # =====================================================================
        replay_positions: list[Vec3] = []

        for step in range(total_steps):
            tl.promote(step)
            replay_positions.append(Vec3(obj.local_position.x, obj.local_position.y, obj.local_position.z))

        # Compare forward and replay positions
        assert len(forward_positions) == len(replay_positions), \
            f"Position count mismatch: forward={len(forward_positions)}, replay={len(replay_positions)}"

        for i, (fwd, rep) in enumerate(zip(forward_positions, replay_positions)):
            dist = ((fwd.x - rep.x)**2 + (fwd.y - rep.y)**2 + (fwd.z - rep.z)**2) ** 0.5
            assert dist < 0.01, \
                f"Position mismatch at step {i}: forward={fwd}, replay={rep}, dist={dist}"

    def test_blink_rewind_forward(self):
        """
        Simple test: blink, rewind, forward - position should be reproducible.
        """
        tl = Timeline("Test")
        obj = ObjectOfTimeline("Player")
        obj.set_local_position(Vec3(0, 0, 0))
        tl.add_object(obj)

        ability = BlinkAbility(cooldown=3.0, blink_time_lapse=0.1)
        obj.add_ability(ability)

        # Blink to (10, 5, 0)
        ability.use_on_environment(Vec3(10, 5, 0), tl, obj.ability_list)

        # Advance to step 5 (after blink)
        tl.promote(5)
        pos_at_5 = Vec3(obj.local_position.x, obj.local_position.y, obj.local_position.z)

        # Continue to step 10
        tl.promote(10)
        pos_at_10 = Vec3(obj.local_position.x, obj.local_position.y, obj.local_position.z)

        # Rewind to step 0
        tl.promote(0)
        assert abs(obj.local_position.x) < 0.01, "Should be at origin after rewind"

        # Go forward to step 5
        tl.promote(5)
        assert abs(obj.local_position.x - pos_at_5.x) < 0.01, \
            f"Position at step 5 should match: expected {pos_at_5}, got {obj.local_position}"
        assert abs(obj.local_position.y - pos_at_5.y) < 0.01

        # Go forward to step 10
        tl.promote(10)
        assert abs(obj.local_position.x - pos_at_10.x) < 0.01, \
            f"Position at step 10 should match: expected {pos_at_10}, got {obj.local_position}"
        assert abs(obj.local_position.y - pos_at_10.y) < 0.01

        # Rewind again and verify
        tl.promote(0)
        tl.promote(10)
        assert abs(obj.local_position.x - pos_at_10.x) < 0.01
        assert abs(obj.local_position.y - pos_at_10.y) < 0.01
