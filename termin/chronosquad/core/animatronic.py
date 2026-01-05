"""
Animatronic - smooth movement/animation cards.

Animatronics define how an object moves between poses over time.
They are evaluated at each step to get the interpolated pose.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from termin.geombase import Pose3, Vec3, Quat


class Animatronic(ABC):
    """
    Base class for movement/animation cards.

    An animatronic has a time range and produces interpolated poses.
    """

    def __init__(self, start_step: int, finish_step: int):
        self.start_step = start_step
        self.finish_step = finish_step

    def is_active_at(self, step: int) -> bool:
        """Check if animatronic is active at given step."""
        return self.start_step <= step <= self.finish_step

    def duration(self) -> int:
        """Duration in steps."""
        return self.finish_step - self.start_step

    def progress(self, step: int) -> float:
        """Get progress [0..1] at given step."""
        if self.finish_step == self.start_step:
            return 1.0
        t = (step - self.start_step) / (self.finish_step - self.start_step)
        return max(0.0, min(1.0, t))

    @abstractmethod
    def evaluate(self, step: int) -> Pose3:
        """Evaluate pose at given step."""
        pass

    @abstractmethod
    def copy(self) -> Animatronic:
        """Create a copy of this animatronic."""
        pass


class StaticAnimatronic(Animatronic):
    """
    Animatronic that holds a static pose.
    """

    def __init__(self, start_step: int, pose: Pose3, finish_step: int | None = None):
        if finish_step is None:
            finish_step = start_step + 1_000_000  # Very long duration
        super().__init__(start_step, finish_step)
        self.pose = pose

    def evaluate(self, step: int) -> Pose3:
        return self.pose.copy()

    def copy(self) -> StaticAnimatronic:
        return StaticAnimatronic(self.start_step, self.pose.copy(), self.finish_step)


class LinearMoveAnimatronic(Animatronic):
    """
    Animatronic that moves linearly from start_pose to end_pose.
    """

    def __init__(
        self,
        start_step: int,
        finish_step: int,
        start_pose: Pose3,
        end_pose: Pose3,
    ):
        super().__init__(start_step, finish_step)
        self.start_pose = start_pose
        self.end_pose = end_pose

    def evaluate(self, step: int) -> Pose3:
        t = self.progress(step)
        return Pose3.lerp(self.start_pose, self.end_pose, t)

    def copy(self) -> LinearMoveAnimatronic:
        return LinearMoveAnimatronic(
            self.start_step,
            self.finish_step,
            self.start_pose.copy(),
            self.end_pose.copy(),
        )


class CubicMoveAnimatronic(Animatronic):
    """
    Animatronic that moves with smooth acceleration/deceleration.
    Uses cubic easing for smoother motion.
    """

    def __init__(
        self,
        start_step: int,
        finish_step: int,
        start_pose: Pose3,
        end_pose: Pose3,
    ):
        super().__init__(start_step, finish_step)
        self.start_pose = start_pose
        self.end_pose = end_pose

    def _smooth_step(self, t: float) -> float:
        """Smooth step function (cubic ease in-out)."""
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - ((-2 * t + 2) ** 3) / 2

    def evaluate(self, step: int) -> Pose3:
        t = self.progress(step)
        smooth_t = self._smooth_step(t)
        return Pose3.lerp(self.start_pose, self.end_pose, smooth_t)

    def copy(self) -> CubicMoveAnimatronic:
        return CubicMoveAnimatronic(
            self.start_step,
            self.finish_step,
            self.start_pose.copy(),
            self.end_pose.copy(),
        )


class WaypointAnimatronic(Animatronic):
    """
    Animatronic that moves through a series of waypoints.
    """

    def __init__(
        self,
        start_step: int,
        waypoints: list[tuple[int, Pose3]],  # (step, pose) pairs
    ):
        if not waypoints:
            raise ValueError("At least one waypoint required")

        # Sort by step
        waypoints = sorted(waypoints, key=lambda w: w[0])
        finish_step = waypoints[-1][0]

        super().__init__(start_step, finish_step)
        self.waypoints = waypoints

    def evaluate(self, step: int) -> Pose3:
        # Find surrounding waypoints
        prev_wp = self.waypoints[0]
        next_wp = self.waypoints[-1]

        for i, (wp_step, wp_pose) in enumerate(self.waypoints):
            if wp_step >= step:
                next_wp = (wp_step, wp_pose)
                if i > 0:
                    prev_wp = self.waypoints[i - 1]
                else:
                    prev_wp = next_wp
                break
            prev_wp = (wp_step, wp_pose)

        # Interpolate between waypoints
        prev_step, prev_pose = prev_wp
        next_step, next_pose = next_wp

        if next_step == prev_step:
            return prev_pose.copy()

        t = (step - prev_step) / (next_step - prev_step)
        t = max(0.0, min(1.0, t))
        return Pose3.lerp(prev_pose, next_pose, t)

    def copy(self) -> WaypointAnimatronic:
        new_waypoints = [(s, p.copy()) for s, p in self.waypoints]
        return WaypointAnimatronic(self.start_step, new_waypoints)
