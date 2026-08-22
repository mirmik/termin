#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <stdexcept>

#include <components/actuator_component.hpp>
#include <components/articulation_component.hpp>
#include <components/kinematic_unit_component.hpp>
#include <components/rotator_component.hpp>
#include <termin/bindings/entity_helpers.hpp>
#include <termin/robotics/articulation3d.hpp>

namespace nb = nanobind;
using namespace termin;

NB_MODULE(_components_kinematic_native, m) {
    m.doc() = "Native kinematic component bindings (ActuatorComponent, "
              "RotatorComponent)";

    nb::module_::import_("termin.scene._scene_native");
    nb::module_::import_("termin.robotics._robotics_native");

    nb::class_<ArticulationComponent, CxxComponent>(m, "ArticulationComponent")
        .def("__init__", [](nb::handle self) { cxx_component_init<ArticulationComponent>(self); })
        .def_prop_ro("initialized", &ArticulationComponent::initialized)
        .def_prop_ro("unit_count", &ArticulationComponent::unit_count)
        .def_prop_ro("diagnostic",
                     [](const ArticulationComponent& component) {
                         return std::string(articulation_component_diagnostic_name(component.diagnostic()));
                     })
        .def("rebuild", &ArticulationComponent::rebuild)
        .def("synchronize", &ArticulationComponent::synchronize)
        .def(
            "integrate_velocity",
            [](ArticulationComponent& component, const std::vector<double>& velocity, double time_step) {
                return component.integrate_velocity(velocity, time_step);
            },
            nb::arg("generalized_velocity"),
            nb::arg("time_step"))
        .def_prop_ro(
            "articulation",
            [](ArticulationComponent& component) -> robotics::Articulation3D& {
                robotics::Articulation3D* articulation = component.articulation();
                if (articulation == nullptr) {
                    throw std::runtime_error("ArticulationComponent has not been rebuilt");
                }
                return *articulation;
            },
            nb::rv_policy::reference_internal);

    // KinematicUnitComponent (abstract base)
    nb::class_<KinematicUnitComponent, CxxComponent>(m, "KinematicUnitComponent")
        .def_prop_rw(
            "axis",
            [](KinematicUnitComponent& c) {
                const Vec3 axis = c.get_axis();
                return nb::make_tuple(axis.x, axis.y, axis.z);
            },
            [](KinematicUnitComponent& c, nb::tuple v) {
                c.set_axis({nb::cast<double>(v[0]), nb::cast<double>(v[1]), nb::cast<double>(v[2])});
            })
        .def_prop_rw("coordinate", &KinematicUnitComponent::get_coordinate, &KinematicUnitComponent::set_coordinate)
        .def_prop_rw("coordinate_scale",
                     &KinematicUnitComponent::get_coordinate_scale,
                     &KinematicUnitComponent::set_coordinate_scale)
        .def_rw("mass", &KinematicUnitComponent::mass)
        .def("apply", &KinematicUnitComponent::apply)
        .def("recalculate_origin", &KinematicUnitComponent::recalculate_origin);

    // ActuatorComponent
    nb::class_<ActuatorComponent, KinematicUnitComponent>(m, "ActuatorComponent").def("__init__", [](nb::handle self) {
        cxx_component_init<ActuatorComponent>(self);
    });

    // RotatorComponent
    nb::class_<RotatorComponent, KinematicUnitComponent>(m, "RotatorComponent").def("__init__", [](nb::handle self) {
        cxx_component_init<RotatorComponent>(self);
    });
}
