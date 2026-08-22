#pragma once

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include <termin/geom/quat.hpp>
#include <termin/geom/spatial_inertia3.hpp>
#include <termin/geom/vec3.hpp>

extern "C" {
#include "tc_types.h"
}

namespace termin {

    // KinematicUnitComponent - abstract base for 1-DOF kinematic components.
    //
    // Provides shared fields (axis, coordinate, origin pose) and inspect
    // registrars. Subclasses override apply() and recalculate_origin() to
    // define the specific kinematic behavior (translation for Actuator,
    // rotation for Rotator).
    //
    // The axis is always unit length. Coordinate scale is stored separately,
    // so geometry never has to infer physical units from a direction vector.
    //
    // The origin pose is the fixed transform from the parent entity to the
    // kinematic frame. Formula: local = origin * motion(coordinate).
    class ENTITY_API KinematicUnitComponent : public CxxComponent {
    public:
        // Current coordinate (interpretation depends on subclass)
        double coordinate = 0.0;
        double min_coordinate = -100.0;
        double max_coordinate = 100.0;

        // Fixed parent-to-kinematic-frame pose. Scale belongs to the entity
        // and is never part of a kinematic coordinate transform.
        Vec3 origin_position = {0, 0, 0};
        Quat origin_rotation = {0, 0, 0, 1};

        // Spatial inertia rigidly attached to this unit's moving output frame.
        // These are model data, not a separate body/link object.
        double mass = 1.0;
        Vec3 inertia_diagonal = {0.1, 0.1, 0.1};
        Vec3 center_of_mass = {0.0, 0.0, 0.0};

    public:
        ~KinematicUnitComponent() override = default;

        static void register_type();

        // Lifecycle
        void on_added() override;
        void deserialize_data(const tc_value* data, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) override;

        // Axis
        void set_axis(const Vec3& axis);
        [[nodiscard]] Vec3 get_axis() const noexcept;

        // Physical displacement per authored coordinate unit. Rotators use
        // radians per unit; actuators use metres per unit.
        void set_coordinate_scale(double value);
        [[nodiscard]] double get_coordinate_scale() const noexcept;
        [[nodiscard]] double physical_coordinate() const noexcept;
        [[nodiscard]] SpatialInertia3 spatial_inertia() const noexcept;

        // Coordinate
        void set_coordinate(double value);
        double get_coordinate() const {
            return coordinate;
        }

        // Apply transform based on current coordinate — override in subclasses
        virtual void apply();

        // Recalculate the origin from the current entity transform without
        // changing the current coordinate or visible pose.
        virtual void recalculate_origin();

    protected:
        KinematicUnitComponent(const char* type_name, Vec3 default_axis, double default_coordinate_scale);

    private:
        Vec3 axis_ = Vec3{0.0, 0.0, 1.0};
        double coordinate_scale_ = 1.0;
        bool deserialized_state_ = false;
    };

} // namespace termin
