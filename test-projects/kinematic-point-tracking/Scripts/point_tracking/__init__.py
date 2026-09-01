"""Project-local components for the kinematic point-tracking example."""

from __future__ import annotations

import math

from termin.base import log
from termin.geombase import Vec3
from termin.inspect import InspectField
from termin.kinematic import ArticulationComponent
from termin.robotics import (
    Articulation3D,
    JointLimitConstraint3D,
    JointVelocityLimitConstraint3D,
    PointVelocityTask3D,
    VelocityHqpController3D,
)
from termin.scene import Entity, PythonComponent


class PointTrackingControllerComponent(PythonComponent):
    """Calculate point-tracking velocity and explicitly advance an arm."""

    component_category = "Kinematic"
    required_components = ("ArticulationComponent",)
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
            max=20.0,
            step=0.1,
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
        self.target: Entity | None = None
        self.end_unit = 1
        self.point_local = (1.35, 0.0, 0.0)
        self.position_gain = 6.0
        self.maximum_joint_velocity = 3.5
        self._owner: ArticulationComponent | None = None
        self._articulation: Articulation3D | None = None
        self._controller: VelocityHqpController3D | None = None

    def start(self) -> None:
        entity = self.entity
        if entity is None:
            log.error("[PointTrackingController] component has no entity")
            self.enabled = False
            return

        owner = entity.get_component(ArticulationComponent)
        if owner is None:
            log.error("[PointTrackingController] ArticulationComponent is missing")
            self.enabled = False
            return
        if not owner.initialized and not owner.rebuild():
            log.error(
                "[PointTrackingController] articulation rebuild failed: "
                f"{owner.diagnostic}"
            )
            self.enabled = False
            return

        articulation = owner.articulation
        if self.end_unit < 0 or self.end_unit >= articulation.unit_count:
            log.error(
                "[PointTrackingController] end unit is outside articulation: "
                f"{self.end_unit}"
            )
            self.enabled = False
            return

        self._owner = owner
        self._articulation = articulation
        self._controller = VelocityHqpController3D(articulation)

    def update(self, dt: float) -> None:
        owner = self._owner
        articulation = self._articulation
        controller = self._controller
        target = self.target
        if owner is None or articulation is None or controller is None:
            return
        if target is None or not target.valid():
            log.error("[PointTrackingController] target entity is missing")
            self.enabled = False
            return
        if not math.isfinite(dt) or dt <= 0.0:
            return

        target_position = target.transform.global_position
        current_position = articulation.point_position(
            self.end_unit, tuple(self.point_local)
        )
        desired_velocity = (
            (target_position.x - current_position[0]) * self.position_gain,
            (target_position.y - current_position[1]) * self.position_gain,
            (target_position.z - current_position[2]) * self.position_gain,
        )
        # Priority 0 protects horizontal tracking. Priority 1 then uses only
        # the remaining null space to improve vertical tracking, so it cannot
        # trade horizontal accuracy for height. Joint limits are hard
        # constraints introduced at the highest level.
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
            PointVelocityTask3D(
                self.end_unit,
                tuple(self.point_local),
                desired_velocity,
                priority=0,
                diagonal_weight=[1.0, 1.0, 0.0],
                diagnostic_name="horizontal point tracking",
            ),
            PointVelocityTask3D(
                self.end_unit,
                tuple(self.point_local),
                desired_velocity,
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
                "[PointTrackingController] HQP solve failed: "
                f"{result.diagnostic}; task={result.failed_task_name}"
            )
            self.enabled = False
            return
        if not owner.integrate_velocity(result.generalized_velocity, dt):
            log.error(
                "[PointTrackingController] explicit integration failed: "
                f"{owner.diagnostic}"
            )
            self.enabled = False


class OrbitingTargetComponent(PythonComponent):
    """Move the target along a spatial orbit around the robot."""

    component_category = "Kinematic"
    inspect_fields = {
        "radius": InspectField(
            path="radius", label="Radius", kind="float", min=0.0, max=3.0
        ),
        "angular_speed": InspectField(
            path="angular_speed",
            label="Angular Speed",
            kind="float",
            min=-5.0,
            max=5.0,
        ),
        "vertical_amplitude": InspectField(
            path="vertical_amplitude",
            label="Vertical Amplitude",
            kind="float",
            min=0.0,
            max=2.0,
        ),
    }

    def __init__(self) -> None:
        super().__init__()
        self.radius = 0.55
        self.angular_speed = 0.55
        self.vertical_amplitude = 0.35
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


__all__ = ["OrbitingTargetComponent", "PointTrackingControllerComponent"]
