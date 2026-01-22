#include "spin_component.hpp"
#include <iostream>

namespace game {

void SpinComponent::update(float dt) {
    printf("[SpinComponent::update] dt=%f, speed=%f\n", dt, speed);
    if (!entity.valid() || !entity.transform().valid()) return;

    termin::GeneralPose3 pose = entity.transform().local_pose();
    printf("[SpinComponent::update] pose before: quat=(%f, %f, %f, %f)\n",
           pose.ang.x, pose.ang.y, pose.ang.z, pose.ang.w);
    float rad_speed = speed * 3.14159265f / 180.0f;
    auto screw = termin::Screw3{
        termin::Vec3{0.0, 0.0, rad_speed},
        termin::Vec3{0.0, 0.0, 0.0}
    }.scaled(dt);
    pose = (pose * screw.to_pose()).normalized();
    printf("[SpinComponent::update] pose after: quat=(%f, %f, %f, %f)\n",
           pose.ang.x, pose.ang.y, pose.ang.z, pose.ang.w);
    entity.transform().relocate(pose);
}

} // namespace game
