#pragma once

#include "../component.hpp"
#include "../component_registry.hpp"
#include "../entity.hpp"
#include "../../geom/geom.hpp"
#include "../../colliders/collider.hpp"
#include <tc_log.hpp>

#ifdef TERMIN_HAS_NANOBIND
#include <nanobind/nanobind.h>
namespace nb = nanobind;
#endif

namespace termin {

// Simple component that rotates entity around Z axis.
// Example of a native C++ component.
class CXXRotatorComponent : public CxxComponent {
public:
    float speed = 1.0f;  // radians per second
#ifdef TERMIN_HAS_NANOBIND
    nb::object collider_component;  // Default-constructed, no Python interaction
#endif
    termin::colliders::Collider* collider = nullptr;

    INSPECT_FIELD(CXXRotatorComponent, speed, "Speed", "float", 0.0, 10.0, 0.1)

    void start() override {
#ifdef TERMIN_HAS_NANOBIND
        // Get Python component by type name
        tc_component* tc = entity().get_component_by_type_name("ColliderComponent");
        if (tc && tc->native_language == TC_LANGUAGE_PYTHON && tc->body) {
            collider_component = nb::borrow((PyObject*)tc->body);
            nb::object collider_obj = collider_component.attr("attached_collider");
            collider = nb::cast<termin::colliders::Collider*>(collider_obj);
        }
        else {
            collider = nullptr;
            tc::Log::warn("CXXRotatorComponent: Entity has no ColliderComponent");
        }
#endif
    }

    void update(float dt) override {
        if (!entity().valid() || !entity().transform().valid()) return;

        GeneralPose3 pose = entity().transform().local_pose();
        auto screw = Screw3{
            Vec3{0.0, 0.0, speed},
            Vec3{0.0, 0.0, 0.0}
        }.scaled(dt);
        pose = (pose * screw.to_pose()).normalized();
        entity().transform().relocate(pose);

        if (collider) {
            collider->angular_velocity = Vec3{0.0, 0.0, speed};
        }
    }
};

REGISTER_COMPONENT(CXXRotatorComponent, Component);

} // namespace termin
