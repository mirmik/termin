<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/line.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Helpers&nbsp;for&nbsp;rendering&nbsp;polylines&nbsp;as&nbsp;entities.&quot;&quot;&quot;<br>
<br>
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
<br>
from&nbsp;termin.geombase.pose3&nbsp;import&nbsp;Pose3<br>
<br>
from&nbsp;.components&nbsp;import&nbsp;MeshRenderer<br>
from&nbsp;.entity&nbsp;import&nbsp;Entity<br>
from&nbsp;.material&nbsp;import&nbsp;Material<br>
from&nbsp;.polyline&nbsp;import&nbsp;Polyline,&nbsp;PolylineDrawable<br>
<br>
<br>
class&nbsp;LineEntity(Entity):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Entity&nbsp;wrapping&nbsp;a&nbsp;:class:`PolylineDrawable`&nbsp;with&nbsp;a&nbsp;material.&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;points:&nbsp;list[np.ndarray],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;material:&nbsp;Material,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;is_strip:&nbsp;bool&nbsp;=&nbsp;True,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name:&nbsp;str&nbsp;=&nbsp;&quot;line&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;priority:&nbsp;int&nbsp;=&nbsp;0,<br>
&nbsp;&nbsp;&nbsp;&nbsp;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__(pose=Pose3.identity(),&nbsp;name=name,&nbsp;priority=priority)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;polyline&nbsp;=&nbsp;Polyline(vertices=np.array(points,&nbsp;dtype=np.float32),&nbsp;indices=None,&nbsp;is_strip=is_strip)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;drawable&nbsp;=&nbsp;PolylineDrawable(polyline)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.add_component(MeshRenderer(drawable,&nbsp;material))<br>
<!-- END SCAT CODE -->
</body>
</html>
