#pragma once

#include "kinematic_unit_component.hpp"

namespace termin {

/**
 * ActuatorComponent - moves entity along a specified axis.
 *
 * The axis vector direction defines the movement axis, and its length
 * serves as a scale factor for the coordinate. Actual displacement
 * = axis * coordinate, composed with base pose.
 *
 * Usage:
 *   actuator.set_axis(Vec3{0.01, 0, 0});  // X axis, cm scale
 *   actuator.set_coordinate(100);           // Move 1.0 scene unit along X
 */
class ENTITY_API ActuatorComponent : public KinematicUnitComponent {
public:
    ActuatorComponent();
    ~ActuatorComponent() override = default;

    void apply() override;
    void capture_base() override;
};

REGISTER_COMPONENT(ActuatorComponent, KinematicUnitComponent);

} // namespace termin
