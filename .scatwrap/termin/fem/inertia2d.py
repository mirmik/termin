<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/inertia2d.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
&quot;&quot;&quot;<br>
Инерционные характеристики для 2D многотельной динамики.<br>
&quot;&quot;&quot;<br>
<br>
import numpy as np<br>
from termin.geombase.pose2 import Pose2<br>
from termin.geombase.screw import Screw2, cross2d_scalar<br>
<br>
<br>
import numpy as np<br>
<br>
def skew2(v):<br>
&#9;&quot;&quot;&quot;2D псевдо-skew: ω × r = [-ω*r_y, ω*r_x].<br>
&#9;Здесь возвращаем 2×2 матрицу для углового ω.&quot;&quot;&quot;<br>
&#9;return np.array([[0, -v],<br>
&#9;&#9;&#9;&#9;&#9;[v,  0]])<br>
<br>
class SpatialInertia2D:<br>
&#9;def __init__(self, mass = 0.0, inertia = 0.0, com=np.zeros(2)):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;mass : масса тела<br>
&#9;&#9;J_com : момент инерции вокруг центра масс (скаляр)<br>
&#9;&#9;com : 2-вектор центра масс в локальной системе<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.m = float(mass)<br>
&#9;&#9;self.Jc = float(inertia)<br>
&#9;&#9;self.c = np.asarray(com, float).reshape(2)<br>
<br>
&#9;@property<br>
&#9;def I_com(self):<br>
&#9;&#9;return self.Jc<br>
<br>
&#9;@property<br>
&#9;def mass(self):<br>
&#9;&#9;return self.m<br>
<br>
&#9;@property<br>
&#9;def inertia(self):<br>
&#9;&#9;return self.Jc<br>
<br>
&#9;@property<br>
&#9;def center_of_mass(self):<br>
&#9;&#9;return self.c<br>
<br>
&#9;<br>
&#9;def transform_by(self, pose: Pose2) -&gt; &quot;SpatialInertia2D&quot;:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Трансформировать инерцию в новую систему координат.<br>
&#9;&#9;В 2D момент инерции инвариантен относительно поворота.<br>
&#9;&#9;Центр масс переводится напрямую.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;c_new = pose.transform_point(self.c)<br>
&#9;&#9;return SpatialInertia2D(self.m, self.I_com, c_new)<br>
<br>
&#9;# ------------------------------<br>
&#9;#       Поворот инерции<br>
&#9;# ------------------------------<br>
&#9;def rotated(self, theta):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Повернуть spatial inertia 2D на угол theta.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;R = np.array([<br>
&#9;&#9;&#9;[np.cos(theta), -np.sin(theta)],<br>
&#9;&#9;&#9;[np.sin(theta),  np.cos(theta)],<br>
&#9;&#9;])<br>
<br>
&#9;&#9;# поворот центра масс<br>
&#9;&#9;c_new = R @ self.c<br>
<br>
&#9;&#9;# J переносится как скаляр (инвариант)<br>
&#9;&#9;return SpatialInertia2D(self.m, self.Jc, c_new)<br>
<br>
&#9;# ------------------------------<br>
&#9;#       Spatial inertia matrix<br>
&#9;# ------------------------------<br>
&#9;def to_matrix_vw_order(self):<br>
&#9;&#9;m = self.m<br>
&#9;&#9;cx, cy = self.c<br>
&#9;&#9;J = self.Jc<br>
<br>
&#9;&#9;upper_left = m * np.eye(2)<br>
&#9;&#9;lower_left = m * np.array([[-cy, cx]])<br>
&#9;&#9;upper_right = lower_left.T<br>
&#9;&#9;lower_right = np.array([[J + m * (cx*cx + cy*cy)]])<br>
<br>
&#9;&#9;return np.block([<br>
&#9;&#9;&#9;[upper_left,    upper_right],<br>
&#9;&#9;&#9;[lower_left,    lower_right]<br>
&#9;&#9;])<br>
<br>
&#9;def to_matrix_wv_order(self):<br>
&#9;&#9;m = self.m<br>
&#9;&#9;cx, cy = self.c<br>
&#9;&#9;J = self.Jc<br>
<br>
&#9;&#9;# spatial inertia в 2D (WV-порядок)<br>
&#9;&#9;return np.array([<br>
&#9;&#9;&#9;[J + m*(cx*cx + cy*cy),  m*cy,   -m*cx],<br>
&#9;&#9;&#9;[m*cy,                    m,      0    ],<br>
&#9;&#9;&#9;[-m*cx,                   0,      m    ]<br>
&#9;&#9;], float)<br>
<br>
&#9;# ------------------------------<br>
&#9;#       Gravity wrench<br>
&#9;# ------------------------------<br>
&#9;def gravity_wrench(self, g):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает 3×1 винт (Fx, Fy, τz) в локальной системе!<br>
&#9;&#9;g — вектор гравитации в ЛОКАЛЬНОЙ системе.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;m = self.m<br>
&#9;&#9;cx, cy = self.c<br>
<br>
&#9;&#9;F = m * g<br>
&#9;&#9;τ = cx * F[1] - cy * F[0]<br>
<br>
&#9;&#9;return Screw2(ang=τ, lin=F)<br>
<br>
&#9;def __add__(self, other):<br>
&#9;&#9;if not isinstance(other, SpatialInertia2D):<br>
&#9;&#9;&#9;return NotImplemented<br>
<br>
&#9;&#9;m1, m2 = self.m, other.m<br>
&#9;&#9;c1, c2 = self.c, other.c<br>
&#9;&#9;J1, J2 = self.Jc, other.Jc<br>
<br>
&#9;&#9;m = m1 + m2<br>
&#9;&#9;if m == 0.0:<br>
&#9;&#9;&#9;# пустая инерция<br>
&#9;&#9;&#9;return SpatialInertia2D(0.0, 0.0, np.zeros(2))<br>
<br>
&#9;&#9;# общий центр масс<br>
&#9;&#9;c = (m1 * c1 + m2 * c2) / m<br>
<br>
&#9;&#9;# смещения от индивидуальных COM к общему<br>
&#9;&#9;d1 = c1 - c<br>
&#9;&#9;d2 = c2 - c<br>
<br>
&#9;&#9;# параллельный перенос для моментов инерции (вокруг общего COM)<br>
&#9;&#9;J = J1 + m1 * (d1 @ d1) + J2 + m2 * (d2 @ d2)<br>
<br>
&#9;&#9;return SpatialInertia2D(m, J, c)<br>
<br>
&#9;<br>
&#9;def get_kinetic_energy(self, velocity: np.ndarray, omega: float) -&gt; float:<br>
&#9;&#9;v_squared = np.dot(velocity, velocity)<br>
&#9;&#9;return 0.5 * self.m * v_squared + 0.5 * self.I_com * omega**2<br>
<br>
&#9;def bias_wrench(self, velocity : Screw2) -&gt; Screw2:<br>
&#9;&#9;vx, vy, omega = velocity.lin[0], velocity.lin[1], velocity.ang<br>
&#9;&#9;m = self.m<br>
&#9;&#9;cx, cy = self.c<br>
<br>
&#9;&#9;Fx =  m * (omega * vy + omega**2 * cx)<br>
&#9;&#9;Fy = -m * (omega * vx) + m * (omega**2 * cy)<br>
<br>
&#9;&#9;τz = 0.0  # В 2D кориолисового момента нет<br>
<br>
&#9;&#9;return Screw2(ang=τz, lin=np.array([Fx, Fy]))<br>
<!-- END SCAT CODE -->
</body>
</html>
