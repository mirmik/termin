<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/camera.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Camera components and controllers.&quot;&quot;&quot;

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import numpy as np

from termin.geombase.pose3 import Pose3

from .entity import Component, InputComponent
from .backends.base import Action, MouseButton

from termin.visualization.inspect import InspectField, inspect


class CameraComponent(Component):
    &quot;&quot;&quot;Component that exposes view/projection matrices based on entity pose.&quot;&quot;&quot;

    def screen_point_to_ray(self, x: float, y: float, viewport_rect):
        import numpy as np
        from termin.geombase.ray import Ray3

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
        
        return Ray3(origin, direction)

    def __init__(self, near: float = 0.1, far: float = 100.0):
        super().__init__(enabled=True)
        self.near = near
        self.far = far
        self.viewport = None 

    def start(self, scene):
        if self.entity is None:
            raise RuntimeError(&quot;CameraComponent must be attached to an entity.&quot;)
        super().start(scene)

    def get_view_matrix(self) -&gt; np.ndarray:
        if self.entity is None:
            raise RuntimeError(&quot;CameraComponent has no entity.&quot;)
    # Entity.pose не существует — берём позу из Transform3
        return self.entity.transform.global_pose().inverse().as_matrix()
        #return self.entity.pose.inverse().as_matrix()

    def get_projection_matrix(self) -&gt; np.ndarray:
        raise NotImplementedError

    def projection_matrix(self) -&gt; np.ndarray:
        return self.get_projection_matrix()

    def view_matrix(self) -&gt; np.ndarray:
        return self.get_view_matrix()

    def set_aspect(self, aspect: float):
        &quot;&quot;&quot;Optional method for perspective cameras.&quot;&quot;&quot;
        return


