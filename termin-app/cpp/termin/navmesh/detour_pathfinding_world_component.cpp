#include "detour_pathfinding_world_component.hpp"

#include "detour_navmesh_asset_utils.hpp"
#include <termin/entity/component_registry.hpp>
#include <DetourNavMesh.h>
#include <DetourNavMeshQuery.h>
#include <DetourStatus.h>
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <sstream>
#include <utility>
#include <tcbase/tc_log.hpp>

namespace termin {

namespace {

const char* detour_poly_type_name(unsigned char type) {
    switch (type) {
        case DT_POLYTYPE_GROUND:
            return "ground";
        case DT_POLYTYPE_OFFMESH_CONNECTION:
            return "offmesh";
        default:
            return "unknown";
    }
}

std::string detour_status_to_string(dtStatus status) {
    std::ostringstream out;
    if (dtStatusSucceed(status)) {
        out << "success";
    } else if (dtStatusFailed(status)) {
        out << "failure";
    } else if (dtStatusInProgress(status)) {
        out << "in_progress";
    } else {
        out << "unknown";
    }
    out << " raw=0x" << std::hex << status << std::dec;

    bool has_detail = false;
    auto append_detail = [&](unsigned int detail, const char* name) {
        if (dtStatusDetail(status, detail)) {
            out << (has_detail ? "|" : " details=");
            out << name;
            has_detail = true;
        }
    };
    append_detail(DT_WRONG_MAGIC, "wrong_magic");
    append_detail(DT_WRONG_VERSION, "wrong_version");
    append_detail(DT_OUT_OF_MEMORY, "out_of_memory");
    append_detail(DT_INVALID_PARAM, "invalid_param");
    append_detail(DT_BUFFER_TOO_SMALL, "buffer_too_small");
    append_detail(DT_OUT_OF_NODES, "out_of_nodes");
    append_detail(DT_PARTIAL_RESULT, "partial_result");
    append_detail(DT_ALREADY_OCCUPIED, "already_occupied");
    return out.str();
}

std::string straight_path_flags_to_string(unsigned char flags) {
    if (flags == 0) {
        return "none";
    }
    std::ostringstream out;
    bool wrote = false;
    auto append_flag = [&](unsigned char flag, const char* name) {
        if ((flags & flag) != 0) {
            if (wrote) {
                out << "|";
            }
            out << name;
            wrote = true;
        }
    };
    append_flag(DT_STRAIGHTPATH_START, "start");
    append_flag(DT_STRAIGHTPATH_END, "end");
    append_flag(DT_STRAIGHTPATH_OFFMESH_CONNECTION, "offmesh");
    const unsigned char known =
        DT_STRAIGHTPATH_START |
        DT_STRAIGHTPATH_END |
        DT_STRAIGHTPATH_OFFMESH_CONNECTION;
    const unsigned char unknown = static_cast<unsigned char>(flags & ~known);
    if (unknown != 0) {
        if (wrote) {
            out << "|";
        }
        out << "unknown(0x" << std::hex << static_cast<int>(unknown) << std::dec << ")";
    }
    return out.str();
}

float point_distance(const std::array<float, 3>& a, const std::array<float, 3>& b) {
    const float dx = a[0] - b[0];
    const float dy = a[1] - b[1];
    const float dz = a[2] - b[2];
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

void log_detour_poly_info(dtNavMesh* navmesh, const char* prefix, int index, dtPolyRef ref) {
    if (!navmesh || ref == 0) {
        tc_log_info("%s[%d]: ref=%llu <none>",
                    prefix, index, static_cast<unsigned long long>(ref));
        return;
    }

    unsigned int salt = 0;
    unsigned int tile_index = 0;
    unsigned int poly_index = 0;
    navmesh->decodePolyId(ref, salt, tile_index, poly_index);

    const dtMeshTile* tile = nullptr;
    const dtPoly* poly = nullptr;
    const dtStatus status = navmesh->getTileAndPolyByRef(ref, &tile, &poly);
    if (!dtStatusSucceed(status) || !poly) {
        const std::string status_text = detour_status_to_string(status);
        tc_log_warn("%s[%d]: ref=%llu salt=%u tile=%u poly=%u getTileAndPolyByRef=%s",
                    prefix,
                    index,
                    static_cast<unsigned long long>(ref),
                    salt,
                    tile_index,
                    poly_index,
                    status_text.c_str());
        return;
    }

    const unsigned char type = poly->getType();
    tc_log_info("%s[%d]: ref=%llu salt=%u tile=%u poly=%u type=%s area=%u flags=0x%04x vert_count=%u",
                prefix,
                index,
                static_cast<unsigned long long>(ref),
                salt,
                tile_index,
                poly_index,
                detour_poly_type_name(type),
                static_cast<unsigned int>(poly->getArea()),
                static_cast<unsigned int>(poly->flags),
                static_cast<unsigned int>(poly->vertCount));

    if (type == DT_POLYTYPE_OFFMESH_CONNECTION) {
        const dtOffMeshConnection* connection = navmesh->getOffMeshConnectionByRef(ref);
        if (connection) {
            tc_log_info("%s[%d] offmesh: user_id=%u radius=%.3f flags=0x%02x side=%u "
                        "start_rc=(%.3f, %.3f, %.3f) end_rc=(%.3f, %.3f, %.3f)",
                        prefix,
                        index,
                        connection->userId,
                        connection->rad,
                        static_cast<unsigned int>(connection->flags),
                        static_cast<unsigned int>(connection->side),
                        connection->pos[0],
                        connection->pos[1],
                        connection->pos[2],
                        connection->pos[3],
                        connection->pos[4],
                        connection->pos[5]);
        }
    }
}

} // namespace

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
    DetourPathResult detailed = find_detailed_path(start, end);
    if (!detailed.success) {
        return result;
    }
    result.reserve(detailed.points.size());
    for (const DetourPathPoint& point : detailed.points) {
        result.push_back(point.point);
    }
    return result;
}

DetourPathResult DetourPathfindingWorldComponent::find_detailed_path(
    const std::array<float, 3>& start,
    const std::array<float, 3>& end
) {
    DetourPathResult result;
    if (!ensure_query_loaded()) {
        tc_log_warn("[DetourPathfindingWorldComponent] path query failed: navmesh is not ready "
                    "uuid=%s loaded_uuid=%s",
                    navmesh_uuid.c_str(),
                    _loaded_navmesh_uuid.c_str());
        return result;
    }

    tc_log_info("[DetourPathfindingWorldComponent] path query begin asset='%s' uuid=%s "
                "start=(%.3f, %.3f, %.3f) end=(%.3f, %.3f, %.3f) "
                "extent=(%.3f, %.3f, %.3f) max_polys=%d max_straight=%d",
                _loaded_asset_path.c_str(),
                navmesh_uuid.c_str(),
                start[0], start[1], start[2],
                end[0], end[1], end[2],
                query_extent_x, query_extent_y, query_extent_z,
                max_polys,
                max_straight_path);

    float nearest_start[3] = {0.0f, 0.0f, 0.0f};
    float nearest_end[3] = {0.0f, 0.0f, 0.0f};
    unsigned long long start_ref_raw = 0;
    unsigned long long end_ref_raw = 0;
    bool start_over_poly = false;
    bool end_over_poly = false;
    const bool has_start_poly = find_nearest_poly(start, start_ref_raw, nearest_start, &start_over_poly);
    const bool has_end_poly = find_nearest_poly(end, end_ref_raw, nearest_end, &end_over_poly);
    if (!has_start_poly || !has_end_poly) {
        tc_log_warn("[DetourPathfindingWorldComponent] path query failed: nearest poly "
                    "start_found=%d start_ref=%llu end_found=%d end_ref=%llu",
                    has_start_poly ? 1 : 0,
                    start_ref_raw,
                    has_end_poly ? 1 : 0,
                    end_ref_raw);
        return result;
    }

    const std::array<float, 3> nearest_start_term = recast_to_termin(nearest_start);
    const std::array<float, 3> nearest_end_term = recast_to_termin(nearest_end);
    tc_log_info("[DetourPathfindingWorldComponent] nearest start ref=%llu over=%d "
                "point=(%.3f, %.3f, %.3f) snap_dist=%.3f",
                start_ref_raw,
                start_over_poly ? 1 : 0,
                nearest_start_term[0], nearest_start_term[1], nearest_start_term[2],
                point_distance(start, nearest_start_term));
    log_detour_poly_info(_navmesh, "[DetourPathfindingWorldComponent] nearest start poly", 0,
                         static_cast<dtPolyRef>(start_ref_raw));

    tc_log_info("[DetourPathfindingWorldComponent] nearest end ref=%llu over=%d "
                "point=(%.3f, %.3f, %.3f) snap_dist=%.3f",
                end_ref_raw,
                end_over_poly ? 1 : 0,
                nearest_end_term[0], nearest_end_term[1], nearest_end_term[2],
                point_distance(end, nearest_end_term));
    log_detour_poly_info(_navmesh, "[DetourPathfindingWorldComponent] nearest end poly", 0,
                         static_cast<dtPolyRef>(end_ref_raw));

    const int max_path = std::max(1, max_polys);
    std::vector<dtPolyRef> path(static_cast<size_t>(max_path));
    int path_count = 0;
    dtQueryFilter filter;
    filter.setIncludeFlags(0xffff);
    filter.setExcludeFlags(0);

    const dtStatus find_path_status = _query->findPath(
            static_cast<dtPolyRef>(start_ref_raw),
            static_cast<dtPolyRef>(end_ref_raw),
            nearest_start,
            nearest_end,
            &filter,
            path.data(),
            &path_count,
            max_path);
    const std::string find_path_status_text = detour_status_to_string(find_path_status);
    tc_log_info("[DetourPathfindingWorldComponent] findPath status=%s path_count=%d",
                find_path_status_text.c_str(),
                path_count);
    if (!dtStatusSucceed(find_path_status) || path_count <= 0) {
        tc_log_warn("[DetourPathfindingWorldComponent] path query failed: findPath returned no corridor");
        return result;
    }

    for (int i = 0; i < path_count; ++i) {
        log_detour_poly_info(_navmesh, "[DetourPathfindingWorldComponent] corridor", i,
                             path[static_cast<size_t>(i)]);
    }

    const int max_straight = std::max(2, max_straight_path);
    std::vector<float> straight(static_cast<size_t>(max_straight) * 3);
    std::vector<unsigned char> flags(static_cast<size_t>(max_straight));
    std::vector<dtPolyRef> refs(static_cast<size_t>(max_straight));
    int straight_count = 0;

    const dtStatus straight_status = _query->findStraightPath(
            nearest_start,
            nearest_end,
            path.data(),
            path_count,
            straight.data(),
            flags.data(),
            refs.data(),
            &straight_count,
            max_straight,
            0);
    const std::string straight_status_text = detour_status_to_string(straight_status);
    tc_log_info("[DetourPathfindingWorldComponent] findStraightPath status=%s straight_count=%d",
                straight_status_text.c_str(),
                straight_count);
    if (!dtStatusSucceed(straight_status) || straight_count <= 0) {
        tc_log_warn("[DetourPathfindingWorldComponent] path query failed: findStraightPath returned no points");
        return result;
    }

    result.success = true;
    result.points.reserve(static_cast<size_t>(straight_count));
    float total_straight_length = 0.0f;
    std::array<float, 3> previous_point{0.0f, 0.0f, 0.0f};
    for (int i = 0; i < straight_count; ++i) {
        const dtPolyRef ref = refs[static_cast<size_t>(i)];

        DetourPathPoint point;
        point.point = recast_to_termin(&straight[static_cast<size_t>(i) * 3]);
        point.flags = flags[static_cast<size_t>(i)];
        point.poly_ref = static_cast<unsigned long long>(ref);
        point.off_mesh_connection = (point.flags & DT_STRAIGHTPATH_OFFMESH_CONNECTION) != 0;

        if (ref != 0) {
            const dtMeshTile* tile = nullptr;
            const dtPoly* poly = nullptr;
            if (dtStatusSucceed(_navmesh->getTileAndPolyByRef(ref, &tile, &poly)) && poly) {
                point.area = poly->getArea();
            }

            if (point.off_mesh_connection) {
                const dtOffMeshConnection* connection = _navmesh->getOffMeshConnectionByRef(ref);
                if (connection) {
                    point.off_mesh_user_id = connection->userId;
                }
            }
        }

        if (i > 0) {
            total_straight_length += point_distance(previous_point, point.point);
        }
        previous_point = point.point;

        const std::string straight_flags = straight_path_flags_to_string(point.flags);
        tc_log_info("[DetourPathfindingWorldComponent] straight[%d]: "
                    "point=(%.3f, %.3f, %.3f) ref=%llu flags=0x%02x(%s) "
                    "area=%u offmesh=%d offmesh_user_id=%u",
                    i,
                    point.point[0], point.point[1], point.point[2],
                    point.poly_ref,
                    static_cast<unsigned int>(point.flags),
                    straight_flags.c_str(),
                    static_cast<unsigned int>(point.area),
                    point.off_mesh_connection ? 1 : 0,
                    point.off_mesh_user_id);
        log_detour_poly_info(_navmesh, "[DetourPathfindingWorldComponent] straight poly", i, ref);

        result.points.push_back(point);
    }
    tc_log_info("[DetourPathfindingWorldComponent] path query success points=%zu corridor=%d "
                "straight_length=%.3f partial=%d",
                result.points.size(),
                path_count,
                total_straight_length,
                dtStatusDetail(find_path_status, DT_PARTIAL_RESULT) ? 1 : 0);
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
