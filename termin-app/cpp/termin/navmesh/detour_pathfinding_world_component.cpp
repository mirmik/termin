#include "detour_pathfinding_world_component.hpp"

#include "detour_navmesh_asset_utils.hpp"
#include <termin/entity/component_registry.hpp>
#include <DetourNavMesh.h>
#include <DetourNavMeshQuery.h>
#include <DetourStatus.h>
#include <algorithm>
#include <filesystem>
#include <utility>
#include <tcbase/tc_log.hpp>

namespace termin {

DetourPathfindingWorldComponent::DetourPathfindingWorldComponent() {
    declare_type_name("DetourPathfindingWorldComponent");
}

DetourPathfindingWorldComponent::~DetourPathfindingWorldComponent() {
    clear();
}

void DetourPathfindingWorldComponent::clear() {
    if (_query) {
        dtFreeNavMeshQuery(_query);
        _query = nullptr;
    }
    if (_navmesh) {
        dtFreeNavMesh(_navmesh);
        _navmesh = nullptr;
    }
    _tile_blobs.clear();
    _loaded_navmesh_uuid.clear();
    _loaded_asset_path.clear();
    _load_failed = false;
}

bool DetourPathfindingWorldComponent::is_ready() const {
    return _navmesh != nullptr && _query != nullptr && _loaded_navmesh_uuid == navmesh_uuid;
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

    _navmesh = dtAllocNavMesh();
    if (!_navmesh ||
        !dtStatusSucceed(_navmesh->init(_tile_blobs[0].data(), static_cast<int>(_tile_blobs[0].size()), 0))) {
        _load_failed = true;
        return false;
    }

    _query = dtAllocNavMeshQuery();
    if (!_query || !dtStatusSucceed(_query->init(_navmesh, std::max(32, max_polys * 4)))) {
        _load_failed = true;
        return false;
    }

    tc_log_info("[DetourPathfindingWorldComponent] loaded '%s'", _loaded_asset_path.c_str());
    return true;
}

bool DetourPathfindingWorldComponent::find_nearest_poly(const std::array<float, 3>& point,
                                                        unsigned long long& poly_ref,
                                                        float nearest[3],
                                                        bool* over_poly) {
    poly_ref = 0;
    if (!ensure_query_loaded()) {
        return false;
    }

    const std::array<float, 3> rc_point = termin_to_recast(point);
    const float extents[3] = {query_extent_x, query_extent_z, query_extent_y};
    dtQueryFilter filter;
    filter.setIncludeFlags(0xffff);
    filter.setExcludeFlags(0);

    dtPolyRef ref = 0;
    dtStatus status = over_poly
        ? _query->findNearestPoly(rc_point.data(), extents, &filter, &ref, nearest, over_poly)
        : _query->findNearestPoly(rc_point.data(), extents, &filter, &ref, nearest);
    if (!dtStatusSucceed(status) || ref == 0) {
        return false;
    }

    poly_ref = static_cast<unsigned long long>(ref);
    return true;
}

DetourClosestPointResult DetourPathfindingWorldComponent::closest_point(const std::array<float, 3>& point) {
    DetourClosestPointResult result;
    float nearest[3] = {0.0f, 0.0f, 0.0f};
    bool over_poly = false;
    unsigned long long ref = 0;
    if (!find_nearest_poly(point, ref, nearest, &over_poly)) {
        return result;
    }

    result.success = true;
    result.over_poly = over_poly;
    result.poly_ref = ref;
    result.point = recast_to_termin(nearest);
    return result;
}

std::vector<std::array<float, 3>> DetourPathfindingWorldComponent::find_path(
    const std::array<float, 3>& start,
    const std::array<float, 3>& end
) {
    std::vector<std::array<float, 3>> result;
    if (!ensure_query_loaded()) {
        return result;
    }

    float nearest_start[3] = {0.0f, 0.0f, 0.0f};
    float nearest_end[3] = {0.0f, 0.0f, 0.0f};
    unsigned long long start_ref_raw = 0;
    unsigned long long end_ref_raw = 0;
    if (!find_nearest_poly(start, start_ref_raw, nearest_start) ||
        !find_nearest_poly(end, end_ref_raw, nearest_end)) {
        return result;
    }

    const int max_path = std::max(1, max_polys);
    std::vector<dtPolyRef> path(static_cast<size_t>(max_path));
    int path_count = 0;
    dtQueryFilter filter;
    filter.setIncludeFlags(0xffff);
    filter.setExcludeFlags(0);

    if (!dtStatusSucceed(_query->findPath(
            static_cast<dtPolyRef>(start_ref_raw),
            static_cast<dtPolyRef>(end_ref_raw),
            nearest_start,
            nearest_end,
            &filter,
            path.data(),
            &path_count,
            max_path)) ||
        path_count <= 0) {
        return result;
    }

    const int max_straight = std::max(2, max_straight_path);
    std::vector<float> straight(static_cast<size_t>(max_straight) * 3);
    std::vector<unsigned char> flags(static_cast<size_t>(max_straight));
    std::vector<dtPolyRef> refs(static_cast<size_t>(max_straight));
    int straight_count = 0;

    if (!dtStatusSucceed(_query->findStraightPath(
            nearest_start,
            nearest_end,
            path.data(),
            path_count,
            straight.data(),
            flags.data(),
            refs.data(),
            &straight_count,
            max_straight,
            0)) ||
        straight_count <= 0) {
        return result;
    }

    result.reserve(static_cast<size_t>(straight_count));
    for (int i = 0; i < straight_count; ++i) {
        result.push_back(recast_to_termin(&straight[static_cast<size_t>(i) * 3]));
    }
    return result;
}

DetourRaycastResult DetourPathfindingWorldComponent::raycast(
    const std::array<float, 3>& start,
    const std::array<float, 3>& end
) {
    DetourRaycastResult result;
    if (!ensure_query_loaded()) {
        return result;
    }

    float nearest_start[3] = {0.0f, 0.0f, 0.0f};
    unsigned long long start_ref_raw = 0;
    if (!find_nearest_poly(start, start_ref_raw, nearest_start)) {
        return result;
    }

    const std::array<float, 3> rc_end = termin_to_recast(end);
    const int max_path = std::max(1, max_polys);
    std::vector<dtPolyRef> visited(static_cast<size_t>(max_path));
    int visited_count = 0;
    float t = 0.0f;
    float hit_normal[3] = {0.0f, 0.0f, 0.0f};
    dtQueryFilter filter;
    filter.setIncludeFlags(0xffff);
    filter.setExcludeFlags(0);

    if (!dtStatusSucceed(_query->raycast(
            static_cast<dtPolyRef>(start_ref_raw),
            nearest_start,
            rc_end.data(),
            &filter,
            &t,
            hit_normal,
            visited.data(),
            &visited_count,
            max_path))) {
        return result;
    }

    result.success = true;
    result.hit = t < 1.0f;
    result.t = result.hit ? t : 1.0f;

    float hit_rc[3] = {
        nearest_start[0] + (rc_end[0] - nearest_start[0]) * result.t,
        nearest_start[1] + (rc_end[1] - nearest_start[1]) * result.t,
        nearest_start[2] + (rc_end[2] - nearest_start[2]) * result.t,
    };
    result.hit_position = recast_to_termin(hit_rc);
    result.hit_normal = recast_to_termin(hit_normal);
    result.visited.reserve(static_cast<size_t>(visited_count));
    for (int i = 0; i < visited_count; ++i) {
        result.visited.push_back(static_cast<unsigned long long>(visited[static_cast<size_t>(i)]));
    }
    return result;
}


namespace {

tc::InspectAccessorFieldRegistrar<DetourPathfindingWorldComponent, std::string>
    detour_pathfinding_world_navmesh_field_reg{
        "DetourPathfindingWorldComponent",
        "navmesh",
        "NavMesh",
        "navmesh_handle",
        [](DetourPathfindingWorldComponent* self) { return self->navmesh_uuid; },
        [](DetourPathfindingWorldComponent* self, std::string value) {
            if (self->navmesh_uuid != value) {
                self->navmesh_uuid = std::move(value);
                self->clear();
            }
        }
    };

tc::InspectFieldRegistrar<DetourPathfindingWorldComponent, float>
    detour_pathfinding_extent_x_field_reg{
        &DetourPathfindingWorldComponent::query_extent_x,
        "DetourPathfindingWorldComponent",
        "query_extent_x",
        "Query Extent X",
        "float"
    };

tc::InspectFieldRegistrar<DetourPathfindingWorldComponent, float>
    detour_pathfinding_extent_y_field_reg{
        &DetourPathfindingWorldComponent::query_extent_y,
        "DetourPathfindingWorldComponent",
        "query_extent_y",
        "Query Extent Y",
        "float"
    };

tc::InspectFieldRegistrar<DetourPathfindingWorldComponent, float>
    detour_pathfinding_extent_z_field_reg{
        &DetourPathfindingWorldComponent::query_extent_z,
        "DetourPathfindingWorldComponent",
        "query_extent_z",
        "Query Extent Z",
        "float"
    };

tc::InspectFieldRegistrar<DetourPathfindingWorldComponent, int>
    detour_pathfinding_max_polys_field_reg{
        &DetourPathfindingWorldComponent::max_polys,
        "DetourPathfindingWorldComponent",
        "max_polys",
        "Max Polys",
        "int"
    };

}

REGISTER_COMPONENT(DetourPathfindingWorldComponent, Component);

} // namespace termin
