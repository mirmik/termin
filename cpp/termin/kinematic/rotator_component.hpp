#pragma once

#include "../entity/component.hpp"
#include "../entity/component_registry.hpp"
#include "../entity/entity.hpp"
#include "../geom/vec3.hpp"
#include "../geom/quat.hpp"

namespace termin {

/**
 * RotatorComponent - rotates entity around a specified axis.
 *
 * The coordinate represents the rotation angle in radians.
 * When coordinate changes, the entity rotates around the axis.
 *
 * Usage:
 *   rotator.set_axis(Vec3{0, 0, 1});  // Z axis
 *   rotator.set_coordinate(M_PI / 2); // 90 degrees
 */
class ENTITY_API RotatorComponent : public CxxComponent {
public:
    // Rotation axis (normalized internally)
    double axis_x = 0.0;
    double axis_y = 0.0;
    double axis_z = 1.0;

    // Current rotation angle in radians
    double coordinate = 0.0;

private:
    // Base rotation (entity rotation when component was added)
    Quat _base_rotation = Quat::identity();

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

private:
    // Apply rotation based on current coordinate
    void _apply_rotation();

    // Get normalized axis
    Vec3 _normalized_axis() const;
};

REGISTER_COMPONENT(RotatorComponent, Component);

} // namespace termin
