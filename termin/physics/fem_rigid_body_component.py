"""FEM Rigid Body Component — твёрдое тело для FEM симуляции."""

from __future__ import annotations

from typing import TYPE_CHECKING
import warnings
import numpy as np

from termin.visualization.core.component import Component
from termin.fem.multibody3d_3 import RigidBody3D
from termin.fem.inertia3d import SpatialInertia3D
from termin.geombase import Pose3
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.physics.fem_physics_world_component import FEMPhysicsWorldComponent


class FEMRigidBodyComponent(Component):
    """
    Компонент твёрдого тела для FEM симуляции.

    Оборачивает RigidBody3D из FEM solver и синхронизирует
    его позу с transform entity.
    """

    inspect_fields = {
        "mass": InspectField(
            path="mass",
            label="Mass",
            kind="float",
            min=0.001,
            step=0.1,
        ),
        "inertia_diagonal": InspectField(
            path="inertia_diagonal",
            label="Inertia (diagonal)",
            kind="vec3",
        ),
        "linear_damping": InspectField(
            path="linear_damping",
            label="Linear Damping",
            kind="float",
            min=0.0,
            step=0.01,
        ),
        "angular_damping": InspectField(
            path="angular_damping",
            label="Angular Damping",
            kind="float",
            min=0.0,
            step=0.01,
        ),
    }

    def __init__(
        self,
        mass: float = 1.0,
        inertia_diagonal: np.ndarray | None = None,
        linear_damping: float = 0.0,
        angular_damping: float = 0.0,
    ):
        super().__init__(enabled=True)

        self.mass = mass
        self.linear_damping = linear_damping
        self.angular_damping = angular_damping

        # Диагональные моменты инерции (Ixx, Iyy, Izz)
        # По умолчанию — сфера радиусом 0.5
        if inertia_diagonal is None:
            # I = 2/5 * m * r^2 для сферы
            r = 0.5
            I_sphere = 0.4 * mass * r * r
            inertia_diagonal = np.array([I_sphere, I_sphere, I_sphere])
        self.inertia_diagonal = np.asarray(inertia_diagonal, dtype=np.float64)

        self._fem_body: RigidBody3D | None = None
        self._fem_world: "FEMPhysicsWorldComponent | None" = None

    @property
    def fem_body(self) -> RigidBody3D | None:
        return self._fem_body

    def _register_with_fem_world(self, world: "FEMPhysicsWorldComponent"):
        """Зарегистрировать тело в FEM мире."""
        self._fem_world = world

        # Проверяем scale у предков
        self._validate_ancestor_scales()

        # Создать инерцию
        inertia = SpatialInertia3D(
            mass=self.mass,
            I_diag=self.inertia_diagonal,
            frame=Pose3.identity(),  # COM в центре, оси совпадают с телом
        )

        # Создать FEM тело
        self._fem_body = RigidBody3D(
            inertia=inertia,
            gravity=world.gravity,
            assembler=world.assembler,
            name=f"body_{id(self)}",
        )

        # Синхронизировать начальную позу из entity
        self._sync_to_physics()

    def _sync_to_physics(self):
        """Скопировать позу из entity в FEM тело (для редактора)."""
        if self._fem_body is None or self.entity is None:
            return

        pose = self.entity.transform.global_pose()
        self._fem_body.set_pose(Pose3(
            lin=np.asarray(pose.lin, dtype=np.float64),
            ang=np.asarray(pose.ang, dtype=np.float64),
        ))

        # Сбросить скорости
        self._fem_body.velocity_var.value[:] = 0.0

    def _sync_from_physics(self):
        """Скопировать позу из FEM тела в entity."""
        if self._fem_body is None or self.entity is None:
            return

        fem_pose = self._fem_body.pose()
        new_pose = Pose3(
            lin=fem_pose.lin,
            ang=fem_pose.ang,
        )
        self.entity.transform.relocate_global(new_pose)

    def _validate_ancestor_scales(self):
        """Проверить, что у предков нет non-identity scale."""
        if self.entity is None:
            return

        t = self.entity.transform.parent
        while t is not None:
            scale = t.local_pose().scale
            if not np.allclose(scale, [1.0, 1.0, 1.0], atol=1e-6):
                warnings.warn(
                    f"FEMRigidBodyComponent on '{self.entity.name}' has ancestor "
                    f"'{t.name}' with scale {scale}. Physics may behave incorrectly.",
                    RuntimeWarning,
                    stacklevel=3,
                )
                break
            t = t.parent

    # --- Вспомогательные фабрики для инерции ---

    @staticmethod
    def inertia_for_sphere(mass: float, radius: float) -> np.ndarray:
        """Вычислить диагональную инерцию для сплошной сферы."""
        I = 0.4 * mass * radius * radius  # 2/5 * m * r^2
        return np.array([I, I, I], dtype=np.float64)

    @staticmethod
    def inertia_for_box(mass: float, half_extents: np.ndarray) -> np.ndarray:
        """Вычислить диагональную инерцию для сплошного параллелепипеда."""
        hx, hy, hz = half_extents
        # I = 1/12 * m * (a^2 + b^2) для каждой оси
        # где a, b — полные размеры по двум другим осям
        Ixx = (1.0 / 12.0) * mass * ((2*hy)**2 + (2*hz)**2)
        Iyy = (1.0 / 12.0) * mass * ((2*hx)**2 + (2*hz)**2)
        Izz = (1.0 / 12.0) * mass * ((2*hx)**2 + (2*hy)**2)
        return np.array([Ixx, Iyy, Izz], dtype=np.float64)

    @staticmethod
    def inertia_for_cylinder(mass: float, radius: float, height: float) -> np.ndarray:
        """Вычислить диагональную инерцию для сплошного цилиндра (ось Z)."""
        # Izz = 1/2 * m * r^2
        # Ixx = Iyy = 1/12 * m * (3*r^2 + h^2)
        Izz = 0.5 * mass * radius * radius
        Ixx = (1.0 / 12.0) * mass * (3 * radius * radius + height * height)
        return np.array([Ixx, Ixx, Izz], dtype=np.float64)

    def compute_damping_dissipation(self, dt: float) -> float:
        """
        Вычислить диссипацию энергии за шаг dt.

        Демпфирование тела — сопротивление среды (воздух):
        - F_damp = -c_lin * v  → P = c_lin * |v|²
        - τ_damp = -c_rot * ω  → P = c_rot * |ω|²
        """
        if self._fem_body is None:
            return 0.0

        v = self._fem_body.velocity_var.value
        v_lin = v[0:3]
        omega = v[3:6]

        dissipation = 0.0
        dissipation += self.linear_damping * np.dot(v_lin, v_lin) * dt
        dissipation += self.angular_damping * np.dot(omega, omega) * dt

        return dissipation
