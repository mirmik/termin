"""
UnitPath - describes a path for actor movement.

Matches original C# UnitPath structure:
- UnitPath is a sequence of waypoints (UnitPathPoint)
- Each waypoint has position, type, normal, and optional braced_coordinates
- Used by MovingCommand to create movement animatronics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Iterator

from termin.geombase import Vec3

if TYPE_CHECKING:
    pass


class UnitPathPointType(Enum):
    """
    Type of movement at a waypoint.

    Matches original C# UnitPathPointType enum.
    """
    STANDART_MESH = auto()       # Standard walking/running on navmesh
    DOWN_TO_BRACED = auto()      # Going down to braced position
    BRACED_TO_UP = auto()        # From braced going up
    JUMP_DOWN = auto()           # Jumping down
    UNKNOWN = auto()             # Unknown type
    BRACED_CLIMBING_LINK = auto()  # Climbing link on braced surface
    BRACED_HANG = auto()         # Hanging on braced surface
    DOOR_LINK = auto()           # Going through door
    AIR_STRIKE = auto()          # Air strike movement
    LEAN = auto()                # Leaning movement
    TO_UPSTAIRS_ZONE = auto()    # Entering upstairs zone
    FROM_UPSTAIRS_ZONE = auto()  # Leaving upstairs zone
    UPSTAIRS_MOVE = auto()       # Moving on stairs
    TO_BURROW_ZONE = auto()      # Entering burrow zone
    FROM_BURROW_ZONE = auto()    # Leaving burrow zone


@dataclass
class BracedCoordinates:
    """Coordinates for braced (climbing) positions."""
    top_position: Vec3 = field(default_factory=lambda: Vec3(0, 0, 0))
    edge_position: Vec3 = field(default_factory=lambda: Vec3(0, 0, 0))
    normal: Vec3 = field(default_factory=lambda: Vec3(0, 0, 1))

    def copy(self) -> BracedCoordinates:
        return BracedCoordinates(
            top_position=Vec3(self.top_position.x, self.top_position.y, self.top_position.z),
            edge_position=Vec3(self.edge_position.x, self.edge_position.y, self.edge_position.z),
            normal=Vec3(self.normal.x, self.normal.y, self.normal.z),
        )


@dataclass
class UnitPathPoint:
    """
    A single waypoint in a UnitPath.

    Matches original C# UnitPathPoint struct.
    """
    position: Vec3
    point_type: UnitPathPointType = UnitPathPointType.STANDART_MESH
    normal: Vec3 = field(default_factory=lambda: Vec3(0, 0, 1))  # Up direction at this point
    braced_coordinates: BracedCoordinates | None = None

    def copy(self) -> UnitPathPoint:
        """Create a copy of this point."""
        return UnitPathPoint(
            position=Vec3(self.position.x, self.position.y, self.position.z),
            point_type=self.point_type,
            normal=Vec3(self.normal.x, self.normal.y, self.normal.z),
            braced_coordinates=self.braced_coordinates.copy() if self.braced_coordinates else None,
        )

    def __str__(self) -> str:
        return f"Position: ({self.position.x:.2f}, {self.position.y:.2f}, {self.position.z:.2f}), Type: {self.point_type.name}"


class UnitPath:
    """
    A path consisting of waypoints for actor movement.

    Matches original C# UnitPath class:
    - Iterable collection of UnitPathPoint
    - Has start_position (position before first waypoint)
    - Used by MovingCommand to generate movement animatronics

    Usage:
    1. Create UnitPath from pathfinding result
    2. Pass to MovingCommand which calls actor.plan_path()
    """

    def __init__(self) -> None:
        self._pass_points: list[UnitPathPoint] = []
        self._start_position: Vec3 | None = None

    @property
    def start_position(self) -> Vec3 | None:
        """Starting position (before first waypoint)."""
        return self._start_position

    def clear(self) -> None:
        """Remove all waypoints."""
        self._pass_points.clear()
        self._start_position = None

    def set_start_position(self, position: Vec3) -> None:
        """Set the starting position."""
        self._start_position = Vec3(position.x, position.y, position.z)

    def add_pass_point(
        self,
        position: Vec3,
        point_type: UnitPathPointType = UnitPathPointType.STANDART_MESH,
        normal: Vec3 | None = None,
        braced_coordinates: BracedCoordinates | None = None,
    ) -> UnitPathPoint:
        """
        Add a waypoint to the path.

        Matches original AddPassPoint method.
        """
        if normal is None:
            normal = Vec3(0, 0, 1)

        point = UnitPathPoint(
            position=Vec3(position.x, position.y, position.z),
            point_type=point_type,
            normal=Vec3(normal.x, normal.y, normal.z),
            braced_coordinates=braced_coordinates,
        )
        self._pass_points.append(point)
        return point

    def remove_last(self) -> None:
        """Remove the last waypoint."""
        if self._pass_points:
            self._pass_points.pop()

    def change_final_point_to_lean(self) -> None:
        """Change the type of the last point to Lean."""
        if self._pass_points:
            self._pass_points[-1].point_type = UnitPathPointType.LEAN

    @property
    def count(self) -> int:
        """Number of waypoints (matches original Count property)."""
        return len(self._pass_points)

    def __len__(self) -> int:
        return len(self._pass_points)

    def __getitem__(self, index: int) -> UnitPathPoint:
        return self._pass_points[index]

    def __setitem__(self, index: int, value: UnitPathPoint) -> None:
        self._pass_points[index] = value

    def __iter__(self) -> Iterator[UnitPathPoint]:
        return iter(self._pass_points)

    def is_empty(self) -> bool:
        """Check if path has no waypoints."""
        return len(self._pass_points) == 0

    def total_distance(self) -> float:
        """Calculate total path distance."""
        if len(self._pass_points) < 1:
            return 0.0

        total = 0.0

        # Distance from start to first point
        if self._start_position is not None and len(self._pass_points) > 0:
            first = self._pass_points[0].position
            dx = first.x - self._start_position.x
            dy = first.y - self._start_position.y
            dz = first.z - self._start_position.z
            total += (dx * dx + dy * dy + dz * dz) ** 0.5

        # Distance between consecutive points
        for i in range(1, len(self._pass_points)):
            prev = self._pass_points[i - 1].position
            curr = self._pass_points[i].position
            dx = curr.x - prev.x
            dy = curr.y - prev.y
            dz = curr.z - prev.z
            total += (dx * dx + dy * dy + dz * dz) ** 0.5

        return total

    def copy(self) -> UnitPath:
        """Create a copy of this path."""
        new_path = UnitPath()
        if self._start_position is not None:
            new_path._start_position = Vec3(
                self._start_position.x,
                self._start_position.y,
                self._start_position.z,
            )
        for point in self._pass_points:
            new_path._pass_points.append(point.copy())
        return new_path

    @classmethod
    def from_positions(
        cls,
        positions: list[Vec3],
        point_type: UnitPathPointType = UnitPathPointType.STANDART_MESH,
    ) -> UnitPath:
        """
        Create UnitPath from a list of positions.

        First position becomes start_position, rest are waypoints.

        Args:
            positions: List of Vec3 positions.
            point_type: Type for all points (default STANDART_MESH).

        Returns:
            New UnitPath with the given positions.
        """
        path = cls()
        if positions:
            path.set_start_position(positions[0])
            for pos in positions[1:]:
                path.add_pass_point(pos, point_type)
        return path

    @classmethod
    def from_numpy_positions(
        cls,
        positions: list,
        point_type: UnitPathPointType = UnitPathPointType.STANDART_MESH,
    ) -> UnitPath:
        """
        Create UnitPath from a list of numpy arrays.

        First position becomes start_position, rest are waypoints.

        Args:
            positions: List of numpy arrays (3D positions).
            point_type: Type for all points (default STANDART_MESH).

        Returns:
            New UnitPath with the given positions.
        """
        path = cls()
        if positions:
            first = positions[0]
            path.set_start_position(Vec3(float(first[0]), float(first[1]), float(first[2])))
            for pos in positions[1:]:
                path.add_pass_point(
                    Vec3(float(pos[0]), float(pos[1]), float(pos[2])),
                    point_type,
                )
        return path

    def info(self) -> str:
        """Debug info."""
        lines = [f"UnitPath: {len(self._pass_points)} points, distance={self.total_distance():.2f}"]
        if self._start_position:
            lines.append(f"  start: ({self._start_position.x:.2f}, {self._start_position.y:.2f}, {self._start_position.z:.2f})")
        for i, p in enumerate(self._pass_points):
            lines.append(f"  [{i}] ({p.position.x:.2f}, {p.position.y:.2f}, {p.position.z:.2f}) {p.point_type.name}")
        return "\n".join(lines)
