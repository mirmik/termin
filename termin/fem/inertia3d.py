#!/usr/bin/env python3

import numpy as np
from termin.geombase.pose3 import Pose3
from termin.geombase.screw import Screw3


def skew3(v):
    """3D skew matrix: v×x = skew3(v) @ x."""
    vx, vy, vz = v
    return np.array([
        [ 0,   -vz,  vy ],
        [ vz,   0,  -vx ],
        [-vy,  vx,   0  ],
    ], float)


class SpatialInertia3D:
    def __init__(self, mass=0.0, inertia=None, com=np.zeros(3)):
        """
        mass    : масса
        inertia : 3×3 матрица тензора инерции в центре масс
        com     : 3-вектор центра масс (в локальной системе)
        """
        self.m = float(mass)
        if inertia is None:
            self.Ic = np.zeros((3,3), float)
        else:
            self.Ic = np.asarray(inertia, float).reshape(3,3)
        self.c = np.asarray(com, float).reshape(3)

    @property
    def mass(self):
        return self.m

    @property
    def inertia_matrix(self):
        return self.Ic

    @property
    def center_of_mass(self):
        return self.c

    # ------------------------------------------------------------
    #     transform / rotated
    # ------------------------------------------------------------
    def transform_by(self, pose: Pose3) -> "SpatialInertia3D":
        """
        Преобразование spatial inertia в новую СК.
        Как и в 2D: COM просто переносится.
        Тензор инерции переносится с помощью правила для тензора.
        """
        R = pose.rotation_matrix()
        cW = pose.transform_point(self.c)

        # I_com_new = R * I_com * R^T
        Ic_new = R @ self.Ic @ R.T
        return SpatialInertia3D(self.m, Ic_new, cW)

    def rotated(self, ang):
        """
        Повернуть spatial inertia в локале.
        ang — 3-вектор, интерпретируем как ось-угол через экспоненту.
        """
        # Pose3 умеет делать экспоненту
        R = Pose3(lin=np.zeros(3), ang=ang).rotation_matrix()

        c_new = R @ self.c
        Ic_new = R @ self.Ic @ R.T
        return SpatialInertia3D(self.m, Ic_new, c_new)

    # ------------------------------------------------------------
    #     Spatial inertia matrix (VW order)
    # ------------------------------------------------------------
    def to_matrix_vw_order(self):
        """
        Возвращает spatial inertia в порядке:
        [ v, ω ]  (первые 3 — линейные, вторые 3 — угловые).
        """
        m = self.m
        c = self.c
        S = skew3(c)

        upper_left  = m * np.eye(3)
        upper_right = -m * S
        lower_left  = m * S
        lower_right = self.Ic + m * (S @ S.T)

        return np.block([
            [upper_left,  upper_right],
            [lower_left,  lower_right]
        ])

    # ------------------------------------------------------------
    #     Gravity wrench
    # ------------------------------------------------------------
    def gravity_wrench(self, g_local: np.ndarray) -> Screw3:
        """
        Возвращает винт (F, τ) в локальной системе.
        g_local — гравитация в ЛОКАЛЕ.
        """
        m = self.m
        c = self.c
        F = m * g_local
        τ = np.cross(c, F)
        return Screw3(ang=τ, lin=F)

    # ------------------------------------------------------------
    #     Bias wrench
    # ------------------------------------------------------------
    def bias_wrench(self, velocity: Screw3) -> Screw3:
        """
        Пространственный bias-винт: v ×* (I v).

        Формула для force cross product (twist ×* wrench):
        [ω, v] ×* [τ, f] = [ω × τ + v × f, ω × f]

        где h = I * v — пространственный импульс (wrench-like).
        """
        # h = I * v
        h = self.apply(velocity)

        # bias = v ×* h (force cross product)
        return velocity.cross_force(h)

    # ------------------------------------------------------------
    #     Сложение spatial inertia
    # ------------------------------------------------------------
    def __add__(self, other):
        if not isinstance(other, SpatialInertia3D):
            return NotImplemented

        m1, m2 = self.m, other.m
        c1, c2 = self.c, other.c
        I1, I2 = self.Ic, other.Ic

        m = m1 + m2
        if m == 0.0:
            return SpatialInertia3D(0.0, np.zeros((3,3)), np.zeros(3))

        c = (m1 * c1 + m2 * c2) / m
        d1 = c1 - c
        d2 = c2 - c

        S1 = skew3(d1)
        S2 = skew3(d2)

        Ic = I1 + m1 * (S1 @ S1.T) + I2 + m2 * (S2 @ S2.T)

        return SpatialInertia3D(m, Ic, c)

    # ------------------------------------------------------------
    #     Kinetic energy
    # ------------------------------------------------------------
    def get_kinetic_energy(self, velocity: np.ndarray, omega: np.ndarray) -> float:
        """
        velocity — линейная скорость
        omega    — угловая скорость
        """
        v2 = np.dot(velocity, velocity)
        return 0.5 * self.m * v2 + 0.5 * (omega @ (self.Ic @ omega))

    def kinetic_energy(self, twist: Screw3) -> float:
        """
        Кинетическая энергия: 0.5 * v^T * I * v
        """
        h = self.apply(twist)
        return 0.5 * twist.dot(h)

    # ------------------------------------------------------------
    #     Apply (multiply by twist -> momentum)
    # ------------------------------------------------------------
    def apply(self, twist: Screw3) -> Screw3:
        """
        Умножение spatial inertia на твист: I * v -> momentum (wrench-like).
        h = I * v, где h = [h_ang, h_lin] — пространственный импульс.

        Для body-frame инерции с COM в точке c:
        h_lin = m * (v_lin + ω × c)
        h_ang = I_c * ω + m * c × v_lin
        """
        m = self.m
        c = self.c
        Ic = self.Ic

        v_lin = twist.lin
        v_ang = twist.ang

        h_lin = m * (v_lin + np.cross(v_ang, c))
        h_ang = Ic @ v_ang + m * np.cross(c, v_lin)

        return Screw3(ang=h_ang, lin=h_lin)

    def __matmul__(self, twist: Screw3) -> Screw3:
        """Operator @ for I @ twist."""
        return self.apply(twist)

    def solve(self, wrench: Screw3) -> Screw3:
        """
        Решение I * a = f для a: a = I⁻¹ * f.
        wrench — винт сил (τ, F)
        Возвращает твист ускорения (α, a).
        """
        I_matrix = self.to_matrix_vw_order()
        f_vec = wrench.to_vw_array()
        a_vec = np.linalg.solve(I_matrix, f_vec)
        return Screw3.from_vw_array(a_vec)
