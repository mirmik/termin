"""Render context passed to components during rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from termin.visualization.core.camera import Camera
    from termin.visualization.core.scene import Scene
    from termin.visualization.platform.backends.base import GraphicsBackend


@dataclass
class RenderContext:
    """Data bundle passed to components during rendering."""

    view: np.ndarray
    projection: np.ndarray
    camera: "Camera"
    scene: "Scene"
    context_key: int
    graphics: "GraphicsBackend"
    phase: str = "main"

    # Shadow mapping данные (опционально, заполняется ColorPass)
    shadow_data: "ShadowMapArray | None" = None
