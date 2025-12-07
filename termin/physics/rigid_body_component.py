"""Компонент RigidBody для сущностей визуализации."""

from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np

from termin.visualization.core.entity import Component
from termin.physics.rigid_body import RigidBody
from termin.geombase.pose3 import Pose3

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class RigidBodyComponent(Component):
    """
    Компонент, связывающий RigidBody с Entity.

    Синхронизирует позу физического тела с трансформом сущности.
    """

    def __init__(
        self,
        mass: float = 1.0,
        is_static: bool = False,
        restitution: float = 0.3,
        friction: float = 0.5,
    ):
        super().__init__(enabled=True)
        self.mass = mass
        self.is_static = is_static
        self.restitution = restitution
        self.friction = friction

        # Будет создано в start()
        self._rigid_body: RigidBody | None = None

    @property
    def rigid_body(self) -> RigidBody | None:
        return self._rigid_body

    def start(self, scene: "Scene"):
        super().start(scene)

        if self.entity is None:
            return

        from termin.fem.inertia3d import SpatialInertia3D

        # Получаем начальную позу из трансформа сущности
        initial_pose = self.entity.transform.global_pose()

        # Определяем коллайдер из меша сущности (если есть)
        collider = self._create_collider_from_entity()

        # Вычисляем главные моменты инерции на основе типа коллайдера
        I_diag = self._compute_inertia_diag(collider)

        # Создаём пространственную инерцию с COM в начале координат
        spatial_inertia = SpatialInertia3D(
            mass=self.mass if not self.is_static else 0.0,
            I_diag=I_diag,
        )

        self._rigid_body = RigidBody(
            spatial_inertia=spatial_inertia,
            pose=initial_pose,
            collider=collider,
            is_static=self.is_static,
        )

    def _create_collider_from_entity(self):
        """Попытка создать коллайдер на основе меша сущности."""
        if self.entity is None:
            return None

        # Проверяем наличие существующего компонента коллайдера
        from termin.colliders.collider_component import ColliderComponent
        collider_comp = self.entity.get_component(ColliderComponent)
        if collider_comp is not None:
            return collider_comp.collider

        # Пробуем создать из меш-рендерера
        from termin.visualization.render.components.mesh_renderer import MeshRenderer
        mesh_renderer = self.entity.get_component(MeshRenderer)
        if mesh_renderer is not None and mesh_renderer.mesh is not None:
            # Аппроксимируем box-коллайдером по границам меша
            mesh = mesh_renderer.mesh
            if hasattr(mesh, 'get_bounds'):
                bounds = mesh.get_bounds()
                from termin.colliders.box import BoxCollider
                size = bounds.max_point - bounds.min_point
                center = (bounds.max_point + bounds.min_point) / 2
                return BoxCollider(center=center, size=size)

        # По умолчанию: единичный куб
        from termin.colliders.box import BoxCollider
        return BoxCollider(
            center=np.zeros(3, dtype=np.float32),
            size=np.ones(3, dtype=np.float32),
        )

    def _compute_inertia_diag(self, collider) -> np.ndarray:
        """Вычисление главных моментов инерции на основе формы коллайдера."""
        from termin.colliders.box import BoxCollider
        from termin.colliders.sphere import SphereCollider

        m = self.mass

        if isinstance(collider, BoxCollider):
            sx, sy, sz = collider.size
            Ixx = (m / 12.0) * (sy**2 + sz**2)
            Iyy = (m / 12.0) * (sx**2 + sz**2)
            Izz = (m / 12.0) * (sx**2 + sy**2)
            return np.array([Ixx, Iyy, Izz])

        elif isinstance(collider, SphereCollider):
            r = collider.radius
            I = (2.0 / 5.0) * m * r**2
            return np.array([I, I, I])

        else:
            # По умолчанию: инерция единичного куба
            return np.array([m / 6.0, m / 6.0, m / 6.0])

    def update(self, dt: float):
        """Синхронизация трансформа сущности из физического тела."""
        if self._rigid_body is None or self.entity is None:
            return

        # Копируем позу из физики в сущность
        self.entity.transform.relocate(self._rigid_body.pose)

    def sync_to_physics(self):
        """Синхронизация физического тела из трансформа сущности (для редактора)."""
        if self._rigid_body is None or self.entity is None:
            return

        self._rigid_body.pose = self.entity.transform.global_pose()
        # Сбрасываем скорости при телепортации
        from termin.geombase.screw import Screw3
        self._rigid_body.velocity = Screw3(
            ang=np.zeros(3, dtype=np.float64),
            lin=np.zeros(3, dtype=np.float64),
        )

    def apply_force(self, force: np.ndarray, point: np.ndarray | None = None):
        """Приложить силу к твёрдому телу."""
        if self._rigid_body is not None:
            self._rigid_body.apply_force(force, point)

    def apply_impulse(self, impulse: np.ndarray, point: np.ndarray):
        """Приложить импульс к твёрдому телу."""
        if self._rigid_body is not None:
            self._rigid_body.apply_impulse(impulse, point)
