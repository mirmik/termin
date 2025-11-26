<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/camera.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Camera components and controllers.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import math<br>
from dataclasses import dataclass<br>
from typing import Dict, Iterable, Optional<br>
<br>
import numpy as np<br>
<br>
from termin.geombase.pose3 import Pose3<br>
<br>
from .entity import Component, InputComponent<br>
from .backends.base import Action, MouseButton<br>
<br>
from termin.visualization.inspect import InspectField, inspect<br>
<br>
<br>
class CameraComponent(Component):<br>
    &quot;&quot;&quot;Component that exposes view/projection matrices based on entity pose.&quot;&quot;&quot;<br>
<br>
    def screen_point_to_ray(self, x: float, y: float, viewport_rect):<br>
        import numpy as np<br>
        from termin.geombase.ray import Ray3<br>
<br>
        px, py, pw, ph = viewport_rect<br>
        <br>
        nx = ( (x - px) / pw ) * 2.0 - 1.0<br>
        ny = ( (y - py) / ph ) * -2.0 + 1.0<br>
        <br>
        PV = self.get_projection_matrix() @ self.get_view_matrix()<br>
        <br>
        inv_PV = np.linalg.inv(PV)<br>
        <br>
        near = np.array([nx, ny, -1.0, 1.0], dtype=np.float32)<br>
        far  = np.array([nx, ny,  1.0, 1.0], dtype=np.float32)<br>
        <br>
        p_near = inv_PV @ near<br>
        p_far  = inv_PV @ far<br>
        <br>
        p_near /= p_near[3]<br>
        p_far  /= p_far[3]<br>
        <br>
        origin = p_near[:3]<br>
        direction = p_far[:3] - p_near[:3]<br>
        <br>
        direction /= np.linalg.norm(direction)<br>
        <br>
        return Ray3(origin, direction)<br>
<br>
    def __init__(self, near: float = 0.1, far: float = 100.0):<br>
        super().__init__(enabled=True)<br>
        self.near = near<br>
        self.far = far<br>
        self.viewport = None <br>
<br>
    def start(self, scene):<br>
        if self.entity is None:<br>
            raise RuntimeError(&quot;CameraComponent must be attached to an entity.&quot;)<br>
        super().start(scene)<br>
<br>
    def get_view_matrix(self) -&gt; np.ndarray:<br>
        if self.entity is None:<br>
            raise RuntimeError(&quot;CameraComponent has no entity.&quot;)<br>
    # Entity.pose не существует — берём позу из Transform3<br>
        return self.entity.transform.global_pose().inverse().as_matrix()<br>
        #return self.entity.pose.inverse().as_matrix()<br>
<br>
    def get_projection_matrix(self) -&gt; np.ndarray:<br>
        raise NotImplementedError<br>
<br>
    def projection_matrix(self) -&gt; np.ndarray:<br>
        return self.get_projection_matrix()<br>
<br>
    def view_matrix(self) -&gt; np.ndarray:<br>
        return self.get_view_matrix()<br>
<br>
    def set_aspect(self, aspect: float):<br>
        &quot;&quot;&quot;Optional method for perspective cameras.&quot;&quot;&quot;<br>
        return<br>
<br>
<br>
class PerspectiveCameraComponent(CameraComponent):<br>
    # поля для инспектора (fov в градусах, near/far как есть)<br>
    inspect_fields = {<br>
        &quot;fov_deg&quot;: InspectField(<br>
            label=&quot;FOV (deg)&quot;,<br>
            kind=&quot;float&quot;,<br>
            min=5.0,<br>
            max=170.0,<br>
            step=1.0,<br>
            getter=lambda obj: math.degrees(obj.fov_y),<br>
            setter=lambda obj, value: setattr(obj, &quot;fov_y&quot;, math.radians(float(value))),<br>
        ),<br>
        &quot;near&quot;: InspectField(<br>
            path=&quot;near&quot;,<br>
            label=&quot;Near clip&quot;,<br>
            kind=&quot;float&quot;,<br>
            min=0.001,<br>
            step=0.01,<br>
        ),<br>
        &quot;far&quot;: InspectField(<br>
            path=&quot;far&quot;,<br>
            label=&quot;Far clip&quot;,<br>
            kind=&quot;float&quot;,<br>
            min=0.01,<br>
            step=0.1,<br>
        ),<br>
    }<br>
