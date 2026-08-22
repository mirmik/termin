#pragma once

#include <components/kinematic_unit_component.hpp>

namespace termin {

    // RotatorComponent - rotates entity around a specified axis.
    //
    // The axis is a unit direction. Actual rotation angle in radians is
    // coordinate * coordinate_scale, composed with the origin pose.
    //
    // Usage:
    //   rotator.set_axis({0, 0, 1});
    //   rotator.set_coordinate_scale(M_PI / 180.0);
    //   rotator.set_coordinate(90);
    class ENTITY_API RotatorComponent : public KinematicUnitComponent {
    public:
        RotatorComponent();
        ~RotatorComponent() override = default;

        static void register_type();

        void apply() override;
        void recalculate_origin() override;
    };

} // namespace termin
