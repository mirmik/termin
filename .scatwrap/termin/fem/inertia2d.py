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
    &quot;&quot;&quot;2D псевдо-skew: ω × r = [-ω*r_y, ω*r_x].<br>
       Здесь возвращаем 2×2 матрицу для углового ω.&quot;&quot;&quot;<br>
    return np.array([[0, -v],<br>
                     [v,  0]])<br>
<br>
class SpatialInertia2D:<br>
    def __init__(self, mass = 0.0, inertia = 0.0, com=np.zeros(2)):<br>
        &quot;&quot;&quot;<br>
        mass : масса тела<br>
        J_com : момент инерции вокруг центра масс (скаляр)<br>
        com : 2-вектор центра масс в локальной системе<br>
        &quot;&quot;&quot;<br>
        self.m = float(mass)<br>
        self.Jc = float(inertia)<br>
        self.c = np.asarray(com, float).reshape(2)<br>
<br>
    @property<br>
    def I_com(self):<br>
        return self.Jc<br>
<br>
    @property<br>
    def mass(self):<br>
        return self.m<br>
<br>
    @property<br>
    def inertia(self):<br>
        return self.Jc<br>
<br>
    @property<br>
    def center_of_mass(self):<br>
        return self.c<br>
<br>
    <br>
    def transform_by(self, pose: Pose2) -&gt; &quot;SpatialInertia2D&quot;:<br>
        &quot;&quot;&quot;<br>
        Трансформировать инерцию в новую систему координат.<br>
        В 2D момент инерции инвариантен относительно поворота.<br>
        Центр масс переводится напрямую.<br>
        &quot;&quot;&quot;<br>
        c_new = pose.transform_point(self.c)<br>
        return SpatialInertia2D(self.m, self.I_com, c_new)<br>
<br>
    # ------------------------------<br>
    #       Поворот инерции<br>
    # ------------------------------<br>
    def rotated(self, theta):<br>
        &quot;&quot;&quot;<br>
        Повернуть spatial inertia 2D на угол theta.<br>
        &quot;&quot;&quot;<br>
        R = np.array([<br>
            [np.cos(theta), -np.sin(theta)],<br>
            [np.sin(theta),  np.cos(theta)],<br>
        ])<br>
<br>
        # поворот центра масс<br>
        c_new = R @ self.c<br>
<br>
        # J переносится как скаляр (инвариант)<br>
        return SpatialInertia2D(self.m, self.Jc, c_new)<br>
<br>
    # ------------------------------<br>
    #       Spatial inertia matrix<br>
    # ------------------------------<br>
    def to_matrix_vw_order(self):<br>
        m = self.m<br>
        cx, cy = self.c<br>
        J = self.Jc<br>
<br>
        upper_left = m * np.eye(2)<br>
        lower_left = m * np.array([[-cy, cx]])<br>
        upper_right = lower_left.T<br>
        lower_right = np.array([[J + m * (cx*cx + cy*cy)]])<br>
<br>
        return np.block([<br>
            [upper_left,    upper_right],<br>
            [lower_left,    lower_right]<br>
        ])<br>
<br>
    def to_matrix_wv_order(self):<br>
        m = self.m<br>
        cx, cy = self.c<br>
        J = self.Jc<br>
<br>
        # spatial inertia в 2D (WV-порядок)<br>
        return np.array([<br>
            [J + m*(cx*cx + cy*cy),  m*cy,   -m*cx],<br>
            [m*cy,                    m,      0    ],<br>
            [-m*cx,                   0,      m    ]<br>
        ], float)<br>
<br>
    # ------------------------------<br>
    #       Gravity wrench<br>
    # ------------------------------<br>
    def gravity_wrench(self, g):<br>
        &quot;&quot;&quot;<br>
        Возвращает 3×1 винт (Fx, Fy, τz) в локальной системе!<br>
        g — вектор гравитации в ЛОКАЛЬНОЙ системе.<br>
        &quot;&quot;&quot;<br>
        m = self.m<br>
        cx, cy = self.c<br>
<br>
        F = m * g<br>
        τ = cx * F[1] - cy * F[0]<br>
<br>
        return Screw2(ang=τ, lin=F)<br>
<br>
    def __add__(self, other):<br>
        if not isinstance(other, SpatialInertia2D):<br>
            return NotImplemented<br>
<br>
        m1, m2 = self.m, other.m<br>
        c1, c2 = self.c, other.c<br>
        J1, J2 = self.Jc, other.Jc<br>
<br>
        m = m1 + m2<br>
        if m == 0.0:<br>
            # пустая инерция<br>
            return SpatialInertia2D(0.0, 0.0, np.zeros(2))<br>
<br>
        # общий центр масс<br>
        c = (m1 * c1 + m2 * c2) / m<br>
<br>
        # смещения от индивидуальных COM к общему<br>
        d1 = c1 - c<br>
        d2 = c2 - c<br>
<br>
        # параллельный перенос для моментов инерции (вокруг общего COM)<br>
        J = J1 + m1 * (d1 @ d1) + J2 + m2 * (d2 @ d2)<br>
<br>
        return SpatialInertia2D(m, J, c)<br>
<br>
    <br>
    def get_kinetic_energy(self, velocity: np.ndarray, omega: float) -&gt; float:<br>
        v_squared = np.dot(velocity, velocity)<br>
        return 0.5 * self.m * v_squared + 0.5 * self.I_com * omega**2<br>
<br>
    def bias_wrench(self, velocity : Screw2) -&gt; Screw2:<br>
        vx, vy, omega = velocity.lin[0], velocity.lin[1], velocity.ang<br>
        m = self.m<br>
        cx, cy = self.c<br>
<br>
        Fx =  m * (omega * vy + omega**2 * cx)<br>
        Fy = -m * (omega * vx) + m * (omega**2 * cy)<br>
<br>
        τz = 0.0  # В 2D кориолисового момента нет<br>
<br>
        return Screw2(ang=τz, lin=np.array([Fx, Fy]))<br>
<!-- END SCAT CODE -->
</body>
</html>