<br>
    def __init__(self, fov_y_degrees: float = 60.0, aspect: float = 1.0, near: float = 0.1, far: float = 100.0):<br>
        super().__init__(near=near, far=far)<br>
        self.fov_y = math.radians(fov_y_degrees)<br>
        self.aspect = aspect<br>
<br>
    def set_aspect(self, aspect: float):<br>
        self.aspect = aspect<br>
<br>
    def get_projection_matrix(self) -&gt; np.ndarray:<br>
        f = 1.0 / math.tan(self.fov_y * 0.5)<br>
        near, far = self.near, self.far<br>
        proj = np.zeros((4, 4), dtype=np.float32)<br>
        proj[0, 0] = f / max(1e-6, self.aspect)<br>
        proj[1, 1] = f<br>
        proj[2, 2] = (far + near) / (near - far)<br>
        proj[2, 3] = (2 * far * near) / (near - far)<br>
        proj[3, 2] = -1.0<br>
        return proj<br>
<br>
<br>
class OrthographicCameraComponent(CameraComponent):<br>
    def __init__(self, left: float = -1.0, right: float = 1.0, bottom: float = -1.0, top: float = 1.0, near: float = 0.1, far: float = 100.0):<br>
        super().__init__(near=near, far=far)<br>
        self.left = left<br>
        self.right = right<br>
        self.bottom = bottom<br>
        self.top = top<br>
<br>
    def get_projection_matrix(self) -&gt; np.ndarray:<br>
        lr = self.right - self.left<br>
        tb = self.top - self.bottom<br>
        fn = self.far - self.near<br>
        proj = np.identity(4, dtype=np.float32)<br>
        proj[0, 0] = 2.0 / lr<br>
        proj[1, 1] = 2.0 / tb<br>
        proj[2, 2] = -2.0 / fn<br>
        proj[0, 3] = -(self.right + self.left) / lr<br>
        proj[1, 3] = -(self.top + self.bottom) / tb<br>
        proj[2, 3] = -(self.far + self.near) / fn<br>
        return proj<br>
<br>
<br>
class CameraController(InputComponent):<br>
    &quot;&quot;&quot;Base class for camera manipulation controllers.&quot;&quot;&quot;<br>
<br>
    def start(self, scene):<br>
        super().start(scene)<br>
        self.camera_component = self.entity.get_component(CameraComponent)<br>
        if self.camera_component is None:<br>
            raise RuntimeError(&quot;OrbitCameraController requires a CameraComponent on the same entity.&quot;)<br>
<br>
    def orbit(self, d_azimuth: float, d_elevation: float):<br>
        return<br>
<br>
    def pan(self, dx: float, dy: float):<br>
        return<br>
<br>
    def zoom(self, delta: float):<br>
        return<br>
<br>
<br>
class OrbitCameraController(CameraController):<br>
    &quot;&quot;&quot;Orbit controller similar to common DCC tools.&quot;&quot;&quot;<br>
<br>
    # Эти поля можно редактировать прямо в инспекторе<br>
    radius = inspect(<br>
        5.0, label=&quot;Radius&quot;, kind=&quot;float&quot;,<br>
        min=0.1, max=100.0, step=0.1,<br>
    )<br>
    # target – vec3, редактируем как три спинбокса<br>
    target = inspect(<br>
        np.array([0.0, 0.0, 0.0], dtype=np.float32),<br>
        label=&quot;Target&quot;, kind=&quot;vec3&quot;,<br>
        setter=lambda obj, value: obj.inspect_target_update(value)<br>
    )<br>
<br>
    def __init__(<br>
        self,<br>
        target: Optional[np.ndarray] = None,<br>
        radius: float = 5.0,<br>
        azimuth: float = 45.0,<br>
        elevation: float = 30.0,<br>
        min_radius: float = 1.0,<br>
        max_radius: float = 100.0,<br>
        prevent_moving: bool = False,<br>
    ):<br>
        super().__init__(enabled=True)<br>
        self.target = np.array(target if target is not None else [0.0, 0.0, 0.0], dtype=np.float32)<br>
        self.radius = radius<br>
        self.azimuth = math.radians(azimuth)<br>
        self.elevation = math.radians(elevation)<br>
        self._min_radius = min_radius<br>
        self._max_radius = max_radius<br>
        self._orbit_speed = 0.2<br>
        self._pan_speed = 0.005<br>
        self._zoom_speed = 0.5<br>
        self._states: Dict[int, dict] = {}<br>
        self._prevent_moving = prevent_moving<br>
