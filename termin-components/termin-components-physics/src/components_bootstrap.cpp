#include <termin/physics_components/components_bootstrap.hpp>

#include <termin/physics_components/components.hpp>

namespace termin {

void register_builtin_physics_component_types() {
    PhysicsWorldComponent::register_type();
    RigidBodyComponent::register_type();
}

} // namespace termin
