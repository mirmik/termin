#include <nanobind/nanobind.h>

#include <components/kinematic_unit_component.hpp>
#include <components/actuator_component.hpp>
#include <components/rotator_component.hpp>
#include <termin/bindings/entity_helpers.hpp>

namespace nb = nanobind;
using namespace termin;

NB_MODULE(_components_kinematic_native, m) {
    m.doc() = "Native kinematic component bindings (ActuatorComponent, RotatorComponent)";

    nb::module_::import_("termin.entity._entity_native");

    // KinematicUnitComponent (abstract base)
    nb::class_<KinematicUnitComponent, CxxComponent>(m, "KinematicUnitComponent")
        .def_prop_rw("axis",
            [](KinematicUnitComponent& c) {
                return nb::make_tuple(c.axis_x, c.axis_y, c.axis_z);
            },
            [](KinematicUnitComponent& c, nb::tuple v) {
                c.set_axis(nb::cast<double>(v[0]), nb::cast<double>(v[1]), nb::cast<double>(v[2]));
            })
        .def_prop_rw("coordinate",
            &KinematicUnitComponent::get_coordinate,
            &KinematicUnitComponent::set_coordinate)
        .def("apply", &KinematicUnitComponent::apply)
        .def("capture_base", &KinematicUnitComponent::capture_base);

    // ActuatorComponent
    nb::class_<ActuatorComponent, KinematicUnitComponent>(m, "ActuatorComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<ActuatorComponent>(self);
        });

    // RotatorComponent
    nb::class_<RotatorComponent, KinematicUnitComponent>(m, "RotatorComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<RotatorComponent>(self);
        });
}
