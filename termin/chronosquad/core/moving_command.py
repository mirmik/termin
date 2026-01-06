"""
MovingCommand - command for moving an actor to a target position.

Matches original C# MovingCommand behavior:
- Uses PathFinding to create UnitPath
- Calls plan_path equivalent to convert UnitPath to animatronics
- Uses MovingAnimatronic for movement
- Synchronizes animation phase between movement segments
"""

from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

from termin.geombase import Vec3, Quat, Pose3

from .actor_command import ActorCommand
from .animatronic import MovingAnimatronic, AnimationType, get_animation_duration
from .unit_path import UnitPath, UnitPathPointType
from .timeline import GAME_FREQUENCY

if TYPE_CHECKING:
    from .object_of_timeline import ObjectOfTimeline
    from .timeline import Timeline
    from .command_buffer import CommandBuffer


def _look_rotation(direction: Vec3) -> Quat:
    """
    Create a rotation that looks in the given direction.

    Convention: Forward = +Y, Up = +Z.
    Returns identity if direction is zero.
    """
    length = direction.norm()
    if length < 0.001:
        return Quat.identity()

    # Normalize direction (in XY plane)
    dx = direction.x / length
    dy = direction.y / length

    # Calculate angle from +Y axis (forward direction)
    angle = -math.atan2(dx, dy)

    # Rotation around Z axis
    return Quat.from_axis_angle(Vec3(0, 0, 1), angle)


class WalkingType(Enum):
    """Type of walking animation/speed."""
    WALK = "walk"
    RUN = "run"
    CROUCH = "crouch"
    SPRINT = "sprint"
    BRACED_HANG_LEFT = "braced_hang_left"
    BRACED_HANG_RIGHT = "braced_hang_right"


def walk_type_to_animation_type(walking_type: WalkingType) -> AnimationType:
    """Convert WalkingType to AnimationType (matches original WalkTypeToAnimationType)."""
    if walking_type == WalkingType.WALK:
        return AnimationType.WALK
    elif walking_type == WalkingType.RUN:
        return AnimationType.RUN
    elif walking_type == WalkingType.CROUCH:
        return AnimationType.CROUCH_WALK
    elif walking_type == WalkingType.SPRINT:
        return AnimationType.SPRINT
    elif walking_type == WalkingType.BRACED_HANG_LEFT:
        return AnimationType.BRACED_HANG_LEFT
    elif walking_type == WalkingType.BRACED_HANG_RIGHT:
        return AnimationType.BRACED_HANG_RIGHT
    return AnimationType.WALK


# Speed in units per second for each animation type
ANIMATION_SPEEDS: dict[AnimationType, float] = {
    AnimationType.WALK: 1.5,
    AnimationType.RUN: 5.0,
    AnimationType.CROUCH_WALK: 0.8,
    AnimationType.SPRINT: 8.0,
    AnimationType.LOW_GRAVITY_WALK: 1.2,
    AnimationType.LOW_GRAVITY_RUN: 4.0,
    AnimationType.ZERO_GRAVITY_WALK: 1.0,
    AnimationType.ZERO_GRAVITY_CRAWL: 0.5,
    AnimationType.BRACED_HANG_LEFT: 0.5,
    AnimationType.BRACED_HANG_RIGHT: 0.5,
}


def walk_speed(anim_type: AnimationType) -> float:
    """Get movement speed for animation type (matches original WalkSpeed)."""
    speed = ANIMATION_SPEEDS.get(anim_type, 1.0)
    if speed <= 0:
        raise ValueError(f"WalkSpeed for {anim_type} is {speed}")
    return speed


# Legacy mapping for backwards compatibility
WALKING_SPEEDS = {
    WalkingType.WALK: 1.5,
    WalkingType.RUN: 5.0,
    WalkingType.CROUCH: 0.8,
    WalkingType.SPRINT: 8.0,
}


