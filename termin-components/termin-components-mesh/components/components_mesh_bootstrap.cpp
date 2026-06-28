#include <components/components_mesh_bootstrap.hpp>

#include <components/mesh_component.hpp>

namespace termin {

void register_builtin_mesh_component_types() {
    MeshComponent::register_type();
}

} // namespace termin
