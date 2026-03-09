#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include <components/collider_component.hpp>
#include <termin/bindings/entity_helpers.hpp>

namespace nb = nanobind;
using namespace termin;

NB_MODULE(_components_collision_native, m) {
    m.doc() = "Native collision component bindings";

    nb::module_::import_("termin.entity._entity_native");
    nb::module_::import_("termin.colliders._colliders_native");

    nb::class_<ColliderComponent, CxxComponent>(m, "ColliderComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<ColliderComponent>(self);
        })
        .def_prop_rw("collider_type",
            [](ColliderComponent& c) { return c.collider_type; },
            [](ColliderComponent& c, const std::string& v) { c.set_collider_type(v); })
        .def_prop_rw("box_size",
            [](ColliderComponent& c) {
                return nb::make_tuple(c.box_size.x, c.box_size.y, c.box_size.z);
            },
            [](ColliderComponent& c, nb::tuple v) {
                c.set_box_size(nb::cast<double>(v[0]), nb::cast<double>(v[1]), nb::cast<double>(v[2]));
            })
        .def_prop_ro("collider", [](ColliderComponent& c) {
            return c.collider();
        }, nb::rv_policy::reference)
        .def_prop_ro("attached_collider", [](ColliderComponent& c) {
            return c.attached_collider();
        }, nb::rv_policy::reference)
        .def_prop_ro("attached", [](ColliderComponent& c) {
            return c.attached_collider();
        }, nb::rv_policy::reference)
        .def("rebuild_collider", &ColliderComponent::rebuild_collider);
}
