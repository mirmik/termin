<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/raycast_hit.py</title>
</head>
<body>
<pre><code>
import numpy as np

class RaycastHit:
    &quot;&quot;&quot;
    Результат пересечения луча с объектом.
    &quot;&quot;&quot;
    def __init__(self, entity, component, point, collider_point, distance):
        self.entity = entity
        self.component = component
        self.point = point
        self.collider_point = collider_point
        self.distance = float(distance)

    def __repr__(self):
        return (f&quot;RaycastHit(entity={self.entity}, distance={self.distance}, &quot;
                f&quot;point={self.point}, collider_point={self.collider_point})&quot;)

</code></pre>
</body>
</html>
