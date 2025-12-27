#pragma once

#include "../component.hpp"
#include "../component_registry.hpp"
#include "../entity.hpp"
#include "../../geom/geom.hpp"
#include "../../inspect/inspect_registry.hpp"
#include <iostream>
#include <pybind11/pybind11.h>
#include <termin/colliders/attached_collider.hpp>

namespace termin {

/**
 * Simple component that rotates entity around Z axis.
 * Example of a native C++ component.
 */
class CXXRotatorComponent : public Component {
public:
    float speed = 1.0f;  // radians per second
    termin::Component* collider_component = nullptr;
    pybind11::object py_collider_component;

    INSPECT_FIELD(CXXRotatorComponent, speed, "Speed", "float", 0.0, 10.0, 0.1)

    void start() override {
        collider_component = entity->get_component_by_type("ColliderComponent");
        if (collider_component) {
            py_collider_component = collider_component->to_python();
        }
    }


    void update(float dt) override {
        if (!entity || !entity->transform().valid()) return;

        GeneralPose3 pose = entity->transform().local_pose();
        auto screw = Screw3{
            Vec3{0.0, 0.0, speed},
            Vec3{0.0, 0.0, 0.0}
        }.scaled(dt);
        pose = (pose * screw.to_pose()).normalized();
        entity->transform().relocate(pose);

        py::object attached = py_collider_component.attr("attached");
        auto* ac = attached.cast<termin::colliders::AttachedCollider*>();
        ac->angular_velocity = Vec3(0, 0, speed);
    }
};

REGISTER_COMPONENT(CXXRotatorComponent);

} // namespace termin
