#pragma once

#include "../entity/component.hpp"
#include "../entity/component_registry.hpp"
#include "../entity/entity.hpp"
#include "../geom/vec3.hpp"
#include "../geom/quat.hpp"

extern "C" {
#include "tc_types.h"
}

namespace termin {

/**
 * RotatorComponent - rotates entity around a specified axis.
 *
 * The axis vector direction defines the rotation axis, and its length
 * serves as a scale factor for the coordinate. Actual rotation angle
 * = coordinate * |axis|.
 *
 * Usage:
 *   rotator.set_axis(Vec3{0, 0, M_PI/180});  // Z axis, degrees scale
 *   rotator.set_coordinate(90);                // 90 degrees
 */
class ENTITY_API RotatorComponent : public CxxComponent {
public:
    // Rotation axis (direction + scale: |axis| is the coordinate scale factor)
    double axis_x = 0.0;
    double axis_y = 0.0;
    double axis_z = 1.0;

    // Current coordinate (actual angle = coordinate * |axis|)
    double coordinate = 0.0;

    // Base pose (full GeneralPose3, set by capture_base())
    tc_vec3 base_position = {0, 0, 0};
    tc_quat base_rotation = {0, 0, 0, 1};
    tc_vec3 base_scale = {1, 1, 1};

public:
    RotatorComponent();
    ~RotatorComponent() override = default;

    // Lifecycle
    void on_added() override;

    // Set rotation axis
    void set_axis(double x, double y, double z);
    Vec3 get_axis() const { return Vec3{axis_x, axis_y, axis_z}; }

    // Set coordinate (rotation angle in radians) and apply rotation
    void set_coordinate(double value);
    double get_coordinate() const { return coordinate; }

    // Capture current entity transform as base (reverse calculation)
    void capture_base();

    // Apply rotation based on current coordinate
    void _apply_rotation();

private:
    // Get normalized axis
    Vec3 _normalized_axis() const;
};

REGISTER_COMPONENT(RotatorComponent, Component);

} // namespace termin
