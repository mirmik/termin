"""
ObjectOfTimeline - base class for all objects that exist on a timeline.

Objects have position (pose), event cards, and can be moved through time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from dataclasses import dataclass

from .event_line import EventLine

if TYPE_CHECKING:
    from .timeline import Timeline
    from .animatronic import Animatronic


@dataclass
class Vec3:
    """Simple 3D vector."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, other: Vec3) -> Vec3:
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vec3) -> Vec3:
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> Vec3:
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def lerp(self, other: Vec3, t: float) -> Vec3:
        """Linear interpolation between self and other."""
        return self + (other - self) * t

    def distance_to(self, other: Vec3) -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return (dx * dx + dy * dy + dz * dz) ** 0.5

    def copy(self) -> Vec3:
        return Vec3(self.x, self.y, self.z)

    def __repr__(self) -> str:
        return f"Vec3({self.x:.2f}, {self.y:.2f}, {self.z:.2f})"


@dataclass
class Quat:
    """Simple quaternion for rotation."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0

    @staticmethod
    def identity() -> Quat:
        return Quat(0, 0, 0, 1)

    def copy(self) -> Quat:
        return Quat(self.x, self.y, self.z, self.w)


@dataclass
class Pose:
    """Position + rotation."""
    position: Vec3
    rotation: Quat

    @staticmethod
    def identity() -> Pose:
        return Pose(Vec3(), Quat.identity())

    def copy(self) -> Pose:
        return Pose(self.position.copy(), self.rotation.copy())

    def lerp(self, other: Pose, t: float) -> Pose:
        """Linear interpolation of position (rotation lerp is simplified)."""
        return Pose(
            self.position.lerp(other.position, t),
            other.rotation.copy() if t > 0.5 else self.rotation.copy()
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
        self._local_pose: Pose = Pose.identity()

        # Event cards for state changes
        self._changes: EventLine[ObjectOfTimeline] = EventLine()

        # Animatronics for smooth movement interpolation
        self._animatronics: list[Animatronic] = []
        self._current_animatronic: Animatronic | None = None

        # Local step (object's own time, can differ from timeline)
        self._local_step: int = 0

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
    def position(self) -> Vec3:
        return self._local_pose.position

    @property
    def pose(self) -> Pose:
        return self._local_pose

    def set_position(self, pos: Vec3) -> None:
        """Set position directly (for initialization)."""
        self._local_pose.position = pos

    def set_pose(self, pose: Pose) -> None:
        """Set pose directly (for initialization)."""
        self._local_pose = pose

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
        self._local_step = timeline_step

        # Find active animatronic
        self._current_animatronic = None
        for anim in self._animatronics:
            if anim.is_active_at(timeline_step):
                self._current_animatronic = anim
                break

        # Evaluate pose from animatronic
        if self._current_animatronic is not None:
            self._local_pose = self._current_animatronic.evaluate(timeline_step)

        # Promote event cards
        self._changes.promote(timeline_step, self)

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
        new_obj._changes = self._changes.copy()
        new_obj._animatronics = [a.copy() for a in self._animatronics]
        return new_obj

    def current_position(self) -> Vec3:
        """Get current interpolated position."""
        return self._local_pose.position

    def info(self) -> str:
        """Debug info."""
        return (
            f"Object '{self._name}' at step {self._local_step}, "
            f"pos={self._local_pose.position}, "
            f"animatronics={len(self._animatronics)}"
        )
