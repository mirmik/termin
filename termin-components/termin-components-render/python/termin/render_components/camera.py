"""Camera helpers owned by the render-components package."""

from __future__ import annotations

import numpy as np

from termin.input import InputComponent
from termin.render_components import (
    CameraComponent,
    OrthographicCameraComponent,
    PerspectiveCameraComponent,
)

__all__ = [
    "CameraComponent",
    "PerspectiveCameraComponent",
    "OrthographicCameraComponent",
    "CameraController",
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
