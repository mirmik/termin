"""
Camera components and controllers.

Coordinate convention: Y-forward, Z-up
  - X: right
  - Y: forward (depth, camera looks along +Y)
  - Z: up

This differs from standard OpenGL (Z-forward, Y-up).
Projection matrices are adapted accordingly.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.core.viewport import Viewport

import numpy as np

from tcbase import log
from termin.geombase import Pose3

from termin.editor.inspect_field import inspect
from termin.visualization.core.python_component import InputComponent
from termin.visualization.core.input_events import MouseButtonEvent, MouseMoveEvent, ScrollEvent
from tcbase import Action, MouseButton

# Re-export from C++
from termin.entity._entity_native import (
    CameraComponent,
    PerspectiveCameraComponent,
    OrthographicCameraComponent,
    OrbitCameraController,
)

__all__ = [
    "CameraComponent",
    "PerspectiveCameraComponent",
    "OrthographicCameraComponent",
    "CameraController",
    "OrbitCameraController",
]


class CameraController(InputComponent):
    """Base class for camera manipulation controllers."""

    def __init__(self, enabled: bool = True):
        super().__init__(enabled)
        self.camera_component: CameraComponent | None = None

    def on_added(self):
        super().on_added()
        self.camera_component = self.entity.get_component(CameraComponent)
        if self.camera_component is None:
            raise RuntimeError("CameraController requires a CameraComponent on the same entity.")

    def orbit(self, d_azimuth: float, d_elevation: float):
        return

    def pan(self, dx: float, dy: float):
        return

    def zoom(self, delta: float):
        return

    def center_on(self, position: np.ndarray) -> None:
        """Center camera on position."""
        return
