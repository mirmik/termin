#include <termin/physics_fem/components_bootstrap.hpp>

#include <termin/physics_fem/components.hpp>

namespace termin {

    void register_builtin_physics_fem_component_types() {
        FEMPhysicsWorldComponent::register_type();
        FEMArticulationComponent::register_type();
        FEMArticulationMotorComponent::register_type();
        FEMJointLimitComponent::register_type();
        FEMJointServoComponent::register_type();
        FEMRigidBodyComponent::register_type();
        FEMFixedJointComponent::register_type();
        FEMRevoluteJointComponent::register_type();
    }

} // namespace termin
