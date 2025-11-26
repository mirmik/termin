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
    &quot;&quot;&quot;3D skew matrix: v×x = skew3(v) @ x.&quot;&quot;&quot;<br>
    vx, vy, vz = v<br>
    return np.array([<br>
        [ 0,   -vz,  vy ],<br>
        [ vz,   0,  -vx ],<br>
        [-vy,  vx,   0  ],<br>
    ], float)<br>
<br>
<br>
class SpatialInertia3D:<br>
    def __init__(self, mass=0.0, inertia=None, com=np.zeros(3)):<br>
        &quot;&quot;&quot;<br>
        mass    : масса<br>
        inertia : 3×3 матрица тензора инерции в центре масс<br>
        com     : 3-вектор центра масс (в локальной системе)<br>
        &quot;&quot;&quot;<br>
        self.m = float(mass)<br>
        if inertia is None:<br>
            self.Ic = np.zeros((3,3), float)<br>
        else:<br>
            self.Ic = np.asarray(inertia, float).reshape(3,3)<br>
        self.c = np.asarray(com, float).reshape(3)<br>
<br>
    @property<br>
    def mass(self):<br>
        return self.m<br>
<br>
    @property<br>
    def inertia_matrix(self):<br>
        return self.Ic<br>
<br>
    @property<br>
    def center_of_mass(self):<br>
        return self.c<br>
<br>
    # ------------------------------------------------------------<br>
    #     transform / rotated<br>
    # ------------------------------------------------------------<br>
    def transform_by(self, pose: Pose3) -&gt; &quot;SpatialInertia3D&quot;:<br>
        &quot;&quot;&quot;<br>
        Преобразование spatial inertia в новую СК.<br>
        Как и в 2D: COM просто переносится.<br>
        Тензор инерции переносится с помощью правила для тензора.<br>
        &quot;&quot;&quot;<br>
        R = pose.rotation_matrix()<br>
        cW = pose.transform_point(self.c)<br>
<br>
        # I_com_new = R * I_com * R^T<br>
        Ic_new = R @ self.Ic @ R.T<br>
        return SpatialInertia3D(self.m, Ic_new, cW)<br>
<br>
    def rotated(self, ang):<br>
        &quot;&quot;&quot;<br>
        Повернуть spatial inertia в локале.<br>
        ang — 3-вектор, интерпретируем как ось-угол через экспоненту.<br>
        &quot;&quot;&quot;<br>
        # Pose3 умеет делать экспоненту<br>
        R = Pose3(lin=np.zeros(3), ang=ang).rotation_matrix()<br>
<br>
        c_new = R @ self.c<br>
        Ic_new = R @ self.Ic @ R.T<br>
        return SpatialInertia3D(self.m, Ic_new, c_new)<br>
<br>
    # ------------------------------------------------------------<br>
    #     Spatial inertia matrix (VW order)<br>
    # ------------------------------------------------------------<br>
    def to_matrix_vw_order(self):<br>
        &quot;&quot;&quot;<br>
        Возвращает spatial inertia в порядке:<br>
        [ v, ω ]  (первые 3 — линейные, вторые 3 — угловые).<br>
        &quot;&quot;&quot;<br>
        m = self.m<br>
        c = self.c<br>
        S = skew3(c)<br>
<br>
        upper_left  = m * np.eye(3)<br>
        upper_right = -m * S<br>
        lower_left  = m * S<br>
        lower_right = self.Ic + m * (S @ S.T)<br>
<br>
        return np.block([<br>
            [upper_left,  upper_right],<br>
            [lower_left,  lower_right]<br>
        ])<br>
<br>
    # ------------------------------------------------------------<br>
    #     Gravity wrench<br>
    # ------------------------------------------------------------<br>
    def gravity_wrench(self, g_local: np.ndarray) -&gt; Screw3:<br>
        &quot;&quot;&quot;<br>
        Возвращает винт (F, τ) в локальной системе.<br>
        g_local — гравитация в ЛОКАЛЕ.<br>
        &quot;&quot;&quot;<br>
        m = self.m<br>
        c = self.c<br>
        F = m * g_local<br>
        τ = np.cross(c, F)<br>
        return Screw3(ang=τ, lin=F)<br>
<br>
    # ------------------------------------------------------------<br>
    #     Bias wrench<br>
    # ------------------------------------------------------------<br>
    def bias_wrench(self, velocity: Screw3) -&gt; Screw3:<br>
        &quot;&quot;&quot;<br>
        Пространственный bias-винт: v ×* (I v).<br>
        Полный 3D аналог твоего 2D-кода.<br>
        &quot;&quot;&quot;<br>
        m = self.m<br>
        c = self.c<br>
        Ic = self.Ic<br>
<br>
        v_lin = velocity.lin<br>
        v_ang = velocity.ang<br>
<br>
        S = skew3(c)<br>
<br>
        # spatial inertia * v:<br>
        h_lin = m * (v_lin + np.cross(v_ang, c))<br>
        h_ang = Ic @ v_ang + m * np.cross(c, v_lin)<br>
<br>
        # теперь bias = v ×* h<br>
        # линейная часть:<br>
        b_lin = np.cross(v_ang, h_lin) + np.cross(v_lin, h_ang)*0.0  # линейная от линейной не даёт<br>
        # угловая часть:<br>
        b_ang = np.cross(v_ang, h_ang)<br>
<br>
        return Screw3(ang=b_ang, lin=b_lin)<br>
<br>
    # ------------------------------------------------------------<br>
    #     Сложение spatial inertia<br>
    # ------------------------------------------------------------<br>
    def __add__(self, other):<br>
        if not isinstance(other, SpatialInertia3D):<br>
            return NotImplemented<br>
<br>
        m1, m2 = self.m, other.m<br>
        c1, c2 = self.c, other.c<br>
        I1, I2 = self.Ic, other.Ic<br>
<br>
        m = m1 + m2<br>
        if m == 0.0:<br>
            return SpatialInertia3D(0.0, np.zeros((3,3)), np.zeros(3))<br>
<br>
        c = (m1 * c1 + m2 * c2) / m<br>
        d1 = c1 - c<br>
        d2 = c2 - c<br>
<br>
        S1 = skew3(d1)<br>
        S2 = skew3(d2)<br>
<br>
        Ic = I1 + m1 * (S1 @ S1.T) + I2 + m2 * (S2 @ S2.T)<br>
<br>
        return SpatialInertia3D(m, Ic, c)<br>
<br>
    # ------------------------------------------------------------<br>
    #     Kinetic energy<br>
    # ------------------------------------------------------------<br>
    def get_kinetic_energy(self, velocity: np.ndarray, omega: np.ndarray) -&gt; float:<br>
        &quot;&quot;&quot;<br>
        velocity — линейная скорость<br>
        omega    — угловая скорость<br>
        &quot;&quot;&quot;<br>
        v2 = np.dot(velocity, velocity)<br>
        return 0.5 * self.m * v2 + 0.5 * (omega @ (self.Ic @ omega))<br>
<!-- END SCAT CODE -->
</body>
</html>
