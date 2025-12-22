#pragma once

#include "../component.hpp"
#include "../component_registry.hpp"
#include "../entity.hpp"

namespace termin {

/**
 * Simple component that rotates entity around Z axis.
 * Example of a native C++ component.
 */
class CXXRotatorComponent : public Component {
public:
    COMPONENT_BODY(CXXRotatorComponent)

    float speed = 1.0f;  // radians per second

    void update(float dt) override {
        if (!entity || !entity->transform) return;

        auto& pose = entity->transform->_local_pose;
        // Rotate around Z axis
        double angle = speed * dt;
        geom::Quat delta = geom::Quat::from_axis_angle({0, 0, 1}, angle);
        pose.ang = delta * pose.ang;
        entity->transform->_mark_dirty();
    }
};

REGISTER_COMPONENT(CXXRotatorComponent);

} // namespace termin
