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
 * KinematicUnitComponent - abstract base for 1-DOF kinematic components.
 *
 * Provides shared fields (axis, coordinate, base pose) and inspect registrars.
 * Subclasses override apply() and capture_base() to define the specific
 * kinematic behavior (translation for Actuator, rotation for Rotator).
 *
 * The axis vector direction defines the DOF axis, and its length
 * serves as a scale factor for the coordinate.
 *
 * Base pose (position + rotation + scale) defines the entity transform
 * at coordinate=0. Formula: local = base * offset(coordinate).
 */
class ENTITY_API KinematicUnitComponent : public CxxComponent {
public:
    // DOF axis (direction + scale factor via length)
    double axis_x = 0.0;
    double axis_y = 0.0;
    double axis_z = 0.0;

    // Current coordinate (interpretation depends on subclass)
    double coordinate = 0.0;

    // Base pose (GeneralPose3, set by capture_base())
    tc_vec3 base_position = {0, 0, 0};
    tc_quat base_rotation = {0, 0, 0, 1};
    tc_vec3 base_scale = {1, 1, 1};

public:
    ~KinematicUnitComponent() override = default;

    // Lifecycle
    void on_added() override;

    // Axis
    void set_axis(double x, double y, double z);
    Vec3 get_axis() const { return Vec3{axis_x, axis_y, axis_z}; }

    // Coordinate
    void set_coordinate(double value);
    double get_coordinate() const { return coordinate; }

    // Apply transform based on current coordinate — override in subclasses
    virtual void apply();

    // Capture current entity transform as base (reverse calculation) — override in subclasses
    virtual void capture_base();

protected:
    // Get normalized axis with fallback for zero-length
    Vec3 normalized_axis(Vec3 fallback) const;

    // Helper: read current entity local transform
    bool read_entity_transform(double pos[3], double rot[4], double scl[3]) const;

    // Helper: write base pose as entity local transform
    void write_base_transform(Entity& ent) const;
};

REGISTER_ABSTRACT_COMPONENT(KinematicUnitComponent, Component);

} // namespace termin
