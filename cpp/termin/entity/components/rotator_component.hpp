#pragma once

#include "../component.hpp"
#include "../component_registry.hpp"
#include "../entity.hpp"
#include "../../geom/geom.hpp"
#include "../../colliders/collider.hpp"
#include <tc_log.hpp>

namespace termin {

// Simple component that rotates entity around Z axis.
// Example of a native C++ component.
class CXXRotatorComponent : public CxxComponent {
public:
    float speed = 1.0f;  // radians per second
    nb::object collider_component = nb::none();
    termin::colliders::Collider* collider = nullptr;

    INSPECT_FIELD(CXXRotatorComponent, speed, "Speed", "float", 0.0, 10.0, 0.1)

    void start() override {
        collider_component = entity.get_python_component("ColliderComponent");
        if (!collider_component.is_none()) {
            // collider_component.attached_collider
            nb::object collider_obj = collider_component.attr("attached_collider");
            collider = nb::cast<termin::colliders::Collider*>(collider_obj);
        }
        else {
            collider = nullptr;
            tc::Log::warn("CXXRotatorComponent: Entity has no ColliderComponent");
        }
    }

    void update(float dt) override {
        if (!entity.valid() || !entity.transform().valid()) return;

        GeneralPose3 pose = entity.transform().local_pose();
        auto screw = Screw3{
            Vec3{0.0, 0.0, speed},
            Vec3{0.0, 0.0, 0.0}
        }.scaled(dt);
        pose = (pose * screw.to_pose()).normalized();
        entity.transform().relocate(pose);

        collider->angular_velocity = Vec3{0.0, 0.0, speed};
    }
};

REGISTER_COMPONENT(CXXRotatorComponent, Component);

} // namespace termin
