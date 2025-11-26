<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/inertia3d.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
<br>
import numpy as np<br>
from termin.geombase.pose3 import Pose3<br>
from termin.geombase.screw import Screw3<br>
<br>
<br>
def skew3(v):<br>
&#9;&quot;&quot;&quot;3D skew matrix: v×x = skew3(v) @ x.&quot;&quot;&quot;<br>
&#9;vx, vy, vz = v<br>
&#9;return np.array([<br>
&#9;&#9;[ 0,   -vz,  vy ],<br>
&#9;&#9;[ vz,   0,  -vx ],<br>
&#9;&#9;[-vy,  vx,   0  ],<br>
&#9;], float)<br>
<br>
<br>
class SpatialInertia3D:<br>
&#9;def __init__(self, mass=0.0, inertia=None, com=np.zeros(3)):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;mass    : масса<br>
&#9;&#9;inertia : 3×3 матрица тензора инерции в центре масс<br>
&#9;&#9;com     : 3-вектор центра масс (в локальной системе)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.m = float(mass)<br>
&#9;&#9;if inertia is None:<br>
&#9;&#9;&#9;self.Ic = np.zeros((3,3), float)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;self.Ic = np.asarray(inertia, float).reshape(3,3)<br>
&#9;&#9;self.c = np.asarray(com, float).reshape(3)<br>
<br>
&#9;@property<br>
&#9;def mass(self):<br>
&#9;&#9;return self.m<br>
<br>
&#9;@property<br>
&#9;def inertia_matrix(self):<br>
&#9;&#9;return self.Ic<br>
<br>
&#9;@property<br>
&#9;def center_of_mass(self):<br>
&#9;&#9;return self.c<br>
<br>
&#9;# ------------------------------------------------------------<br>
&#9;#     transform / rotated<br>
&#9;# ------------------------------------------------------------<br>
&#9;def transform_by(self, pose: Pose3) -&gt; &quot;SpatialInertia3D&quot;:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Преобразование spatial inertia в новую СК.<br>
&#9;&#9;Как и в 2D: COM просто переносится.<br>
&#9;&#9;Тензор инерции переносится с помощью правила для тензора.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;R = pose.rotation_matrix()<br>
&#9;&#9;cW = pose.transform_point(self.c)<br>
<br>
&#9;&#9;# I_com_new = R * I_com * R^T<br>
&#9;&#9;Ic_new = R @ self.Ic @ R.T<br>
&#9;&#9;return SpatialInertia3D(self.m, Ic_new, cW)<br>
<br>
&#9;def rotated(self, ang):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Повернуть spatial inertia в локале.<br>
&#9;&#9;ang — 3-вектор, интерпретируем как ось-угол через экспоненту.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Pose3 умеет делать экспоненту<br>
&#9;&#9;R = Pose3(lin=np.zeros(3), ang=ang).rotation_matrix()<br>
<br>
&#9;&#9;c_new = R @ self.c<br>
&#9;&#9;Ic_new = R @ self.Ic @ R.T<br>
&#9;&#9;return SpatialInertia3D(self.m, Ic_new, c_new)<br>
<br>
&#9;# ------------------------------------------------------------<br>
&#9;#     Spatial inertia matrix (VW order)<br>
&#9;# ------------------------------------------------------------<br>
&#9;def to_matrix_vw_order(self):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает spatial inertia в порядке:<br>
&#9;&#9;[ v, ω ]  (первые 3 — линейные, вторые 3 — угловые).<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;m = self.m<br>
&#9;&#9;c = self.c<br>
&#9;&#9;S = skew3(c)<br>
<br>
&#9;&#9;upper_left  = m * np.eye(3)<br>
&#9;&#9;upper_right = -m * S<br>
&#9;&#9;lower_left  = m * S<br>
&#9;&#9;lower_right = self.Ic + m * (S @ S.T)<br>
<br>
&#9;&#9;return np.block([<br>
&#9;&#9;&#9;[upper_left,  upper_right],<br>
&#9;&#9;&#9;[lower_left,  lower_right]<br>
&#9;&#9;])<br>
<br>
&#9;# ------------------------------------------------------------<br>
&#9;#     Gravity wrench<br>
&#9;# ------------------------------------------------------------<br>
&#9;def gravity_wrench(self, g_local: np.ndarray) -&gt; Screw3:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает винт (F, τ) в локальной системе.<br>
&#9;&#9;g_local — гравитация в ЛОКАЛЕ.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;m = self.m<br>
&#9;&#9;c = self.c<br>
&#9;&#9;F = m * g_local<br>
&#9;&#9;τ = np.cross(c, F)<br>
&#9;&#9;return Screw3(ang=τ, lin=F)<br>
<br>
&#9;# ------------------------------------------------------------<br>
&#9;#     Bias wrench<br>
&#9;# ------------------------------------------------------------<br>
&#9;def bias_wrench(self, velocity: Screw3) -&gt; Screw3:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Пространственный bias-винт: v ×* (I v).<br>
&#9;&#9;Полный 3D аналог твоего 2D-кода.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;m = self.m<br>
&#9;&#9;c = self.c<br>
&#9;&#9;Ic = self.Ic<br>
<br>
&#9;&#9;v_lin = velocity.lin<br>
&#9;&#9;v_ang = velocity.ang<br>
<br>
&#9;&#9;S = skew3(c)<br>
<br>
&#9;&#9;# spatial inertia * v:<br>
&#9;&#9;h_lin = m * (v_lin + np.cross(v_ang, c))<br>
&#9;&#9;h_ang = Ic @ v_ang + m * np.cross(c, v_lin)<br>
<br>
&#9;&#9;# теперь bias = v ×* h<br>
&#9;&#9;# линейная часть:<br>
&#9;&#9;b_lin = np.cross(v_ang, h_lin) + np.cross(v_lin, h_ang)*0.0  # линейная от линейной не даёт<br>
&#9;&#9;# угловая часть:<br>
&#9;&#9;b_ang = np.cross(v_ang, h_ang)<br>
<br>
&#9;&#9;return Screw3(ang=b_ang, lin=b_lin)<br>
<br>
&#9;# ------------------------------------------------------------<br>
&#9;#     Сложение spatial inertia<br>
&#9;# ------------------------------------------------------------<br>
&#9;def __add__(self, other):<br>
&#9;&#9;if not isinstance(other, SpatialInertia3D):<br>
&#9;&#9;&#9;return NotImplemented<br>
<br>
&#9;&#9;m1, m2 = self.m, other.m<br>
&#9;&#9;c1, c2 = self.c, other.c<br>
&#9;&#9;I1, I2 = self.Ic, other.Ic<br>
<br>
&#9;&#9;m = m1 + m2<br>
&#9;&#9;if m == 0.0:<br>
&#9;&#9;&#9;return SpatialInertia3D(0.0, np.zeros((3,3)), np.zeros(3))<br>
<br>
&#9;&#9;c = (m1 * c1 + m2 * c2) / m<br>
&#9;&#9;d1 = c1 - c<br>
&#9;&#9;d2 = c2 - c<br>
<br>
&#9;&#9;S1 = skew3(d1)<br>
&#9;&#9;S2 = skew3(d2)<br>
<br>
&#9;&#9;Ic = I1 + m1 * (S1 @ S1.T) + I2 + m2 * (S2 @ S2.T)<br>
<br>
&#9;&#9;return SpatialInertia3D(m, Ic, c)<br>
<br>
&#9;# ------------------------------------------------------------<br>
&#9;#     Kinetic energy<br>
&#9;# ------------------------------------------------------------<br>
&#9;def get_kinetic_energy(self, velocity: np.ndarray, omega: np.ndarray) -&gt; float:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;velocity — линейная скорость<br>
&#9;&#9;omega    — угловая скорость<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;v2 = np.dot(velocity, velocity)<br>
&#9;&#9;return 0.5 * self.m * v2 + 0.5 * (omega @ (self.Ic @ omega))<br>
<!-- END SCAT CODE -->
</body>
</html>
