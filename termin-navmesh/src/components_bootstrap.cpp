#include <termin/navmesh/components_bootstrap.hpp>

#include <termin/navmesh/detour_pathfinding_world_component.hpp>
#include <termin/navmesh/navmesh_bake_source.hpp>
#include <termin/navmesh/navmesh_keeper_component.hpp>
#include <termin/navmesh/off_mesh_link_component.hpp>
#include <termin/navmesh/recast_navmesh_builder_component.hpp>
#include <termin/navmesh/tc_pathfinding_world.h>

namespace termin {

void register_builtin_navmesh_component_types() {
    tc_pathfinding_world_extension_init();
    NavMeshKeeperComponent::register_type();
    DetourPathfindingWorldComponent::register_type();
    OffMeshLinkComponent::register_type();
    RecastNavMeshBuilderComponent::register_type();
    NavMeshBakeVisitorRegistry::instance().ensure_builtin_visitors_registered();
}

} // namespace termin
