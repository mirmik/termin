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
    &quot;&quot;&quot;Axis-Aligned Bounding Box in 3D space.&quot;&quot;&quot;<br>
    def __init__(self, min_point: numpy.ndarray, max_point: numpy.ndarray):<br>
        self.min_point = min_point<br>
        self.max_point = max_point<br>
<br>
    def extend(self, point: numpy.ndarray):<br>
        &quot;&quot;&quot;Extend the AABB to include the given point.&quot;&quot;&quot;<br>
        self.min_point = numpy.minimum(self.min_point, point)<br>
        self.max_point = numpy.maximum(self.max_point, point)<br>
<br>
    def intersects(self, other: &quot;AABB&quot;) -&gt; bool:<br>
        &quot;&quot;&quot;Check if this AABB intersects with another AABB.&quot;&quot;&quot;<br>
        return numpy.all(self.max_point &gt;= other.min_point) and numpy.all(other.max_point &gt;= self.min_point)<br>
<br>
    def __repr__(self):<br>
        return f&quot;AABB(min_point={self.min_point}, max_point={self.max_point})&quot;<br>
<br>
    @staticmethod<br>
    def from_points(points: numpy.ndarray) -&gt; &quot;AABB&quot;:<br>
        &quot;&quot;&quot;Create an AABB that encompasses a set of points.&quot;&quot;&quot;<br>
        min_point = numpy.min(points, axis=0)<br>
        max_point = numpy.max(points, axis=0)<br>
        return AABB(min_point, max_point)<br>
<br>
    def merge(self, other: &quot;AABB&quot;) -&gt; &quot;AABB&quot;:<br>
        &quot;&quot;&quot;Merge this AABB with another AABB and return the resulting AABB.&quot;&quot;&quot;<br>
        new_min = numpy.minimum(self.min_point, other.min_point)<br>
        new_max = numpy.maximum(self.max_point, other.max_point)<br>
        return AABB(new_min, new_max)<br>
<br>
    def get_corners_homogeneous(self) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Get the 8 corners of the AABB in homogeneous coordinates.&quot;&quot;&quot;<br>
        corners = numpy.array([<br>
            [self.min_point[0], self.min_point[1], self.min_point[2], 1.0],<br>
            [self.min_point[0], self.min_point[1], self.max_point[2], 1.0], <br>
            [self.min_point[0], self.max_point[1], self.min_point[2], 1.0],<br>
            [self.min_point[0], self.max_point[1], self.max_point[2], 1.0],<br>
            [self.max_point[0], self.min_point[1], self.min_point[2], 1.0],<br>
            [self.max_point[0], self.min_point[1], self.max_point[2], 1.0],<br>
            [self.max_point[0], self.max_point[1], self.min_point[2], 1.0],<br>
            [self.max_point[0], self.max_point[1], self.max_point[2], 1.0],<br>
        ])<br>
        return corners<br>
    <br>
    def project_point(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Project a point onto the AABB is performed with clamping.&quot;&quot;&quot;<br>
        return numpy.minimum(numpy.maximum(point, self.min_point), self.max_point)<br>
    <br>
    def project_segment_on_aabb(self, seg_start: numpy.ndarray, seg_end: numpy.ndarray):<br>
        &quot;&quot;&quot;Project a segment onto the AABB and return the closest points and distance.&quot;&quot;&quot;<br>
        return project_segment_on_aabb(seg_start, seg_end, self.min_point, self.max_point)<br>
        <br>
                                <br>
<br>
class TransformAABB:<br>
    &quot;&quot;&quot;AABB associated with a Transform.&quot;&quot;&quot;<br>
    transform_to_taabb_map = WeakKeyDictionary()<br>
<br>
    def __init__(self, transform: 'Transform', aabb: AABB):<br>
        self._transform = transform<br>
        self._my_aabb = aabb<br>
        self._my_world_aabb = None<br>
        self._compiled_aabb = None<br>
        self._last_inspected_version = -1<br>
        self._last_tree_inspected_version = -1<br>
        TransformAABB.transform_to_taabb_map[transform] = self<br>
<br>
    def compile_tree_aabb(self) -&gt; AABB:<br>
        if self._last_tree_inspected_version == self._transform._version_for_walking_to_distal:<br>
            return self._compiled_aabb<br>
        result = self.get_world_aabb()<br>
        for child in self._transform.children:<br>
            child_taabb = TransformAABB.transform_to_taabb_map.get(child)<br>
            if child_taabb:<br>
                child_aabb = child_taabb.compile_tree_aabb()<br>
                result = result.merge(child_aabb)<br>
        self._compiled_aabb = result<br>
        self._last_tree_inspected_version = self._transform._version_for_walking_to_distal<br>
        return self._compiled_aabb<br>
<br>
    def get_world_aabb(self) -&gt; AABB:<br>
        &quot;&quot;&quot;Get the AABB widened by the rotation of the transform.&quot;&quot;&quot;<br>
        if self._last_inspected_version == self._transform._version_only_my:<br>
            return self._my_world_aabb<br>
        matrix = self._transform.global_pose().as_matrix34()<br>
        corners = self._my_aabb.get_corners_homogeneous()<br>
        transformed_corners = numpy.dot(matrix, corners.T).T<br>
        new_aabb = AABB.from_points(transformed_corners)<br>
        self._my_world_aabb = new_aabb<br>
        return new_aabb<br>
<!-- END SCAT CODE -->
</body>
</html>
