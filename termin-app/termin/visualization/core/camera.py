"""Compatibility exports for camera components.

Canonical camera helpers live in :mod:`termin.render_components.camera`.
``OrbitCameraController`` is still owned by termin-app native bindings.
"""

from __future__ import annotations

from termin._native import OrbitCameraController
from termin.render_components.camera import (
    CameraComponent,
    CameraController,
    OrthographicCameraComponent,
    PerspectiveCameraComponent,
)

__all__ = [
    "CameraComponent",
    "PerspectiveCameraComponent",
    "OrthographicCameraComponent",
    "CameraController",
    "OrbitCameraController",
]
