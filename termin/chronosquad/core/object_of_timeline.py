"""
ObjectOfTimeline - base class for all objects that exist on a timeline.

Objects have position (pose), event cards, and can be moved through time.
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

    def promote(self, timeline_step: int) -> None:
        """
        Promote object to timeline step.
        Updates local step and evaluates animatronics.
        """
        # Update object time and get local step
        self._object_time.promote(timeline_step)
        self._local_step = self._object_time.timeline_to_local(timeline_step)
        self._time_modifier = self._object_time.current_time_multiplier()

        # Find active animatronic at local step
        self._current_animatronic = None
        for anim in self._animatronics:
            if anim.is_active_at(self._local_step):
                self._current_animatronic = anim
                break

        # Evaluate pose from animatronic
        if self._current_animatronic is not None:
            self._local_pose = self._current_animatronic.evaluate(self._local_step)

        # Promote event cards
        self._changes.promote(self._local_step, self)

    def add_card(self, card) -> None:
        """Add an event card."""
        self._changes.add(card)

    def drop_to_current(self) -> None:
        """Drop future events/animatronics."""
        self._changes.drop_future()
        # Remove animatronics that start after current step
        self._animatronics = [
            a for a in self._animatronics
            if a.start_step <= self._local_step
        ]

    def copy(self, new_timeline: Timeline) -> ObjectOfTimeline:
        """Create a copy for a new timeline."""
        new_obj = ObjectOfTimeline(self._name)
        new_obj._local_pose = self._local_pose.copy()
        new_obj._local_step = self._local_step
        new_obj._time_modifier = self._time_modifier
        new_obj._changes = self._changes.copy()
        new_obj._animatronics = [a.copy() for a in self._animatronics]
        new_obj._object_time = self._object_time.copy()
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
        Move object to target position.

        Creates a LinearMoveAnimatronic from current position to target.
        Duration is calculated based on distance and speed.
        Target rotation is calculated to face movement direction.

        Args:
            target: Target position in world coordinates
            speed: Movement speed in units per second (default 5.0)
        """
        from .animatronic import LinearMoveAnimatronic

        if self._timeline is None:
            return

        current_pos = self._local_pose.lin
        current_rot = self._local_pose.ang

        # Calculate direction and distance
        dx = target.x - current_pos.x
        dy = target.y - current_pos.y
        dz = target.z - current_pos.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        if distance < 0.001:
            return  # Already at target

        # Calculate target rotation (look in movement direction)
        # Convention: Forward = +Y, Up = +Z, so horizontal plane is XY
        direction = Vec3(dx, dy, 0)  # Ignore Z for horizontal look direction
        if direction.norm() > 0.001:
            target_rot = Quat.look_rotation(direction)
        else:
            target_rot = current_rot

        # Calculate duration in steps
        duration_seconds = distance / speed
        duration_steps = max(1, int(duration_seconds * GAME_FREQUENCY))

        # Create animatronic
        start_step = self._timeline.current_step
        end_step = start_step + duration_steps

        start_pose = Pose3(current_rot, current_pos)
        end_pose = Pose3(target_rot, target)

        move = LinearMoveAnimatronic(start_step, end_step, start_pose, end_pose)
        self.add_animatronic(move)

    def animations(self, local_time: float) -> list[AnimatronicAnimationTask]:
        """
        Get animation tasks for blending at given local time.

        Returns a list of AnimatronicAnimationTask with blending coefficients.
        Most recent animatronic has highest coefficient, older ones blend out.
        """
        from .animatronic import AnimationType

        result: list[AnimatronicAnimationTask] = []

        if not self._animatronics:
            return result

        # Find current animatronic (last one that's active or closest)
        current_idx = -1
        for i, anim in enumerate(self._animatronics):
            if anim.start_local_time() <= local_time:
                current_idx = i

        if current_idx < 0:
            return result

        # Blend animations with overlap
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

            local_step = int(local_time * GAME_FREQUENCY)
            result.append(AnimatronicAnimationTask(
                animation_type=anim.get_animation_type(),
                animation_time=anim.animation_time_on_local_time(local_time),
                coeff=coeff,
                loop=anim.is_looped(),
                animation_booster=anim.animation_booster(),
                animatronic=anim,
            ))

        return result
