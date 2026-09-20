#include <tc_inspect_cpp.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/navmesh/pathfinding_world.hpp>
#include <termin/navmesh/world_navmesh_link_component.hpp>
#include <termin/tc_scene.hpp>

namespace termin {
    WorldNavMeshLinkComponent::~WorldNavMeshLinkComponent() {
        on_removed();
    }
    void WorldNavMeshLinkComponent::on_added() {
        if (entity().valid()) {
            if (auto* world = PathfindingWorld::ensure_scene(entity().scene().handle()))
                world->add_link(this);
        }
    }
    void WorldNavMeshLinkComponent::on_removed() {
        if (entity().valid()) {
            if (auto* world = PathfindingWorld::from_scene(entity().scene().handle()))
                world->remove_link(this);
        }
    }
    void WorldNavMeshLinkComponent::register_type() {
        auto descriptor = ComponentTypeDescriptorBuilder::native<WorldNavMeshLinkComponent>(
            "WorldNavMeshLinkComponent", "termin-navmesh", "Component");
        descriptor.category("Navigation");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshLinkComponent::start_surface,
                                "WorldNavMeshLinkComponent",
                                "start_surface",
                                "Start Surface",
                                "entity");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshLinkComponent::end_surface,
                                "WorldNavMeshLinkComponent",
                                "end_surface",
                                "End Surface",
                                "entity");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshLinkComponent::start_local,
                                "WorldNavMeshLinkComponent",
                                "start_local",
                                "Start Local",
                                "vec3");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshLinkComponent::end_local,
                                "WorldNavMeshLinkComponent",
                                "end_local",
                                "End Local",
                                "vec3");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshLinkComponent::snap_radius,
                                "WorldNavMeshLinkComponent",
                                "snap_radius",
                                "Snap Radius",
                                "double");
        tc::stage_inspect_field(descriptor.inspect(),
                                &WorldNavMeshLinkComponent::bidirectional,
                                "WorldNavMeshLinkComponent",
                                "bidirectional",
                                "Bidirectional",
                                "bool");
        (void)descriptor.commit();
    }
} // namespace termin
