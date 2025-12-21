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
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.core.viewport import Viewport

import numpy as np

from termin.geombase import Pose3

from termin.editor.inspect_field import InspectField, inspect
from termin.visualization.core.component import Component, InputComponent
from termin.visualization.core.input_events import MouseButtonEvent, MouseMoveEvent, ScrollEvent
from termin.visualization.platform.backends.base import Action, MouseButton


class CameraComponent(Component):
    """Component that exposes view/projection matrices based on entity pose."""

    def screen_point_to_ray(self, x: float, y: float, viewport_rect):
        import numpy as np
        from termin.geombase import Ray3, Vec3

        px, py, pw, ph = viewport_rect

        nx = ( (x - px) / pw ) * 2.0 - 1.0
        ny = ( (y - py) / ph ) * -2.0 + 1.0

        PV = self.get_projection_matrix() @ self.get_view_matrix()

        inv_PV = np.linalg.inv(PV)

        near = np.array([nx, ny, -1.0, 1.0], dtype=np.float32)
        far  = np.array([nx, ny,  1.0, 1.0], dtype=np.float32)

        p_near = inv_PV @ near
        p_far  = inv_PV @ far

        p_near /= p_near[3]
        p_far  /= p_far[3]

        origin = p_near[:3]
        direction = p_far[:3] - p_near[:3]
        direction /= np.linalg.norm(direction)

        return Ray3(Vec3(float(origin[0]), float(origin[1]), float(origin[2])),
                    Vec3(float(direction[0]), float(direction[1]), float(direction[2])))

    def __init__(self, near: float = 0.1, far: float = 100.0):
        super().__init__(enabled=True)
        self.near = near
        self.far = far
        self._viewports: List["Viewport"] = []

    @property
    def viewport(self) -> Optional["Viewport"]:
        """First viewport (for backward compatibility)."""
        return self._viewports[0] if self._viewports else None

    @viewport.setter
    def viewport(self, value: Optional["Viewport"]) -> None:
        """Set single viewport (for backward compatibility)."""
        if value is None:
            self._viewports.clear()
        elif value not in self._viewports:
            self._viewports.clear()
            self._viewports.append(value)

    @property
    def viewports(self) -> List["Viewport"]:
        """List of viewports this camera renders to."""
        return self._viewports

    def add_viewport(self, viewport: "Viewport") -> None:
        """Add viewport to camera's viewport list."""
        if viewport not in self._viewports:
            self._viewports.append(viewport)

    def remove_viewport(self, viewport: "Viewport") -> None:
        """Remove viewport from camera's viewport list."""
        if viewport in self._viewports:
            self._viewports.remove(viewport)

    def has_viewport(self, viewport: "Viewport") -> bool:
        """Check if camera is bound to viewport."""
        return viewport in self._viewports

    # def on_added(self, scene):
    #     if self.entity is None:
    #         raise RuntimeError("CameraComponent must be attached to an entity.")
    #     super().on_added(scene)

    def get_view_matrix(self) -> np.ndarray:
        if self.entity is None:
            raise RuntimeError("CameraComponent has no entity.")
    # Entity.pose не существует — берём позу из Transform3
        return self.entity.transform.global_pose().inverse().as_matrix()
        #return self.entity.pose.inverse().as_matrix()

    def get_projection_matrix(self) -> np.ndarray:
        raise NotImplementedError

    def projection_matrix(self) -> np.ndarray:
        return self.get_projection_matrix()

    def view_matrix(self) -> np.ndarray:
        return self.get_view_matrix()

    def set_aspect(self, aspect: float):
        """Optional method for perspective cameras."""
        return


class PerspectiveCameraComponent(CameraComponent):
    # поля для инспектора (fov в градусах, near/far как есть)
    inspect_fields = {
        "fov_deg": InspectField(
            label="FOV (deg)",
            kind="float",
            min=5.0,
            max=170.0,
            step=1.0,
            getter=lambda obj: math.degrees(obj.fov_y),
            setter=lambda obj, value: setattr(obj, "fov_y", math.radians(float(value))),
        ),
        "near": InspectField(
            path="near",
            label="Near clip",
            kind="float",
            min=0.001,
            step=0.01,
        ),
        "far": InspectField(
            path="far",
            label="Far clip",
            kind="float",
            min=0.01,
            step=0.1,
        ),
    }

    def __init__(self, fov_y_degrees: float = 60.0, aspect: float = 1.0, near: float = 0.1, far: float = 100.0):
        super().__init__(near=near, far=far)
        self.fov_y = math.radians(fov_y_degrees)
        self.aspect = aspect

    def set_aspect(self, aspect: float):
        self.aspect = aspect

    def get_projection_matrix(self) -> np.ndarray:
        """
        Projection matrix for Y-forward convention.

        Camera looks along +Y axis:
        - View X → Screen X (right)
        - View Z → Screen Y (up)
        - View Y → Depth (forward)
        """
        f = 1.0 / math.tan(self.fov_y * 0.5)
        near, far = self.near, self.far
        proj = np.zeros((4, 4), dtype=np.float32)
        proj[0, 0] = f / max(1e-6, self.aspect)  # X → screen X
        proj[1, 2] = f                            # Z → screen Y (up)
        proj[2, 1] = (far + near) / (far - near)  # Y → depth
        proj[2, 3] = (-2 * far * near) / (far - near)
        proj[3, 1] = 1.0                          # w = y
        return proj


