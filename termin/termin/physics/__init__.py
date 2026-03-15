"""Модуль физической симуляции для динамики твёрдых тел."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

import os as _os
_sdk_dir = _os.path.join(_os.sep, "opt", "termin", "lib", "python", "termin", "physics")
if _os.path.isdir(_sdk_dir) and _sdk_dir not in __path__:
    __path__.append(_sdk_dir)

from termin.physics._physics_native import (
    RigidBody,
    PhysicsWorld,
    Contact,
)
from termin.physics_components import PhysicsWorldComponent, RigidBodyComponent

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
    "RigidBodyComponent",
    "PhysicsWorldComponent",
    # FEM physics
    "FEMPhysicsWorldComponent",
    "FEMRigidBodyComponent",
    "FEMFixedJointComponent",
    "FEMRevoluteJointComponent",
]