def make_unit_path_for_moving(
    start_position: Vec3,
    target_position: Vec3,
) -> UnitPath:
    """
    Create UnitPath for movement using PathfindingWorldComponent.

    Matches original PathFinding.MakeUnitPathForMoving():
    - Tries to find path using pathfinding
    - Falls back to direct line if no pathfinding available

    Args:
        start_position: Starting position.
        target_position: Target position.

    Returns:
        UnitPath with waypoints.
    """
    from termin.navmesh.pathfinding_world_component import PathfindingWorldComponent

    pathfinding = PathfindingWorldComponent.instance()

    if pathfinding is not None:
        # Use pathfinding to find path
        start = np.array([start_position.x, start_position.y, start_position.z], dtype=np.float32)
        end = np.array([target_position.x, target_position.y, target_position.z], dtype=np.float32)

        path_points = pathfinding.find_path(start, end)

        if path_points is not None and len(path_points) >= 2:
            # Convert to UnitPath
            unit_path = UnitPath.from_numpy_positions(path_points, UnitPathPointType.STANDART_MESH)
            return unit_path

    # Fallback: direct line
    unit_path = UnitPath()
    unit_path.set_start_position(start_position)
    unit_path.add_pass_point(target_position, UnitPathPointType.STANDART_MESH)
    return unit_path


