"""Компонент RigidBody для сущностей визуализации (C++ backend)."""

from __future__ import annotations

from typing import Optional
import warnings
import numpy as np

from termin.visualization.core.python_component import PythonComponent
from termin.geombase._geom_native import Pose3 as CppPose3, Vec3, Quat
from termin.physics._physics_native import PhysicsWorld, RigidBody
from termin.geombase import Pose3
from termin.geombase import GeneralPose3
from termin.editor.inspect_field import InspectField

class RigidBodyComponent(PythonComponent):
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

    def start(self):
        super().start()

        if self.entity is None:
            return

        # Проверяем scale у предков
        self._validate_ancestor_scales()

        # Определяем размеры коллайдера из меша сущности
        self._half_extents = self._compute_half_extents()

        # Ищем PhysicsWorldComponent в сцене и регистрируемся
        scene = self.entity.scene if self.entity else None
        if scene:
            self._find_and_register_with_physics_world(scene)

    def _validate_ancestor_scales(self):
        """Проверить, что у предков нет non-identity scale."""
        if self.entity is None:
            return

        t = self.entity.transform.parent
        while t is not None:
            scale = t.local_pose().scale
            if not np.allclose(scale, [1.0, 1.0, 1.0], atol=1e-6):
                warnings.warn(
                    f"RigidBodyComponent on '{self.entity.name}' has ancestor "
                    f"'{t.name}' with scale {scale}. Physics may behave incorrectly.",
                    RuntimeWarning,
                    stacklevel=3,
                )
                break
            t = t.parent

    def _compute_half_extents(self) -> np.ndarray:
        """Вычислить half_extents из меша или коллайдера сущности."""
        if self.entity is None:
            return np.array([0.5, 0.5, 0.5])

        # Получаем global scale
        global_scale = np.asarray(self.entity.transform.global_pose().scale)

        # Проверяем наличие существующего компонента коллайдера
        from termin.colliders.collider_component import ColliderComponent
        from termin.colliders import BoxCollider, SphereCollider

        collider_comp = self.entity.get_component(ColliderComponent)
        if collider_comp is not None:
            collider = collider_comp.collider
            if isinstance(collider, BoxCollider):
                hs = collider.half_size
                return np.array([hs.x, hs.y, hs.z]) * global_scale
            elif isinstance(collider, SphereCollider):
                r = collider.radius
                # Для сферы берём максимальный scale
                max_scale = np.max(global_scale)
                return np.array([r, r, r]) * max_scale

        # Пробуем создать из меш-рендерера
        from termin.visualization.render.components.mesh_renderer import MeshRenderer
        mesh_renderer = self.entity.get_component(MeshRenderer)
        if mesh_renderer is not None and mesh_renderer.mesh is not None:
            mesh = mesh_renderer.mesh
            if hasattr(mesh, 'get_bounds'):
                bounds = mesh.get_bounds()
                size = bounds.max_point - bounds.min_point
                return (size / 2.0) * global_scale

        # По умолчанию: единичный куб
        return np.array([0.5, 0.5, 0.5]) * global_scale

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

        if self._body_index >= 0 and self._physics_world is world:
            return

        self._physics_world = world

        # Получаем начальную позу
        py_pose = self.entity.transform.global_pose()
        cpp_pose = CppPose3(
            Quat(py_pose.ang[0], py_pose.ang[1], py_pose.ang[2], py_pose.ang[3]),
            Vec3(py_pose.lin[0], py_pose.lin[1], py_pose.lin[2])
        )

        # Создаём RigidBody
        from termin.physics._physics_native import RigidBody
        sx, sy, sz = self._half_extents * 2.0
        body = RigidBody.create_box(sx, sy, sz, self.mass, cpp_pose, self.is_static)
        self._body_index = world.add_body(body)

        # Связываем с существующим ColliderComponent (если есть)
        from termin.colliders.collider_component import ColliderComponent
        collider_comp = self.entity.get_component(ColliderComponent)
        if collider_comp is not None and collider_comp.attached is not None:
            world.register_collider(self._body_index, collider_comp.attached)

    def _sync_from_physics(self):
        """Синхронизация трансформа сущности из C++ физического тела."""
        if self._body_index < 0 or self._physics_world is None or self.entity is None:
            return

        # Получаем тело из C++ мира
        cpp_body = self._physics_world.get_body(self._body_index)
        cpp_pose = cpp_body.pose

        # Конвертируем в GeneralPose3, сохраняя текущий global scale
        current_global_scale = self.entity.transform.global_pose().scale.copy()
        global_pose = GeneralPose3(
            ang=np.array([cpp_pose.ang.x, cpp_pose.ang.y, cpp_pose.ang.z, cpp_pose.ang.w]),
            lin=np.array([cpp_pose.lin.x, cpp_pose.lin.y, cpp_pose.lin.z]),
            scale=current_global_scale
        )

        # Обновляем трансформ сущности (relocate_global пересчитает local pose)
        self.entity.transform.relocate_global(global_pose)

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
        cpp_body.linear_velocity = Vec3(0, 0, 0)
        cpp_body.angular_velocity = Vec3(0, 0, 0)

    def apply_impulse(self, impulse: np.ndarray, point: Optional[np.ndarray] = None):
        """Приложить импульс к твёрдому телу.

        Args:
            impulse: Вектор импульса (3,)
            point: Точка приложения в мировых координатах. Если None, импульс к центру масс.
        """
        if self._body_index < 0 or self._physics_world is None:
            return

        cpp_body = self._physics_world.get_body(self._body_index)
        impulse_vec = Vec3(float(impulse[0]), float(impulse[1]), float(impulse[2]))

        if point is not None:
            cpp_body.apply_impulse_at_point(
                impulse_vec,
                Vec3(float(point[0]), float(point[1]), float(point[2]))
            )
        else:
            cpp_body.apply_impulse(impulse_vec)

    # Legacy compatibility
    @property
    def rigid_body(self):
        """Для совместимости - возвращает None (тело теперь в C++)."""
        return None

    def update(self, dt: float):
        """Legacy - синхронизация теперь через _sync_from_physics."""
        self._sync_from_physics()
