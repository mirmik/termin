"""Компонент PhysicsWorld для интеграции со сценой."""

from __future__ import annotations

from typing import TYPE_CHECKING, List
import numpy as np

from termin.visualization.core.entity import Component
from termin.physics.world import PhysicsWorld
from termin.physics.rigid_body_component import RigidBodyComponent

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class PhysicsWorldComponent(Component):
    """
    Компонент, управляющий физической симуляцией для сцены.

    Прикрепите к любой сущности в сцене. Он будет:
    1. Собирать все RigidBodyComponent в сцене
    2. Выполнять физическую симуляцию каждый кадр
    3. Синхронизировать трансформы обратно в сущности
    """

    def __init__(
        self,
        gravity: np.ndarray | None = None,
        iterations: int = 10,
        restitution: float = 0.3,
        friction: float = 0.5,
        ground_height: float = 0.0,
        ground_enabled: bool = True,
    ):
        super().__init__(enabled=True)

        if gravity is None:
            gravity = np.array([0, 0, -9.81], dtype=np.float64)

        self._physics_world = PhysicsWorld(
            gravity=gravity,
            iterations=iterations,
            restitution=restitution,
            friction=friction,
        )
        self._physics_world.ground_height = ground_height
        self._physics_world.ground_enabled = ground_enabled

        self._rigid_body_components: List[RigidBodyComponent] = []
        self._initialized = False

    @property
    def physics_world(self) -> PhysicsWorld:
        return self._physics_world

    def start(self, scene: "Scene"):
        super().start(scene)
        self._collect_rigid_bodies(scene)
        self._initialized = True

    def _collect_rigid_bodies(self, scene: "Scene"):
        """Найти все RigidBodyComponent в сцене и зарегистрировать их."""
        self._rigid_body_components.clear()

        for entity in scene.entities:
            self._collect_from_entity(entity)

    def _collect_from_entity(self, entity):
        """Рекурсивно собрать RigidBodyComponent из дерева сущностей."""
        rb_comp = entity.get_component(RigidBodyComponent)
        if rb_comp is not None and rb_comp.rigid_body is not None:
            self._rigid_body_components.append(rb_comp)
            self._physics_world.add_body(rb_comp.rigid_body)

        # Проверяем дочерние элементы через трансформ
        for child_transform in entity.transform.children:
            if child_transform.entity is not None:
                self._collect_from_entity(child_transform.entity)

    def add_rigid_body_component(self, rb_comp: RigidBodyComponent):
        """Динамически добавить RigidBodyComponent после инициализации."""
        if rb_comp.rigid_body is not None:
            self._rigid_body_components.append(rb_comp)
            self._physics_world.add_body(rb_comp.rigid_body)

    def remove_rigid_body_component(self, rb_comp: RigidBodyComponent):
        """Удалить RigidBodyComponent из симуляции."""
        if rb_comp in self._rigid_body_components:
            self._rigid_body_components.remove(rb_comp)
            if rb_comp.rigid_body is not None:
                self._physics_world.remove_body(rb_comp.rigid_body)

    def update(self, dt: float):
        """Шаг физики и синхронизация трансформов."""
        if not self._initialized or not self.enabled:
            return

        # Шаг физической симуляции
        self._physics_world.step(dt)

        # Синхронизация трансформов из физики в сущности
        for rb_comp in self._rigid_body_components:
            rb_comp.update(dt)
