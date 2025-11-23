import math
import numpy
from termin.geombase import Pose3

class Transform:
    """A class for 3D transformations tree using Pose3."""

    def __init__(self, local_pose, parent: 'Transform' = None, name: str = ""):
        self._local_pose = local_pose
        self.name = name
        self.parent = None
        self.children = []
        self._global_pose = None
        self._dirty = True

        self._version_for_walking_to_proximal = 0
        self._version_for_walking_to_distal = 0
        self._version_only_my = 0

        if parent:
            parent.add_child(self)

    def _unparent(self):
        if self.parent:
            self.parent.children.remove(self)
            self.parent = None

    def is_dirty(self):
        return self._dirty

    def add_child(self, child: 'Transform'):
        child._unparent()
        self.children.append(child)
        child.parent = self
        child._mark_dirty()

    def link(self, child: 'Transform'):
        """Can be overridden to link child transforms differently."""
        self.add_child(child)

    def relocate(self, pose: Pose3):
        self._local_pose = pose
        self._mark_dirty()

    def relocate_global(self, global_pose):
        if self.parent:
            parent_global = self.parent.global_pose()
            inv_parent_global = parent_global.inverse()
            self._local_pose = inv_parent_global * global_pose
        else:
            self._local_pose = global_pose
        self._mark_dirty()

    def increment_version(self, version):
        return (version + 1) % (2**31 - 1)

    def _spread_changes_to_distal(self):
        self._version_for_walking_to_proximal = self.increment_version(self._version_for_walking_to_proximal)
        self._dirty = True
        for child in self.children:
            child._spread_changes_to_distal()

    def _spread_changes_to_proximal(self):
        self._version_for_walking_to_distal = self.increment_version(self._version_for_walking_to_distal)
        if self.parent:
            self.parent._spread_changes_to_proximal()

    def _mark_dirty(self):
        self._version_only_my = self.increment_version(self._version_only_my)
        self._spread_changes_to_proximal()
        self._spread_changes_to_distal() 
        # self._dirty = True # already done in _spread_changes_to_distal 

    def local_pose(self) -> Pose3:
        return self._local_pose

    def global_pose(self) -> Pose3:
        if self._dirty:
            if self.parent:
                self._global_pose = self.parent.global_pose() * self._local_pose
            else:
                self._global_pose = self._local_pose
            self._dirty = False
        return self._global_pose

    def _has_ancestor(self, possible_ancestor):
        current = self.parent
        while current:
            if current == possible_ancestor:
                return True
            current = current.parent
        return False

    def set_parent(self, parent: 'Transform'):
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
        return f"Transform({self.name}, local_pose={self._local_pose})"
    
    def to_trent_with_children(self, top_without_pose=False) -> str:
        dct = {
            "type" : "transform",
            "name": self.name,
            "children": [child.to_trent_with_children() for child in self.children]
        }
        if not top_without_pose:
            dct["pose"] = {
                "position": self._local_pose.lin.tolist(),
                "orientation": self._local_pose.ang.tolist()
            }
        return dct


def inspect_tree(transform: 'Transform', level: int = 0, name_only: bool = False):
    indent = "  " * level
    if name_only:
        print(f"{indent}{transform.name}")
    else:
        print(f"{indent}{transform}")
    for child in transform.children:
        inspect_tree(child, level + 1, name_only=name_only)


class Transform3(Transform):
    """A 3D Transform with directional helpers."""
    def __init__(self, local_pose: Pose3 = Pose3.identity(), parent: 'Transform3' = None, name: str = ""):
        super().__init__(local_pose, parent, name)

    def forward(self, distance: float) -> numpy.ndarray:
        """Get the forward direction vector in global coordinates."""
        local_forward = numpy.array([0.0, 0.0, distance])
        return self.transform_vector(local_forward)

    def up(self, distance: float) -> numpy.ndarray:
        """Get the up direction vector in global coordinates."""
        local_up = numpy.array([0.0, distance, 0.0])
        return self.transform_vector(local_up)

    def right(self, distance: float) -> numpy.ndarray:
        """Get the right direction vector in global coordinates."""
        local_right = numpy.array([distance, 0.0, 0.0])
        return self.transform_vector(local_right)

    def backward(self, distance: float) -> numpy.ndarray:
        """Get the backward direction vector in global coordinates."""
        return -self.forward(distance)

    def down(self, distance: float) -> numpy.ndarray:
        """Get the down direction vector in global coordinates."""
        return -self.up(distance)

    def left(self, distance: float) -> numpy.ndarray:
        """Get the left direction vector in global coordinates."""
        return -self.right(distance)


