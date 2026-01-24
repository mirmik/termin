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

from termin._native import log
from termin.geombase import Pose3

from termin.editor.inspect_field import inspect
from termin.visualization.core.python_component import InputComponent
from termin.visualization.core.input_events import MouseButtonEvent, MouseMoveEvent, ScrollEvent
from termin.visualization.platform.backends.base import Action, MouseButton

# Re-export from C++
from termin.entity._entity_native import (
    CameraComponent,
    PerspectiveCameraComponent,
    OrthographicCameraComponent,
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


class OrbitCameraController(CameraController):
    """
    Orbit controller similar to common DCC tools.

    Transform is the single source of truth. Internal state (azimuth, elevation, target)
    is derived from transform and updated when external changes are detected.
    """

    active_in_editor = True

    radius = inspect(
        5.0, label="Radius", kind="float",
        min=0.1, max=100.0, step=0.1,
    )
    min_radius = inspect(
        1.0, label="Min Radius", kind="float",
        min=0.1, max=100.0, step=0.1,
    )
    max_radius = inspect(
        100.0, label="Max Radius", kind="float",
        min=1.0, max=1000.0, step=1.0,
    )

    def __init__(
        self,
        radius: float = 5.0,
        min_radius: float = 1.0,
        max_radius: float = 100.0,
        prevent_moving: bool = False,
    ):
        super().__init__(enabled=True)
        self.radius = radius
        self.min_radius = min_radius
        self.max_radius = max_radius

        # Internal state - derived from transform, not serialized
        self._azimuth: float = 0.0
        self._elevation: float = 0.0
        self._target: np.ndarray = np.array([0.0, 0.0, 0.0], dtype=np.float32)

        # For detecting external transform changes
        self._last_position = None  # Vec3 or None
        self._last_rotation = None  # Quat or None

        self._orbit_speed = 0.2
        self._pan_speed = 0.005
        self._zoom_speed = 0.5
        self._states: Dict[int, dict] = {}
        self._prevent_moving = prevent_moving

    def on_added(self):
        if self.entity is None:
            raise RuntimeError("OrbitCameraController must be attached to an entity.")
        super().on_added()
        self._sync_from_transform()

    def prevent_moving(self):
        self._prevent_moving = True

    def update(self, dt: float):
        """Check for external transform changes and sync internal state."""
        if self.entity is None:
            return

        pos = self.entity.transform.global_position
        rot = self.entity.transform.global_rotation

        # Check if transform changed externally
        if self._last_position is not None:
            pos_changed = not pos.approx_eq(self._last_position, 1e-6)
            # For rotation, compare components
            rot_changed = (
                abs(rot.x - self._last_rotation.x) > 1e-6 or
                abs(rot.y - self._last_rotation.y) > 1e-6 or
                abs(rot.z - self._last_rotation.z) > 1e-6 or
                abs(rot.w - self._last_rotation.w) > 1e-6
            )
            if pos_changed or rot_changed:
                self._sync_from_transform()

        self._last_position = pos
        self._last_rotation = rot

    def _sync_from_transform(self):
        """Compute internal state (azimuth, elevation, target) from current transform."""
        if self.entity is None:
            return

        pos = self.entity.transform.global_position
        rot = self.entity.transform.global_rotation

        # Forward direction (Y-forward convention)
        rot_matrix = self.entity.transform.global_pose().rotation_matrix()
        forward = rot_matrix[:, 1]  # local Y is forward

        # Target is position + forward * radius
        self._target = pos + forward * self.radius

        # Compute direction from target to camera
        to_camera = pos - self._target
        dist = np.linalg.norm(to_camera)
        if dist < 1e-6:
            return

        # Normalize
        to_camera_norm = to_camera / dist

        # Elevation: angle from XY plane (asin of Z component)
        self._elevation = math.asin(np.clip(to_camera_norm[2], -1.0, 1.0))

        # Azimuth: angle in XY plane
        # At azimuth=0, camera is behind target (-Y direction)
        # atan2(x, -y) gives us the angle from -Y axis
        self._azimuth = math.atan2(to_camera_norm[0], -to_camera_norm[1])

        # Update last known position/rotation
        self._last_position = pos.copy()
        self._last_rotation = rot.copy()

    def _update_pose(self):
        """
        Update camera pose from internal state.

        At azimuth=0, elevation=0: camera is behind target (-Y), looking at +Y.
        Azimuth rotates around Z axis (up).
        Elevation raises/lowers the camera.
        """
        entity = self.entity
        if entity is None:
            return

        r = float(np.clip(self.radius, self.min_radius, self.max_radius))
        cos_elev = math.cos(self._elevation)
        eye = np.array(
            [
                self._target[0] + r * math.sin(self._azimuth) * cos_elev,  # X - side
                self._target[1] - r * math.cos(self._azimuth) * cos_elev,  # Y - behind target
                self._target[2] + r * math.sin(self._elevation),           # Z - height
            ],
            dtype=np.float32,
        )
        entity.transform.relocate(Pose3.looking_at(eye=eye, target=self._target))

        # Update last known position to avoid re-sync
        self._last_position = entity.transform.global_position
        self._last_rotation = entity.transform.global_rotation.copy()

    def orbit(self, delta_azimuth: float, delta_elevation: float):
        self._azimuth += math.radians(delta_azimuth)
        self._elevation = np.clip(
            self._elevation + math.radians(delta_elevation),
            math.radians(-89.0),
            math.radians(89.0)
        )
        self._update_pose()

    def zoom(self, delta: float):
        if self.camera_component is not None and self.camera_component.projection_type == "orthographic":
            scale_factor = 1.0 + delta * 0.1
            self.camera_component.ortho_size = max(0.1, self.camera_component.ortho_size * scale_factor)
        else:
            self.radius = np.clip(self.radius + delta, self.min_radius, self.max_radius)
            self._update_pose()

    def pan(self, dx: float, dy: float):
        entity = self.entity
        if entity is None:
            return
        rot = entity.transform.global_pose().rotation_matrix()
        right = rot[:, 0]  # local X
        up = rot[:, 2]     # local Z (up in Y-forward convention)
        self._target = self._target + right * dx + up * dy
        self._update_pose()

    def _state(self, viewport) -> dict:
        key = id(viewport)
        if key not in self._states:
            self._states[key] = {"orbit": False, "pan": False, "last": None}
        return self._states[key]

    def on_mouse_button(self, event: MouseButtonEvent):
        if not self.camera_component.has_viewport(event.viewport):
            return

        state = self._state(event.viewport)
        if event.button == MouseButton.MIDDLE:
            state["orbit"] = event.action == Action.PRESS
        elif event.button == MouseButton.RIGHT:
            state["pan"] = event.action == Action.PRESS
        if event.action == Action.RELEASE:
            state["last"] = None

    def on_mouse_move(self, event: MouseMoveEvent):
        if self._prevent_moving:
            return
        if self.camera_component is None:
            return
        if not self.camera_component.has_viewport(event.viewport):
            return
        state = self._state(event.viewport)
        if state.get("last") is None:
            state["last"] = (event.x, event.y)
            return
        state["last"] = (event.x, event.y)
        if state.get("orbit"):
            self.orbit(-event.dx * self._orbit_speed, event.dy * self._orbit_speed)
        elif state.get("pan"):
            self.pan(-event.dx * self._pan_speed, event.dy * self._pan_speed)

    def on_scroll(self, event: ScrollEvent):
        if self._prevent_moving:
            return
        if not self.camera_component.has_viewport(event.viewport):
            return
        self.zoom(-event.yoffset * self._zoom_speed)

    def center_on(self, position: np.ndarray) -> None:
        """Center camera on position."""
        self._target = np.array(position, dtype=np.float32)
        self._update_pose()
