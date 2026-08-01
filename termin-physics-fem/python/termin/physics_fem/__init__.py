"""Reference implementation of the retired Python FEM scene bridge.

Runtime component names are owned by the native ``termin_components_physics_fem``
module. These aliases remain available for algorithmic comparison and tests;
they must not be published into the runtime component registry.
"""

from termin.physics_fem.fem_fixed_joint_component import (
    FEMFixedJointComponent as ReferenceFEMFixedJointComponent,
)
from termin.physics_fem.fem_physics_world_component import (
    FEMPhysicsWorldComponent as ReferenceFEMPhysicsWorldComponent,
)
from termin.physics_fem.fem_revolute_joint_component import (
    FEMRevoluteJointComponent as ReferenceFEMRevoluteJointComponent,
)
from termin.physics_fem.fem_rigid_body_component import (
    FEMRigidBodyComponent as ReferenceFEMRigidBodyComponent,
)

__all__ = [
    "ReferenceFEMFixedJointComponent",
    "ReferenceFEMPhysicsWorldComponent",
    "ReferenceFEMRevoluteJointComponent",
    "ReferenceFEMRigidBodyComponent",
]
