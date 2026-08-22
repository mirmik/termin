"""Base Tween class and transform tweens."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import Enum, auto
from numbers import Real
from typing import Callable, TYPE_CHECKING

from termin.geombase import Quat, Vec3
from termin.tween.ease import Ease, evaluate as ease_evaluate

if TYPE_CHECKING:
    from termin.kinematic.general_transform import GeneralTransform3


Vec3Value = Vec3 | Sequence[float]
QuatValue = Quat | Sequence[float]


def _finite_vec3(value: Vec3Value, *, name: str) -> Vec3:
    if len(value) != 3:
        raise ValueError(f"{name} must contain exactly 3 components")
    result = Vec3(value)
    if not result.is_finite():
        raise ValueError(f"{name} must contain only finite values")
    return result


def _normalized_quat(value: QuatValue, *, name: str) -> Quat:
    if len(value) != 4:
        raise ValueError(f"{name} must contain exactly 4 components")
    result = Quat(value).try_normalized()
    if result is None:
        raise ValueError(f"{name} must be a finite, non-degenerate quaternion")
    return result


class TweenState(Enum):
    """Tween lifecycle state."""

    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    KILLED = auto()


class Tween(ABC):
    """
    Base class for all tweens.

    Subclasses must implement:
    - _apply(t: float): Apply interpolated value at normalized time t (0..1)
    """

    def __init__(
        self,
        duration: float,
        ease: Ease = Ease.LINEAR,
        delay: float = 0.0,
    ):
        self.duration = duration
        self.ease = ease
        self.delay = delay

        self._elapsed: float = 0.0
        self._state: TweenState = TweenState.RUNNING
        self._on_complete: Callable[[], None] | None = None
        self._on_update: Callable[[float], None] | None = None

    @property
    def state(self) -> TweenState:
        return self._state

    @property
    def is_alive(self) -> bool:
        """True if tween is running or paused."""
        return self._state in (TweenState.RUNNING, TweenState.PAUSED)

    @property
    def is_complete(self) -> bool:
        return self._state == TweenState.COMPLETED

    def pause(self) -> "Tween":
        """Pause the tween."""
        if self._state == TweenState.RUNNING:
            self._state = TweenState.PAUSED
        return self

    def resume(self) -> "Tween":
        """Resume paused tween."""
        if self._state == TweenState.PAUSED:
            self._state = TweenState.RUNNING
        return self

    def kill(self) -> "Tween":
        """Kill the tween immediately without completing."""
        self._state = TweenState.KILLED
        return self

    def on_complete(self, callback: Callable[[], None]) -> "Tween":
        """Set callback to invoke when tween completes."""
        self._on_complete = callback
        return self

    def on_update(self, callback: Callable[[float], None]) -> "Tween":
        """Set callback to invoke on each update with current t value."""
        self._on_update = callback
        return self

    def update(self, dt: float) -> bool:
        """
        Update tween by dt seconds.

        Returns:
            True if tween is still alive, False if completed or killed.
        """
        if self._state != TweenState.RUNNING:
            return self._state == TweenState.PAUSED

        self._elapsed += dt

        # Handle delay
        if self._elapsed < self.delay:
            return True

        # Calculate progress
        active_time = self._elapsed - self.delay
        raw_t = min(1.0, active_time / self.duration) if self.duration > 0 else 1.0
        eased_t = ease_evaluate(self.ease, raw_t)

        # Apply the tween
        self._apply(eased_t)

        if self._on_update is not None:
            self._on_update(eased_t)

        # Check completion
        if raw_t >= 1.0:
            self._state = TweenState.COMPLETED
            if self._on_complete is not None:
                self._on_complete()
            return False

        return True

    @abstractmethod
    def _apply(self, t: float) -> None:
        """Apply interpolated value at normalized time t (0..1)."""
        pass


class MoveTween(Tween):
    """Tween for animating transform position."""

    def __init__(
        self,
        transform: "GeneralTransform3",
        target: Vec3Value,
        duration: float,
        ease: Ease = Ease.LINEAR,
        delay: float = 0.0,
    ):
        super().__init__(duration, ease, delay)
        self.transform = transform
        self.target = _finite_vec3(target, name="move target")
        self._start: Vec3 | None = None

    def _apply(self, t: float) -> None:
        pose = self.transform.local_pose()
        if self._start is None:
            self._start = _finite_vec3(pose.lin, name="move start")

        new_pos = self._start + (self.target - self._start) * t
        if not new_pos.is_finite():
            raise ValueError("move interpolation produced a non-finite position")
        pose.lin = new_pos
        self.transform.relocate(pose)


class RotateTween(Tween):
    """Tween for animating transform rotation (quaternion slerp)."""

    def __init__(
        self,
        transform: "GeneralTransform3",
        target: QuatValue,
        duration: float,
        ease: Ease = Ease.LINEAR,
        delay: float = 0.0,
    ):
        super().__init__(duration, ease, delay)
        self.transform = transform
        self.target = _normalized_quat(target, name="rotation target")
        self._start: Quat | None = None

    def _apply(self, t: float) -> None:
        pose = self.transform.local_pose()
        if self._start is None:
            self._start = _normalized_quat(pose.ang, name="rotation start")

        pose.ang = Quat.slerp(self._start, self.target, t)
        self.transform.relocate(pose)


class ScaleTween(Tween):
    """Tween for animating transform scale."""

    def __init__(
        self,
        transform: "GeneralTransform3",
        target: Vec3Value | float,
        duration: float,
        ease: Ease = Ease.LINEAR,
        delay: float = 0.0,
    ):
        super().__init__(duration, ease, delay)
        self.transform = transform
        if isinstance(target, Real):
            uniform_scale = float(target)
            self.target = _finite_vec3(
                Vec3(uniform_scale, uniform_scale, uniform_scale),
                name="scale target",
            )
        else:
            self.target = _finite_vec3(target, name="scale target")
        self._start: Vec3 | None = None

    def _apply(self, t: float) -> None:
        pose = self.transform.local_pose()
        if self._start is None:
            self._start = _finite_vec3(pose.scale, name="scale start")

        new_scale = self._start + (self.target - self._start) * t
        if not new_scale.is_finite():
            raise ValueError("scale interpolation produced a non-finite scale")
        pose.scale = new_scale
        self.transform.relocate(pose)