<br>
    def inspect_target_update(self, val):<br>
        self.target = val<br>
        self._update_pose()<br>
<br>
    def start(self, scene):<br>
        if self.entity is None:<br>
            raise RuntimeError(&quot;OrbitCameraController must be attached to an entity.&quot;)<br>
        super().start(scene)<br>
        self._update_pose()<br>
<br>
    def prevent_moving(self):<br>
        self._prevent_moving = True<br>
<br>
    def _update_pose(self):<br>
        entity = self.entity<br>
        if entity is None:<br>
            return<br>
        r = float(np.clip(self.radius, self._min_radius, self._max_radius))<br>
        cos_elev = math.cos(self.elevation)<br>
        eye = np.array(<br>
            [<br>
                self.target[0] + r * math.cos(self.azimuth) * cos_elev,<br>
                self.target[1] + r * math.sin(self.azimuth) * cos_elev,<br>
                self.target[2] + r * math.sin(self.elevation),<br>
            ],<br>
            dtype=np.float32,<br>
        )<br>
        entity.transform.relocate(Pose3.looking_at(eye=eye, target=self.target))<br>
<br>
    def orbit(self, delta_azimuth: float, delta_elevation: float):<br>
        self.azimuth += math.radians(delta_azimuth)<br>
        self.elevation = np.clip(self.elevation + math.radians(delta_elevation), math.radians(-89.0), math.radians(89.0))<br>
        self._update_pose()<br>
<br>
    def zoom(self, delta: float):<br>
        self.radius += delta<br>
        self._update_pose()<br>
<br>
    def pan(self, dx: float, dy: float):<br>
        entity = self.entity<br>
        if entity is None:<br>
            return<br>
        rot = entity.transform.global_pose().rotation_matrix()<br>
        right = rot[:, 0]<br>
        up = rot[:, 1]<br>
        self.target = self.target + right * dx + up * dy<br>
        self._update_pose()<br>
<br>
    def _state(self, viewport) -&gt; dict:<br>
        key = id(viewport)<br>
        if key not in self._states:<br>
            self._states[key] = {&quot;orbit&quot;: False, &quot;pan&quot;: False, &quot;last&quot;: None}<br>
        return self._states[key]<br>
<br>
    def on_mouse_button(self, viewport, button: int, action: int, mods: int):<br>
        #print(f&quot;!!!!!!!!!!!!Mouse button event: button={button}, action={action}, mods={mods}&quot;)  # --- DEBUG ---<br>
        if viewport != self.camera_component.viewport:<br>
            return<br>
<br>
        state = self._state(viewport)<br>
        if button == MouseButton.MIDDLE:<br>
            state[&quot;orbit&quot;] = action == Action.PRESS<br>
        elif button == MouseButton.RIGHT:<br>
            state[&quot;pan&quot;] = action == Action.PRESS<br>
        if action == Action.RELEASE:<br>
            state[&quot;last&quot;] = None<br>
<br>
    def on_mouse_move(self, viewport, x: float, y: float, dx: float, dy: float):<br>
        if self._prevent_moving:<br>
            return<br>
        if viewport != self.camera_component.viewport:<br>
            return<br>
        state = self._state(viewport)<br>
        if state.get(&quot;last&quot;) is None:<br>
            state[&quot;last&quot;] = (x, y)<br>
            return<br>
        state[&quot;last&quot;] = (x, y)<br>
        if state.get(&quot;orbit&quot;):<br>
            self.orbit(-dx * self._orbit_speed, dy * self._orbit_speed)<br>
        elif state.get(&quot;pan&quot;):<br>
            self.pan(-dx * self._pan_speed, dy * self._pan_speed)<br>
<br>
    def on_scroll(self, viewport, xoffset: float, yoffset: float):<br>
        print(f&quot;!!!!!!!!!!!!Scroll event: xoffset={xoffset}, yoffset={yoffset}&quot;)  # --- DEBUG ---<br>
        if self._prevent_moving:<br>
            return<br>
        if viewport != self.camera_component.viewport:<br>
            return<br>
        self.zoom(-yoffset * self._zoom_speed)<br>
<!-- END SCAT CODE -->
</body>
</html>
