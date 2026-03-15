"""Модуль физической симуляции для динамики твёрдых тел."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

_dll_setup.extend_package_path(__path__, "physics")

from termin.physics._physics_native import (
    RigidBody,
    PhysicsWorld,
    Contact,
)

# FEM physics
from termin.physics.fem_physics_world_component import FEMPhysicsWorldComponent
from termin.physics.fem_rigid_body_component import FEMRigidBodyComponent
from termin.physics.fem_fixed_joint_component import FEMFixedJointComponent
from termin.physics.fem_revolute_joint_component import FEMRevoluteJointComponent

__all__ = [
    # C++ physics
    "RigidBody",
    "PhysicsWorld",
    "Contact",
    # FEM physics
    "FEMPhysicsWorldComponent",
    "FEMRigidBodyComponent",
    "FEMFixedJointComponent",
    "FEMRevoluteJointComponent",
]
