#pragma once

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include <termin/geom/quat.hpp>
#include <termin/geom/vec3.hpp>

extern "C"
{
#include "tc_types.h"
}

namespace termin
{

    // KinematicUnitComponent - abstract base for 1-DOF kinematic components.
    //
    // Provides shared fields (axis, coordinate, origin pose) and inspect
    // registrars. Subclasses override apply() and recalculate_origin() to
    // define the specific kinematic behavior (translation for Actuator,
    // rotation for Rotator).
    //
    // The axis vector direction defines the DOF axis, and its length
    // serves as a scale factor for the coordinate.
    //
    // The origin pose is the fixed transform from the parent entity to the
    // kinematic frame. Formula: local = origin * motion(coordinate).
    class ENTITY_API KinematicUnitComponent : public CxxComponent
    {
    public:
        // DOF axis (direction + scale factor via length)
        double axis_x = 0.0;
        double axis_y = 0.0;
        double axis_z = 0.0;

        // Current coordinate (interpretation depends on subclass)
        double coordinate = 0.0;
        double min_coordinate = -100.0;
        double max_coordinate = 100.0;

        // Fixed parent-to-kinematic-frame pose. Scale belongs to the entity
        // and is never part of a kinematic coordinate transform.
        tc_vec3 origin_position = {0, 0, 0};
        tc_quat origin_rotation = {0, 0, 0, 1};

    public:
        ~KinematicUnitComponent() override = default;

        static void register_type();

        // Lifecycle
        void on_added() override;
        void deserialize_data(
            const tc_value* data,
            tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) override;

        // Axis
        void set_axis(double x, double y, double z);
        Vec3 get_axis() const
        {
            return Vec3{axis_x, axis_y, axis_z};
        }

        // Coordinate
        void set_coordinate(double value);
        double get_coordinate() const
        {
            return coordinate;
        }

        // Apply transform based on current coordinate — override in subclasses
        virtual void apply();

        // Recalculate the origin from the current entity transform without
        // changing the current coordinate or visible pose.
        virtual void recalculate_origin();

    protected:
        explicit KinematicUnitComponent(const char* type_name)
            : CxxComponent(type_name)
        {
        }

        // Get normalized axis with fallback for zero-length
        Vec3 normalized_axis(Vec3 fallback) const;

        // Helper: read current entity local rigid pose.
        bool read_entity_transform(double pos[3], double rot[4]) const;

    private:
        bool deserialized_state_ = false;
    };

} // namespace termin
