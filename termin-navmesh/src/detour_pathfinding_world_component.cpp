#include <termin/navmesh/detour_pathfinding_world_component.hpp>

#include <termin/navmesh/detour_navmesh_asset_utils.hpp>
#include <termin/navmesh/pathfinding_world.hpp>
#include <termin/navmesh/tc_navmesh_handle.hpp>
#include <termin/tc_scene.hpp>
#include <termin/entity/component_registry.hpp>
#include <algorithm>
#include <utility>
#include <tcbase/tc_log.hpp>

namespace termin {

DetourPathfindingWorldComponent::DetourPathfindingWorldComponent()
    : CxxComponent("DetourPathfindingWorldComponent")
{}

DetourPathfindingWorldComponent::~DetourPathfindingWorldComponent() {
    on_removed();
    clear();
}

void DetourPathfindingWorldComponent::on_added() {
    const Entity owner = entity();
    if (!owner.valid()) {
        tc_log_warn("[DetourPathfindingWorldComponent] on_added skipped: owner entity is invalid");
        return;
    }

    PathfindingWorld* world = PathfindingWorld::ensure_scene(owner.scene().handle());
    if (!world) {
        tc_log_warn("[DetourPathfindingWorldComponent] on_added skipped: pathfinding world is unavailable");
        return;
    }
    world->add(this);
}

void DetourPathfindingWorldComponent::on_removed() {
    const Entity owner = entity();
    if (!owner.valid()) {
        return;
    }

    PathfindingWorld* world = PathfindingWorld::from_scene(owner.scene().handle());
    if (world) {
        world->remove(this);
    }
}

void DetourPathfindingWorldComponent::sync_query_settings() {
    _query_session.query_extent_x = query_extent_x;
    _query_session.query_extent_y = query_extent_y;
    _query_session.query_extent_z = query_extent_z;
    _query_session.max_polys = max_polys;
    _query_session.max_straight_path = max_straight_path;
}

void DetourPathfindingWorldComponent::clear() {
    _query_session.clear();
    _tile_blobs.clear();
    _loaded_navmesh_uuid.clear();
    _loaded_asset_path.clear();
    _load_failed = false;
}

bool DetourPathfindingWorldComponent::is_ready() const {
    return _query_session.is_ready() && _loaded_navmesh_uuid == navmesh_uuid;
}

bool DetourPathfindingWorldComponent::rebuild() {
    clear();
    return ensure_query_loaded();
}

bool DetourPathfindingWorldComponent::ensure_query_loaded() {
    if (navmesh_uuid.empty()) {
        clear();
        return false;
    }
    if (is_ready()) {
        sync_query_settings();
        return true;
    }
    if (_loaded_navmesh_uuid == navmesh_uuid && _load_failed) {
        return false;
    }

    clear();
    _loaded_navmesh_uuid = navmesh_uuid;

    TcNavMesh navmesh = TcNavMesh::from_uuid(navmesh_uuid);
    if (!navmesh.is_valid()) {
        tc_log_warn("[DetourPathfindingWorldComponent] navmesh not found for uuid=%s",
                    navmesh_uuid.c_str());
        _load_failed = true;
        return false;
    }
    _loaded_asset_path = navmesh.name();

    if (!load_detour_tile_blobs_from_navmesh(navmesh, _tile_blobs)) {
        _load_failed = true;
        return false;
    }

    if (_tile_blobs.size() != 1) {
        tc_log_warn("[DetourPathfindingWorldComponent] multi-tile Detour assets are not supported yet: %s",
                    _loaded_asset_path.c_str());
        _load_failed = true;
        return false;
    }

    sync_query_settings();
    if (!_query_session.load_single_tile_data(_tile_blobs[0], _loaded_asset_path)) {
        _load_failed = true;
        return false;
    }

    tc_log_info("[DetourPathfindingWorldComponent] loaded '%s'", _loaded_asset_path.c_str());
    return true;
}

DetourClosestPointResult DetourPathfindingWorldComponent::closest_point(
    const Vec3f& point
) {
    if (!ensure_query_loaded()) {
        return {};
    }
    sync_query_settings();
    return _query_session.closest_point(point);
}

DetourClosestPointResult DetourPathfindingWorldComponent::closest_point_world(
    const Pose3& bake_frame,
    const Vec3f& point
) {
    if (!ensure_query_loaded()) {
        return {};
    }
    sync_query_settings();
    return _query_session.closest_point_world(bake_frame, point);
}

std::vector<Vec3f> DetourPathfindingWorldComponent::find_path(
    const Vec3f& start,
    const Vec3f& end
) {
    if (!ensure_query_loaded()) {
        return {};
    }
    sync_query_settings();
    return _query_session.find_path(start, end);
}

std::vector<Vec3f> DetourPathfindingWorldComponent::find_path_world(
    const Pose3& bake_frame,
    const Vec3f& start,
    const Vec3f& end
) {
    if (!ensure_query_loaded()) {
        return {};
    }
    sync_query_settings();
    return _query_session.find_path_world(bake_frame, start, end);
}

DetourPathResult DetourPathfindingWorldComponent::find_detailed_path(
    const Vec3f& start,
    const Vec3f& end
) {
    if (!ensure_query_loaded()) {
        tc_log_warn("[DetourPathfindingWorldComponent] path query failed: navmesh is not ready "
                    "uuid=%s loaded_uuid=%s",
                    navmesh_uuid.c_str(),
                    _loaded_navmesh_uuid.c_str());
        return {};
    }
    sync_query_settings();
    return _query_session.find_detailed_path(start, end);
}

DetourPathResult DetourPathfindingWorldComponent::find_detailed_path_world(
    const Pose3& bake_frame,
    const Vec3f& start,
    const Vec3f& end
) {
    if (!ensure_query_loaded()) {
        tc_log_warn("[DetourPathfindingWorldComponent] world-space path query failed: navmesh is not ready "
                    "uuid=%s loaded_uuid=%s",
                    navmesh_uuid.c_str(),
                    _loaded_navmesh_uuid.c_str());
        return {};
    }
    sync_query_settings();
    return _query_session.find_detailed_path_world(bake_frame, start, end);
}

DetourRaycastResult DetourPathfindingWorldComponent::raycast(
    const Vec3f& start,
    const Vec3f& end
) {
    if (!ensure_query_loaded()) {
        return {};
    }
    sync_query_settings();
    return _query_session.raycast(start, end);
}

DetourRaycastResult DetourPathfindingWorldComponent::raycast_world(
    const Pose3& bake_frame,
    const Vec3f& start,
    const Vec3f& end
) {
    if (!ensure_query_loaded()) {
        return {};
    }
    sync_query_settings();
    return _query_session.raycast_world(bake_frame, start, end);
}

namespace {

void register_detour_pathfinding_world_inspect_fields() {
    tc::InspectAccessorFieldRegistrar<DetourPathfindingWorldComponent, TcNavMesh>(
        "DetourPathfindingWorldComponent",
        "navmesh",
        "NavMesh",
        "navmesh_handle",
        [](DetourPathfindingWorldComponent* self) {
            return TcNavMesh::from_uuid(self->navmesh_uuid);
        },
        [](DetourPathfindingWorldComponent* self, TcNavMesh value) {
            const char* uuid = value.uuid();
            std::string next_uuid = uuid ? uuid : "";
            if (self->navmesh_uuid != next_uuid) {
                self->navmesh_uuid = std::move(next_uuid);
                self->clear();
            }
        }
    );
    tc::register_inspect_field(
        &DetourPathfindingWorldComponent::query_extent_x,
        "DetourPathfindingWorldComponent",
        "query_extent_x",
        "Query Extent X",
        "float"
    );
    tc::register_inspect_field(
        &DetourPathfindingWorldComponent::query_extent_y,
        "DetourPathfindingWorldComponent",
        "query_extent_y",
        "Query Extent Y",
        "float"
    );
    tc::register_inspect_field(
        &DetourPathfindingWorldComponent::query_extent_z,
        "DetourPathfindingWorldComponent",
        "query_extent_z",
        "Query Extent Z",
        "float"
    );
    tc::register_inspect_field(
        &DetourPathfindingWorldComponent::max_polys,
        "DetourPathfindingWorldComponent",
        "max_polys",
        "Max Polys",
        "int"
    );
}

} // namespace

void DetourPathfindingWorldComponent::register_type() {
    register_component_type<DetourPathfindingWorldComponent>(
        "DetourPathfindingWorldComponent",
        "Component"
    );
    register_detour_pathfinding_world_inspect_fields();
}

} // namespace termin
