"""Experimental FEM scene physics components.

This package bridges the Python optimization/FEM solver stack from
``termin.fem`` to scene components. It is intentionally separate from
``termin.physics``, which owns the C++ rigid-body runtime.
"""

from termin.physics_fem.fem_fixed_joint_component import FEMFixedJointComponent
from termin.physics_fem.fem_physics_world_component import FEMPhysicsWorldComponent
from termin.physics_fem.fem_revolute_joint_component import FEMRevoluteJointComponent
from termin.physics_fem.fem_rigid_body_component import FEMRigidBodyComponent

__all__ = [
    "FEMFixedJointComponent",
    "FEMPhysicsWorldComponent",
    "FEMRevoluteJointComponent",
    "FEMRigidBodyComponent",
]
