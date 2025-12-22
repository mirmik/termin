"""Компонент PhysicsWorld для интеграции со сценой (C++ backend)."""

from __future__ import annotations

from typing import TYPE_CHECKING, List
import numpy as np

from termin.visualization.core.component import Component
from termin.geombase._geom_native import Vec3
from termin.physics._physics_native import PhysicsWorld
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.physics.rigid_body_component import RigidBodyComponent


class PhysicsWorldComponent(Component):
    """
    Компонент, управляющий физической симуляцией для сцены.

    Использует C++ бэкенд для высокой производительности.

    Прикрепите к любой сущности в сцене. Он будет:
    1. Собирать все RigidBodyComponent в сцене
    2. Выполнять физическую симуляцию каждый кадр
    3. Синхронизировать трансформы обратно в сущности
    """

    inspect_fields = {
        "gravity": InspectField(
            path="gravity",
            label="Gravity",
            kind="vec3",
            non_serializable=True,  # getter/setter работают с C++ объектом
        ),
        "iterations": InspectField(
            path="iterations",
            label="Iterations",
            kind="int",
            min=1,
            max=100,
            non_serializable=True,
        ),
        "restitution": InspectField(
            path="restitution",
            label="Restitution",
            kind="float",
            min=0.0,
            max=1.0,
            step=0.05,
            non_serializable=True,
        ),
        "friction": InspectField(
            path="friction",
            label="Friction",
            kind="float",
            min=0.0,
            max=2.0,
            step=0.05,
            non_serializable=True,
        ),
        "ground_enabled": InspectField(
            path="ground_enabled",
            label="Ground Enabled",
            kind="bool",
            non_serializable=True,
        ),
        "ground_height": InspectField(
            path="ground_height",
            label="Ground Height",
            kind="float",
            step=0.1,
            non_serializable=True,
        ),
    }

    def __init__(
        self,
        gravity: np.ndarray | None = None,
        iterations: int = 10,
        restitution: float = 0.3,
        friction: float = 0.5,
        ground_height: float = 0.0,
        ground_enabled: bool = False,
    ):
        super().__init__(enabled=True)

        if gravity is None:
            gravity = np.array([0, 0, -9.81], dtype=np.float64)

        # C++ PhysicsWorld
        self._physics_world = PhysicsWorld()
        self._physics_world.gravity = Vec3(gravity[0], gravity[1], gravity[2])
        self._physics_world.solver_iterations = iterations
        self._physics_world.restitution = restitution
        self._physics_world.friction = friction
        self._physics_world.ground_height = ground_height
        self._physics_world.ground_enabled = ground_enabled

        self._rigid_body_components: List["RigidBodyComponent"] = []
        self._initialized = False

    @property
    def physics_world(self) -> PhysicsWorld:
        return self._physics_world

    # --- Свойства-прокси для инспектора ---

    @property
    def gravity(self) -> np.ndarray:
        g = self._physics_world.gravity
        return np.array([g.x, g.y, g.z], dtype=np.float64)

    @gravity.setter
    def gravity(self, value: np.ndarray):
        self._physics_world.gravity = Vec3(value[0], value[1], value[2])

    @property
    def iterations(self) -> int:
        return self._physics_world.solver_iterations

    @iterations.setter
    def iterations(self, value: int):
        self._physics_world.solver_iterations = value

    @property
    def restitution(self) -> float:
        return self._physics_world.restitution

    @restitution.setter
    def restitution(self, value: float):
        self._physics_world.restitution = value

    @property
    def friction(self) -> float:
        return self._physics_world.friction

    @friction.setter
    def friction(self, value: float):
        self._physics_world.friction = value

    @property
    def ground_enabled(self) -> bool:
        return self._physics_world.ground_enabled

    @ground_enabled.setter
    def ground_enabled(self, value: bool):
        self._physics_world.ground_enabled = value

    @property
    def ground_height(self) -> float:
        return self._physics_world.ground_height

    @ground_height.setter
    def ground_height(self, value: float):
        self._physics_world.ground_height = value

    def start(self):
        super().start()
        scene = self.entity.scene
        # Передаём CollisionWorld из сцены в PhysicsWorld
        self._physics_world.set_collision_world(scene.collision_world)
        self._collect_rigid_bodies(scene)
        self._initialized = True

    def _collect_rigid_bodies(self, scene: "Scene"):
        """Найти все RigidBodyComponent в сцене и зарегистрировать их без дублей."""
        from termin.physics.rigid_body_component import RigidBodyComponent

        self._rigid_body_components.clear()

        visited_entities = set()
        for entity in scene.entities:
            self._collect_from_entity(entity, visited_entities)

    def _collect_from_entity(self, entity, visited_entities):
        """Рекурсивно собрать RigidBodyComponent из дерева сущностей."""
        from termin.physics.rigid_body_component import RigidBodyComponent

        entity_id = id(entity)
        if entity_id in visited_entities:
            return
        visited_entities.add(entity_id)

        rb_comp = entity.get_component(RigidBodyComponent)
        if rb_comp is not None:
            self._rigid_body_components.append(rb_comp)
            # Регистрируем тело в C++ мире
            rb_comp._register_with_world(self._physics_world)

        # Проверяем дочерние элементы через трансформ
        for child_transform in entity.transform.children:
            if child_transform.entity is not None:
                self._collect_from_entity(child_transform.entity, visited_entities)

    def add_rigid_body_component(self, rb_comp: "RigidBodyComponent"):
        """Динамически добавить RigidBodyComponent после инициализации."""
        if rb_comp in self._rigid_body_components:
            return
        self._rigid_body_components.append(rb_comp)
        rb_comp._register_with_world(self._physics_world)

    def remove_rigid_body_component(self, rb_comp: "RigidBodyComponent"):
        """Удалить RigidBodyComponent из симуляции."""
        if rb_comp in self._rigid_body_components:
            self._rigid_body_components.remove(rb_comp)
            # Note: C++ world не поддерживает удаление тел (пока)

    def fixed_update(self, dt: float):
        """Шаг физики с фиксированным dt и синхронизация трансформов."""
        if not self._initialized or not self.enabled:
            return

        # Шаг физической симуляции (C++)
        self._physics_world.step(dt)

        # Синхронизация трансформов из физики в сущности
        for rb_comp in self._rigid_body_components:
            rb_comp._sync_from_physics()
