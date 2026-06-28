#include <termin/navmesh/components_bootstrap.hpp>

#include <components/components_mesh_bootstrap.hpp>
#include <termin/navmesh/detour_pathfinding_world_component.hpp>
#include <termin/navmesh/navmesh_keeper_component.hpp>
#include <termin/navmesh/off_mesh_link_component.hpp>
#include <termin/navmesh/recast_navmesh_builder_component.hpp>

namespace termin {

void register_builtin_navmesh_component_types() {
    register_builtin_mesh_component_types();
    NavMeshKeeperComponent::register_type();
    DetourPathfindingWorldComponent::register_type();
    OffMeshLinkComponent::register_type();
    RecastNavMeshBuilderComponent::register_type();
}

} // namespace termin
