"""
ObjectOfTimeline - base class for all objects that exist on a timeline.

Objects have position (pose), event cards, command buffer, and can be moved through time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import math

from termin.geombase import Vec3, Quat, Pose3, GeneralPose3

from .event_line import EventLine
from .object_time import ObjectTime
from .timeline import GAME_FREQUENCY

if TYPE_CHECKING:
    from .timeline import Timeline
    from .animatronic import Animatronic, AnimationType
    from .command_buffer import CommandBuffer
    from .moving_command import WalkingType


@dataclass
class AnimatronicAnimationTask:
    """Animation task from animatronic for blending."""
    animation_type: AnimationType
    animation_time: float
    coeff: float
    loop: bool
    animation_booster: float
    animatronic: Animatronic | None = None

    def info(self) -> str:
        return (
            f"AnimatronicAnimationTask: type={self.animation_type}, "
            f"time={self.animation_time:.2f}, coeff={self.coeff:.2f}, loop={self.loop}"
        )


class ObjectOfTimeline:
    """
    Base class for all timeline objects.

    Has:
    - Name/ID
    - Local pose (position + rotation)
    - Event cards for state changes
    - Animatronics for smooth movement
    """

    def __init__(self, name: str):
        self._name = name
        self._timeline: Timeline | None = None

        # Current local pose
        self._local_pose: Pose3 = Pose3.identity()

        # Event cards for state changes
        self._changes: EventLine[ObjectOfTimeline] = EventLine()

        # Animatronics for smooth movement interpolation
        self._animatronics: list[Animatronic] = []
        self._current_animatronic: Animatronic | None = None

        # Object time management (broken time, modifiers)
        self._object_time: ObjectTime = ObjectTime()

        # Pre-evaluated local step (object's own time, can differ from timeline)
        self._local_step: int = 0
        self._time_modifier: float = 1.0

        # Command buffer for managing actor commands
        self._command_buffer: CommandBuffer | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def timeline(self) -> Timeline | None:
        return self._timeline

    @property
    def local_step(self) -> int:
        return self._local_step

    @property
    def object_time(self) -> ObjectTime:
        return self._object_time

    @property
    def current_animatronic(self) -> Animatronic | None:
        return self._current_animatronic

    @property
    def time_modifier(self) -> float:
        """Current time modifier (from ObjectTime)."""
        return self._time_modifier

    @property
    def command_buffer(self) -> CommandBuffer:
        """Get or create command buffer."""
        if self._command_buffer is None:
            from .command_buffer import CommandBuffer
            self._command_buffer = CommandBuffer(self)
        return self._command_buffer

    def local_time_real_time(self, timeline_time: float) -> float:
        """Convert timeline time (seconds) to object's local time."""
        return self._object_time.timeline_to_local_time(timeline_time)

    def local_time_by_step(self) -> float:
        """Get local time in seconds from local step."""
        return self._local_step / GAME_FREQUENCY

    @property
    def local_position(self) -> Vec3:
        return self._local_pose.lin

    @property
    def local_rotation(self) -> Quat:
        return self._local_pose.ang

    @property
    def local_pose(self) -> Pose3:
        return self._local_pose

    def set_local_position(self, pos: Vec3) -> None:
        """Set local position."""
        self._local_pose.lin = pos

    def set_local_rotation(self, rot: Quat) -> None:
        """Set local rotation."""
        self._local_pose.ang = rot

    def set_local_pose(self, pose: Pose3 | GeneralPose3) -> None:
        """Set local pose. Accepts Pose3 or GeneralPose3 (scale ignored)."""
        self._local_pose = Pose3(pose.ang, pose.lin)

    def add_animatronic(self, anim: Animatronic) -> None:
        """Add an animatronic (movement card)."""
        self._animatronics.append(anim)
        # Keep sorted by start_step
        self._animatronics.sort(key=lambda a: a.start_step)

    def _find_current_animatronic(self) -> None:
        """
        Find current animatronic at local_step.

        Picks the LAST animatronic (highest start_step) where start_step <= local_step.
        This is critical for correct behavior when a new command interrupts movement:
        the new animatronic starts at the same step, and we need to use it, not the old one.
        Old animatronics are kept in the list for reverse time playback.
        """
        self._current_animatronic = None
        # Animatronics are sorted by start_step ascending
        # We need the last one with start_step <= local_step
        for anim in self._animatronics:
            if anim.start_step <= self._local_step:
                self._current_animatronic = anim
            else:
                break  # List is sorted, no need to continue

    def promote(self, timeline_step: int) -> None:
        """
        Promote object to timeline step.
        Updates local step, evaluates animatronics, then executes commands.
        """
        # Update object time and get local step
        self._object_time.promote(timeline_step)
        self._local_step = self._object_time.timeline_to_local(timeline_step)
        self._time_modifier = self._object_time.current_time_multiplier()

        # First, find and evaluate active animatronic at local step
        # This must happen BEFORE command execution so commands see current pose
        self._find_current_animatronic()
        if self._current_animatronic is not None:
            self._local_pose = self._current_animatronic.evaluate(self._local_step)

        # Execute command buffer (may add new animatronics)
        # Commands can now read the current pose correctly
        if self._command_buffer is not None and self._timeline is not None:
            self._command_buffer.execute(self._local_step, self._timeline)

        # Re-find animatronic after command execution
        # (command may have added a new animatronic starting at this step)
        self._find_current_animatronic()
        if self._current_animatronic is not None:
            self._local_pose = self._current_animatronic.evaluate(self._local_step)

        # Promote event cards
        self._changes.promote(self._local_step, self)

    def add_card(self, card) -> None:
        """Add an event card."""
        self._changes.add(card)

    def drop_to_current(self) -> None:
        """Drop future events/animatronics/commands."""
        self._changes.drop_future()
        # Remove animatronics that START after current step
        # Keep animatronics that started before (even if they extend past current step)
        # They're needed for reverse time playback
        self._animatronics = [
            a for a in self._animatronics
            if a.start_step <= self._local_step
        ]
        # Drop future commands
        if self._command_buffer is not None:
            self._command_buffer.drop_to_current_state()

    def copy(self, new_timeline: Timeline) -> ObjectOfTimeline:
        """Create a copy for a new timeline."""
        new_obj = ObjectOfTimeline(self._name)
        new_obj._timeline = new_timeline
        new_obj._local_pose = self._local_pose.copy()
        new_obj._local_step = self._local_step
        new_obj._time_modifier = self._time_modifier
        new_obj._changes = self._changes.copy()
        new_obj._animatronics = [a.copy() for a in self._animatronics]
        new_obj._object_time = self._object_time.copy()
        # Copy command buffer
        if self._command_buffer is not None:
            new_obj._command_buffer = self._command_buffer.copy(new_obj)
        return new_obj

    def current_position(self) -> Vec3:
        """Get current interpolated position."""
        return self._local_pose.lin

    def info(self) -> str:
        """Debug info."""
        return (
            f"Object '{self._name}' at step {self._local_step}, "
            f"pos={self._local_pose.lin}, "
            f"animatronics={len(self._animatronics)}"
        )

    def move_to(self, target: Vec3, speed: float = 5.0) -> None:
        """
        Move object to target position using MovingCommand.

        Creates a MovingCommand that will generate the appropriate animatronic.
        Walking type is determined by speed.

        Args:
            target: Target position in world coordinates
            speed: Movement speed in units per second (default 5.0)
        """
        from .moving_command import MovingCommand, WalkingType

        if self._timeline is None:
            return

        # Determine walking type based on speed
        if speed <= 1.0:
            walking_type = WalkingType.CROUCH
        elif speed <= 2.5:
            walking_type = WalkingType.WALK
        elif speed <= 6.0:
            walking_type = WalkingType.RUN
        else:
            walking_type = WalkingType.SPRINT

        # Create and add command
        cmd = MovingCommand(target, walking_type, self._local_step)
        self.command_buffer.add_command(cmd)

    def move_command(
        self,
        target: Vec3,
        walking_type: WalkingType | None = None,
    ) -> None:
        """
        Move object to target position using MovingCommand.

        Args:
            target: Target position in world coordinates
            walking_type: Type of walking animation/speed (default: RUN)
        """
        from .moving_command import MovingCommand, WalkingType

        if self._timeline is None:
            return

        if walking_type is None:
            from .moving_command import WalkingType
            walking_type = WalkingType.RUN

        cmd = MovingCommand(target, walking_type, self._local_step)
        self.command_buffer.add_command(cmd)

    def animations(self, local_time: float) -> list[AnimatronicAnimationTask]:
        """
        Get animation tasks for blending at given local time.

        Returns a list of AnimatronicAnimationTask with blending coefficients.
        Most recent animatronic has highest coefficient, older ones blend out.
        If the last animatronic has finished, returns Idle with blend from finished anim.
        """
        from .animatronic import AnimationType

        result: list[AnimatronicAnimationTask] = []

        if not self._animatronics:
            return result

        # Find current animatronic (last one whose start <= local_time)
        current_idx = -1
        for i, anim in enumerate(self._animatronics):
            if anim.start_local_time() <= local_time:
                current_idx = i

        if current_idx < 0:
            return result

        current_anim = self._animatronics[current_idx]

        # Check if current animatronic has finished - blend to Idle
        if local_time > current_anim.finish_local_time():
            time_after_finish = local_time - current_anim.finish_local_time()
            OVERLAP = 0.5

            # Blend coefficient: 0 at finish, 1.0 after OVERLAP seconds
            idle_coeff = time_after_finish / OVERLAP if OVERLAP > 0 else 1.0
            idle_coeff = max(0.0, min(1.0, idle_coeff))
            anim_coeff = 1.0 - idle_coeff

            # Add Idle as primary (first in list)
            result.append(AnimatronicAnimationTask(
                animation_type=AnimationType.IDLE,
                animation_time=local_time,  # Idle loops, time doesn't matter much
                coeff=idle_coeff,
                loop=True,
                animation_booster=1.0,
                animatronic=None,
            ))

            # Add finished animatronic for blending out (if still significant)
            if anim_coeff > 0.01:
                result.append(AnimatronicAnimationTask(
                    animation_type=current_anim.get_animation_type(),
                    animation_time=current_anim.animation_time_on_local_time(
                        current_anim.finish_local_time()
                    ),
                    coeff=anim_coeff,
                    loop=current_anim.is_looped(),
                    animation_booster=current_anim.animation_booster(),
                    animatronic=current_anim,
                ))

            return result

        # Animatronic is still active - blend with previous ones
        OVERLAP = 0.5  # seconds
        backpack = 1.0
        max_anims = 3

        for i in range(current_idx, -1, -1):
            if len(result) >= max_anims:
                break

            if backpack < 0.01:
                break

            anim = self._animatronics[i]
            time_from_start = anim.time_from_start(local_time)

            # Calculate blend coefficient
            coeff = time_from_start / OVERLAP if OVERLAP > 0 else 1.0
            coeff = max(0.0, min(1.0, coeff))
            coeff = coeff * backpack
            backpack = backpack - coeff
            backpack = max(0.0, min(1.0, backpack))

            result.append(AnimatronicAnimationTask(
                animation_type=anim.get_animation_type(),
                animation_time=anim.animation_time_on_local_time(local_time),
                coeff=coeff,
                loop=anim.is_looped(),
                animation_booster=anim.animation_booster(),
                animatronic=anim,
            ))

        return result