class OrthographicCameraComponent(CameraComponent):
    """
    Orthographic camera for Y-forward convention.

    Camera looks along +Y axis:
    - View X → Screen X (controlled by left/right)
    - View Z → Screen Y (controlled by bottom/top, representing up)
    - View Y → Depth (controlled by near/far)
    """

    def __init__(self, left: float = -1.0, right: float = 1.0, bottom: float = -1.0, top: float = 1.0, near: float = 0.1, far: float = 100.0):
        super().__init__(near=near, far=far)
        self.left = left
        self.right = right
        self.bottom = bottom
        self.top = top

    def get_projection_matrix(self) -> np.ndarray:
        lr = self.right - self.left
        tb = self.top - self.bottom
        fn = self.far - self.near
        proj = np.zeros((4, 4), dtype=np.float32)
        proj[0, 0] = 2.0 / lr                       # X → screen X
        proj[1, 2] = 2.0 / tb                       # Z → screen Y (up)
        proj[2, 1] = 2.0 / fn                       # Y → depth
        proj[0, 3] = -(self.right + self.left) / lr
        proj[1, 3] = -(self.top + self.bottom) / tb
        proj[2, 3] = -(self.far + self.near) / fn
        proj[3, 3] = 1.0
        return proj


class CameraController(InputComponent):
    """Base class for camera manipulation controllers."""

    def __init__(self, enabled: bool = True):
        super().__init__(enabled)
        self.camera_component: CameraComponent | None = None

    def on_added(self, scene):
        super().on_added(scene)
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
        """Центрирует камеру на заданной позиции."""
        return


class OrbitCameraController(CameraController):
    """Orbit controller similar to common DCC tools."""

    # Эти поля можно редактировать прямо в инспекторе
    radius = inspect(
        5.0, label="Radius", kind="float",
        min=0.1, max=100.0, step=0.1,
    )
    # target – vec3, редактируем как три спинбокса
    target = inspect(
        np.array([0.0, 0.0, 0.0], dtype=np.float32),
        label="Target", kind="vec3",
        setter=lambda obj, value: obj.inspect_target_update(value)
    )

    def __init__(
        self,
        target: Optional[np.ndarray] = None,
        radius: float = 5.0,
        azimuth: float = 45.0,
        elevation: float = 30.0,
        min_radius: float = 1.0,
        max_radius: float = 100.0,
        prevent_moving: bool = False,
    ):
        super().__init__(enabled=True)
        self.target = np.array(target if target is not None else [0.0, 0.0, 0.0], dtype=np.float32)
        self.radius = radius
        self.azimuth = math.radians(azimuth)
        self.elevation = math.radians(elevation)
        self._min_radius = min_radius
        self._max_radius = max_radius
        self._orbit_speed = 0.2
        self._pan_speed = 0.005
        self._zoom_speed = 0.5
        self._states: Dict[int, dict] = {}
        self._prevent_moving = prevent_moving

    def inspect_target_update(self, val):
        self.target = val
        self._update_pose()

    def on_added(self, scene):
        if self.entity is None:
            raise RuntimeError("OrbitCameraController must be attached to an entity.")
        super().on_added(scene)
        self._update_pose()

    def prevent_moving(self):
        self._prevent_moving = True

    def _update_pose(self):
        """
        Update camera pose for Y-forward convention.

        At azimuth=0, elevation=0: camera is behind target (-Y), looking at +Y.
        Azimuth rotates around Z axis (up).
        Elevation raises/lowers the camera.
        """
        entity = self.entity
        if entity is None:
            return
        r = float(np.clip(self.radius, self._min_radius, self._max_radius))
        cos_elev = math.cos(self.elevation)
        eye = np.array(
            [
                self.target[0] + r * math.sin(self.azimuth) * cos_elev,  # X - side
                self.target[1] - r * math.cos(self.azimuth) * cos_elev,  # Y - behind target
                self.target[2] + r * math.sin(self.elevation),           # Z - height
            ],
            dtype=np.float32,
        )
        entity.transform.relocate(Pose3.looking_at(eye=eye, target=self.target))

    def orbit(self, delta_azimuth: float, delta_elevation: float):
        self.azimuth += math.radians(delta_azimuth)
        self.elevation = np.clip(self.elevation + math.radians(delta_elevation), math.radians(-89.0), math.radians(89.0))
        self._update_pose()

    def zoom(self, delta: float):
        self.radius += delta
        self._update_pose()

    def pan(self, dx: float, dy: float):
        entity = self.entity
        if entity is None:
            return
        rot = entity.transform.global_pose().rotation_matrix()
        right = rot[:, 0]  # local X
        up = rot[:, 2]     # local Z (up in Y-forward convention)
        self.target = self.target + right * dx + up * dy
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
        """Центрирует камеру на заданной позиции."""
        self.target = np.array(position, dtype=np.float32)
        self._update_pose()
