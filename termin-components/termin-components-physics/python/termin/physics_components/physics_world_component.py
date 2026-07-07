"""PhysicsWorldComponent canonical import path."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, List

from termin.scene import PythonComponent
from termin.geombase._geom_native import Vec3
from termin.collision import CollisionWorld
from termin.physics._physics_native import PhysicsWorld
from termin.inspect import InspectField
from tcbase import log

if TYPE_CHECKING:
    from termin.physics_components.rigid_body_component import RigidBodyComponent


class PhysicsWorldComponent(PythonComponent):
    """
    Компонент, управляющий физической симуляцией для сцены.

    Использует C++ бэкенд для высокой производительности.
    """

    inspect_fields = {
        "gravity": InspectField(
            path="gravity",
            label="Gravity",
            kind="vec3",
            is_serializable=False,
        ),
        "iterations": InspectField(
            path="iterations",
            label="Iterations",
            kind="int",
            min=1,
            max=100,
            is_serializable=False,
        ),
        "restitution": InspectField(
            path="restitution",
            label="Restitution",
            kind="float",
            min=0.0,
            max=1.0,
            step=0.05,
            is_serializable=False,
        ),
        "friction": InspectField(
            path="friction",
            label="Friction",
            kind="float",
            min=0.0,
            max=2.0,
            step=0.05,
            is_serializable=False,
        ),
        "ground_enabled": InspectField(
            path="ground_enabled",
            label="Ground Enabled",
            kind="bool",
            is_serializable=False,
        ),
        "ground_height": InspectField(
            path="ground_height",
            label="Ground Height",
            kind="float",
            step=0.1,
            is_serializable=False,
        ),
    }

    def __init__(
        self,
        gravity: Vec3 | Sequence[float] | None = None,
        iterations: int = 10,
        restitution: float = 0.3,
        friction: float = 0.5,
        ground_height: float = 0.0,
        ground_enabled: bool = False,
    ):
        super().__init__(enabled=True)

        if gravity is None:
            gravity = Vec3(0.0, 0.0, -9.81)

        self._physics_world = PhysicsWorld()
        self._physics_world.gravity = _to_vec3(gravity)
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

    @property
    def gravity(self) -> Vec3:
        return self._physics_world.gravity.copy()

    @gravity.setter
    def gravity(self, value: Vec3 | Sequence[float]):
        self._physics_world.gravity = _to_vec3(value)

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
        scene = self.entity.scene if self.entity else None
        if not scene:
            return

        scene_collision_world = CollisionWorld.from_scene(scene)
        if scene_collision_world is None:
            log.error("PhysicsWorldComponent: no CollisionWorld on scene")
            return
        self._physics_world.set_collision_world(scene_collision_world)
        self._collect_rigid_bodies(scene)
        self._initialized = True

    def _collect_rigid_bodies(self, scene):
        self._rigid_body_components.clear()

        visited_entities = set()
        for entity in scene.get_all_entities():
            self._collect_from_entity(entity, visited_entities)

    def _collect_from_entity(self, entity, visited_entities):
        from termin.physics_components.rigid_body_component import RigidBodyComponent

        entity_id = id(entity)
        if entity_id in visited_entities:
            return
        visited_entities.add(entity_id)

        rb_comp = entity.get_component(RigidBodyComponent)
        if rb_comp is not None:
            self._rigid_body_components.append(rb_comp)
            rb_comp._register_with_world(self._physics_world)

        for child_transform in entity.transform.children:
            if child_transform.entity is not None:
                self._collect_from_entity(child_transform.entity, visited_entities)

    def add_rigid_body_component(self, rb_comp: "RigidBodyComponent"):
        if rb_comp in self._rigid_body_components:
            return
        self._rigid_body_components.append(rb_comp)
        rb_comp._register_with_world(self._physics_world)

    def remove_rigid_body_component(self, rb_comp: "RigidBodyComponent"):
        if rb_comp in self._rigid_body_components:
            self._rigid_body_components.remove(rb_comp)

    def fixed_update(self, dt: float):
        if not self._initialized or not self.enabled:
            return

        self._physics_world.step(dt)

        for rb_comp in self._rigid_body_components:
            rb_comp._sync_from_physics()


def _to_vec3(value: Vec3 | Sequence[float]) -> Vec3:
    if isinstance(value, Vec3):
        return value.copy()
    return Vec3(float(value[0]), float(value[1]), float(value[2]))
