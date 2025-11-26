<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/line.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Helpers for rendering polylines as entities.&quot;&quot;&quot;

from __future__ import annotations

import numpy as np

from termin.geombase.pose3 import Pose3

from .components import MeshRenderer
from .entity import Entity
from .material import Material
from .polyline import Polyline, PolylineDrawable


class LineEntity(Entity):
    &quot;&quot;&quot;Entity wrapping a :class:`PolylineDrawable` with a material.&quot;&quot;&quot;

    def __init__(
        self,
        points: list[np.ndarray],
        material: Material,
        is_strip: bool = True,
        name: str = &quot;line&quot;,
        priority: int = 0,
    ):
        super().__init__(pose=Pose3.identity(), name=name, priority=priority)
        polyline = Polyline(vertices=np.array(points, dtype=np.float32), indices=None, is_strip=is_strip)
        drawable = PolylineDrawable(polyline)
        self.add_component(MeshRenderer(drawable, material))

</code></pre>
</body>
</html>