class MovingCommand(ActorCommand):
    """
    Command that moves an actor to a target position.

    Matches original C# MovingCommand:
    - Uses PathFinding.MakeUnitPathForMoving() to create UnitPath
    - Calls ApplyUnitPath() which uses actor.PlanPath() to create animatronics
    - Creates MovingAnimatronic for each path segment
    - Synchronizes animation phase between segments
    """

    def __init__(
        self,
        target_position: Vec3,
        walking_type: WalkingType,
        start_step: int,
    ):
        super().__init__(start_step)
        self._target_position = target_position
        self._walking_type = walking_type
        self._created_animatronics: list[MovingAnimatronic] = []

    @property
    def target_position(self) -> Vec3:
        return self._target_position

    @property
    def walking_type(self) -> WalkingType:
        return self._walking_type

    def execute_first_time(self, actor: ObjectOfTimeline, timeline: Timeline) -> bool:
        """
        Create movement animatronics.

        Matches original MovingCommand.MovingPhase():
        1. Create UnitPath using pathfinding
        2. Call plan_path equivalent to convert UnitPath to animatronics
        """
        if timeline.is_past:
            actor.drop_to_current()

        # Get current position
        current_pos = actor.current_position()
        target = self._target_position

        # Calculate distance to check if we're already there
        dx = target.x - current_pos.x
        dy = target.y - current_pos.y
        dz = target.z - current_pos.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        if distance < 0.01:
            return True  # Already at target

        # Create UnitPath using pathfinding (matches PathFinding.MakeUnitPathForMoving)
        unit_path = make_unit_path_for_moving(current_pos, target)

        if unit_path.is_empty():
            return True  # No path found

        # Plan path - convert UnitPath to animatronics (matches Actor.PlanPath)
        self._created_animatronics = self._plan_path(
            actor, unit_path, self._walking_type, self._start_step
        )

        # Add animatronics to actor (matches Actor.ApplyAnimatronicsList)
        for anim in self._created_animatronics:
            actor.add_animatronic(anim)

        return len(self._created_animatronics) == 0

    def _plan_path(
        self,
        actor: ObjectOfTimeline,
        path: UnitPath,
        walking_type: WalkingType,
        local_start_step: int,
    ) -> list[MovingAnimatronic]:
        """
        Convert UnitPath to list of animatronics.

        Matches original Actor.PlanPath():
        - Iterates over each point in UnitPath
        - Creates appropriate animatronic based on point type
        - For STANDART_MESH, calls move_to equivalent
        """
        animatronics: list[MovingAnimatronic] = []

        current_pose = Pose3(actor.local_rotation, actor.current_position())
        current_step = local_start_step

        for point in path:
            target_pos = point.position
            point_type = point.point_type
            normal = point.normal

            if point_type in (UnitPathPointType.STANDART_MESH, UnitPathPointType.UNKNOWN):
                # Standard movement - use move_to equivalent
                anim, final_pose, final_step = self._move_to(
                    target_pos,
                    current_step,
                    current_pose,
                    walking_type,
                    animatronics,  # For animation phase sync
                    normal,
                )
                if anim is not None:
                    animatronics.append(anim)
                    current_pose = final_pose
                    current_step = final_step
            else:
                # For other point types, use simple linear movement for now
                # TODO: implement specialized handlers (jump_down, climb, etc.)
                anim, final_pose, final_step = self._move_to(
                    target_pos,
                    current_step,
                    current_pose,
                    walking_type,
                    animatronics,
                    normal,
                )
                if anim is not None:
                    animatronics.append(anim)
                    current_pose = final_pose
                    current_step = final_step

        return animatronics

    def _move_to(
        self,
        target_pos: Vec3,
        local_start_step: int,
        start_pose: Pose3,
        walking_type: WalkingType,
        previous_animatronics: list[MovingAnimatronic],
        normal: Vec3,
    ) -> tuple[MovingAnimatronic | None, Pose3, int]:
        """
        Create MovingAnimatronic for movement to target.

        Matches original Actor.move_to():
        - Calculates distance and duration
        - Creates MovingAnimatronic
        - Synchronizes animation phase with previous animatronic
        """
        current_pos = start_pose.lin

        # Calculate direction and distance
        dx = target_pos.x - current_pos.x
        dy = target_pos.y - current_pos.y
        dz = target_pos.z - current_pos.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        if distance < 0.01:
            return None, start_pose, local_start_step

        # Get animation parameters
        anim_type = walk_type_to_animation_type(walking_type)
        anim_duration = get_animation_duration(anim_type)
        speed = walk_speed(anim_type)

        # Calculate target rotation (look in movement direction)
        direction = Vec3(dx, dy, 0)  # Horizontal direction only
        if direction.norm() > 0.001:
            target_rot = _look_rotation(direction)
        else:
            target_rot = start_pose.ang

        # Calculate duration: finish_step = start_step + (dist / speed * GAME_FREQUENCY)
        duration_steps = max(1, int(distance / speed * GAME_FREQUENCY))

        start_step = local_start_step
        finish_step = start_step + duration_steps

        # Ensure finish_step > start_step
        if finish_step == start_step:
            finish_step += 1

        # Create poses
        finish_pose = Pose3(target_rot, target_pos)

        # Create MovingAnimatronic
        anim = MovingAnimatronic(
            animation_type=anim_type,
            start_pose=start_pose,
            finish_pose=finish_pose,
            start_step=start_step,
            finish_step=finish_step,
            animation_duration=anim_duration,
        )

        # Synchronize animation phase with previous animatronic
        # (matches original: continue foot cycle from previous movement)
        if previous_animatronics:
            last_anim = previous_animatronics[-1]
            moving_phase = last_anim.moving_phase_for_step(start_step)
            initial_animation_time = anim.initial_walking_time_for_phase(moving_phase)
            anim.set_initial_animation_time(initial_animation_time)

        return anim, finish_pose, finish_step

    def execute(self, actor: ObjectOfTimeline, timeline: Timeline) -> bool:
        """
        Check if movement is complete.

        Returns True when actor reaches target.
        """
        if not self._created_animatronics:
            return True

        # Check if last animatronic has finished
        last_anim = self._created_animatronics[-1]
        if actor.local_step >= last_anim.finish_step:
            return True

        # Check distance to target (AllowedMovingError)
        current_pos = actor.current_position()
        dx = self._target_position.x - current_pos.x
        dy = self._target_position.y - current_pos.y
        dz = self._target_position.z - current_pos.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        if distance < 0.05:  # Utility.AllowedMovingError
            return True

        return False

    def cancel_handler(self, command_buffer: CommandBuffer) -> None:
        """Called when command is cancelled."""
        pass

    def clone(self) -> MovingCommand:
        """Create a copy of this command."""
        cmd = MovingCommand(
            Vec3(self._target_position.x, self._target_position.y, self._target_position.z),
            self._walking_type,
            self._start_step,
        )
        cmd._finish_step = self._finish_step
        return cmd

    def hash_code(self) -> int:
        """Hash for deduplication."""
        return hash((
            "MovingCommand",
            self._start_step,
            round(self._target_position.x, 3),
            round(self._target_position.y, 3),
            round(self._target_position.z, 3),
            self._walking_type,
        ))

    def info(self) -> str:
        return (
            f"MovingCommand(start={self._start_step}, "
            f"target={self._target_position}, type={self._walking_type.value})"
        )
