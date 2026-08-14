"""Native FEM scene-control API and retired reference implementation.

Runtime component names are owned by the native ``termin_components_physics_fem``
module. The reference aliases remain available for algorithmic comparison.
"""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("nanobind", "termin_components_physics_fem")

from termin.physics_fem._components_physics_fem_native import (  # noqa: E402
    FEMArticulationComponent,
    FEMArticulationMotorComponent,
)

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
    "FEMArticulationComponent",
    "FEMArticulationMotorComponent",
    "ReferenceFEMFixedJointComponent",
    "ReferenceFEMPhysicsWorldComponent",
    "ReferenceFEMRevoluteJointComponent",
    "ReferenceFEMRigidBodyComponent",
]
