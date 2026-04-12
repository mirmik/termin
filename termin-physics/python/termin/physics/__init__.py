"""Physics simulation bindings (thin wrapper around _physics_native).

The core C++ rigid-body types (RigidBody, PhysicsWorld, Contact) are exposed
here directly. Pure-Python FEM components (FEMPhysicsWorldComponent,
FEMRigidBodyComponent, …) live as submodules and must be imported explicitly
because they depend on higher-level termin modules that may not be available
in every deployment.
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
