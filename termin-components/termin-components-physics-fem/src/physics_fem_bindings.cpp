#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>

#include <stdexcept>

#include <termin/bindings/entity_helpers.hpp>
#include <termin/physics_fem/components.hpp>

namespace nb = nanobind;
using namespace termin;

NB_MODULE(_components_physics_fem_native, m)
{
    m.doc() = "Native FEM articulation scene bindings";

    nb::module_::import_("termin.scene._scene_native");
    nb::module_::import_("termin.robotics._robotics_native");

    nb::class_<FEMArticulationComponent, CxxComponent>(
        m, "FEMArticulationComponent")
        .def("__init__",
             [](nb::handle self)
             { cxx_component_init<FEMArticulationComponent>(self); })
        .def_prop_ro("initialized", &FEMArticulationComponent::initialized)
        .def_prop_ro("unit_count", &FEMArticulationComponent::unit_count)
        .def_prop_ro("actuator_dof_indices",
                     &FEMArticulationComponent::actuator_dof_indices)
        .def_prop_ro("actuator_effort_limits",
                     &FEMArticulationComponent::actuator_effort_limits)
        .def_prop_ro(
            "gravity_world",
            [](const FEMArticulationComponent& component)
            {
                const Vec3 value = component.gravity_world();
                return nb::make_tuple(value.x, value.y, value.z);
            })
        .def_prop_ro(
            "articulation",
            [](FEMArticulationComponent& component)
                -> robotics::Articulation3D&
            {
                robotics::Articulation3D* articulation =
                    component.articulation();
                if (articulation == nullptr)
                {
                    throw std::runtime_error(
                        "FEMArticulationComponent is not initialized");
                }
                return *articulation;
            },
            nb::rv_policy::reference_internal)
        .def("apply_inverse_dynamics_control",
             &FEMArticulationComponent::apply_inverse_dynamics_control,
             nb::arg("control"));

    nb::class_<FEMArticulationMotorComponent, CxxComponent>(
        m, "FEMArticulationMotorComponent")
        .def("__init__",
             [](nb::handle self)
             { cxx_component_init<FEMArticulationMotorComponent>(self); })
        .def_rw("commanded_effort",
                &FEMArticulationMotorComponent::commanded_effort)
        .def_rw("maximum_effort",
                &FEMArticulationMotorComponent::maximum_effort)
        .def_prop_ro("initialized",
                     &FEMArticulationMotorComponent::initialized)
        .def_prop_ro("applied_effort",
                     &FEMArticulationMotorComponent::applied_effort)
        .def_prop_ro("saturated",
                     &FEMArticulationMotorComponent::saturated);
}