class PerspectiveCameraComponent(CameraComponent):
    # поля для инспектора (fov в градусах, near/far как есть)
    inspect_fields = {
        &quot;fov_deg&quot;: InspectField(
            label=&quot;FOV (deg)&quot;,
            kind=&quot;float&quot;,
            min=5.0,
            max=170.0,
            step=1.0,
            getter=lambda obj: math.degrees(obj.fov_y),
            setter=lambda obj, value: setattr(obj, &quot;fov_y&quot;, math.radians(float(value))),
        ),
        &quot;near&quot;: InspectField(
            path=&quot;near&quot;,
            label=&quot;Near clip&quot;,
            kind=&quot;float&quot;,
            min=0.001,
            step=0.01,
        ),
        &quot;far&quot;: InspectField(
            path=&quot;far&quot;,
            label=&quot;Far clip&quot;,
            kind=&quot;float&quot;,
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

    def get_projection_matrix(self) -&gt; np.ndarray:
        f = 1.0 / math.tan(self.fov_y * 0.5)
        near, far = self.near, self.far
        proj = np.zeros((4, 4), dtype=np.float32)
        proj[0, 0] = f / max(1e-6, self.aspect)
        proj[1, 1] = f
        proj[2, 2] = (far + near) / (near - far)
        proj[2, 3] = (2 * far * near) / (near - far)
        proj[3, 2] = -1.0
        return proj


class OrthographicCameraComponent(CameraComponent):
    def __init__(self, left: float = -1.0, right: float = 1.0, bottom: float = -1.0, top: float = 1.0, near: float = 0.1, far: float = 100.0):
        super().__init__(near=near, far=far)
        self.left = left
        self.right = right
        self.bottom = bottom
        self.top = top

    def get_projection_matrix(self) -&gt; np.ndarray:
        lr = self.right - self.left
        tb = self.top - self.bottom
        fn = self.far - self.near
        proj = np.identity(4, dtype=np.float32)
        proj[0, 0] = 2.0 / lr
        proj[1, 1] = 2.0 / tb
        proj[2, 2] = -2.0 / fn
        proj[0, 3] = -(self.right + self.left) / lr
        proj[1, 3] = -(self.top + self.bottom) / tb
        proj[2, 3] = -(self.far + self.near) / fn
        return proj


class CameraController(InputComponent):
    &quot;&quot;&quot;Base class for camera manipulation controllers.&quot;&quot;&quot;

    def start(self, scene):
        super().start(scene)
        self.camera_component = self.entity.get_component(CameraComponent)
        if self.camera_component is None:
            raise RuntimeError(&quot;OrbitCameraController requires a CameraComponent on the same entity.&quot;)

    def orbit(self, d_azimuth: float, d_elevation: float):
        return

    def pan(self, dx: float, dy: float):
        return

    def zoom(self, delta: float):
        return


class OrbitCameraController(CameraController):
    &quot;&quot;&quot;Orbit controller similar to common DCC tools.&quot;&quot;&quot;

    # Эти поля можно редактировать прямо в инспекторе
    radius = inspect(
        5.0, label=&quot;Radius&quot;, kind=&quot;float&quot;,
        min=0.1, max=100.0, step=0.1,
    )
    # target – vec3, редактируем как три спинбокса
    target = inspect(
        np.array([0.0, 0.0, 0.0], dtype=np.float32),
        label=&quot;Target&quot;, kind=&quot;vec3&quot;,
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

    def start(self, scene):
        if self.entity is None:
            raise RuntimeError(&quot;OrbitCameraController must be attached to an entity.&quot;)
        super().start(scene)
        self._update_pose()

    def prevent_moving(self):
        self._prevent_moving = True

    def _update_pose(self):
        entity = self.entity
        if entity is None:
            return
        r = float(np.clip(self.radius, self._min_radius, self._max_radius))
        cos_elev = math.cos(self.elevation)
        eye = np.array(
            [
                self.target[0] + r * math.cos(self.azimuth) * cos_elev,
                self.target[1] + r * math.sin(self.azimuth) * cos_elev,
                self.target[2] + r * math.sin(self.elevation),
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
        right = rot[:, 0]
        up = rot[:, 1]
        self.target = self.target + right * dx + up * dy
        self._update_pose()

    def _state(self, viewport) -&gt; dict:
        key = id(viewport)
        if key not in self._states:
            self._states[key] = {&quot;orbit&quot;: False, &quot;pan&quot;: False, &quot;last&quot;: None}
        return self._states[key]

    def on_mouse_button(self, viewport, button: int, action: int, mods: int):
        #print(f&quot;!!!!!!!!!!!!Mouse button event: button={button}, action={action}, mods={mods}&quot;)  # --- DEBUG ---
        if viewport != self.camera_component.viewport:
            return

        state = self._state(viewport)
        if button == MouseButton.MIDDLE:
            state[&quot;orbit&quot;] = action == Action.PRESS
        elif button == MouseButton.RIGHT:
            state[&quot;pan&quot;] = action == Action.PRESS
        if action == Action.RELEASE:
            state[&quot;last&quot;] = None

    def on_mouse_move(self, viewport, x: float, y: float, dx: float, dy: float):
        if self._prevent_moving:
            return
        if viewport != self.camera_component.viewport:
            return
        state = self._state(viewport)
        if state.get(&quot;last&quot;) is None:
            state[&quot;last&quot;] = (x, y)
            return
        state[&quot;last&quot;] = (x, y)
        if state.get(&quot;orbit&quot;):
            self.orbit(-dx * self._orbit_speed, dy * self._orbit_speed)
        elif state.get(&quot;pan&quot;):
            self.pan(-dx * self._pan_speed, dy * self._pan_speed)

    def on_scroll(self, viewport, xoffset: float, yoffset: float):
        print(f&quot;!!!!!!!!!!!!Scroll event: xoffset={xoffset}, yoffset={yoffset}&quot;)  # --- DEBUG ---
        if self._prevent_moving:
            return
        if viewport != self.camera_component.viewport:
            return
        self.zoom(-yoffset * self._zoom_speed)

</code></pre>
</body>
</html>
