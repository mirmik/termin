#pragma once

#include <string>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/navmesh/detour_query_session.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>

namespace termin {

class TERMIN_NAVMESH_COMPONENTS_API DetourPathfindingWorldComponent : public CxxComponent {
public:
    std::string navmesh_uuid;
    float query_extent_x = 2.0f;
    float query_extent_y = 4.0f;
    float query_extent_z = 2.0f;
    int max_polys = 256;
    int max_straight_path = 256;

    DetourPathfindingWorldComponent();
    ~DetourPathfindingWorldComponent() override;

    static void register_type();

    void on_added() override;
    void on_removed() override;

    bool rebuild();
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

    std::vector<std::array<float, 3>> find_path_world(
        const Pose3& bake_frame,
        const std::array<float, 3>& start,
        const std::array<float, 3>& end);

    DetourPathResult find_detailed_path_world(
        const Pose3& bake_frame,
        const std::array<float, 3>& start,
        const std::array<float, 3>& end);

    DetourRaycastResult raycast_world(
        const Pose3& bake_frame,
        const std::array<float, 3>& start,
        const std::array<float, 3>& end);

    DetourClosestPointResult closest_point_world(
        const Pose3& bake_frame,
        const std::array<float, 3>& point);

private:
    mutable std::string _loaded_navmesh_uuid;
    mutable std::string _loaded_asset_path;
    mutable bool _load_failed = false;
    std::vector<std::vector<unsigned char>> _tile_blobs;
    DetourQuerySession _query_session;

    bool ensure_query_loaded();
    void sync_query_settings();
};

} // namespace termin
