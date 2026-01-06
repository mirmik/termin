"""
Animatronic - smooth movement/animation cards.

Animatronics define how an object moves between poses over time.
They are evaluated at each step to get the interpolated pose.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from enum import Enum, auto

from termin.geombase import Pose3, Vec3, Quat


def _angle_between_vectors(v1: Vec3, v2: Vec3) -> float:
    """Compute angle in degrees between two vectors."""
    n1 = v1.norm()
    n2 = v2.norm()
    if n1 < 1e-6 or n2 < 1e-6:
        return 0.0
    dot = v1.dot(v2) / (n1 * n2)
    dot = max(-1.0, min(1.0, dot))  # Clamp for numerical stability
    return math.degrees(math.acos(dot))


def _quat_slerp(q1: Quat, q2: Quat, t: float) -> Quat:
    """Spherical linear interpolation between two quaternions."""
    # Compute dot product
    dot = q1.x * q2.x + q1.y * q2.y + q1.z * q2.z + q1.w * q2.w

    # If dot is negative, negate one quaternion to take shorter path
    if dot < 0:
        q2 = Quat(-q2.x, -q2.y, -q2.z, -q2.w)
        dot = -dot

    # Clamp for numerical stability
    dot = min(1.0, dot)

    # If quaternions are very close, use linear interpolation
    if dot > 0.9995:
        x = q1.x + t * (q2.x - q1.x)
        y = q1.y + t * (q2.y - q1.y)
        z = q1.z + t * (q2.z - q1.z)
        w = q1.w + t * (q2.w - q1.w)
        result = Quat(x, y, z, w)
        return result.normalized()

    # Slerp
    theta_0 = math.acos(dot)
    theta = theta_0 * t
    sin_theta = math.sin(theta)
    sin_theta_0 = math.sin(theta_0)

    s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0

    x = s0 * q1.x + s1 * q2.x
    y = s0 * q1.y + s1 * q2.y
    z = s0 * q1.z + s1 * q2.z
    w = s0 * q1.w + s1 * q2.w

    return Quat(x, y, z, w)


class AnimationType(Enum):
    """Animation types that can be played by AnimationPlayer."""
    NONE = auto()
    IDLE = auto()
    WALK = auto()
    RUN = auto()
    CROUCH_WALK = auto()
    SPRINT = auto()
    DEATH = auto()
    LOW_GRAVITY_WALK = auto()
    LOW_GRAVITY_RUN = auto()
    ZERO_GRAVITY_WALK = auto()
    ZERO_GRAVITY_CRAWL = auto()
    CLIMBING_UP_WALL = auto()
    CLIMBING_DOWN_WALL = auto()
    BRACED_HANG_LEFT = auto()
    BRACED_HANG_RIGHT = auto()
    DOOR_ENTRANCE = auto()
    PULLED_MOVE = auto()


# Default animation durations in seconds (from original game data)
ANIMATION_DURATIONS: dict[AnimationType, float] = {
    AnimationType.IDLE: 1.0,
    AnimationType.WALK: 1.0,
    AnimationType.RUN: 0.7,
    AnimationType.CROUCH_WALK: 1.2,
    AnimationType.SPRINT: 0.5,
    AnimationType.LOW_GRAVITY_WALK: 1.2,
    AnimationType.LOW_GRAVITY_RUN: 0.8,
    AnimationType.ZERO_GRAVITY_WALK: 1.5,
    AnimationType.ZERO_GRAVITY_CRAWL: 2.0,
    AnimationType.CLIMBING_UP_WALL: 1.0,
    AnimationType.CLIMBING_DOWN_WALL: 1.0,
    AnimationType.BRACED_HANG_LEFT: 1.0,
    AnimationType.BRACED_HANG_RIGHT: 1.0,
    AnimationType.DOOR_ENTRANCE: 0.5,
    AnimationType.PULLED_MOVE: 1.0,
}


def get_animation_duration(anim_type: AnimationType) -> float:
    """Get animation cycle duration in seconds."""
    return ANIMATION_DURATIONS.get(anim_type, 1.0)


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
        angle_deg = _angle_between_vectors(start_dir, end_dir)
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
            rot = _quat_slerp(self.start_pose.ang, self.end_pose.ang, t_rot)
        else:
            rot = self.end_pose.ang

        return Pose3(rot, pos)

    def get_animation_type(self) -> AnimationType:
        return self._animation_type

    def set_animation_type(self, anim_type: AnimationType) -> None:
        """Set the animation type."""
        self._animation_type = anim_type

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


class MovingAnimatronic(Animatronic):
    """
    Animatronic for walking/running movement.

    Matches original C# MovingAnimatronic behavior:
    - Position interpolates linearly over entire duration
    - Rotation happens at start with angular_speed (degrees/sec)
    - Animation is looped
    - Tracks animation_duration for foot cycle synchronization
    """

    DEFAULT_ANGULAR_SPEED = 360.0  # degrees per second

    def __init__(
        self,
        animation_type: AnimationType,
        start_pose: Pose3,
        finish_pose: Pose3,
        start_step: int,
        finish_step: int,
        animation_duration: float,
        angular_speed: float = DEFAULT_ANGULAR_SPEED,
        animation_booster: float = 1.0,
    ):
        super().__init__(start_step, finish_step)
        self._animation_type = animation_type
        self._start_pose = start_pose
        self._finish_pose = finish_pose
        self._animation_duration = animation_duration
        self._angular_speed = angular_speed
        self._animation_booster_value = animation_booster

        # Calculate time to rotate (in seconds)
        from .timeline import GAME_FREQUENCY
        forward = Vec3(0, 1, 0)  # +Y is forward
        start_dir = start_pose.ang.rotate(forward)
        end_dir = finish_pose.ang.rotate(forward)
        angle_deg = _angle_between_vectors(start_dir, end_dir)
        self._time_to_rotate = angle_deg / angular_speed if angular_speed > 0 else 0.0

    @property
    def start_pose(self) -> Pose3:
        return self._start_pose

    @property
    def finish_pose(self) -> Pose3:
        return self._finish_pose

    def initial_direction(self) -> Vec3:
        """Get initial facing direction."""
        forward = Vec3(0, 1, 0)
        return self._start_pose.ang.rotate(forward)

    def target_direction(self) -> Vec3:
        """Get target facing direction."""
        forward = Vec3(0, 1, 0)
        return self._finish_pose.ang.rotate(forward)

    def target_rotation(self) -> Quat:
        """Get target rotation."""
        return self._finish_pose.ang

    def target_position(self) -> Vec3:
        """Get target position."""
        return self._finish_pose.lin

    def initial_position(self) -> Vec3:
        """Get initial position."""
        return self._start_pose.lin

    def time_to_rotate(self) -> float:
        """Time needed for rotation phase (seconds)."""
        return self._time_to_rotate

    def final_pose(self) -> Pose3:
        """Get final pose."""
        return Pose3(self._finish_pose.ang, self._finish_pose.lin)

    def evaluate(self, step: int) -> Pose3:
        """Evaluate pose at given step."""
        from .timeline import GAME_FREQUENCY

        # Position: linear interpolation
        if step <= self.start_step:
            pos = self._start_pose.lin
        elif step >= self.finish_step:
            pos = self._finish_pose.lin
        else:
            koeff = (step - self.start_step) / (self.finish_step - self.start_step)
            pos = Vec3(
                self._start_pose.lin.x + koeff * (self._finish_pose.lin.x - self._start_pose.lin.x),
                self._start_pose.lin.y + koeff * (self._finish_pose.lin.y - self._start_pose.lin.y),
                self._start_pose.lin.z + koeff * (self._finish_pose.lin.z - self._start_pose.lin.z),
            )

        # Rotation: slerp during rotation phase, then hold target
        time_from_start = (step - self.start_step) / GAME_FREQUENCY
        if self._time_to_rotate > 0 and time_from_start < self._time_to_rotate:
            koeff = time_from_start / self._time_to_rotate
            rot = _quat_slerp(self._start_pose.ang, self._finish_pose.ang, koeff)
        else:
            rot = self._finish_pose.ang

        return Pose3(rot, pos)

    def get_animation_type(self) -> AnimationType:
        return self._animation_type

    def is_looped(self) -> bool:
        """Walking animations are looped."""
        return True

    def animation_booster(self) -> float:
        """Animation speed multiplier."""
        return self._animation_booster_value

    def moving_phase_for_step(self, step: int) -> float:
        """
        Get animation phase (0.0-1.0) at given step.

        Used for synchronizing foot cycles between movement segments.
        """
        time_from_start = self.animation_time_on_step(step)
        if self._animation_duration <= 0:
            return 0.0
        phase = time_from_start / self._animation_duration
        # Return fractional part (0.0-1.0)
        return phase - int(phase)

    def initial_walking_time_for_phase(self, phase: float) -> float:
        """
        Convert animation phase to initial animation time offset.

        Used when creating a new animatronic that continues from
        the foot cycle phase of a previous one.
        """
        return phase * self._animation_duration

    def copy(self) -> MovingAnimatronic:
        anim = MovingAnimatronic(
            self._animation_type,
            self._start_pose.copy(),
            self._finish_pose.copy(),
            self.start_step,
            self.finish_step,
            self._animation_duration,
            self._angular_speed,
            self._animation_booster_value,
        )
        anim._initial_animation_time = self._initial_animation_time
        return anim
