"""GeneralTransform3 - Transform using GeneralPose3 with scale inheritance.

This is a copy of Transform3, adapted to use GeneralPose3 instead of Pose3.
Scale is inherited through the transform hierarchy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import numpy

from termin.geombase.general_pose3 import GeneralPose3
from termin.geombase.pose3 import Pose3

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity


class GeneralTransform3:
    """Transform node using GeneralPose3 (with scale inheritance)."""

    def __init__(
        self,
        local_pose: GeneralPose3 = None,
        parent: 'GeneralTransform3' = None,
        name: str = ""
    ):
        if local_pose is None:
            local_pose = GeneralPose3.identity()
        self._local_pose = local_pose
        self.name = name
        self.parent: Optional[GeneralTransform3] = None
        self.children: List[GeneralTransform3] = []
        self._global_pose: Optional[GeneralPose3] = None
        self._dirty = True
        self.entity: Optional['Entity'] = None

        self._version_for_walking_to_proximal = 0
        self._version_for_walking_to_distal = 0
        self._version_only_my = 0

        if parent:
            parent.add_child(self)

    def _unparent(self):
        if self.parent:
            self.parent.children.remove(self)
            self.parent = None

    def is_dirty(self) -> bool:
        return self._dirty

    def add_child(self, child: 'GeneralTransform3'):
        child._unparent()
        self.children.append(child)
        child.parent = self
        child._mark_dirty()

    def link(self, child: 'GeneralTransform3'):
        """Can be overridden to link child transforms differently."""
        self.add_child(child)

    def relocate(self, pose: GeneralPose3 | Pose3):
        """Set local pose. Accepts both GeneralPose3 and Pose3 (converting Pose3 to GeneralPose3)."""
        if isinstance(pose, Pose3):
            # Convert Pose3 to GeneralPose3, preserving current scale
            current_scale = self._local_pose.scale.copy()
            pose = GeneralPose3(
                ang=pose.ang.copy(),
                lin=pose.lin.copy(),
                scale=current_scale
            )
        self._local_pose = pose
        self._mark_dirty()

    def relocate_global(self, global_pose: GeneralPose3 | Pose3):
        """Set global pose by computing corresponding local pose."""
        if isinstance(global_pose, Pose3):
            # Convert Pose3 to GeneralPose3, preserving current GLOBAL scale
            # (not local scale, to avoid scale drift when parent has non-unit scale)
            current_global_scale = self.global_pose().scale.copy()
            global_pose = GeneralPose3(
                ang=global_pose.ang.copy(),
                lin=global_pose.lin.copy(),
                scale=current_global_scale
            )
        if self.parent:
            parent_global = self.parent.global_pose()
            inv_parent_global = parent_global.inverse()
            self._local_pose = inv_parent_global * global_pose
        else:
            self._local_pose = global_pose
        self._mark_dirty()

    def increment_version(self, version: int) -> int:
        return (version + 1) % (2**31 - 1)

    def _spread_changes_to_distal(self):
        self._version_for_walking_to_proximal = self.increment_version(
            self._version_for_walking_to_proximal
        )
        self._dirty = True
        for child in self.children:
            child._spread_changes_to_distal()

    def _spread_changes_to_proximal(self):
        self._version_for_walking_to_distal = self.increment_version(
            self._version_for_walking_to_distal
        )
        if self.parent:
            self.parent._spread_changes_to_proximal()

    def _mark_dirty(self):
        self._version_only_my = self.increment_version(self._version_only_my)
        self._spread_changes_to_proximal()
        self._spread_changes_to_distal()

    def local_pose(self) -> GeneralPose3:
        """Get local pose."""
        return self._local_pose

    def global_pose(self) -> GeneralPose3:
        """Get global pose (computed from parent chain).

        Scale is inherited: child global position = parent.lin + rot(parent.ang, parent.scale * child.lin)
        """
        if self._dirty:
            if self.parent:
                self._global_pose = self.parent.global_pose() * self._local_pose
            else:
                self._global_pose = self._local_pose
            self._dirty = False
        return self._global_pose

    def world_matrix(self) -> numpy.ndarray:
        """Return 4x4 homogeneous transformation matrix in world coordinates."""
        return self.global_pose().as_matrix()

    def _has_ancestor(self, possible_ancestor: 'GeneralTransform3') -> bool:
        current = self.parent
        while current:
            if current == possible_ancestor:
                return True
            current = current.parent
        return False

    def set_parent(self, parent: 'GeneralTransform3'):
        if self._has_ancestor(parent):
            raise ValueError("Cycle detected in Transform hierarchy")
        self._unparent()
        parent.children.append(self)
        self.parent = parent
        self._mark_dirty()

    def transform_point(self, point: numpy.ndarray) -> numpy.ndarray:
        """Transform a point from local to global coordinates."""
        global_pose = self.global_pose()
        return global_pose.transform_point(point)

    def transform_point_inverse(self, point: numpy.ndarray) -> numpy.ndarray:
        """Transform a point from global to local coordinates."""
        global_pose = self.global_pose()
        inv_global_pose = global_pose.inverse()
        return inv_global_pose.transform_point(point)

    def transform_vector(self, vector: numpy.ndarray) -> numpy.ndarray:
        """Transform a vector from local to global coordinates."""
        global_pose = self.global_pose()
        return global_pose.transform_vector(vector)

    def transform_vector_inverse(self, vector: numpy.ndarray) -> numpy.ndarray:
        """Transform a vector from global to local coordinates."""
        global_pose = self.global_pose()
        inv_global_pose = global_pose.inverse()
        return inv_global_pose.transform_vector(vector)

    def __repr__(self):
        return f"GeneralTransform3({self.name}, local_pose={self._local_pose})"

    # Direction helpers using Y-forward convention (X=right, Y=forward, Z=up)

    def forward(self, distance: float = 1.0) -> numpy.ndarray:
        """Get the forward direction vector in global coordinates (Y-axis)."""
        local_forward = numpy.array([0.0, distance, 0.0])
        return self.transform_vector(local_forward)

    def up(self, distance: float = 1.0) -> numpy.ndarray:
        """Get the up direction vector in global coordinates (Z-axis)."""
        local_up = numpy.array([0.0, 0.0, distance])
        return self.transform_vector(local_up)

    def right(self, distance: float = 1.0) -> numpy.ndarray:
        """Get the right direction vector in global coordinates (X-axis)."""
        local_right = numpy.array([distance, 0.0, 0.0])
        return self.transform_vector(local_right)

    def backward(self, distance: float = 1.0) -> numpy.ndarray:
        """Get the backward direction vector in global coordinates."""
        return -self.forward(distance)

    def down(self, distance: float = 1.0) -> numpy.ndarray:
        """Get the down direction vector in global coordinates."""
        return -self.up(distance)

    def left(self, distance: float = 1.0) -> numpy.ndarray:
        """Get the left direction vector in global coordinates."""
        return -self.right(distance)
