"""Модуль физической симуляции для динамики твёрдых тел (C++ backend)."""

from termin.physics._physics_native import (
    RigidBody,
    PhysicsWorld,
    Contact,
)
from termin.physics.rigid_body_component import RigidBodyComponent
from termin.physics.physics_world_component import PhysicsWorldComponent

__all__ = [
    "RigidBody",
    "PhysicsWorld",
    "Contact",
    "RigidBodyComponent",
    "PhysicsWorldComponent",
]
