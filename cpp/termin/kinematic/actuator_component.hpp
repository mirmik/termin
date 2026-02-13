#pragma once

#include "../entity/component.hpp"
#include "../entity/component_registry.hpp"
#include "../entity/entity.hpp"
#include "../geom/vec3.hpp"

namespace termin {

/**
 * ActuatorComponent - moves entity along a specified axis.
 *
 * The axis vector direction defines the movement axis, and its length
 * serves as a scale factor for the coordinate. Actual displacement
 * = axis * coordinate (no normalization).
 *
 * Usage:
 *   actuator.set_axis(Vec3{0.01, 0, 0});  // X axis, cm scale
 *   actuator.set_coordinate(100);           // Move 1.0 scene unit along X
 */
class ENTITY_API ActuatorComponent : public CxxComponent {
public:
    // Movement axis (direction + scale: |axis| is the coordinate scale factor)
    double axis_x = 1.0;
    double axis_y = 0.0;
    double axis_z = 0.0;

    // Current coordinate (actual displacement = axis * coordinate)
    double coordinate = 0.0;

private:
    // Base position (entity position when component was added)
    // Vec3 _base_position = Vec3::zero();

public:
    ActuatorComponent();
    ~ActuatorComponent() override = default;

    // Lifecycle
    void on_added() override;

    // Set movement axis
    void set_axis(double x, double y, double z);
    Vec3 get_axis() const { return Vec3{axis_x, axis_y, axis_z}; }

    // Set coordinate (displacement) and apply movement
    void set_coordinate(double value);
    double get_coordinate() const { return coordinate; }

private:
    // Apply movement based on current coordinate
    void _apply_movement();

    // Get normalized axis
    Vec3 _normalized_axis() const;
};

REGISTER_COMPONENT(ActuatorComponent, Component);

} // namespace termin
