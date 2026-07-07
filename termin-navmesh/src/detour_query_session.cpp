#include <termin/navmesh/detour_query_session.hpp>

#include <termin/navmesh/detour_navmesh_asset_utils.hpp>
#include <termin/navmesh/navmesh_query_space.hpp>
#include <DetourNavMesh.h>
#include <DetourNavMeshQuery.h>
#include <DetourStatus.h>
#include <algorithm>
#include <cmath>
#include <sstream>
#include <tcbase/tc_log.hpp>

namespace termin {

namespace {

const char* detour_poly_type_name(unsigned char type) {
    switch (type) {
        case DT_POLYTYPE_GROUND:
            return "ground";
        case DT_POLYTYPE_OFFMESH_CONNECTION:
            return "offmesh";
        case DT_POLYTYPE_LINEAR:
            return "linear";
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
    append_flag(DT_STRAIGHTPATH_LINEAR, "linear");
    const unsigned char known =
        DT_STRAIGHTPATH_START |
        DT_STRAIGHTPATH_END |
        DT_STRAIGHTPATH_OFFMESH_CONNECTION |
        DT_STRAIGHTPATH_LINEAR;
    const unsigned char unknown = static_cast<unsigned char>(flags & ~known);
    if (unknown != 0) {
        if (wrote) {
            out << "|";
        }
        out << "unknown(0x" << std::hex << static_cast<int>(unknown) << std::dec << ")";
    }
    return out.str();
}

float point_distance(const Vec3f& a, const Vec3f& b) {
    const float dx = a[0] - b[0];
    const float dy = a[1] - b[1];
    const float dz = a[2] - b[2];
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

const float* vec3_ptr(const Vec3f& value) {
    return &value.x;
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
    } else if (type == DT_POLYTYPE_LINEAR) {
        const dtLinearSegment* segment = navmesh->getLinearSegmentByRef(ref);
        if (segment) {
            const float* v0 = &tile->verts[poly->verts[0] * 3];
            const float* v1 = &tile->verts[poly->verts[1] * 3];
            tc_log_info("%s[%d] linear: user_id=%u flags=0x%04x "
                        "start_rc=(%.3f, %.3f, %.3f) end_rc=(%.3f, %.3f, %.3f)",
                        prefix,
                        index,
                        segment->userId,
                        static_cast<unsigned int>(segment->flags),
                        v0[0],
                        v0[1],
                        v0[2],
                        v1[0],
                        v1[1],
                        v1[2]);
        }
    }
}

} // namespace

DetourQuerySession::DetourQuerySession() = default;

DetourQuerySession::~DetourQuerySession() {
    clear();
}

void DetourQuerySession::clear() {
    if (_query) {
        dtFreeNavMeshQuery(_query);
        _query = nullptr;
    }
    if (_navmesh) {
        dtFreeNavMesh(_navmesh);
        _navmesh = nullptr;
    }
    _tile_blob.clear();
    _asset_name.clear();
}

bool DetourQuerySession::is_ready() const {
    return _navmesh != nullptr && _query != nullptr;
}

bool DetourQuerySession::load_single_tile_data(
    const unsigned char* data,
    int data_size,
    const std::string& asset_name)
{
    clear();
    _asset_name = asset_name;
    if (!data || data_size <= 0) {
        tc_log_warn("[DetourQuerySession] cannot load empty Detour tile data");
        return false;
    }

    _tile_blob.assign(data, data + data_size);
    _navmesh = dtAllocNavMesh();
    if (!_navmesh ||
        !dtStatusSucceed(_navmesh->init(_tile_blob.data(), static_cast<int>(_tile_blob.size()), 0))) {
        tc_log_warn("[DetourQuerySession] failed to init Detour navmesh '%s'", _asset_name.c_str());
        clear();
        return false;
    }

    _query = dtAllocNavMeshQuery();
    if (!_query || !dtStatusSucceed(_query->init(_navmesh, std::max(32, max_polys * 4)))) {
        tc_log_warn("[DetourQuerySession] failed to init Detour navmesh query '%s'", _asset_name.c_str());
        clear();
        return false;
    }

    tc_log_info("[DetourQuerySession] loaded '%s'", _asset_name.c_str());
    return true;
}

bool DetourQuerySession::load_single_tile_data(const std::vector<unsigned char>& data,
                                               const std::string& asset_name) {
    return load_single_tile_data(data.data(), static_cast<int>(data.size()), asset_name);
}

bool DetourQuerySession::find_nearest_poly(const Vec3f& point,
                                           unsigned long long& poly_ref,
                                           float nearest[3],
                                           bool* over_poly) {
    poly_ref = 0;
    if (!is_ready()) {
        return false;
    }

    const Vec3f rc_point = termin_to_recast(point);
    const float extents[3] = {query_extent_x, query_extent_z, query_extent_y};
    dtQueryFilter filter;
    filter.setIncludeFlags(0xffff);
    filter.setExcludeFlags(0);

    dtPolyRef ref = 0;
    dtStatus status = over_poly
        ? _query->findNearestPoly(vec3_ptr(rc_point), extents, &filter, &ref, nearest, over_poly)
        : _query->findNearestPoly(vec3_ptr(rc_point), extents, &filter, &ref, nearest);
    if (!dtStatusSucceed(status) || ref == 0) {
        return false;
    }

    poly_ref = static_cast<unsigned long long>(ref);
    return true;
}

DetourClosestPointResult DetourQuerySession::closest_point(const Vec3f& point) {
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

DetourClosestPointResult DetourQuerySession::closest_point_world(
    const Pose3& bake_frame,
    const Vec3f& point)
{
    DetourClosestPointResult result = closest_point(navmesh_world_to_bake_point(bake_frame, point));
    if (result.success) {
        result.point = navmesh_bake_to_world_point(bake_frame, result.point);
    }
    return result;
}

std::vector<Vec3f> DetourQuerySession::find_path(
    const Vec3f& start,
    const Vec3f& end
) {
    std::vector<Vec3f> result;
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

std::vector<Vec3f> DetourQuerySession::find_path_world(
    const Pose3& bake_frame,
    const Vec3f& start,
    const Vec3f& end)
{
    std::vector<Vec3f> result;
    DetourPathResult detailed = find_detailed_path_world(bake_frame, start, end);
    if (!detailed.success) {
        return result;
    }
    result.reserve(detailed.points.size());
    for (const DetourPathPoint& point : detailed.points) {
        result.push_back(point.point);
    }
    return result;
}

DetourPathResult DetourQuerySession::find_detailed_path(
    const Vec3f& start,
    const Vec3f& end
) {
    DetourPathResult result;
    if (!is_ready()) {
        tc_log_warn("[DetourQuerySession] path query failed: navmesh is not ready");
        return result;
    }

    tc_log_info("[DetourQuerySession] path query begin asset='%s' "
                "start=(%.3f, %.3f, %.3f) end=(%.3f, %.3f, %.3f) "
                "extent=(%.3f, %.3f, %.3f) max_polys=%d max_straight=%d",
                _asset_name.c_str(),
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
        tc_log_warn("[DetourQuerySession] path query failed: nearest poly "
                    "start_found=%d start_ref=%llu end_found=%d end_ref=%llu",
                    has_start_poly ? 1 : 0,
                    start_ref_raw,
                    has_end_poly ? 1 : 0,
                    end_ref_raw);
        return result;
    }

    const Vec3f nearest_start_term = recast_to_termin(nearest_start);
    const Vec3f nearest_end_term = recast_to_termin(nearest_end);
    tc_log_info("[DetourQuerySession] nearest start ref=%llu over=%d "
                "point=(%.3f, %.3f, %.3f) snap_dist=%.3f",
                start_ref_raw,
                start_over_poly ? 1 : 0,
                nearest_start_term[0], nearest_start_term[1], nearest_start_term[2],
                point_distance(start, nearest_start_term));
    log_detour_poly_info(_navmesh, "[DetourQuerySession] nearest start poly", 0,
                         static_cast<dtPolyRef>(start_ref_raw));

    tc_log_info("[DetourQuerySession] nearest end ref=%llu over=%d "
                "point=(%.3f, %.3f, %.3f) snap_dist=%.3f",
                end_ref_raw,
                end_over_poly ? 1 : 0,
                nearest_end_term[0], nearest_end_term[1], nearest_end_term[2],
                point_distance(end, nearest_end_term));
    log_detour_poly_info(_navmesh, "[DetourQuerySession] nearest end poly", 0,
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
    tc_log_info("[DetourQuerySession] findPath status=%s path_count=%d",
                find_path_status_text.c_str(),
                path_count);
    if (!dtStatusSucceed(find_path_status) || path_count <= 0) {
        tc_log_warn("[DetourQuerySession] path query failed: findPath returned no corridor");
        return result;
    }

    for (int i = 0; i < path_count; ++i) {
        log_detour_poly_info(_navmesh, "[DetourQuerySession] corridor", i,
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
    tc_log_info("[DetourQuerySession] findStraightPath status=%s straight_count=%d",
                straight_status_text.c_str(),
                straight_count);
    if (!dtStatusSucceed(straight_status) || straight_count <= 0) {
        tc_log_warn("[DetourQuerySession] path query failed: findStraightPath returned no points");
        return result;
    }

    result.success = true;
    result.points.reserve(static_cast<size_t>(straight_count));
    float total_straight_length = 0.0f;
    Vec3f previous_point{0.0f, 0.0f, 0.0f};
    for (int i = 0; i < straight_count; ++i) {
        const dtPolyRef ref = refs[static_cast<size_t>(i)];

        DetourPathPoint point;
        point.point = recast_to_termin(&straight[static_cast<size_t>(i) * 3]);
        point.flags = flags[static_cast<size_t>(i)];
        point.poly_ref = static_cast<unsigned long long>(ref);
        point.off_mesh_connection = (point.flags & DT_STRAIGHTPATH_OFFMESH_CONNECTION) != 0;
        point.linear_segment = (point.flags & DT_STRAIGHTPATH_LINEAR) != 0;

        if (ref != 0) {
            const dtMeshTile* tile = nullptr;
            const dtPoly* poly = nullptr;
            if (dtStatusSucceed(_navmesh->getTileAndPolyByRef(ref, &tile, &poly)) && poly) {
                point.area = poly->getArea();
                point.poly_type = poly->getType();
            }

            if (point.off_mesh_connection) {
                const dtOffMeshConnection* connection = _navmesh->getOffMeshConnectionByRef(ref);
                if (connection) {
                    point.off_mesh_user_id = connection->userId;
                }
            }
            if (point.linear_segment) {
                const dtLinearSegment* segment = _navmesh->getLinearSegmentByRef(ref);
                if (segment) {
                    point.linear_user_id = segment->userId;
                }
            }
        }

        if (i > 0) {
            total_straight_length += point_distance(previous_point, point.point);
        }
        previous_point = point.point;

        const std::string straight_flags = straight_path_flags_to_string(point.flags);
        tc_log_info("[DetourQuerySession] straight[%d]: "
                    "point=(%.3f, %.3f, %.3f) ref=%llu flags=0x%02x(%s) "
                    "area=%u type=%s offmesh=%d offmesh_user_id=%u linear=%d linear_user_id=%u",
                    i,
                    point.point[0], point.point[1], point.point[2],
                    point.poly_ref,
                    static_cast<unsigned int>(point.flags),
                    straight_flags.c_str(),
                    static_cast<unsigned int>(point.area),
                    detour_poly_type_name(point.poly_type),
                    point.off_mesh_connection ? 1 : 0,
                    point.off_mesh_user_id,
                    point.linear_segment ? 1 : 0,
                    point.linear_user_id);
        log_detour_poly_info(_navmesh, "[DetourQuerySession] straight poly", i, ref);

        result.points.push_back(point);
    }
    tc_log_info("[DetourQuerySession] path query success points=%zu corridor=%d "
                "straight_length=%.3f partial=%d",
                result.points.size(),
                path_count,
                total_straight_length,
                dtStatusDetail(find_path_status, DT_PARTIAL_RESULT) ? 1 : 0);
    return result;
}

DetourPathResult DetourQuerySession::find_detailed_path_world(
    const Pose3& bake_frame,
    const Vec3f& start,
    const Vec3f& end)
{
    DetourPathResult result = find_detailed_path(
        navmesh_world_to_bake_point(bake_frame, start),
        navmesh_world_to_bake_point(bake_frame, end));
    if (!result.success) {
        return result;
    }
    for (DetourPathPoint& point : result.points) {
        point.point = navmesh_bake_to_world_point(bake_frame, point.point);
    }
    return result;
}

DetourRaycastResult DetourQuerySession::raycast(
    const Vec3f& start,
    const Vec3f& end
) {
    DetourRaycastResult result;
    if (!is_ready()) {
        return result;
    }

    float nearest_start[3] = {0.0f, 0.0f, 0.0f};
    unsigned long long start_ref_raw = 0;
    if (!find_nearest_poly(start, start_ref_raw, nearest_start)) {
        return result;
    }

    const Vec3f rc_end = termin_to_recast(end);
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
            vec3_ptr(rc_end),
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

DetourRaycastResult DetourQuerySession::raycast_world(
    const Pose3& bake_frame,
    const Vec3f& start,
    const Vec3f& end)
{
    DetourRaycastResult result = raycast(
        navmesh_world_to_bake_point(bake_frame, start),
        navmesh_world_to_bake_point(bake_frame, end));
    if (result.success) {
        result.hit_position = navmesh_bake_to_world_point(bake_frame, result.hit_position);
        result.hit_normal = navmesh_bake_to_world_vector(bake_frame, result.hit_normal);
    }
    return result;
}

} // namespace termin
