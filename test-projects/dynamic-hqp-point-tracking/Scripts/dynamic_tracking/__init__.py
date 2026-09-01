"""Dynamic inverse-HQP point tracking example components."""

from __future__ import annotations

import math

from termin.base import log
from termin.geombase import Vec3
from termin.inspect import InspectField
from termin.physics_fem import FEMArticulationComponent
from termin.robotics import (
    Articulation3D,
    InverseDynamicsHqpController3D,
    JointLimitConstraint3D,
    JointVelocityLimitConstraint3D,
    PointAccelerationTask3D,
)
from termin.scene import (
    FIXED_UPDATE_PRIORITY_CONTROL,
    Entity,
    PythonComponent,
)


class DynamicPointTrackingControllerComponent(PythonComponent):
    """Calculate bounded joint efforts; FEM remains the only integrator."""

    component_category = "Robotics"
    required_components = (
        "ArticulationComponent",
        "FEMArticulationComponent",
    )
    inspect_fields = {
        "target": InspectField(path="target", label="Target", kind="entity"),
        "end_unit": InspectField(
            path="end_unit", label="End Unit", kind="int", min=0, max=64
        ),
        "point_local": InspectField(
            path="point_local", label="Point Local", kind="vec3"
        ),
        "position_gain": InspectField(
            path="position_gain",
            label="Position Gain",
            kind="float",
            min=0.0,
            max=100.0,
            step=0.5,
        ),
        "velocity_gain": InspectField(
            path="velocity_gain",
            label="Velocity Gain",
            kind="float",
            min=0.0,
            max=50.0,
            step=0.25,
        ),
        "maximum_joint_velocity": InspectField(
            path="maximum_joint_velocity",
            label="Maximum Joint Velocity",
            kind="float",
            min=0.01,
            max=20.0,
            step=0.1,
        ),
    }

    def __init__(self) -> None:
        super().__init__()
        self.fixed_update_priority = FIXED_UPDATE_PRIORITY_CONTROL
        self.target: Entity | None = None
        self.end_unit = 2
        self.point_local = (1.35, 0.0, 0.0)
        self.position_gain = 35.0
        self.velocity_gain = 12.0
        self.maximum_joint_velocity = 4.0
        self._plant: FEMArticulationComponent | None = None
        self._articulation: Articulation3D | None = None
        self._controller: InverseDynamicsHqpController3D | None = None

    def start(self) -> None:
        entity = self.entity
        if entity is None:
            log.error("[DynamicPointTrackingController] component has no entity")
            self.enabled = False
            return
        self._plant = entity.get_component(FEMArticulationComponent)
        if self._plant is None:
            log.error(
                "[DynamicPointTrackingController] FEMArticulationComponent "
                "is missing"
            )
            self.enabled = False

    def _initialize_controller(self) -> bool:
        plant = self._plant
        if plant is None or not plant.initialized:
            log.error(
                "[DynamicPointTrackingController] physical articulation "
                "is not initialized"
            )
            return False
        articulation = plant.articulation
        if self.end_unit < 0 or self.end_unit >= articulation.unit_count:
            log.error(
                "[DynamicPointTrackingController] end unit is outside "
                f"articulation: {self.end_unit}"
            )
            return False
        dofs = plant.actuator_dof_indices
        limits = plant.actuator_effort_limits
        if not dofs or len(dofs) != len(limits):
            log.error(
                "[DynamicPointTrackingController] articulation has no valid "
                "motor model"
            )
            return False
        self._articulation = articulation
        self._controller = InverseDynamicsHqpController3D(
            articulation, dofs, limits, plant.gravity_world
        )
        return True

    def fixed_update(self, dt: float) -> None:
        if not math.isfinite(dt) or dt <= 0.0:
            return
        if self._controller is None and not self._initialize_controller():
            self.enabled = False
            return
        plant = self._plant
        articulation = self._articulation
        controller = self._controller
        target = self.target
        if plant is None or articulation is None or controller is None:
            return
        if target is None or not target.valid():
            log.error("[DynamicPointTrackingController] target entity is missing")
            self.enabled = False
            return

        target_position = target.transform.global_position
        target_position_world = (
            target_position.x,
            target_position.y,
            target_position.z,
        )
        # Effort bounds and unactuated dynamics are hard controller
        # constraints. These explicit tasks add a genuine lexicographic
        # hierarchy: vertical tracking may use the null space left by the
        # protected horizontal objective, but may never degrade it.
        tasks = [
            JointLimitConstraint3D(
                priority=0, diagnostic_name="joint position limits"
            ),
            JointVelocityLimitConstraint3D(
                [],
                [-self.maximum_joint_velocity] * articulation.unit_count,
                [self.maximum_joint_velocity] * articulation.unit_count,
                priority=0,
                diagnostic_name="joint velocity limits",
            ),
            PointAccelerationTask3D(
                self.end_unit,
                tuple(self.point_local),
                target_position_world,
                position_gain=self.position_gain,
                velocity_gain=self.velocity_gain,
                priority=0,
                diagonal_weight=[1.0, 1.0, 0.0],
                diagnostic_name="horizontal point tracking",
            ),
            PointAccelerationTask3D(
                self.end_unit,
                tuple(self.point_local),
                target_position_world,
                position_gain=self.position_gain,
                velocity_gain=self.velocity_gain,
                priority=1,
                diagonal_weight=[0.0, 0.0, 1.0],
                diagnostic_name="vertical point tracking",
            ),
        ]
        result = controller.solve(
            tasks,
            time_step=dt,
        )
        if not result.ok:
            log.error(
                "[DynamicPointTrackingController] HQP solve failed: "
                f"{result.diagnostic}; task={result.failed_task_name}"
            )
            self.enabled = False
            return
        if not plant.apply_inverse_dynamics_control(result):
            log.error(
                "[DynamicPointTrackingController] motor adapter rejected "
                "the HQP result"
            )
            self.enabled = False


class OrbitingTargetComponent(PythonComponent):
    """Move the target through a slow spatial orbit."""

    component_category = "Robotics"

    def __init__(self) -> None:
        super().__init__()
        self.radius = 0.8
        self.angular_speed = 0.8
        self.vertical_amplitude = 0.3
        self._time = 0.0
        self._center = Vec3(0.0, 0.0, 0.0)

    def start(self) -> None:
        entity = self.entity
        if entity is None:
            log.error("[OrbitingTarget] component has no entity")
            self.enabled = False
            return
        position = entity.transform.global_position
        self._center = Vec3(position.x, position.y, position.z)

    def update(self, dt: float) -> None:
        entity = self.entity
        if entity is None or not math.isfinite(dt) or dt <= 0.0:
            return
        self._time += dt
        phase = self._time * self.angular_speed
        entity.transform.set_global_position(
            Vec3(
                self._center.x + self.radius * math.cos(phase),
                self._center.y + self.radius * math.sin(phase),
                self._center.z
                + self.vertical_amplitude * math.sin(phase * 1.7),
            )
        )


__all__ = ["DynamicPointTrackingControllerComponent", "OrbitingTargetComponent"]
