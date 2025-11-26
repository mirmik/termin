<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/aabb.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
import numpy <br>
from weakref import WeakKeyDictionary<br>
from termin.geomalgo.project import project_point_on_aabb, project_segment_on_aabb<br>
<br>
class AABB:<br>
&#9;&quot;&quot;&quot;Axis-Aligned Bounding Box in 3D space.&quot;&quot;&quot;<br>
&#9;def __init__(self, min_point: numpy.ndarray, max_point: numpy.ndarray):<br>
&#9;&#9;self.min_point = min_point<br>
&#9;&#9;self.max_point = max_point<br>
<br>
&#9;def extend(self, point: numpy.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;Extend the AABB to include the given point.&quot;&quot;&quot;<br>
&#9;&#9;self.min_point = numpy.minimum(self.min_point, point)<br>
&#9;&#9;self.max_point = numpy.maximum(self.max_point, point)<br>
<br>
&#9;def intersects(self, other: &quot;AABB&quot;) -&gt; bool:<br>
&#9;&#9;&quot;&quot;&quot;Check if this AABB intersects with another AABB.&quot;&quot;&quot;<br>
&#9;&#9;return numpy.all(self.max_point &gt;= other.min_point) and numpy.all(other.max_point &gt;= self.min_point)<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;AABB(min_point={self.min_point}, max_point={self.max_point})&quot;<br>
<br>
&#9;@staticmethod<br>
&#9;def from_points(points: numpy.ndarray) -&gt; &quot;AABB&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Create an AABB that encompasses a set of points.&quot;&quot;&quot;<br>
&#9;&#9;min_point = numpy.min(points, axis=0)<br>
&#9;&#9;max_point = numpy.max(points, axis=0)<br>
&#9;&#9;return AABB(min_point, max_point)<br>
<br>
&#9;def merge(self, other: &quot;AABB&quot;) -&gt; &quot;AABB&quot;:<br>
&#9;&#9;&quot;&quot;&quot;Merge this AABB with another AABB and return the resulting AABB.&quot;&quot;&quot;<br>
&#9;&#9;new_min = numpy.minimum(self.min_point, other.min_point)<br>
&#9;&#9;new_max = numpy.maximum(self.max_point, other.max_point)<br>
&#9;&#9;return AABB(new_min, new_max)<br>
<br>
&#9;def get_corners_homogeneous(self) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Get the 8 corners of the AABB in homogeneous coordinates.&quot;&quot;&quot;<br>
&#9;&#9;corners = numpy.array([<br>
&#9;&#9;&#9;[self.min_point[0], self.min_point[1], self.min_point[2], 1.0],<br>
&#9;&#9;&#9;[self.min_point[0], self.min_point[1], self.max_point[2], 1.0], <br>
&#9;&#9;&#9;[self.min_point[0], self.max_point[1], self.min_point[2], 1.0],<br>
&#9;&#9;&#9;[self.min_point[0], self.max_point[1], self.max_point[2], 1.0],<br>
&#9;&#9;&#9;[self.max_point[0], self.min_point[1], self.min_point[2], 1.0],<br>
&#9;&#9;&#9;[self.max_point[0], self.min_point[1], self.max_point[2], 1.0],<br>
&#9;&#9;&#9;[self.max_point[0], self.max_point[1], self.min_point[2], 1.0],<br>
&#9;&#9;&#9;[self.max_point[0], self.max_point[1], self.max_point[2], 1.0],<br>
&#9;&#9;])<br>
&#9;&#9;return corners<br>
&#9;<br>
&#9;def project_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Project a point onto the AABB is performed with clamping.&quot;&quot;&quot;<br>
&#9;&#9;return numpy.minimum(numpy.maximum(point, self.min_point), self.max_point)<br>
&#9;<br>
&#9;def project_segment_on_aabb(self, seg_start: numpy.ndarray, seg_end: numpy.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;Project a segment onto the AABB and return the closest points and distance.&quot;&quot;&quot;<br>
&#9;&#9;return project_segment_on_aabb(seg_start, seg_end, self.min_point, self.max_point)<br>
&#9;&#9;<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;<br>
<br>
class TransformAABB:<br>
&#9;&quot;&quot;&quot;AABB associated with a Transform.&quot;&quot;&quot;<br>
&#9;transform_to_taabb_map = WeakKeyDictionary()<br>
<br>
&#9;def __init__(self, transform: 'Transform', aabb: AABB):<br>
&#9;&#9;self._transform = transform<br>
&#9;&#9;self._my_aabb = aabb<br>
&#9;&#9;self._my_world_aabb = None<br>
&#9;&#9;self._compiled_aabb = None<br>
&#9;&#9;self._last_inspected_version = -1<br>
&#9;&#9;self._last_tree_inspected_version = -1<br>
&#9;&#9;TransformAABB.transform_to_taabb_map[transform] = self<br>
<br>
&#9;def compile_tree_aabb(self) -&gt; AABB:<br>
&#9;&#9;if self._last_tree_inspected_version == self._transform._version_for_walking_to_distal:<br>
&#9;&#9;&#9;return self._compiled_aabb<br>
&#9;&#9;result = self.get_world_aabb()<br>
&#9;&#9;for child in self._transform.children:<br>
&#9;&#9;&#9;child_taabb = TransformAABB.transform_to_taabb_map.get(child)<br>
&#9;&#9;&#9;if child_taabb:<br>
&#9;&#9;&#9;&#9;child_aabb = child_taabb.compile_tree_aabb()<br>
&#9;&#9;&#9;&#9;result = result.merge(child_aabb)<br>
&#9;&#9;self._compiled_aabb = result<br>
&#9;&#9;self._last_tree_inspected_version = self._transform._version_for_walking_to_distal<br>
&#9;&#9;return self._compiled_aabb<br>
<br>
&#9;def get_world_aabb(self) -&gt; AABB:<br>
&#9;&#9;&quot;&quot;&quot;Get the AABB widened by the rotation of the transform.&quot;&quot;&quot;<br>
&#9;&#9;if self._last_inspected_version == self._transform._version_only_my:<br>
&#9;&#9;&#9;return self._my_world_aabb<br>
&#9;&#9;matrix = self._transform.global_pose().as_matrix34()<br>
&#9;&#9;corners = self._my_aabb.get_corners_homogeneous()<br>
&#9;&#9;transformed_corners = numpy.dot(matrix, corners.T).T<br>
&#9;&#9;new_aabb = AABB.from_points(transformed_corners)<br>
&#9;&#9;self._my_world_aabb = new_aabb<br>
&#9;&#9;return new_aabb<br>
<!-- END SCAT CODE -->
</body>
</html>
