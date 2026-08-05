#include <nanobind/nanobind.h>

#include <termin/bindings/entity_helpers.hpp>
#include <termin/physics_components/components.hpp>

namespace nb = nanobind;
using namespace termin;

NB_MODULE(_components_physics_native, m) {
    m.doc() = "Native game physics scene component bindings";

    nb::module_::import_("termin.scene._scene_native");
    nb::module_::import_("termin.physics._physics_native");

    nb::class_<PhysicsWorldComponent, CxxComponent>(m, "PhysicsWorldComponent")
        .def("__init__",
             [](nb::handle self,
                const Vec3& gravity,
                int iterations,
                double restitution,
                double friction) {
                 cxx_component_init<PhysicsWorldComponent>(self);
                 auto* component = nb::inst_ptr<PhysicsWorldComponent>(self);
                 component->gravity = gravity;
                 component->iterations = iterations;
                 component->restitution = restitution;
                 component->friction = friction;
             },
             nb::arg("gravity") = Vec3{0.0, 0.0, -9.81},
             nb::arg("iterations") = 10,
             nb::arg("restitution") = 0.3,
             nb::arg("friction") = 0.5)
        .def_prop_rw(
            "gravity",
            [](const PhysicsWorldComponent& c) {
                return Vec3{c.gravity.x, c.gravity.y, c.gravity.z};
            },
            [](PhysicsWorldComponent& c, const Vec3& value) {
                c.gravity = value;
            })
        .def_rw("iterations", &PhysicsWorldComponent::iterations)
        .def_rw("restitution", &PhysicsWorldComponent::restitution)
        .def_rw("friction", &PhysicsWorldComponent::friction)
        .def_prop_ro("initialized", &PhysicsWorldComponent::initialized)
        .def_prop_ro(
            "physics_world",
            [](PhysicsWorldComponent& c) -> physics::PhysicsWorld& {
                return c.physics_world();
            },
            nb::rv_policy::reference_internal);

    nb::class_<RigidBodyComponent, CxxComponent>(m, "RigidBodyComponent")
        .def("__init__",
             [](nb::handle self,
                double mass,
                bool is_static,
                double restitution,
                double friction) {
                 cxx_component_init<RigidBodyComponent>(self);
                 auto* component = nb::inst_ptr<RigidBodyComponent>(self);
                 component->mass = mass;
                 component->is_static = is_static;
                 component->restitution = restitution;
                 component->friction = friction;
             },
             nb::arg("mass") = 1.0,
             nb::arg("is_static") = false,
             nb::arg("restitution") = 0.3,
             nb::arg("friction") = 0.5)
        .def_rw("mass", &RigidBodyComponent::mass)
        .def_rw("is_static", &RigidBodyComponent::is_static)
        .def_rw("restitution", &RigidBodyComponent::restitution)
        .def_rw("friction", &RigidBodyComponent::friction)
        .def_prop_ro("initialized", &RigidBodyComponent::initialized)
        .def_prop_ro("body_index", &RigidBodyComponent::body_index)
        .def_prop_ro(
            "rigid_body",
            [](RigidBodyComponent& c) { return c.rigid_body(); },
            nb::rv_policy::reference_internal)
        .def("sync_to_physics", &RigidBodyComponent::sync_to_physics)
        .def("apply_impulse", &RigidBodyComponent::apply_impulse, nb::arg("impulse"))
        .def("apply_impulse_at_point",
             &RigidBodyComponent::apply_impulse_at_point,
             nb::arg("impulse"),
             nb::arg("point"));
}
