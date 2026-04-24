"""Kinematics and transforms.

Provides:
- Transforms (Transform, Transform3)
- Kinematic transforms (Rotator3, Actuator3)
- Kinematic chains (KinematicChain3)
- Kinematic components (KinematicUnitComponent, ActuatorComponent, RotatorComponent)
"""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("nanobind", "termin_components_kinematic")

from termin.kinematic.transform import Transform, Transform3
from termin.kinematic.general_transform import GeneralTransform3
from termin.kinematic.kinematic import (
    KinematicTransform3,
    KinematicTransform3OneScrew,
    Rotator3,
    Actuator3,
)
from termin.kinematic.kinchain import KinematicChain3
# conditions submodule depends on termin.linalg (main termin). Users who need
# it should import it explicitly: from termin.kinematic.conditions import ...
from termin.kinematic.kinematic_components import (
    KinematicUnitComponent,
    ActuatorComponent,
    RotatorComponent,
)

__all__ = [
    "Transform",
    "Transform3",
    "GeneralTransform3",
    "KinematicTransform3",
    "KinematicTransform3OneScrew",
    "Rotator3",
    "Actuator3",
    "KinematicChain3",
    "KinematicUnitComponent",
    "ActuatorComponent",
    "RotatorComponent",
]
