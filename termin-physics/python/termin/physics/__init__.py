"""Rigid-body physics simulation bindings.

The core C++ rigid-body types (RigidBody, PhysicsWorld, Contact) are exposed
here directly. Experimental FEM scene components live in the separate
``termin.physics_fem`` package so importing or installing ``termin.physics``
does not pull the Python optimization stack.
"""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_physics")

from termin.physics._physics_native import (
    RigidBody,
    PhysicsWorld,
    Contact,
)

__all__ = [
    "RigidBody",
    "PhysicsWorld",
    "Contact",
]
