#pragma once

// RecastNavMeshBuilder - builds navigation mesh from triangle geometry using Recast.
// Provides debug data capture for visualization of intermediate stages.

#include "recast_debug_data.hpp"
#include <Recast.h>
#include <string>

namespace termin {

// Build configuration
struct RecastConfig {
    // Rasterization
    float cell_size = 0.3f;      // XZ cell size (smaller = more detail, slower)
    float cell_height = 0.2f;    // Y cell size

    // Agent parameters
    float agent_height = 2.0f;   // Agent height
    float agent_radius = 0.5f;   // Agent radius (for erosion)
    float agent_max_climb = 0.4f;   // Max step height
    float agent_max_slope = 45.0f;  // Max walkable slope (degrees)

    // Region building
    int min_region_area = 8;     // Min cells for a region (filters noise)
    int merge_region_area = 20;  // Regions smaller than this merge with neighbors

    // Polygonization
    float max_edge_length = 12.0f;       // Max edge length (0 = no limit)
    float max_simplification_error = 1.3f;  // Contour simplification tolerance
    int max_verts_per_poly = 6;          // Max vertices per polygon (3-6)

    // Detail mesh
    float detail_sample_dist = 6.0f;        // Detail mesh sampling distance
    float detail_sample_max_error = 1.0f;   // Detail mesh max error
    bool build_detail_mesh = false;         // Build detail mesh for height accuracy
};

// Result of navmesh build
struct RecastBuildResult {
    bool success = false;
    std::string error;

    // Resulting meshes (caller takes ownership, must call free_result)
    rcPolyMesh* poly_mesh = nullptr;
    rcPolyMeshDetail* detail_mesh = nullptr;
};

// NavMesh builder using Recast library
class RecastNavMeshBuilder {
public:
    RecastConfig config;

    // Debug capture flags
    bool capture_heightfield = false;
    bool capture_compact = false;
    bool capture_contours = false;
    bool capture_poly_mesh = false;
    bool capture_detail_mesh = false;

    // Captured debug data (filled during build if capture flags are set)
    RecastDebugData debug_data;

    RecastNavMeshBuilder() = default;
    ~RecastNavMeshBuilder() = default;

    // Build navmesh from triangle soup
    // verts: float[nverts * 3] - vertex positions (x, y, z)
    // tris: int[ntris * 3] - triangle indices
    RecastBuildResult build(const float* verts, int nverts,
                            const int* tris, int ntris);

    // Free result meshes
    static void free_result(RecastBuildResult& result);

private:
    // Capture debug data from Recast structures
    void capture_heightfield_data(rcHeightfield* hf);
    void capture_compact_data(rcCompactHeightfield* chf);
    void capture_contour_data(rcContourSet* cset);
    void capture_poly_mesh_data(rcPolyMesh* pmesh);
    void capture_detail_mesh_data(rcPolyMeshDetail* dmesh);
};

} // namespace termin
