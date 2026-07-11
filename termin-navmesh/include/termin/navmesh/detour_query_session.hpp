#pragma once

#include <string>
#include <vector>

#include <termin/geom/pose3.hpp>
#include <termin/geom/vec3.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>

class dtNavMesh;
class dtNavMeshQuery;

namespace termin {

struct TERMIN_NAVMESH_COMPONENTS_API DetourRaycastResult {
    bool success = false;
    bool hit = false;
    float t = 0.0f;
    Vec3f hit_position{0.0f, 0.0f, 0.0f};
    Vec3f hit_normal{0.0f, 0.0f, 0.0f};
    std::vector<unsigned long long> visited;
};

struct TERMIN_NAVMESH_COMPONENTS_API DetourClosestPointResult {
    bool success = false;
    bool over_poly = false;
    unsigned long long poly_ref = 0;
    Vec3f point{0.0f, 0.0f, 0.0f};
};

struct TERMIN_NAVMESH_COMPONENTS_API DetourPathPoint {
    Vec3f point{0.0f, 0.0f, 0.0f};
    unsigned char flags = 0;
    unsigned long long poly_ref = 0;
    unsigned char poly_type = 0;
    bool off_mesh_connection = false;
    unsigned int off_mesh_user_id = 0;
    bool linear_segment = false;
    unsigned int linear_user_id = 0;
    unsigned char area = 0;
};

struct TERMIN_NAVMESH_COMPONENTS_API DetourPathResult {
    bool success = false;
    std::vector<DetourPathPoint> points;
};

class TERMIN_NAVMESH_COMPONENTS_API DetourQuerySession {
private:
    std::string _asset_name;
    dtNavMesh* _navmesh = nullptr;
    dtNavMeshQuery* _query = nullptr;
    std::vector<unsigned char> _tile_blob;

public:
    float query_extent_x = 2.0f;
    float query_extent_y = 4.0f;
    float query_extent_z = 2.0f;
    int max_polys = 256;
    int max_straight_path = 256;

    DetourQuerySession();
    ~DetourQuerySession();

    DetourQuerySession(const DetourQuerySession&) = delete;
    DetourQuerySession& operator=(const DetourQuerySession&) = delete;

    bool load_single_tile_data(const unsigned char* data, int data_size, const std::string& asset_name = "");
    bool load_single_tile_data(const std::vector<unsigned char>& data, const std::string& asset_name = "");
    void clear();
    bool is_ready() const;

    std::vector<Vec3f> find_path(
        const Vec3f& start,
        const Vec3f& end);

    DetourPathResult find_detailed_path(
        const Vec3f& start,
        const Vec3f& end);

    DetourRaycastResult raycast(
        const Vec3f& start,
        const Vec3f& end);

    DetourClosestPointResult closest_point(const Vec3f& point);

    std::vector<Vec3f> find_path_world(
        const Pose3& bake_frame,
        const Vec3f& start,
        const Vec3f& end);

    DetourPathResult find_detailed_path_world(
        const Pose3& bake_frame,
        const Vec3f& start,
        const Vec3f& end);

    DetourRaycastResult raycast_world(
        const Pose3& bake_frame,
        const Vec3f& start,
        const Vec3f& end);

    DetourClosestPointResult closest_point_world(
        const Pose3& bake_frame,
        const Vec3f& point);

private:
    bool find_nearest_poly(const Vec3f& point,
                           unsigned long long& poly_ref,
                           float nearest[3],
                           bool* over_poly = nullptr);
};

} // namespace termin
