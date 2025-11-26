<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/line.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Helpers for rendering polylines as entities.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import numpy as np<br>
<br>
from termin.geombase.pose3 import Pose3<br>
<br>
from .components import MeshRenderer<br>
from .entity import Entity<br>
from .material import Material<br>
from .polyline import Polyline, PolylineDrawable<br>
<br>
<br>
class LineEntity(Entity):<br>
    &quot;&quot;&quot;Entity wrapping a :class:`PolylineDrawable` with a material.&quot;&quot;&quot;<br>
<br>
    def __init__(<br>
        self,<br>
        points: list[np.ndarray],<br>
        material: Material,<br>
        is_strip: bool = True,<br>
        name: str = &quot;line&quot;,<br>
        priority: int = 0,<br>
    ):<br>
        super().__init__(pose=Pose3.identity(), name=name, priority=priority)<br>
        polyline = Polyline(vertices=np.array(points, dtype=np.float32), indices=None, is_strip=is_strip)<br>
        drawable = PolylineDrawable(polyline)<br>
        self.add_component(MeshRenderer(drawable, material))<br>
<!-- END SCAT CODE -->
</body>
</html>
