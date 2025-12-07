"""Твёрдое тело для физической симуляции (spatial algebra в стиле Фезерстоуна)."""

from __future__ import annotations

import numpy as np
from termin.geombase.pose3 import Pose3
from termin.geombase.screw import Screw3
from termin.fem.inertia3d import SpatialInertia3D
from termin.colliders.collider import Collider


class RigidBody:
    """
    Твёрдое тело в формализме spatial algebra (нотация Фезерстоуна).

    Состояние:
    - pose: Pose3 — система координат тела относительно мира (X_WB)
    - velocity: Screw3 — пространственная скорость в МИРОВОЙ СК (ang=ω, lin=v)

    Динамика:
    - spatial_inertia: SpatialInertia3D — в системе координат тела
    - wrench: Screw3 — накопленный внешний винт сил в мировой СК

    Уравнение движения (в СК тела):
        I * a = f - v ×* (I * v)

    Где v ×* h — пространственное силовое скрещивание (bias/кориолисов член).
    """

    def __init__(
        self,
        spatial_inertia: SpatialInertia3D | None = None,
        pose: Pose3 | None = None,
        collider: Collider | None = None,
        is_static: bool = False,
    ):
        # Пространственная инерция в СК тела (COM в начале координат по умолчанию)
        if spatial_inertia is None:
            spatial_inertia = SpatialInertia3D(mass=1.0, inertia=np.eye(3) / 6.0)
        self.spatial_inertia = spatial_inertia

        # Поза: СК тела в мире
        self.pose = pose if pose is not None else Pose3.identity()

        # Скорость: пространственный твист в МИРОВОЙ СК
        self.velocity = Screw3.zero()

        # Накопленный внешний винт сил в МИРОВОЙ СК
        self.wrench = Screw3.zero()

        # Коллайдер (в СК тела)
        self.collider = collider

        # Статические тела не двигаются
        self.is_static = is_static

    # ----------------------------------------------------------------
    #  Вспомогательные свойства (для совместимости)
    # ----------------------------------------------------------------
    @property
    def mass(self) -> float:
        return self.spatial_inertia.m

    @property
    def inv_mass(self) -> float:
        return 0.0 if self.is_static or self.mass <= 0 else 1.0 / self.mass

    @property
    def position(self) -> np.ndarray:
        """Позиция (начало СК тела) в мировой СК."""
        return self.pose.lin

    @position.setter
    def position(self, p: np.ndarray):
        self.pose = Pose3(ang=self.pose.ang.copy(), lin=np.asarray(p, dtype=np.float64))

    @property
    def rotation(self) -> np.ndarray:
        """Матрица поворота (из СК тела в мир)."""
        return self.pose.rotation_matrix()

    @property
    def omega(self) -> np.ndarray:
        """Угловая скорость в мировой СК."""
        return self.velocity.ang

    @property
    def linear_velocity(self) -> np.ndarray:
        """Линейная скорость в мировой СК."""
        return self.velocity.lin

    # ----------------------------------------------------------------
    #  Пространственная инерция в мировой СК
    # ----------------------------------------------------------------
    def world_inertia(self) -> SpatialInertia3D:
        """Пространственная инерция, преобразованная в мировую СК."""
        return self.spatial_inertia.transform_by(self.pose)

    def world_inertia_inv(self) -> np.ndarray:
        """Обратный тензор инерции 3x3 в мировой СК (для импульсов)."""
        R = self.rotation
        Ic_inv = np.linalg.inv(self.spatial_inertia.Ic) if self.mass > 0 else np.zeros((3, 3))
        return R @ Ic_inv @ R.T

    # ----------------------------------------------------------------
    #  Приложение сил и винтов
    # ----------------------------------------------------------------
    def apply_wrench(self, w: Screw3):
        """Приложить винт сил в мировой СК."""
        self.wrench = self.wrench + w

    def apply_force(self, force: np.ndarray, point: np.ndarray | None = None):
        """
        Приложить силу в точке (мировые координаты).
        Если point=None, прикладывается в начале СК тела (без момента).
        """
        if point is None:
            self.wrench = self.wrench + Screw3(ang=np.zeros(3), lin=force)
        else:
            r = point - self.position
            self.wrench = self.wrench + Screw3(ang=np.cross(r, force), lin=force)

    def apply_impulse(self, impulse: np.ndarray, point: np.ndarray):
        """
        Приложить импульс в точке. Меняет скорость напрямую.

        Δv = I⁻¹ · J, где J — пространственный импульс (wrench).
        """
        if self.is_static:
            return

        # Строим пространственный импульс в мировой СК
        # r измеряется относительно позиции тела (начала СК тела)
        r = point - self.position
        J = Screw3(ang=np.cross(r, impulse), lin=impulse)

        # Инерция повёрнутая в мировую СК (без трансляции COM)
        I_world = self.spatial_inertia.rotated_by(self.pose)

        # Δv = I⁻¹ · J
        dv = I_world.solve(J)

        self.velocity = self.velocity + dv

    # ----------------------------------------------------------------
    #  Кинематика
    # ----------------------------------------------------------------
    def point_velocity(self, point: np.ndarray) -> np.ndarray:
        """Скорость точки, закреплённой на теле (мировые координаты)."""
        r = point - self.position
        return self.velocity.lin + np.cross(self.velocity.ang, r)

    # ----------------------------------------------------------------
    #  Интегрирование (в стиле Фезерстоуна)
    # ----------------------------------------------------------------
    def integrate_forces(self, dt: float, gravity: np.ndarray):
        """
        Интегрирование сил для обновления скорости.

        Уравнение движения в СК тела:
            I * a = f_ext + f_gravity - v ×* (I * v)

        Где v ×* h — пространственное силовое скрещивание (bias/кориолисов член).
        """
        if self.is_static:
            self.wrench = Screw3.zero()
            return

        I = self.spatial_inertia

        # Всё в СК тела
        v_body = self.velocity.inverse_transform_by(self.pose)
        g_body = self.pose.inverse_transform_vector(gravity)
        f_ext_body = self.wrench.inverse_transform_by(self.pose)

        # Суммарный винт: внешний + гравитация - bias
        f_total = f_ext_body + I.gravity_wrench(g_body) - I.bias_wrench(v_body)

        # Ускорение: a = I⁻¹ * f
        a_body = I.solve(f_total)

        # В мировую СК и обновляем скорость
        self.velocity = self.velocity + a_body.transform_by(self.pose) * dt
        self.wrench = Screw3.zero()

    def integrate_positions(self, dt: float):
        """
        Интегрирование скорости для обновления позы.

        Скорость в СК тела, композиция справа:
            pose_new = pose_old * exp(v_body * dt)
        """
        if self.is_static:
            return

        # Переводим скорость из мировой СК в СК тела
        v_body = self.velocity.inverse_transform_by(self.pose)

        delta_pose = (v_body * dt).to_pose()

        # Стандартная композиция SE(3): pose * delta
        self.pose = (self.pose * delta_pose).normalized()

    def world_collider(self) -> Collider | None:
        """Коллайдер, преобразованный в мировую СК."""
        if self.collider is None:
            return None
        return self.collider.transform_by(self.pose)

    # ----------------------------------------------------------------
    #  Фабричные методы
    # ----------------------------------------------------------------
    @staticmethod
    def create_box(
        size: np.ndarray | tuple = (1, 1, 1),
        mass: float = 1.0,
        pose: Pose3 | None = None,
        is_static: bool = False,
    ) -> RigidBody:
        """Создать кубоид с правильной пространственной инерцией."""
        from termin.colliders.box import BoxCollider

        size = np.asarray(size, dtype=np.float64)
        sx, sy, sz = size

        # Тензор инерции кубоида (относительно центра масс)
        Ixx = (mass / 12.0) * (sy**2 + sz**2)
        Iyy = (mass / 12.0) * (sx**2 + sz**2)
        Izz = (mass / 12.0) * (sx**2 + sy**2)
        inertia = np.diag([Ixx, Iyy, Izz])

        # COM в начале СК тела
        spatial_inertia = SpatialInertia3D(
            mass=mass,
            inertia=inertia,
            com=np.zeros(3),
        )

        collider = BoxCollider(
            center=np.zeros(3, dtype=np.float32),
            size=size.astype(np.float32),
        )

        return RigidBody(
            spatial_inertia=spatial_inertia,
            pose=pose,
            collider=collider,
            is_static=is_static,
        )

    @staticmethod
    def create_sphere(
        radius: float = 0.5,
        mass: float = 1.0,
        pose: Pose3 | None = None,
        is_static: bool = False,
    ) -> RigidBody:
        """Создать сферу с правильной пространственной инерцией."""
        from termin.colliders.sphere import SphereCollider

        # Инерция сферы: I = (2/5) * m * r²
        I = (2.0 / 5.0) * mass * radius**2
        inertia = np.diag([I, I, I])

        spatial_inertia = SpatialInertia3D(
            mass=mass,
            inertia=inertia,
            com=np.zeros(3),
        )

        collider = SphereCollider(
            center=np.zeros(3, dtype=np.float32),
            radius=radius,
        )

        return RigidBody(
            spatial_inertia=spatial_inertia,
            pose=pose,
            collider=collider,
            is_static=is_static,
        )

    @staticmethod
    def create_static_ground(
        size: tuple = (100, 100, 1),
        height: float = 0.0,
    ) -> RigidBody:
        """Создать статическую плоскость земли (большой плоский кубоид)."""
        pose = Pose3.identity().with_translation(np.array([0, 0, height - size[2] / 2]))

        return RigidBody.create_box(
            size=size,
            mass=0.0,
            pose=pose,
            is_static=True,
        )
