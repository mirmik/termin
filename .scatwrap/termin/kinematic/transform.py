<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/transform.py</title>
</head>
<body>
<pre><code>
import math
import numpy
from termin.geombase import Pose3

class Transform:
    &quot;&quot;&quot;A class for 3D transformations tree using Pose3.&quot;&quot;&quot;

    def __init__(self, local_pose, parent: 'Transform' = None, name: str = &quot;&quot;):
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
        &quot;&quot;&quot;Can be overridden to link child transforms differently.&quot;&quot;&quot;
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

    def local_pose(self) -&gt; Pose3:
        return self._local_pose

    def global_pose(self) -&gt; Pose3:
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
            raise ValueError(&quot;Cycle detected in Transform hierarchy&quot;)
        self._unparent()
        parent.children.append(self)
        self.parent = parent
        self._mark_dirty()

    def transform_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Transform a point from local to global coordinates.&quot;&quot;&quot;
        global_pose = self.global_pose()
        return global_pose.transform_point(point)

    def transform_point_inverse(self, point: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Transform a point from global to local coordinates.&quot;&quot;&quot;
        global_pose = self.global_pose()
        inv_global_pose = global_pose.inverse()
        return inv_global_pose.transform_point(point)

    def transform_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Transform a vector from local to global coordinates.&quot;&quot;&quot;
        global_pose = self.global_pose()
        return global_pose.transform_vector(vector)

    def transform_vector_inverse(self, vector: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Transform a vector from global to local coordinates.&quot;&quot;&quot;
        global_pose = self.global_pose()
        inv_global_pose = global_pose.inverse()
        return inv_global_pose.transform_vector(vector)

    def __repr__(self):
        return f&quot;Transform({self.name}, local_pose={self._local_pose})&quot;
    
    def to_trent_with_children(self, top_without_pose=False) -&gt; str:
        dct = {
            &quot;type&quot; : &quot;transform&quot;,
            &quot;name&quot;: self.name,
            &quot;children&quot;: [child.to_trent_with_children() for child in self.children]
        }
        if not top_without_pose:
            dct[&quot;pose&quot;] = {
                &quot;position&quot;: self._local_pose.lin.tolist(),
                &quot;orientation&quot;: self._local_pose.ang.tolist()
            }
        return dct


def inspect_tree(transform: 'Transform', level: int = 0, name_only: bool = False):
    indent = &quot;  &quot; * level
    if name_only:
        print(f&quot;{indent}{transform.name}&quot;)
    else:
        print(f&quot;{indent}{transform}&quot;)
    for child in transform.children:
        inspect_tree(child, level + 1, name_only=name_only)


class Transform3(Transform):
    &quot;&quot;&quot;A 3D Transform with directional helpers.&quot;&quot;&quot;
    def __init__(self, local_pose: Pose3 = None, parent: 'Transform3' = None, name: str = &quot;&quot;):
        if local_pose is None:
            local_pose = Pose3()
        super().__init__(local_pose, parent, name)

    def forward(self, distance: float = 1.0) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Get the forward direction vector in global coordinates.&quot;&quot;&quot;
        local_forward = numpy.array([0.0, 0.0, distance])
        return self.transform_vector(local_forward)

    def up(self, distance: float = 1.0) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Get the up direction vector in global coordinates.&quot;&quot;&quot;
        local_up = numpy.array([0.0, distance, 0.0])
        return self.transform_vector(local_up)

    def right(self, distance: float = 1.0) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Get the right direction vector in global coordinates.&quot;&quot;&quot;
        local_right = numpy.array([distance, 0.0, 0.0])
        return self.transform_vector(local_right)

    def backward(self, distance: float = 1.0) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Get the backward direction vector in global coordinates.&quot;&quot;&quot;
        return -self.forward(distance)

    def down(self, distance: float = 1.0) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Get the down direction vector in global coordinates.&quot;&quot;&quot;
        return -self.up(distance)

    def left(self, distance: float = 1.0) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Get the left direction vector in global coordinates.&quot;&quot;&quot;
        return -self.right(distance)



</code></pre>
</body>
</html>
