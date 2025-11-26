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
&#9;&quot;&quot;&quot;A class for 3D transformations tree using Pose3.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, local_pose, parent: 'Transform' = None, name: str = &quot;&quot;):<br>
&#9;&#9;self._local_pose = local_pose<br>
&#9;&#9;self.name = name<br>
&#9;&#9;self.parent = None<br>
&#9;&#9;self.children = []<br>
&#9;&#9;self._global_pose = None<br>
&#9;&#9;self._dirty = True<br>
<br>
&#9;&#9;self._version_for_walking_to_proximal = 0<br>
&#9;&#9;self._version_for_walking_to_distal = 0<br>
&#9;&#9;self._version_only_my = 0<br>
<br>
&#9;&#9;if parent:<br>
&#9;&#9;&#9;parent.add_child(self)<br>
<br>
&#9;def _unparent(self):<br>
&#9;&#9;if self.parent:<br>
&#9;&#9;&#9;self.parent.children.remove(self)<br>
&#9;&#9;&#9;self.parent = None<br>
<br>
&#9;def is_dirty(self):<br>
&#9;&#9;return self._dirty<br>
<br>
&#9;def add_child(self, child: 'Transform'):<br>
&#9;&#9;child._unparent()<br>
&#9;&#9;self.children.append(child)<br>
&#9;&#9;child.parent = self<br>
&#9;&#9;child._mark_dirty()<br>
<br>
&#9;def link(self, child: 'Transform'):<br>
&#9;&#9;&quot;&quot;&quot;Can be overridden to link child transforms differently.&quot;&quot;&quot;<br>
&#9;&#9;self.add_child(child)<br>
<br>
&#9;def relocate(self, pose: Pose3):<br>
&#9;&#9;self._local_pose = pose<br>
&#9;&#9;self._mark_dirty()<br>
<br>
&#9;def relocate_global(self, global_pose):<br>
&#9;&#9;if self.parent:<br>
&#9;&#9;&#9;parent_global = self.parent.global_pose()<br>
&#9;&#9;&#9;inv_parent_global = parent_global.inverse()<br>
&#9;&#9;&#9;self._local_pose = inv_parent_global * global_pose<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;self._local_pose = global_pose<br>
&#9;&#9;self._mark_dirty()<br>
<br>
&#9;def increment_version(self, version):<br>
&#9;&#9;return (version + 1) % (2**31 - 1)<br>
<br>
&#9;def _spread_changes_to_distal(self):<br>
&#9;&#9;self._version_for_walking_to_proximal = self.increment_version(self._version_for_walking_to_proximal)<br>
&#9;&#9;self._dirty = True<br>
&#9;&#9;for child in self.children:<br>
&#9;&#9;&#9;child._spread_changes_to_distal()<br>
<br>
&#9;def _spread_changes_to_proximal(self):<br>
&#9;&#9;self._version_for_walking_to_distal = self.increment_version(self._version_for_walking_to_distal)<br>
&#9;&#9;if self.parent:<br>
&#9;&#9;&#9;self.parent._spread_changes_to_proximal()<br>
<br>
&#9;def _mark_dirty(self):<br>
&#9;&#9;self._version_only_my = self.increment_version(self._version_only_my)<br>
&#9;&#9;self._spread_changes_to_proximal()<br>
&#9;&#9;self._spread_changes_to_distal() <br>
&#9;&#9;# self._dirty = True # already done in _spread_changes_to_distal <br>
<br>
&#9;def local_pose(self) -&gt; Pose3:<br>
&#9;&#9;return self._local_pose<br>
<br>
&#9;def global_pose(self) -&gt; Pose3:<br>
&#9;&#9;if self._dirty:<br>
&#9;&#9;&#9;if self.parent:<br>
&#9;&#9;&#9;&#9;self._global_pose = self.parent.global_pose() * self._local_pose<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;self._global_pose = self._local_pose<br>
&#9;&#9;&#9;self._dirty = False<br>
&#9;&#9;return self._global_pose<br>
<br>
&#9;def _has_ancestor(self, possible_ancestor):<br>
&#9;&#9;current = self.parent<br>
&#9;&#9;while current:<br>
&#9;&#9;&#9;if current == possible_ancestor:<br>
&#9;&#9;&#9;&#9;return True<br>
&#9;&#9;&#9;current = current.parent<br>
&#9;&#9;return False<br>
<br>
&#9;def set_parent(self, parent: 'Transform'):<br>
&#9;&#9;if self._has_ancestor(parent):<br>
&#9;&#9;&#9;raise ValueError(&quot;Cycle detected in Transform hierarchy&quot;)<br>
&#9;&#9;self._unparent()<br>
&#9;&#9;parent.children.append(self)<br>
&#9;&#9;self.parent = parent<br>
&#9;&#9;self._mark_dirty()<br>
<br>
&#9;def transform_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Transform a point from local to global coordinates.&quot;&quot;&quot;<br>
&#9;&#9;global_pose = self.global_pose()<br>
&#9;&#9;return global_pose.transform_point(point)<br>
<br>
&#9;def transform_point_inverse(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Transform a point from global to local coordinates.&quot;&quot;&quot;<br>
&#9;&#9;global_pose = self.global_pose()<br>
&#9;&#9;inv_global_pose = global_pose.inverse()<br>
&#9;&#9;return inv_global_pose.transform_point(point)<br>
<br>
&#9;def transform_vector(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Transform a vector from local to global coordinates.&quot;&quot;&quot;<br>
&#9;&#9;global_pose = self.global_pose()<br>
&#9;&#9;return global_pose.transform_vector(vector)<br>
<br>
&#9;def transform_vector_inverse(self, vector: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Transform a vector from global to local coordinates.&quot;&quot;&quot;<br>
&#9;&#9;global_pose = self.global_pose()<br>
&#9;&#9;inv_global_pose = global_pose.inverse()<br>
&#9;&#9;return inv_global_pose.transform_vector(vector)<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;Transform({self.name}, local_pose={self._local_pose})&quot;<br>
&#9;<br>
&#9;def to_trent_with_children(self, top_without_pose=False) -&gt; str:<br>
&#9;&#9;dct = {<br>
&#9;&#9;&#9;&quot;type&quot; : &quot;transform&quot;,<br>
&#9;&#9;&#9;&quot;name&quot;: self.name,<br>
&#9;&#9;&#9;&quot;children&quot;: [child.to_trent_with_children() for child in self.children]<br>
&#9;&#9;}<br>
&#9;&#9;if not top_without_pose:<br>
&#9;&#9;&#9;dct[&quot;pose&quot;] = {<br>
&#9;&#9;&#9;&#9;&quot;position&quot;: self._local_pose.lin.tolist(),<br>
&#9;&#9;&#9;&#9;&quot;orientation&quot;: self._local_pose.ang.tolist()<br>
&#9;&#9;&#9;}<br>
&#9;&#9;return dct<br>
<br>
<br>
def inspect_tree(transform: 'Transform', level: int = 0, name_only: bool = False):<br>
&#9;indent = &quot;  &quot; * level<br>
&#9;if name_only:<br>
&#9;&#9;print(f&quot;{indent}{transform.name}&quot;)<br>
&#9;else:<br>
&#9;&#9;print(f&quot;{indent}{transform}&quot;)<br>
&#9;for child in transform.children:<br>
&#9;&#9;inspect_tree(child, level + 1, name_only=name_only)<br>
<br>
<br>
class Transform3(Transform):<br>
&#9;&quot;&quot;&quot;A 3D Transform with directional helpers.&quot;&quot;&quot;<br>
&#9;def __init__(self, local_pose: Pose3 = None, parent: 'Transform3' = None, name: str = &quot;&quot;):<br>
&#9;&#9;if local_pose is None:<br>
&#9;&#9;&#9;local_pose = Pose3()<br>
&#9;&#9;super().__init__(local_pose, parent, name)<br>
<br>
&#9;def forward(self, distance: float = 1.0) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Get the forward direction vector in global coordinates.&quot;&quot;&quot;<br>
&#9;&#9;local_forward = numpy.array([0.0, 0.0, distance])<br>
&#9;&#9;return self.transform_vector(local_forward)<br>
<br>
&#9;def up(self, distance: float = 1.0) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Get the up direction vector in global coordinates.&quot;&quot;&quot;<br>
&#9;&#9;local_up = numpy.array([0.0, distance, 0.0])<br>
&#9;&#9;return self.transform_vector(local_up)<br>
<br>
&#9;def right(self, distance: float = 1.0) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Get the right direction vector in global coordinates.&quot;&quot;&quot;<br>
&#9;&#9;local_right = numpy.array([distance, 0.0, 0.0])<br>
&#9;&#9;return self.transform_vector(local_right)<br>
<br>
&#9;def backward(self, distance: float = 1.0) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Get the backward direction vector in global coordinates.&quot;&quot;&quot;<br>
&#9;&#9;return -self.forward(distance)<br>
<br>
&#9;def down(self, distance: float = 1.0) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Get the down direction vector in global coordinates.&quot;&quot;&quot;<br>
&#9;&#9;return -self.up(distance)<br>
<br>
&#9;def left(self, distance: float = 1.0) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Get the left direction vector in global coordinates.&quot;&quot;&quot;<br>
&#9;&#9;return -self.right(distance)<br>
<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
