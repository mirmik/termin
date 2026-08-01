"""Rigid-body physics simulation bindings.

The core C++ rigid-body types (RigidBody, PhysicsWorld, Contact) are exposed
here directly. Experimental FEM scene components live in the separate
``termin.physics_fem`` package so importing or installing ``termin.physics``
does not pull the Python optimization stack.
"""

from termin_nanobind.runtime import preload_sdk_libs
from termin.geombase import SpatialInertia3

preload_sdk_libs("termin_physics")

from termin.physics._physics_native import (
    RigidBody,
    PhysicsWorld,
    Contact,
    compute_mass_properties,
)

__all__ = [
    "SpatialInertia3",
    "RigidBody",
    "PhysicsWorld",
    "Contact",
    "compute_mass_properties",
]
