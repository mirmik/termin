<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/transform.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import math<br>
import numpy<br>
from termin.geombase import Pose3<br>
<br>
class Transform:<br>
    &quot;&quot;&quot;A class for 3D transformations tree using Pose3.&quot;&quot;&quot;<br>
<br>
    def __init__(self, local_pose, parent: 'Transform' = None, name: str = &quot;&quot;):<br>
        self._local_pose = local_pose<br>
        self.name = name<br>
        self.parent = None<br>
        self.children = []<br>
        self._global_pose = None<br>
        self._dirty = True<br>
<br>
        self._version_for_walking_to_proximal = 0<br>
        self._version_for_walking_to_distal = 0<br>
        self._version_only_my = 0<br>
<br>
        if parent:<br>
            parent.add_child(self)<br>
<br>
    def _unparent(self):<br>
        if self.parent:<br>
            self.parent.children.remove(self)<br>
            self.parent = None<br>
<br>
    def is_dirty(self):<br>
        return self._dirty<br>
<br>
    def add_child(self, child: 'Transform'):<br>
        child._unparent()<br>
        self.children.append(child)<br>
        child.parent = self<br>
        child._mark_dirty()<br>
<br>
    def link(self, child: 'Transform'):<br>
        &quot;&quot;&quot;Can be overridden to link child transforms differently.&quot;&quot;&quot;<br>
        self.add_child(child)<br>
<br>
    def relocate(self, pose: Pose3):<br>
        self._local_pose = pose<br>
        self._mark_dirty()<br>
<br>
    def relocate_global(self, global_pose):<br>
        if self.parent:<br>
            parent_global = self.parent.global_pose()<br>
            inv_parent_global = parent_global.inverse()<br>
            self._local_pose = inv_parent_global * global_pose<br>
        else:<br>
            self._local_pose = global_pose<br>
        self._mark_dirty()<br>
<br>
    def increment_version(self, version):<br>
        return (version + 1) % (2**31 - 1)<br>
<br>
    def _spread_changes_to_distal(self):<br>
        self._version_for_walking_to_proximal = self.increment_version(self._version_for_walking_to_proximal)<br>
        self._dirty = True<br>
        for child in self.children:<br>
            child._spread_changes_to_distal()<br>
<br>
    def _spread_changes_to_proximal(self):<br>
        self._version_for_walking_to_distal = self.increment_version(self._version_for_walking_to_distal)<br>
        if self.parent:<br>
            self.parent._spread_changes_to_proximal()<br>
<br>
    def _mark_dirty(self):<br>
        self._version_only_my = self.increment_version(self._version_only_my)<br>
        self._spread_changes_to_proximal()<br>
        self._spread_changes_to_distal() <br>
        # self._dirty = True # already done in _spread_changes_to_distal <br>
<br>
    def local_pose(self) -&gt; Pose3:<br>
        return self._local_pose<br>
<br>
    def global_pose(self) -&gt; Pose3:<br>
        if self._dirty:<br>
            if self.parent:<br>
                self._global_pose = self.parent.global_pose() * self._local_pose<br>
            else:<br>
                self._global_pose = self._local_pose<br>
            self._dirty = False<br>
        return self._global_pose<br>
<br>
    def _has_ancestor(self, possible_ancestor):<br>
        current = self.parent<br>
        while current:<br>
            if current == possible_ancestor:<br>
                return True<br>
            current = current.parent<br>
        return False<br>
<br>
    def set_parent(self, parent: 'Transform'):<br>
        if self._has_ancestor(parent):<br>
            raise ValueError(&quot;Cycle detected in Transform hierarchy&quot;)<br>
        self._unparent()<br>
        parent.children.append(self)<br>
        self.parent = parent<br>
        self._mark_dirty()<br>
<br>
    def transform_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Transform a point from local to global coordinates.&quot;&quot;&quot;<br>
        global_pose = self.global_pose()<br>
        return global_pose.transform_point(point)<br>
<br>
    def transform_point_inverse(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Transform a point from global to local coordinates.&quot;&quot;&quot;<br>
        global_pose = self.global_pose()<br>
        inv_global_pose = global_pose.inverse()<br>
        return inv_global_pose.transform_point(point)<br>
<br>
    def transform_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Transform a vector from local to global coordinates.&quot;&quot;&quot;<br>
        global_pose = self.global_pose()<br>
        return global_pose.transform_vector(vector)<br>
<br>
    def transform_vector_inverse(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Transform a vector from global to local coordinates.&quot;&quot;&quot;<br>
        global_pose = self.global_pose()<br>
        inv_global_pose = global_pose.inverse()<br>
        return inv_global_pose.transform_vector(vector)<br>
<br>
    def __repr__(self):<br>
        return f&quot;Transform({self.name}, local_pose={self._local_pose})&quot;<br>
    <br>
    def to_trent_with_children(self, top_without_pose=False) -&gt; str:<br>
        dct = {<br>
            &quot;type&quot; : &quot;transform&quot;,<br>
            &quot;name&quot;: self.name,<br>
            &quot;children&quot;: [child.to_trent_with_children() for child in self.children]<br>
        }<br>
        if not top_without_pose:<br>
            dct[&quot;pose&quot;] = {<br>
                &quot;position&quot;: self._local_pose.lin.tolist(),<br>
                &quot;orientation&quot;: self._local_pose.ang.tolist()<br>
            }<br>
        return dct<br>
<br>
<br>
def inspect_tree(transform: 'Transform', level: int = 0, name_only: bool = False):<br>
    indent = &quot;  &quot; * level<br>
    if name_only:<br>
        print(f&quot;{indent}{transform.name}&quot;)<br>
    else:<br>
        print(f&quot;{indent}{transform}&quot;)<br>
    for child in transform.children:<br>
        inspect_tree(child, level + 1, name_only=name_only)<br>
<br>
<br>
class Transform3(Transform):<br>
    &quot;&quot;&quot;A 3D Transform with directional helpers.&quot;&quot;&quot;<br>
    def __init__(self, local_pose: Pose3 = None, parent: 'Transform3' = None, name: str = &quot;&quot;):<br>
        if local_pose is None:<br>
            local_pose = Pose3()<br>
        super().__init__(local_pose, parent, name)<br>
<br>
    def forward(self, distance: float = 1.0) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Get the forward direction vector in global coordinates.&quot;&quot;&quot;<br>
        local_forward = numpy.array([0.0, 0.0, distance])<br>
        return self.transform_vector(local_forward)<br>
<br>
    def up(self, distance: float = 1.0) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Get the up direction vector in global coordinates.&quot;&quot;&quot;<br>
        local_up = numpy.array([0.0, distance, 0.0])<br>
        return self.transform_vector(local_up)<br>
<br>
    def right(self, distance: float = 1.0) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Get the right direction vector in global coordinates.&quot;&quot;&quot;<br>
        local_right = numpy.array([distance, 0.0, 0.0])<br>
        return self.transform_vector(local_right)<br>
<br>
    def backward(self, distance: float = 1.0) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Get the backward direction vector in global coordinates.&quot;&quot;&quot;<br>
        return -self.forward(distance)<br>
<br>
    def down(self, distance: float = 1.0) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Get the down direction vector in global coordinates.&quot;&quot;&quot;<br>
        return -self.up(distance)<br>
<br>
    def left(self, distance: float = 1.0) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Get the left direction vector in global coordinates.&quot;&quot;&quot;<br>
        return -self.right(distance)<br>
<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
