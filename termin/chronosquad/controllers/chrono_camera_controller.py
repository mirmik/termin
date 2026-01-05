"""ChronoCameraController - camera controller for ChronoSquad game.

Unlike OrbitCameraController, this is not an InputComponent.
It receives commands from GameController which filters input events.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict

import numpy as np

from termin.geombase import Pose3
from termin.visualization.core.python_component import PythonComponent
from termin.visualization.core.camera import CameraComponent
from termin.visualization.platform.backends.base import Action, MouseButton

if TYPE_CHECKING:
    from termin.visualization.core.input_events import (
        MouseButtonEvent,
        MouseMoveEvent,
        ScrollEvent,
    )
    from termin.visualization.core.viewport import Viewport


class ChronoCameraController(PythonComponent):
    """
    Camera controller for ChronoSquad game.

    Not an InputComponent - receives filtered events from GameController.
    This allows GameController to filter out scroll events when Shift is held
    (for time control instead of camera zoom).
    """

    def __init__(
        self,
        radius: float = 10.0,
        min_radius: float = 2.0,
        max_radius: float = 50.0,
    ):
        super().__init__(enabled=True)
        self.radius = radius
        self.min_radius = min_radius
        self.max_radius = max_radius

        self.camera_component: CameraComponent | None = None

        # Internal state
        self._azimuth: float = 0.0
        self._elevation: float = math.radians(45.0)  # Default: looking down at 45 degrees
        self._target: np.ndarray = np.array([0.0, 0.0, 0.0], dtype=np.float32)

        # For detecting external transform changes
        self._last_position = None
        self._last_rotation = None

        # Speed settings
        self._orbit_speed = 0.2
        self._pan_speed = 0.005
        self._zoom_speed = 0.5

        # Mouse state per viewport
        self._states: Dict[int, dict] = {}

    def start(self) -> None:
        """Called when scene starts - find CameraComponent."""
        super().start()
        if self.entity is None:
            return
        self.camera_component = self.entity.get_component(CameraComponent)
        if self.camera_component is not None:
            from termin._native import log
            log.info("[ChronoCameraController] Found CameraComponent")
            self._sync_from_transform()

    def update(self, dt: float) -> None:
        """Check for external transform changes and sync internal state."""
        if self.entity is None:
            return

        pos = self.entity.transform.global_position
        rot = self.entity.transform.global_rotation

        # Check if transform changed externally
        if self._last_position is not None:
            pos_changed = not pos.approx_eq(self._last_position, 1e-6)
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

    def _sync_from_transform(self) -> None:
        """Compute internal state from current transform."""
        if self.entity is None:
            return

        pos = self.entity.transform.global_position
        rot = self.entity.transform.global_rotation

        # Forward direction (Y-forward convention)
        rot_matrix = self.entity.transform.global_pose().rotation_matrix()
        forward = rot_matrix[:, 1]  # local Y is forward

        # Convert position to numpy array
        pos_np = np.array([pos.x, pos.y, pos.z], dtype=np.float32)

        # Target is position + forward * radius
        self._target = pos_np + forward * self.radius

        # Compute direction from target to camera
        to_camera = pos_np - self._target
        dist = np.linalg.norm(to_camera)
        if dist < 1e-6:
            self._last_position = pos
            self._last_rotation = rot.copy()
            return

        # Normalize
        to_camera_norm = to_camera / dist

        # Elevation: angle from XY plane
        self._elevation = math.asin(np.clip(to_camera_norm[2], -1.0, 1.0))

        # Azimuth: angle in XY plane (at azimuth=0, camera is behind target)
        self._azimuth = math.atan2(to_camera_norm[0], -to_camera_norm[1])

        self._last_position = pos
        self._last_rotation = rot.copy()

    def _update_pose(self) -> None:
        """Update entity transform from internal state."""
        entity = self.entity
        if entity is None:
            return

        r = float(np.clip(self.radius, self.min_radius, self.max_radius))
        cos_elev = math.cos(self._elevation)
        eye = np.array(
            [
                self._target[0] + r * math.sin(self._azimuth) * cos_elev,
                self._target[1] - r * math.cos(self._azimuth) * cos_elev,
                self._target[2] + r * math.sin(self._elevation),
            ],
            dtype=np.float32,
        )
        entity.transform.relocate(Pose3.looking_at(eye=eye, target=self._target))

        self._last_position = entity.transform.global_position
        self._last_rotation = entity.transform.global_rotation.copy()

    # ----------------------------------------------------------------
    # Camera control methods (called by GameController)
    # ----------------------------------------------------------------

    def orbit(self, delta_azimuth: float, delta_elevation: float) -> None:
        """Rotate camera around target."""
        self._azimuth += math.radians(delta_azimuth)
        self._elevation = np.clip(
            self._elevation + math.radians(delta_elevation),
            math.radians(-89.0),
            math.radians(89.0)
        )
        self._update_pose()

    def zoom(self, delta: float) -> None:
        """Zoom camera (change radius or ortho size)."""
        if self.camera_component is not None and self.camera_component.projection_type == "orthographic":
            scale_factor = 1.0 + delta * 0.1
            self.camera_component.ortho_size = max(0.1, self.camera_component.ortho_size * scale_factor)
        else:
            self.radius = np.clip(self.radius + delta, self.min_radius, self.max_radius)
            self._update_pose()

    def pan(self, dx: float, dy: float) -> None:
        """Pan camera (move target)."""
        entity = self.entity
        if entity is None:
            return
        rot = entity.transform.global_pose().rotation_matrix()
        right = rot[:, 0]  # local X
        up = rot[:, 2]     # local Z
        self._target = self._target + right * dx + up * dy
        self._update_pose()

    def center_on(self, position) -> None:
        """Center camera on position."""
        self._target = np.array([position.x, position.y, position.z], dtype=np.float32)
        self._update_pose()

    # ----------------------------------------------------------------
    # Event handlers (called by GameController)
    # ----------------------------------------------------------------

    def _state(self, viewport: "Viewport") -> dict:
        key = id(viewport)
        if key not in self._states:
            self._states[key] = {"orbit": False, "pan": False, "last": None}
        return self._states[key]

    def handle_mouse_button(self, event: "MouseButtonEvent") -> None:
        """Handle mouse button event."""
        if self.camera_component is None:
            return
        if not self.camera_component.has_viewport(event.viewport):
            return

        state = self._state(event.viewport)
        if event.button == MouseButton.MIDDLE:
            state["orbit"] = event.action == Action.PRESS
        elif event.button == MouseButton.RIGHT:
            state["pan"] = event.action == Action.PRESS
        if event.action == Action.RELEASE:
            state["last"] = None

    def handle_mouse_move(self, event: "MouseMoveEvent") -> None:
        """Handle mouse move event."""
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

    def handle_scroll(self, event: "ScrollEvent") -> None:
        """Handle scroll event (zoom)."""
        if self.camera_component is None:
            return
        if not self.camera_component.has_viewport(event.viewport):
            return

        self.zoom(-event.yoffset * self._zoom_speed)
