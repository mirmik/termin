#pragma once

#include <array>
#include <string>
#include <vector>

#include <termin/navmesh/termin_navmesh_components_api.hpp>

class dtNavMesh;
class dtNavMeshQuery;

namespace termin {

struct TERMIN_NAVMESH_COMPONENTS_API DetourRaycastResult {
    bool success = false;
    bool hit = false;
    float t = 0.0f;
    std::array<float, 3> hit_position{0.0f, 0.0f, 0.0f};
    std::array<float, 3> hit_normal{0.0f, 0.0f, 0.0f};
    std::vector<unsigned long long> visited;
};

struct TERMIN_NAVMESH_COMPONENTS_API DetourClosestPointResult {
    bool success = false;
    bool over_poly = false;
    unsigned long long poly_ref = 0;
    std::array<float, 3> point{0.0f, 0.0f, 0.0f};
};

struct TERMIN_NAVMESH_COMPONENTS_API DetourPathPoint {
    std::array<float, 3> point{0.0f, 0.0f, 0.0f};
    unsigned char flags = 0;
    unsigned long long poly_ref = 0;
    bool off_mesh_connection = false;
    unsigned int off_mesh_user_id = 0;
    unsigned char area = 0;
};

struct TERMIN_NAVMESH_COMPONENTS_API DetourPathResult {
    bool success = false;
    std::vector<DetourPathPoint> points;
};

class TERMIN_NAVMESH_COMPONENTS_API DetourQuerySession {
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

    std::vector<std::array<float, 3>> find_path(
        const std::array<float, 3>& start,
        const std::array<float, 3>& end);

    DetourPathResult find_detailed_path(
        const std::array<float, 3>& start,
        const std::array<float, 3>& end);

    DetourRaycastResult raycast(
        const std::array<float, 3>& start,
        const std::array<float, 3>& end);

    DetourClosestPointResult closest_point(const std::array<float, 3>& point);

private:
    std::string _asset_name;
    dtNavMesh* _navmesh = nullptr;
    dtNavMeshQuery* _query = nullptr;
    std::vector<unsigned char> _tile_blob;

    bool find_nearest_poly(const std::array<float, 3>& point,
                           unsigned long long& poly_ref,
                           float nearest[3],
                           bool* over_poly = nullptr);
};

} // namespace termin
