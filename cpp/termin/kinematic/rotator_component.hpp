#pragma once

#include "kinematic_unit_component.hpp"

namespace termin {

/**
 * RotatorComponent - rotates entity around a specified axis.
 *
 * The axis vector direction defines the rotation axis, and its length
 * serves as a scale factor for the coordinate. Actual rotation angle
 * = coordinate * |axis|, composed with base pose.
 *
 * Usage:
 *   rotator.set_axis(Vec3{0, 0, M_PI/180});  // Z axis, degrees scale
 *   rotator.set_coordinate(90);                // 90 degrees
 */
class ENTITY_API RotatorComponent : public KinematicUnitComponent {
public:
    RotatorComponent();
    ~RotatorComponent() override = default;

    void apply() override;
    void capture_base() override;
};

REGISTER_COMPONENT(RotatorComponent, KinematicUnitComponent);

} // namespace termin
