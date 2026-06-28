#include <components/components_kinematic_bootstrap.hpp>

#include <components/actuator_component.hpp>
#include <components/kinematic_unit_component.hpp>
#include <components/rotator_component.hpp>

namespace termin {

void register_builtin_kinematic_component_types() {
    KinematicUnitComponent::register_type();
    ActuatorComponent::register_type();
    RotatorComponent::register_type();
}

} // namespace termin
