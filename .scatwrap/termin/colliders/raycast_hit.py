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
    &quot;&quot;&quot;<br>
    Результат пересечения луча с объектом.<br>
    &quot;&quot;&quot;<br>
    def __init__(self, entity, component, point, collider_point, distance):<br>
        self.entity = entity<br>
        self.component = component<br>
        self.point = point<br>
        self.collider_point = collider_point<br>
        self.distance = float(distance)<br>
<br>
    def __repr__(self):<br>
        return (f&quot;RaycastHit(entity={self.entity}, distance={self.distance}, &quot;<br>
                f&quot;point={self.point}, collider_point={self.collider_point})&quot;)<br>
<!-- END SCAT CODE -->
</body>
</html>
