#pragma once

#include <components/kinematic_unit_component.hpp>

namespace termin {

    // ActuatorComponent - moves entity along a specified axis.
    //
    // The axis is a unit direction. Actual displacement in metres is
    // axis * coordinate * coordinate_scale, composed with the origin pose.
    //
    // Usage:
    //   actuator.set_axis({1, 0, 0});
    //   actuator.set_coordinate_scale(0.01); // coordinate is centimetres
    //   actuator.set_coordinate(100);       // Move 1 metre along X
    class ENTITY_API ActuatorComponent : public KinematicUnitComponent {
    public:
        ActuatorComponent();
        ~ActuatorComponent() override = default;

        static void register_type();

        void apply() override;
        void recalculate_origin() override;
    };

} // namespace termin
