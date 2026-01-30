#pragma once

#include "../entity/component.hpp"
#include "../entity/component_registry.hpp"
#include "../entity/entity.hpp"
#include "../geom/vec3.hpp"

namespace termin {

/**
 * ActuatorComponent - moves entity along a specified axis.
 *
 * The coordinate represents the displacement along the axis.
 * When coordinate changes, the entity moves along the axis.
 *
 * Usage:
 *   actuator.set_axis(Vec3{1, 0, 0});  // X axis
 *   actuator.set_coordinate(2.5);       // Move 2.5 units along X
 */
class ENTITY_API ActuatorComponent : public CxxComponent {
public:
    // Movement axis (normalized internally)
    double axis_x = 1.0;
    double axis_y = 0.0;
    double axis_z = 0.0;

    // Current displacement along axis
    double coordinate = 0.0;

private:
    // Base position (entity position when component was added)
    Vec3 _base_position = Vec3::zero();

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
