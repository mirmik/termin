"""Компонент RigidBody для сущностей визуализации (C++ backend)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
import numpy as np

from termin.visualization.core.entity import Component
from termin.geombase._geom_native import Pose3 as CppPose3, Vec3, Quat, Screw3
from termin.physics._physics_native import PhysicsWorld, RigidBody
from termin.geombase.pose3 import Pose3
from termin.geombase.general_pose3 import GeneralPose3
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class RigidBodyComponent(Component):
    """
    Компонент, связывающий RigidBody с Entity.

    Использует C++ бэкенд. Синхронизирует позу физического тела с трансформом сущности.
    """

    inspect_fields = {
        "mass": InspectField(
            path="mass",
            label="Mass",
            kind="float",
            min=0.001,
            max=10000.0,
            step=0.1,
        ),
        "is_static": InspectField(
            path="is_static",
            label="Static",
            kind="bool",
        ),
        "restitution": InspectField(
            path="restitution",
            label="Restitution",
            kind="float",
            min=0.0,
            max=1.0,
            step=0.05,
        ),
        "friction": InspectField(
            path="friction",
            label="Friction",
            kind="float",
            min=0.0,
            max=2.0,
            step=0.05,
        ),
    }

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

        # Индекс тела в C++ PhysicsWorld (-1 = не зарегистрировано)
        self._body_index: int = -1
        self._physics_world: Optional[PhysicsWorld] = None

        # Размеры коллайдера (определяются в start)
        self._half_extents: np.ndarray = np.array([0.5, 0.5, 0.5])

    def start(self, scene: "Scene"):
        super().start(scene)

        if self.entity is None:
            return

        # Определяем размеры коллайдера из меша сущности
        self._half_extents = self._compute_half_extents()

        # Ищем PhysicsWorldComponent в сцене и регистрируемся
        self._find_and_register_with_physics_world(scene)

    def _compute_half_extents(self) -> np.ndarray:
        """Вычислить half_extents из меша или коллайдера сущности."""
        if self.entity is None:
            return np.array([0.5, 0.5, 0.5])

        # Проверяем наличие существующего компонента коллайдера
        from termin.colliders.collider_component import ColliderComponent
        from termin.colliders.box import BoxCollider as PyBoxCollider
        from termin.colliders.sphere import SphereCollider as PySphereCollider

        collider_comp = self.entity.get_component(ColliderComponent)
        if collider_comp is not None:
            collider = collider_comp.collider
            if isinstance(collider, PyBoxCollider):
                return collider.size / 2.0
            elif isinstance(collider, PySphereCollider):
                r = collider.radius
                return np.array([r, r, r])

        # Пробуем создать из меш-рендерера
        from termin.visualization.render.components.mesh_renderer import MeshRenderer
        mesh_renderer = self.entity.get_component(MeshRenderer)
        if mesh_renderer is not None and mesh_renderer.mesh is not None:
            mesh = mesh_renderer.mesh
            if hasattr(mesh, 'get_bounds'):
                bounds = mesh.get_bounds()
                size = bounds.max_point - bounds.min_point
                return size / 2.0

        # По умолчанию: единичный куб
        return np.array([0.5, 0.5, 0.5])

    def _find_and_register_with_physics_world(self, scene: "Scene"):
        """Найти PhysicsWorldComponent в сцене и зарегистрироваться."""
        if self._body_index >= 0:
            # Уже зарегистрированы
            return

        from termin.physics.physics_world_component import PhysicsWorldComponent

        for entity in scene.entities:
            pw_comp = entity.get_component(PhysicsWorldComponent)
            if pw_comp is not None:
                pw_comp.add_rigid_body_component(self)
                return

    def _register_with_world(self, world: PhysicsWorld):
        """Зарегистрировать тело в C++ PhysicsWorld."""
        if self.entity is None:
            return

        self._physics_world = world

        # Получаем начальную позу
        py_pose = self.entity.transform.global_pose()
        cpp_pose = CppPose3(
            Quat(py_pose.ang[0], py_pose.ang[1], py_pose.ang[2], py_pose.ang[3]),
            Vec3(py_pose.lin[0], py_pose.lin[1], py_pose.lin[2])
        )

        # Добавляем тело в C++ мир
        sx, sy, sz = self._half_extents * 2.0  # size = 2 * half_extents
        self._body_index = world.add_box(
            sx, sy, sz,
            self.mass,
            cpp_pose,
            self.is_static
        )

    def _sync_from_physics(self):
        """Синхронизация трансформа сущности из C++ физического тела."""
        if self._body_index < 0 or self._physics_world is None or self.entity is None:
            return

        # Получаем тело из C++ мира
        cpp_body = self._physics_world.get_body(self._body_index)
        cpp_pose = cpp_body.pose

        # Конвертируем в GeneralPose3, сохраняя текущий scale
        current_scale = self.entity.transform.local_pose().scale.copy()
        general_pose = GeneralPose3(
            ang=np.array([cpp_pose.ang.x, cpp_pose.ang.y, cpp_pose.ang.z, cpp_pose.ang.w]),
            lin=np.array([cpp_pose.lin.x, cpp_pose.lin.y, cpp_pose.lin.z]),
            scale=current_scale
        )

        # Обновляем трансформ сущности
        self.entity.transform.relocate(general_pose)

    def sync_to_physics(self):
        """Синхронизация физического тела из трансформа сущности (для редактора)."""
        if self._body_index < 0 or self._physics_world is None or self.entity is None:
            return

        py_pose = self.entity.transform.global_pose()
        cpp_body = self._physics_world.get_body(self._body_index)

        # Обновляем позу
        cpp_body.pose = CppPose3(
            Quat(py_pose.ang[0], py_pose.ang[1], py_pose.ang[2], py_pose.ang[3]),
            Vec3(py_pose.lin[0], py_pose.lin[1], py_pose.lin[2])
        )

        # Сбрасываем скорости при телепортации
        cpp_body.velocity = Screw3()

    def apply_impulse(self, impulse: np.ndarray, point: np.ndarray):
        """Приложить импульс к твёрдому телу."""
        if self._body_index < 0 or self._physics_world is None:
            return

        cpp_body = self._physics_world.get_body(self._body_index)
        cpp_body.apply_impulse(
            Vec3(impulse[0], impulse[1], impulse[2]),
            Vec3(point[0], point[1], point[2])
        )

    # Legacy compatibility
    @property
    def rigid_body(self):
        """Для совместимости - возвращает None (тело теперь в C++)."""
        return None

    def update(self, dt: float):
        """Legacy - синхронизация теперь через _sync_from_physics."""
        self._sync_from_physics()
