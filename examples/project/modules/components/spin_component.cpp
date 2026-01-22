#include "spin_component.hpp"
#include <iostream>

namespace game {

void SpinComponent::update(float dt) {
    if (!entity.valid() || !entity.transform().valid()) return;

    termin::GeneralPose3 pose = entity.transform().local_pose();
    float rad_speed = speed * 3.14159265f / 180.0f;
    auto screw = termin::Screw3{
        termin::Vec3{0.0, 0.0, rad_speed},
        termin::Vec3{0.0, 0.0, 0.0}
    }.scaled(dt);
    pose = (pose * screw.to_pose()).normalized();
    entity.transform().relocate(pose);
}

} // namespace game