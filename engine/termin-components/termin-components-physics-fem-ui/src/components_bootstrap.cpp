#include <termin/physics_fem_ui/components_bootstrap.hpp>

#include <termin/physics_fem_ui/components.hpp>

namespace termin {

    void register_builtin_physics_fem_ui_component_types() {
        FEMPhysicsHudComponent::register_type();
    }

} // namespace termin
