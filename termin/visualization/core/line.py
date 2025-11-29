"""Helpers for rendering polylines as entities."""

from __future__ import annotations

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.visualization.render.components import MeshRenderer
from termin.visualization.core.entity import Entity
from termin.visualization.core.material import Material
from termin.visualization.core.polyline import Polyline, PolylineDrawable


class LineEntity(Entity):
    """Entity wrapping a :class:`PolylineDrawable` with a material."""

    def __init__(
        self,
        points: list[np.ndarray],
        material: Material,
        is_strip: bool = True,
        name: str = "line",
        priority: int = 0,
    ):
        super().__init__(pose=Pose3.identity(), name=name, priority=priority)
        polyline = Polyline(vertices=np.array(points, dtype=np.float32), indices=None, is_strip=is_strip)
        drawable = PolylineDrawable(polyline)
        self.add_component(MeshRenderer(drawable, material))
