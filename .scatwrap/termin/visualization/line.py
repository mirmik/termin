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
&#9;&quot;&quot;&quot;Entity wrapping a :class:`PolylineDrawable` with a material.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;points: list[np.ndarray],<br>
&#9;&#9;material: Material,<br>
&#9;&#9;is_strip: bool = True,<br>
&#9;&#9;name: str = &quot;line&quot;,<br>
&#9;&#9;priority: int = 0,<br>
&#9;):<br>
&#9;&#9;super().__init__(pose=Pose3.identity(), name=name, priority=priority)<br>
&#9;&#9;polyline = Polyline(vertices=np.array(points, dtype=np.float32), indices=None, is_strip=is_strip)<br>
&#9;&#9;drawable = PolylineDrawable(polyline)<br>
&#9;&#9;self.add_component(MeshRenderer(drawable, material))<br>
<!-- END SCAT CODE -->
</body>
</html>
