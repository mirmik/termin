#pragma once

#include <functional>
#include <string>

#include <termin/navmesh/termin_navmesh_components_api.hpp>
#include <Recast.h>

namespace termin {

struct TERMIN_NAVMESH_COMPONENTS_API RecastBuildResult {
    bool success = false;
    std::string error;

    rcPolyMesh* poly_mesh = nullptr;
    rcPolyMeshDetail* detail_mesh = nullptr;
};

struct TERMIN_NAVMESH_COMPONENTS_API RecastNavMeshBuildConfig {
    float cell_size = 0.3f;
    float cell_height = 0.2f;

    float agent_height = 2.0f;
    float agent_radius = 0.5f;
    float agent_max_climb = 0.4f;
    float agent_max_slope = 45.0f;

    int min_region_area = 8;
    int merge_region_area = 20;

    float max_edge_length = 12.0f;
    float max_simplification_error = 1.3f;
    int max_verts_per_poly = 6;

    float detail_sample_dist = 6.0f;
    float detail_sample_max_error = 1.0f;
    bool build_detail_mesh = false;
    int default_area_id = 0;
};

struct TERMIN_NAVMESH_COMPONENTS_API RecastNavMeshBuildDebugHooks {
    std::function<void(const float* verts, int nverts, const int* tris, int ntris)> build_input_mesh;
    std::function<void(rcHeightfield* heightfield)> capture_heightfield;
    std::function<void(rcCompactHeightfield* compact_heightfield)> capture_compact;
    std::function<void(rcContourSet* contours)> capture_contours;
    std::function<void(rcPolyMesh* poly_mesh)> capture_poly_mesh;
    std::function<void(rcPolyMeshDetail* detail_mesh)> capture_detail_mesh;
};

TERMIN_NAVMESH_COMPONENTS_API RecastBuildResult build_recast_navmesh(
    const float* verts,
    int nverts,
    const int* tris,
    int ntris,
    const unsigned char* triangle_area_ids,
    const RecastNavMeshBuildConfig& config,
    const RecastNavMeshBuildDebugHooks* debug_hooks = nullptr);

TERMIN_NAVMESH_COMPONENTS_API RecastBuildResult build_recast_navmesh(
    const float* verts,
    int nverts,
    const int* tris,
    int ntris,
    const RecastNavMeshBuildConfig& config,
    const RecastNavMeshBuildDebugHooks* debug_hooks = nullptr);

TERMIN_NAVMESH_COMPONENTS_API void free_recast_build_result(RecastBuildResult& result);

} // namespace termin
