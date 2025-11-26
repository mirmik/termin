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
&#9;&quot;&quot;&quot;Component that exposes view/projection matrices based on entity pose.&quot;&quot;&quot;<br>
<br>
&#9;def screen_point_to_ray(self, x: float, y: float, viewport_rect):<br>
&#9;&#9;import numpy as np<br>
&#9;&#9;from termin.geombase.ray import Ray3<br>
<br>
&#9;&#9;px, py, pw, ph = viewport_rect<br>
&#9;&#9;<br>
&#9;&#9;nx = ( (x - px) / pw ) * 2.0 - 1.0<br>
&#9;&#9;ny = ( (y - py) / ph ) * -2.0 + 1.0<br>
&#9;&#9;<br>
&#9;&#9;PV = self.get_projection_matrix() @ self.get_view_matrix()<br>
&#9;&#9;<br>
&#9;&#9;inv_PV = np.linalg.inv(PV)<br>
&#9;&#9;<br>
&#9;&#9;near = np.array([nx, ny, -1.0, 1.0], dtype=np.float32)<br>
&#9;&#9;far  = np.array([nx, ny,  1.0, 1.0], dtype=np.float32)<br>
&#9;&#9;<br>
&#9;&#9;p_near = inv_PV @ near<br>
&#9;&#9;p_far  = inv_PV @ far<br>
&#9;&#9;<br>
&#9;&#9;p_near /= p_near[3]<br>
&#9;&#9;p_far  /= p_far[3]<br>
&#9;&#9;<br>
&#9;&#9;origin = p_near[:3]<br>
&#9;&#9;direction = p_far[:3] - p_near[:3]<br>
&#9;&#9;<br>
&#9;&#9;direction /= np.linalg.norm(direction)<br>
&#9;&#9;<br>
&#9;&#9;return Ray3(origin, direction)<br>
<br>
&#9;def __init__(self, near: float = 0.1, far: float = 100.0):<br>
&#9;&#9;super().__init__(enabled=True)<br>
&#9;&#9;self.near = near<br>
&#9;&#9;self.far = far<br>
&#9;&#9;self.viewport = None <br>
<br>
&#9;def start(self, scene):<br>
&#9;&#9;if self.entity is None:<br>
&#9;&#9;&#9;raise RuntimeError(&quot;CameraComponent must be attached to an entity.&quot;)<br>
&#9;&#9;super().start(scene)<br>
<br>
&#9;def get_view_matrix(self) -&gt; np.ndarray:<br>
&#9;&#9;if self.entity is None:<br>
&#9;&#9;&#9;raise RuntimeError(&quot;CameraComponent has no entity.&quot;)<br>
&#9;# Entity.pose не существует — берём позу из Transform3<br>
&#9;&#9;return self.entity.transform.global_pose().inverse().as_matrix()<br>
&#9;&#9;#return self.entity.pose.inverse().as_matrix()<br>
<br>
&#9;def get_projection_matrix(self) -&gt; np.ndarray:<br>
&#9;&#9;raise NotImplementedError<br>
<br>
&#9;def projection_matrix(self) -&gt; np.ndarray:<br>
&#9;&#9;return self.get_projection_matrix()<br>
<br>
&#9;def view_matrix(self) -&gt; np.ndarray:<br>
&#9;&#9;return self.get_view_matrix()<br>
<br>
&#9;def set_aspect(self, aspect: float):<br>
&#9;&#9;&quot;&quot;&quot;Optional method for perspective cameras.&quot;&quot;&quot;<br>
&#9;&#9;return<br>
<br>
<br>
class PerspectiveCameraComponent(CameraComponent):<br>
&#9;# поля для инспектора (fov в градусах, near/far как есть)<br>
&#9;inspect_fields = {<br>
&#9;&#9;&quot;fov_deg&quot;: InspectField(<br>
&#9;&#9;&#9;label=&quot;FOV (deg)&quot;,<br>
&#9;&#9;&#9;kind=&quot;float&quot;,<br>
&#9;&#9;&#9;min=5.0,<br>
&#9;&#9;&#9;max=170.0,<br>
&#9;&#9;&#9;step=1.0,<br>
&#9;&#9;&#9;getter=lambda obj: math.degrees(obj.fov_y),<br>
&#9;&#9;&#9;setter=lambda obj, value: setattr(obj, &quot;fov_y&quot;, math.radians(float(value))),<br>
&#9;&#9;),<br>
&#9;&#9;&quot;near&quot;: InspectField(<br>
&#9;&#9;&#9;path=&quot;near&quot;,<br>
&#9;&#9;&#9;label=&quot;Near clip&quot;,<br>
&#9;&#9;&#9;kind=&quot;float&quot;,<br>
&#9;&#9;&#9;min=0.001,<br>
&#9;&#9;&#9;step=0.01,<br>
&#9;&#9;),<br>
&#9;&#9;&quot;far&quot;: InspectField(<br>
&#9;&#9;&#9;path=&quot;far&quot;,<br>
&#9;&#9;&#9;label=&quot;Far clip&quot;,<br>
&#9;&#9;&#9;kind=&quot;float&quot;,<br>
&#9;&#9;&#9;min=0.01,<br>
&#9;&#9;&#9;step=0.1,<br>
&#9;&#9;),<br>
&#9;}<br>
<br>
&#9;def __init__(self, fov_y_degrees: float = 60.0, aspect: float = 1.0, near: float = 0.1, far: float = 100.0):<br>
&#9;&#9;super().__init__(near=near, far=far)<br>
&#9;&#9;self.fov_y = math.radians(fov_y_degrees)<br>
&#9;&#9;self.aspect = aspect<br>
<br>
&#9;def set_aspect(self, aspect: float):<br>
&#9;&#9;self.aspect = aspect<br>
<br>
&#9;def get_projection_matrix(self) -&gt; np.ndarray:<br>
&#9;&#9;f = 1.0 / math.tan(self.fov_y * 0.5)<br>
&#9;&#9;near, far = self.near, self.far<br>
&#9;&#9;proj = np.zeros((4, 4), dtype=np.float32)<br>
&#9;&#9;proj[0, 0] = f / max(1e-6, self.aspect)<br>
&#9;&#9;proj[1, 1] = f<br>
&#9;&#9;proj[2, 2] = (far + near) / (near - far)<br>
&#9;&#9;proj[2, 3] = (2 * far * near) / (near - far)<br>
&#9;&#9;proj[3, 2] = -1.0<br>
&#9;&#9;return proj<br>
<br>
<br>
class OrthographicCameraComponent(CameraComponent):<br>
&#9;def __init__(self, left: float = -1.0, right: float = 1.0, bottom: float = -1.0, top: float = 1.0, near: float = 0.1, far: float = 100.0):<br>
&#9;&#9;super().__init__(near=near, far=far)<br>
&#9;&#9;self.left = left<br>
&#9;&#9;self.right = right<br>
&#9;&#9;self.bottom = bottom<br>
&#9;&#9;self.top = top<br>
<br>
&#9;def get_projection_matrix(self) -&gt; np.ndarray:<br>
&#9;&#9;lr = self.right - self.left<br>
&#9;&#9;tb = self.top - self.bottom<br>
&#9;&#9;fn = self.far - self.near<br>
&#9;&#9;proj = np.identity(4, dtype=np.float32)<br>
&#9;&#9;proj[0, 0] = 2.0 / lr<br>
&#9;&#9;proj[1, 1] = 2.0 / tb<br>
&#9;&#9;proj[2, 2] = -2.0 / fn<br>
&#9;&#9;proj[0, 3] = -(self.right + self.left) / lr<br>
&#9;&#9;proj[1, 3] = -(self.top + self.bottom) / tb<br>
&#9;&#9;proj[2, 3] = -(self.far + self.near) / fn<br>
&#9;&#9;return proj<br>
<br>
<br>
class CameraController(InputComponent):<br>
&#9;&quot;&quot;&quot;Base class for camera manipulation controllers.&quot;&quot;&quot;<br>
<br>
&#9;def start(self, scene):<br>
&#9;&#9;super().start(scene)<br>
&#9;&#9;self.camera_component = self.entity.get_component(CameraComponent)<br>
&#9;&#9;if self.camera_component is None:<br>
&#9;&#9;&#9;raise RuntimeError(&quot;OrbitCameraController requires a CameraComponent on the same entity.&quot;)<br>
<br>
&#9;def orbit(self, d_azimuth: float, d_elevation: float):<br>
&#9;&#9;return<br>
<br>
&#9;def pan(self, dx: float, dy: float):<br>
&#9;&#9;return<br>
<br>
&#9;def zoom(self, delta: float):<br>
&#9;&#9;return<br>
<br>
<br>
class OrbitCameraController(CameraController):<br>
&#9;&quot;&quot;&quot;Orbit controller similar to common DCC tools.&quot;&quot;&quot;<br>
<br>
&#9;# Эти поля можно редактировать прямо в инспекторе<br>
&#9;radius = inspect(<br>
&#9;&#9;5.0, label=&quot;Radius&quot;, kind=&quot;float&quot;,<br>
&#9;&#9;min=0.1, max=100.0, step=0.1,<br>
&#9;)<br>
&#9;# target – vec3, редактируем как три спинбокса<br>
&#9;target = inspect(<br>
&#9;&#9;np.array([0.0, 0.0, 0.0], dtype=np.float32),<br>
&#9;&#9;label=&quot;Target&quot;, kind=&quot;vec3&quot;,<br>
&#9;&#9;setter=lambda obj, value: obj.inspect_target_update(value)<br>
&#9;)<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;target: Optional[np.ndarray] = None,<br>
&#9;&#9;radius: float = 5.0,<br>
&#9;&#9;azimuth: float = 45.0,<br>
&#9;&#9;elevation: float = 30.0,<br>
&#9;&#9;min_radius: float = 1.0,<br>
&#9;&#9;max_radius: float = 100.0,<br>
&#9;&#9;prevent_moving: bool = False,<br>
&#9;):<br>
&#9;&#9;super().__init__(enabled=True)<br>
&#9;&#9;self.target = np.array(target if target is not None else [0.0, 0.0, 0.0], dtype=np.float32)<br>
&#9;&#9;self.radius = radius<br>
&#9;&#9;self.azimuth = math.radians(azimuth)<br>
&#9;&#9;self.elevation = math.radians(elevation)<br>
&#9;&#9;self._min_radius = min_radius<br>
&#9;&#9;self._max_radius = max_radius<br>
&#9;&#9;self._orbit_speed = 0.2<br>
&#9;&#9;self._pan_speed = 0.005<br>
&#9;&#9;self._zoom_speed = 0.5<br>
&#9;&#9;self._states: Dict[int, dict] = {}<br>
&#9;&#9;self._prevent_moving = prevent_moving<br>
<br>
&#9;def inspect_target_update(self, val):<br>
&#9;&#9;self.target = val<br>
&#9;&#9;self._update_pose()<br>
<br>
&#9;def start(self, scene):<br>
&#9;&#9;if self.entity is None:<br>
&#9;&#9;&#9;raise RuntimeError(&quot;OrbitCameraController must be attached to an entity.&quot;)<br>
&#9;&#9;super().start(scene)<br>
&#9;&#9;self._update_pose()<br>
<br>
&#9;def prevent_moving(self):<br>
&#9;&#9;self._prevent_moving = True<br>
<br>
&#9;def _update_pose(self):<br>
&#9;&#9;entity = self.entity<br>
&#9;&#9;if entity is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;r = float(np.clip(self.radius, self._min_radius, self._max_radius))<br>
&#9;&#9;cos_elev = math.cos(self.elevation)<br>
&#9;&#9;eye = np.array(<br>
&#9;&#9;&#9;[<br>
&#9;&#9;&#9;&#9;self.target[0] + r * math.cos(self.azimuth) * cos_elev,<br>
&#9;&#9;&#9;&#9;self.target[1] + r * math.sin(self.azimuth) * cos_elev,<br>
&#9;&#9;&#9;&#9;self.target[2] + r * math.sin(self.elevation),<br>
&#9;&#9;&#9;],<br>
&#9;&#9;&#9;dtype=np.float32,<br>
&#9;&#9;)<br>
&#9;&#9;entity.transform.relocate(Pose3.looking_at(eye=eye, target=self.target))<br>
<br>
&#9;def orbit(self, delta_azimuth: float, delta_elevation: float):<br>
&#9;&#9;self.azimuth += math.radians(delta_azimuth)<br>
&#9;&#9;self.elevation = np.clip(self.elevation + math.radians(delta_elevation), math.radians(-89.0), math.radians(89.0))<br>
&#9;&#9;self._update_pose()<br>
<br>
&#9;def zoom(self, delta: float):<br>
&#9;&#9;self.radius += delta<br>
&#9;&#9;self._update_pose()<br>
<br>
&#9;def pan(self, dx: float, dy: float):<br>
&#9;&#9;entity = self.entity<br>
&#9;&#9;if entity is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;rot = entity.transform.global_pose().rotation_matrix()<br>
&#9;&#9;right = rot[:, 0]<br>
&#9;&#9;up = rot[:, 1]<br>
&#9;&#9;self.target = self.target + right * dx + up * dy<br>
&#9;&#9;self._update_pose()<br>
<br>
&#9;def _state(self, viewport) -&gt; dict:<br>
&#9;&#9;key = id(viewport)<br>
&#9;&#9;if key not in self._states:<br>
&#9;&#9;&#9;self._states[key] = {&quot;orbit&quot;: False, &quot;pan&quot;: False, &quot;last&quot;: None}<br>
&#9;&#9;return self._states[key]<br>
<br>
&#9;def on_mouse_button(self, viewport, button: int, action: int, mods: int):<br>
&#9;&#9;#print(f&quot;!!!!!!!!!!!!Mouse button event: button={button}, action={action}, mods={mods}&quot;)  # --- DEBUG ---<br>
&#9;&#9;if viewport != self.camera_component.viewport:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;state = self._state(viewport)<br>
&#9;&#9;if button == MouseButton.MIDDLE:<br>
&#9;&#9;&#9;state[&quot;orbit&quot;] = action == Action.PRESS<br>
&#9;&#9;elif button == MouseButton.RIGHT:<br>
&#9;&#9;&#9;state[&quot;pan&quot;] = action == Action.PRESS<br>
&#9;&#9;if action == Action.RELEASE:<br>
&#9;&#9;&#9;state[&quot;last&quot;] = None<br>
<br>
&#9;def on_mouse_move(self, viewport, x: float, y: float, dx: float, dy: float):<br>
&#9;&#9;if self._prevent_moving:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;if viewport != self.camera_component.viewport:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;state = self._state(viewport)<br>
&#9;&#9;if state.get(&quot;last&quot;) is None:<br>
&#9;&#9;&#9;state[&quot;last&quot;] = (x, y)<br>
&#9;&#9;&#9;return<br>
&#9;&#9;state[&quot;last&quot;] = (x, y)<br>
&#9;&#9;if state.get(&quot;orbit&quot;):<br>
&#9;&#9;&#9;self.orbit(-dx * self._orbit_speed, dy * self._orbit_speed)<br>
&#9;&#9;elif state.get(&quot;pan&quot;):<br>
&#9;&#9;&#9;self.pan(-dx * self._pan_speed, dy * self._pan_speed)<br>
<br>
&#9;def on_scroll(self, viewport, xoffset: float, yoffset: float):<br>
&#9;&#9;print(f&quot;!!!!!!!!!!!!Scroll event: xoffset={xoffset}, yoffset={yoffset}&quot;)  # --- DEBUG ---<br>
&#9;&#9;if self._prevent_moving:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;if viewport != self.camera_component.viewport:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self.zoom(-yoffset * self._zoom_speed)<br>
<!-- END SCAT CODE -->
</body>
</html>
