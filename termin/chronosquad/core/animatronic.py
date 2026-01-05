"""
Animatronic - smooth movement/animation cards.

Animatronics define how an object moves between poses over time.
They are evaluated at each step to get the interpolated pose.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto

from termin.geombase import Pose3, Vec3, Quat


class AnimationType(Enum):
    """Animation types that can be played by AnimationPlayer."""
    NONE = auto()
    IDLE = auto()
    WALK = auto()
    RUN = auto()
    DEATH = auto()


class Animatronic(ABC):
    """
    Base class for movement/animation cards.

    An animatronic has a time range and produces interpolated poses.
    """

    def __init__(self, start_step: int, finish_step: int):
        self.start_step = start_step
        self.finish_step = finish_step
        self._initial_animation_time: float = 0.0

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

    # Animation time methods

    def time_from_start_step(self, step: int) -> float:
        """Time elapsed since start (from step)."""
        from .timeline import GAME_FREQUENCY
        return (step - self.start_step) / GAME_FREQUENCY

    def time_from_start(self, local_time: float) -> float:
        """Time elapsed since start (from local time in seconds)."""
        from .timeline import GAME_FREQUENCY
        start_time = self.start_step / GAME_FREQUENCY
        return local_time - start_time

    def animation_time_on_step(self, step: int) -> float:
        """Animation time at given step."""
        return self._initial_animation_time + self.time_from_start_step(step)

    def animation_time_on_local_time(self, local_time: float) -> float:
        """Animation time at given local time (seconds)."""
        return self._initial_animation_time + self.time_from_start(local_time)

    def start_local_time(self) -> float:
        """Start time in seconds."""
        from .timeline import GAME_FREQUENCY
        return self.start_step / GAME_FREQUENCY

    def finish_local_time(self) -> float:
        """Finish time in seconds."""
        from .timeline import GAME_FREQUENCY
        return self.finish_step / GAME_FREQUENCY

    def set_initial_animation_time(self, time: float) -> None:
        """Set initial animation time offset."""
        self._initial_animation_time = time

    def initial_animation_time(self) -> float:
        """Get initial animation time offset."""
        return self._initial_animation_time

    def is_looped(self) -> bool:
        """Whether this animation should loop."""
        return False

    def animation_booster(self) -> float:
        """Animation speed multiplier."""
        return 1.0

    def overlap_time(self) -> float:
        """Overlap time for blending with previous animation."""
        return 0.25

    @abstractmethod
    def evaluate(self, step: int) -> Pose3:
        """Evaluate pose at given step."""
        pass

    @abstractmethod
    def get_animation_type(self) -> AnimationType:
        """Get the animation type to play during this animatronic."""
        pass

    @abstractmethod
    def copy(self) -> Animatronic:
        """Create a copy of this animatronic."""
        pass


class StaticAnimatronic(Animatronic):
    """
    Animatronic that holds a static pose (Idle animation).
    """

    def __init__(self, start_step: int, pose: Pose3, finish_step: int | None = None):
        if finish_step is None:
            finish_step = start_step + 1_000_000  # Very long duration
        super().__init__(start_step, finish_step)
        self.pose = pose

    def evaluate(self, step: int) -> Pose3:
        return self.pose.copy()

    def get_animation_type(self) -> AnimationType:
        return AnimationType.IDLE

    def is_looped(self) -> bool:
        return True

    def copy(self) -> StaticAnimatronic:
        return StaticAnimatronic(self.start_step, self.pose.copy(), self.finish_step)


class LinearMoveAnimatronic(Animatronic):
    """
    Animatronic that moves linearly from start_pose to end_pose.

    Rotation happens at the start with angular_speed (degrees/sec).
    Position interpolates linearly over the entire duration.
    """

    # Default angular speed in degrees per second
    DEFAULT_ANGULAR_SPEED = 360.0

    def __init__(
        self,
        start_step: int,
        finish_step: int,
        start_pose: Pose3,
        end_pose: Pose3,
        animation_type: AnimationType = AnimationType.WALK,
        angular_speed: float = DEFAULT_ANGULAR_SPEED,
    ):
        super().__init__(start_step, finish_step)
        self.start_pose = start_pose
        self.end_pose = end_pose
        self._animation_type = animation_type
        self._angular_speed = angular_speed

        # Calculate time to rotate (in seconds)
        # Convention: Forward = +Y
        from .timeline import GAME_FREQUENCY
        forward = Vec3(0, 1, 0)  # +Y is forward
        start_dir = start_pose.ang.rotate(forward)
        end_dir = end_pose.ang.rotate(forward)
        angle_deg = Vec3.angle_degrees(start_dir, end_dir)
        self._time_to_rotate = angle_deg / angular_speed if angular_speed > 0 else 0.0
        self._steps_to_rotate = int(self._time_to_rotate * GAME_FREQUENCY)

    def evaluate(self, step: int) -> Pose3:
        from .timeline import GAME_FREQUENCY

        # Position: linear interpolation over entire duration
        t_pos = self.progress(step)
        pos = Vec3(
            self.start_pose.lin.x + t_pos * (self.end_pose.lin.x - self.start_pose.lin.x),
            self.start_pose.lin.y + t_pos * (self.end_pose.lin.y - self.start_pose.lin.y),
            self.start_pose.lin.z + t_pos * (self.end_pose.lin.z - self.start_pose.lin.z),
        )

        # Rotation: slerp only during rotation phase
        time_from_start = (step - self.start_step) / GAME_FREQUENCY
        if self._time_to_rotate > 0 and time_from_start < self._time_to_rotate:
            t_rot = time_from_start / self._time_to_rotate
            rot = Quat.slerp(self.start_pose.ang, self.end_pose.ang, t_rot)
        else:
            rot = self.end_pose.ang

        return Pose3(rot, pos)

    def get_animation_type(self) -> AnimationType:
        return self._animation_type

    def copy(self) -> LinearMoveAnimatronic:
        return LinearMoveAnimatronic(
            self.start_step,
            self.finish_step,
            self.start_pose.copy(),
            self.end_pose.copy(),
            self._animation_type,
            self._angular_speed,
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
        animation_type: AnimationType = AnimationType.WALK,
    ):
        super().__init__(start_step, finish_step)
        self.start_pose = start_pose
        self.end_pose = end_pose
        self._animation_type = animation_type

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

    def get_animation_type(self) -> AnimationType:
        return self._animation_type

    def copy(self) -> CubicMoveAnimatronic:
        return CubicMoveAnimatronic(
            self.start_step,
            self.finish_step,
            self.start_pose.copy(),
            self.end_pose.copy(),
            self._animation_type,
        )


class WaypointAnimatronic(Animatronic):
    """
    Animatronic that moves through a series of waypoints.
    """

    def __init__(
        self,
        start_step: int,
        waypoints: list[tuple[int, Pose3]],  # (step, pose) pairs
        animation_type: AnimationType = AnimationType.WALK,
    ):
        if not waypoints:
            raise ValueError("At least one waypoint required")

        # Sort by step
        waypoints = sorted(waypoints, key=lambda w: w[0])
        finish_step = waypoints[-1][0]

        super().__init__(start_step, finish_step)
        self.waypoints = waypoints
        self._animation_type = animation_type

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

    def get_animation_type(self) -> AnimationType:
        return self._animation_type

    def copy(self) -> WaypointAnimatronic:
        new_waypoints = [(s, p.copy()) for s, p in self.waypoints]
        return WaypointAnimatronic(self.start_step, new_waypoints, self._animation_type)
