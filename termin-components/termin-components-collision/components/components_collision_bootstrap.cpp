#include <components/components_collision_bootstrap.hpp>

#include <components/collider_component.hpp>
#include <components/components_mesh_bootstrap.hpp>

namespace termin {

void register_builtin_collision_component_types() {
    register_builtin_mesh_component_types();
    ColliderComponent::register_type();
}

} // namespace termin
