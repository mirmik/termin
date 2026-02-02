<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/transform_aabb.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;TransformAABB&nbsp;-&nbsp;AABB&nbsp;associated&nbsp;with&nbsp;a&nbsp;Transform.&quot;&quot;&quot;<br>
<br>
import&nbsp;numpy<br>
from&nbsp;weakref&nbsp;import&nbsp;WeakKeyDictionary<br>
from&nbsp;._geom_native&nbsp;import&nbsp;AABB<br>
<br>
<br>
class&nbsp;TransformAABB:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;AABB&nbsp;associated&nbsp;with&nbsp;a&nbsp;Transform.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;transform_to_taabb_map&nbsp;=&nbsp;WeakKeyDictionary()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;__slots__&nbsp;=&nbsp;('_transform',&nbsp;'_my_aabb',&nbsp;'_my_world_aabb',&nbsp;'_compiled_aabb',<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'_last_inspected_version',&nbsp;'_last_tree_inspected_version')<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;transform:&nbsp;'Transform',&nbsp;aabb:&nbsp;AABB):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._transform&nbsp;=&nbsp;transform<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._my_aabb&nbsp;=&nbsp;aabb<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._my_world_aabb&nbsp;=&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._compiled_aabb&nbsp;=&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._last_inspected_version&nbsp;=&nbsp;-1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._last_tree_inspected_version&nbsp;=&nbsp;-1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;TransformAABB.transform_to_taabb_map[transform]&nbsp;=&nbsp;self<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;compile_tree_aabb(self)&nbsp;-&gt;&nbsp;AABB:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self._last_tree_inspected_version&nbsp;==&nbsp;self._transform._version_for_walking_to_distal:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._compiled_aabb<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;result&nbsp;=&nbsp;self.get_world_aabb()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;child&nbsp;in&nbsp;self._transform.children:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;child_taabb&nbsp;=&nbsp;TransformAABB.transform_to_taabb_map.get(child)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;child_taabb:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;child_aabb&nbsp;=&nbsp;child_taabb.compile_tree_aabb()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;result&nbsp;=&nbsp;result.merge(child_aabb)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._compiled_aabb&nbsp;=&nbsp;result<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._last_tree_inspected_version&nbsp;=&nbsp;self._transform._version_for_walking_to_distal<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._compiled_aabb<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;get_world_aabb(self)&nbsp;-&gt;&nbsp;AABB:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Get&nbsp;the&nbsp;AABB&nbsp;widened&nbsp;by&nbsp;the&nbsp;rotation&nbsp;of&nbsp;the&nbsp;transform.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self._last_inspected_version&nbsp;==&nbsp;self._transform._version_only_my:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._my_world_aabb<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;matrix&nbsp;=&nbsp;self._transform.global_pose().as_matrix()[:3,&nbsp;:]&nbsp;&nbsp;#&nbsp;3x4&nbsp;from&nbsp;4x4<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;corners&nbsp;=&nbsp;self._my_aabb.get_corners_homogeneous()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;transformed_corners&nbsp;=&nbsp;numpy.dot(matrix,&nbsp;corners.T).T<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;new_aabb&nbsp;=&nbsp;AABB.from_points(transformed_corners)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._my_world_aabb&nbsp;=&nbsp;new_aabb<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;new_aabb<br>
<!-- END SCAT CODE -->
</body>
</html>
