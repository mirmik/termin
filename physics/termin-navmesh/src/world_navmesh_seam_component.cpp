#include <tc_inspect_cpp.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/navmesh/pathfinding_world.hpp>
#include <termin/navmesh/world_navmesh_seam_component.hpp>
#include <termin/tc_scene.hpp>

namespace termin {
    WorldNavMeshSeamComponent::~WorldNavMeshSeamComponent() {
        on_removed();
    }
    void WorldNavMeshSeamComponent::on_added() {
        if (entity().valid()) {
            if (auto* world = PathfindingWorld::ensure_scene(entity().scene().handle()))
                world->add_seam(this);
        }
    }
    void WorldNavMeshSeamComponent::on_removed() {
        if (entity().valid()) {
            if (auto* world = PathfindingWorld::from_scene(entity().scene().handle()))
                world->remove_seam(this);
        }
    }
    void WorldNavMeshSeamComponent::register_type() {
        auto descriptor = ComponentTypeDescriptorBuilder::native<WorldNavMeshSeamComponent>(
            "WorldNavMeshSeamComponent", "termin-navmesh", "Component");
        descriptor.category("Navigation");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshSeamComponent::start_surface,
                                "WorldNavMeshSeamComponent",
                                "start_surface",
                                "Start Surface",
                                "entity");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshSeamComponent::end_surface,
                                "WorldNavMeshSeamComponent",
                                "end_surface",
                                "End Surface",
                                "entity");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshSeamComponent::start_a,
                                "WorldNavMeshSeamComponent",
                                "start_a",
                                "Start A",
                                "vec3");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshSeamComponent::start_b,
                                "WorldNavMeshSeamComponent",
                                "start_b",
                                "Start B",
                                "vec3");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshSeamComponent::end_a,
                                "WorldNavMeshSeamComponent",
                                "end_a",
                                "End A",
                                "vec3");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshSeamComponent::end_b,
                                "WorldNavMeshSeamComponent",
                                "end_b",
                                "End B",
                                "vec3");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshSeamComponent::max_extension,
                                "WorldNavMeshSeamComponent",
                                "max_extension",
                                "Max Extension",
                                "double");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshSeamComponent::bidirectional,
                                "WorldNavMeshSeamComponent",
                                "bidirectional",
                                "Bidirectional",
                                "bool");
        (void)descriptor.commit();
    }
} // namespace termin
