"""Opt-in registration of the experimental FEM/QP scene components."""

from termin.physics_fem import (
    FEMFixedJointComponent,
    FEMPhysicsWorldComponent,
    FEMRevoluteJointComponent,
    FEMRigidBodyComponent,
)
from termin.scene import publish_python_components


publish_python_components(
    [
        FEMPhysicsWorldComponent,
        FEMRigidBodyComponent,
        FEMFixedJointComponent,
        FEMRevoluteJointComponent,
    ],
    owner="fem_double_pendulum",
)

