#pragma once

#include <string>
#include <vector>

#include <termin/navmesh/recast_navmesh_bake.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>

namespace termin {

struct TERMIN_NAVMESH_COMPONENTS_API DetourOffMeshLinkData {
    std::vector<float> verts;
    std::vector<float> radii;
    std::vector<unsigned char> dirs;
    std::vector<unsigned char> areas;
    std::vector<unsigned short> flags;
    std::vector<unsigned int> user_ids;

    int count() const {
        return static_cast<int>(radii.size());
    }
};

struct TERMIN_NAVMESH_COMPONENTS_API DetourLinearLinkData {
    unsigned short from_segment = 0;
    unsigned short to_segment = 0;
    unsigned short from_t = 0;
    unsigned short to_t = 0;
    unsigned char flags = 0;
};

struct TERMIN_NAVMESH_COMPONENTS_API DetourLinearPathData {
    std::vector<float> segment_verts;
    std::vector<unsigned char> areas;
    std::vector<unsigned short> flags;
    std::vector<unsigned int> user_ids;
    std::vector<DetourLinearLinkData> links;

    int count() const {
        return static_cast<int>(areas.size());
    }
};

struct TERMIN_NAVMESH_COMPONENTS_API DetourNavMeshBuildConfig {
    int area_id = 0;
    float agent_height = 2.0f;
    float agent_radius = 0.5f;
    float agent_max_climb = 0.4f;
};

struct TERMIN_NAVMESH_COMPONENTS_API DetourNavMeshTileBuildResult {
    bool success = false;
    std::string error;
    std::vector<unsigned char> data;

    int data_size() const {
        return static_cast<int>(data.size());
    }
};

TERMIN_NAVMESH_COMPONENTS_API DetourNavMeshTileBuildResult build_detour_navmesh_tile_data(
    const RecastBuildResult& recast_result,
    const DetourNavMeshBuildConfig& config,
    const DetourOffMeshLinkData* off_mesh_links = nullptr,
    const DetourLinearPathData* linear_paths = nullptr);

} // namespace termin
