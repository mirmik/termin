#!/usr/bin/env python3
"""
Пространственная инерция в стиле Фезерстоуна.

Инерция представлена как:
- m: масса
- I_diag: вектор главных моментов инерции (3 компоненты)
- frame: Pose3 — система координат эллипсоида инерции относительно СК тела
         (lin = положение COM, ang = ориентация главных осей)
"""

import numpy as np
from termin.geombase.pose3 import Pose3
from termin.geombase.screw import Screw3


class SpatialInertia3D:
    """
    Пространственная инерция твёрдого тела.

    Хранит:
    - m: масса
    - I_diag: главные моменты инерции (вектор из 3 компонент)
    - frame: Pose3 — СК эллипсоида инерции (lin = COM, ang = ориентация главных осей)

    Все операции (apply, solve) работают через преобразование в СК эллипсоида,
    где тензор инерции диагонален.
    """

    def __init__(
        self,
        mass: float = 0.0,
        I_diag: np.ndarray = None,
        frame: Pose3 = None,
    ):
        self.m = float(mass)

        if I_diag is None:
            self.I_diag = np.zeros(3, dtype=np.float64)
        else:
            self.I_diag = np.asarray(I_diag, dtype=np.float64).reshape(3)

        if frame is None:
            self.frame = Pose3.identity()
        else:
            self.frame = frame

    @staticmethod
    def from_matrix(mass: float, inertia: np.ndarray, com: np.ndarray = None) -> "SpatialInertia3D":
        """
        Создать SpatialInertia3D из матрицы инерции 3x3.

        Диагонализует матрицу для получения главных моментов и осей.
        """
        if com is None:
            com = np.zeros(3)

        inertia = np.asarray(inertia, dtype=np.float64).reshape(3, 3)

        # Диагонализация: I = R @ diag(eigenvalues) @ R.T
        eigenvalues, eigenvectors = np.linalg.eigh(inertia)

        # eigenvectors — столбцы, это матрица поворота
        # Убеждаемся что это правая СК (det = +1)
        if np.linalg.det(eigenvectors) < 0:
            eigenvectors[:, 0] *= -1

        # Строим кватернион из матрицы поворота
        R = eigenvectors
        trace = np.trace(R)
        if trace > 0:
            s = 0.5 / np.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (R[2, 1] - R[1, 2]) * s
            y = (R[0, 2] - R[2, 0]) * s
            z = (R[1, 0] - R[0, 1]) * s
        elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
            s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
            w = (R[2, 1] - R[1, 2]) / s
            x = 0.25 * s
            y = (R[0, 1] + R[1, 0]) / s
            z = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
            w = (R[0, 2] - R[2, 0]) / s
            x = (R[0, 1] + R[1, 0]) / s
            y = 0.25 * s
            z = (R[1, 2] + R[2, 1]) / s
        else:
            s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
            w = (R[1, 0] - R[0, 1]) / s
            x = (R[0, 2] + R[2, 0]) / s
            y = (R[1, 2] + R[2, 1]) / s
            z = 0.25 * s

        quat = np.array([x, y, z, w], dtype=np.float64)
        quat /= np.linalg.norm(quat)

        frame = Pose3(ang=quat, lin=np.asarray(com, dtype=np.float64))

        return SpatialInertia3D(mass=mass, I_diag=eigenvalues, frame=frame)

    # ----------------------------------------------------------------
    #  Свойства для совместимости
    # ----------------------------------------------------------------
    @property
    def mass(self) -> float:
        return self.m

    @property
    def c(self) -> np.ndarray:
        """Центр масс (для совместимости)."""
        return self.frame.lin

    @property
    def Ic(self) -> np.ndarray:
        """Матрица инерции 3x3 (для совместимости)."""
        R = self.frame.rotation_matrix()
        return R @ np.diag(self.I_diag) @ R.T

    # ----------------------------------------------------------------
    #  Преобразования
    # ----------------------------------------------------------------
    def rotated_by(self, pose: Pose3) -> "SpatialInertia3D":
        """
        Повернуть инерцию матрицей поворота из pose (без трансляции COM).
        """
        # Поворачиваем frame эллипсоида
        new_frame = Pose3(
            ang=(pose * Pose3(ang=self.frame.ang, lin=np.zeros(3))).ang,
            lin=pose.rotate_point(self.frame.lin),
        )
        return SpatialInertia3D(mass=self.m, I_diag=self.I_diag.copy(), frame=new_frame)

    def transform_by(self, pose: Pose3) -> "SpatialInertia3D":
        """
        Полное преобразование инерции (поворот + трансляция COM).
        """
        new_frame = pose * self.frame
        return SpatialInertia3D(mass=self.m, I_diag=self.I_diag.copy(), frame=new_frame)

    # ----------------------------------------------------------------
    #  Применение инерции: I @ twist -> momentum
    # ----------------------------------------------------------------
    def apply(self, twist: Screw3) -> Screw3:
        """
        I @ twist -> momentum (wrench-like).

        1. Переводим twist в СК эллипсоида
        2. Умножаем на диагональную инерцию
        3. Переводим обратно
        """
        # В СК эллипсоида
        t_local = twist.inverse_transform_by(self.frame)

        # h = I @ v (диагональное умножение)
        h_lin = self.m * t_local.lin
        h_ang = self.I_diag * t_local.ang

        h_local = Screw3(ang=h_ang, lin=h_lin)

        # Обратно в исходную СК
        return h_local.transform_by(self.frame)

    def __matmul__(self, twist: Screw3) -> Screw3:
        """Operator @ for I @ twist."""
        return self.apply(twist)

    # ----------------------------------------------------------------
    #  Обратное применение: I⁻¹ @ wrench -> twist
    # ----------------------------------------------------------------
    def solve(self, wrench: Screw3) -> Screw3:
        """
        I⁻¹ @ wrench -> twist.

        1. Переводим wrench в СК эллипсоида
        2. Делим на диагональную инерцию
        3. Переводим обратно
        """
        # В СК эллипсоида
        w_local = wrench.inverse_transform_by(self.frame)

        # a = I⁻¹ @ f (диагональное деление)
        a_lin = w_local.lin / self.m if self.m > 0 else np.zeros(3)
        a_ang = w_local.ang / self.I_diag

        a_local = Screw3(ang=a_ang, lin=a_lin)

        # Обратно в исходную СК
        return a_local.transform_by(self.frame)

    # ----------------------------------------------------------------
    #  Gravity wrench
    # ----------------------------------------------------------------
    def gravity_wrench(self, g_local: np.ndarray) -> Screw3:
        """
        Винт гравитации (F, τ) в локальной системе.
        g_local — вектор гравитации в СК тела.
        """
        c = self.frame.lin  # COM
        F = self.m * g_local
        τ = np.cross(c, F)
        return Screw3(ang=τ, lin=F)

    # ----------------------------------------------------------------
    #  Bias wrench
    # ----------------------------------------------------------------
    def bias_wrench(self, velocity: Screw3) -> Screw3:
        """
        Пространственный bias-винт: v ×* (I @ v).
        """
        h = self.apply(velocity)
        return velocity.cross_force(h)

    # ----------------------------------------------------------------
    #  Kinetic energy
    # ----------------------------------------------------------------
    def kinetic_energy(self, twist: Screw3) -> float:
        """
        Кинетическая энергия: 0.5 * v^T @ I @ v
        """
        h = self.apply(twist)
        return 0.5 * twist.dot(h)

    # ----------------------------------------------------------------
    #  Сложение инерций
    # ----------------------------------------------------------------
    def __add__(self, other: "SpatialInertia3D") -> "SpatialInertia3D":
        """
        Сложение двух инерций.

        Результат — новая инерция с общим COM и суммарным тензором.
        """
        if not isinstance(other, SpatialInertia3D):
            return NotImplemented

        m1, m2 = self.m, other.m
        c1, c2 = self.frame.lin, other.frame.lin

        m = m1 + m2
        if m == 0.0:
            return SpatialInertia3D(mass=0.0)

        # Новый COM
        c = (m1 * c1 + m2 * c2) / m

        # Тензоры инерции относительно нового COM (теорема Штейнера)
        d1 = c1 - c
        d2 = c2 - c

        I1 = self.Ic + m1 * (np.dot(d1, d1) * np.eye(3) - np.outer(d1, d1))
        I2 = other.Ic + m2 * (np.dot(d2, d2) * np.eye(3) - np.outer(d2, d2))

        I_total = I1 + I2

        return SpatialInertia3D.from_matrix(mass=m, inertia=I_total, com=c)
