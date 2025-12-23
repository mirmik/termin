#pragma once

#include "../component.hpp"
#include "../component_registry.hpp"
#include "../entity.hpp"
#include "../../geom/geom.hpp"
#include <iostream>

namespace termin {

/**
 * Simple component that rotates entity around Z axis.
 * Example of a native C++ component.
 */
class CXXRotatorComponent : public Component {
public:
    float speed = 1.0f;  // radians per second

    void update(float dt) override {
        std::cout << "CXXRotatorComponent::update dt=" << dt << " speed=" << speed << std::endl;
        if (!entity || !entity->transform) return;

        auto& pose = entity->transform->_local_pose;
        auto screw = Screw3{
            Vec3{0.0, 0.0, speed},
            Vec3{0.0, 0.0, 0.0}
        }.scaled(dt);
        pose = (pose * screw.to_pose()).normalized();
        entity->transform->relocate(pose);
    }
};

REGISTER_COMPONENT(CXXRotatorComponent);

} // namespace termin
