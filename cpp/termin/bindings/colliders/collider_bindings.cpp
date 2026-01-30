// collider_bindings.cpp - Python bindings for ColliderComponent

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include "termin/colliders/collider_component.hpp"
#include "termin/bindings/entity/entity_helpers.hpp"

namespace nb = nanobind;

namespace termin {

void bind_collider_component(nb::module_& m) {
    nb::class_<ColliderComponent, CxxComponent>(m, "ColliderComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<ColliderComponent>(self);
        })

        // Collider type
        .def_prop_rw("collider_type",
            [](ColliderComponent& c) { return c.collider_type; },
            [](ColliderComponent& c, const std::string& v) { c.set_collider_type(v); })

        // Box size (as tuple for compatibility)
        // Only applies to Box type - Sphere/Capsule use entity scale
        .def_prop_rw("box_size",
            [](ColliderComponent& c) {
                return nb::make_tuple(c.box_size_x, c.box_size_y, c.box_size_z);
            },
            [](ColliderComponent& c, nb::tuple v) {
                double x = nb::cast<double>(v[0]);
                double y = nb::cast<double>(v[1]);
                double z = nb::cast<double>(v[2]);
                c.set_box_size(x, y, z);
            })

        // Accessors
        .def_prop_ro("collider", [](ColliderComponent& c) {
            return c.collider();
        }, nb::rv_policy::reference)
        .def_prop_ro("attached_collider", [](ColliderComponent& c) {
            return c.attached_collider();
        }, nb::rv_policy::reference)

        // Alias for Python compatibility
        .def_prop_ro("attached", [](ColliderComponent& c) {
            return c.attached_collider();
        }, nb::rv_policy::reference)

        // Rebuild after manual parameter changes
        .def("rebuild_collider", &ColliderComponent::rebuild_collider);
}

} // namespace termin
