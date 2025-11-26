<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/raycast_hit.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy as np<br>
<br>
class RaycastHit:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Результат пересечения луча с объектом.<br>
&#9;&quot;&quot;&quot;<br>
&#9;def __init__(self, entity, component, point, collider_point, distance):<br>
&#9;&#9;self.entity = entity<br>
&#9;&#9;self.component = component<br>
&#9;&#9;self.point = point<br>
&#9;&#9;self.collider_point = collider_point<br>
&#9;&#9;self.distance = float(distance)<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return (f&quot;RaycastHit(entity={self.entity}, distance={self.distance}, &quot;<br>
&#9;&#9;&#9;&#9;f&quot;point={self.point}, collider_point={self.collider_point})&quot;)<br>
<!-- END SCAT CODE -->
</body>
</html>
