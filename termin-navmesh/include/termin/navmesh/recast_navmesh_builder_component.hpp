#pragma once

// RecastNavMeshBuilderComponent - C++ component for building NavMesh using Recast.
// Provides debug data capture and visualization of intermediate stages.

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/render/drawable.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <termin/navmesh/recast_debug_data.hpp>
#include <termin/navmesh/navmesh_keeper_component.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>
#include <Recast.h>
#include <string>

namespace termin {

// Source of mesh geometry for navmesh building
enum class MeshSource : int {
    CurrentMesh = 0,      // Only current entity mesh
    AllDescendants = 1,   // All descendant meshes (including current entity)
};

// Result of navmesh build
struct TERMIN_NAVMESH_COMPONENTS_API RecastBuildResult {
    bool success = false;
    std::string error;

    // Resulting meshes (caller takes ownership, must call free_result)
    rcPolyMesh* poly_mesh = nullptr;
    rcPolyMeshDetail* detail_mesh = nullptr;
};

// NavMesh builder component using Recast library
class TERMIN_NAVMESH_COMPONENTS_API RecastNavMeshBuilderComponent : public CxxComponent, public Drawable {
public:
    // --- Configuration fields (exposed to inspector) ---

    // Agent type selection (from Navigation Settings)
    std::string agent_type_name = "Human";
    int area_id = 0;

    // Rasterization
    float cell_size = 0.3f;
    float cell_height = 0.2f;

    // Agent parameters (set from agent_type_name via apply_agent_type())
    float agent_height = 2.0f;
    float agent_radius = 0.5f;
    float agent_max_climb = 0.4f;
    float agent_max_slope = 45.0f;

    // Region building
    int min_region_area = 8;
    int merge_region_area = 20;

    // Polygonization
    float max_edge_length = 12.0f;
    float max_simplification_error = 1.3f;
    int max_verts_per_poly = 6;

    // Detail mesh
    float detail_sample_dist = 6.0f;
    float detail_sample_max_error = 1.0f;
    bool build_detail_mesh = false;

    // Mesh source
    int mesh_source = static_cast<int>(MeshSource::CurrentMesh);

    // Debug capture flags (auto-enable corresponding show flags)
    bool capture_heightfield = false;
    bool capture_compact = false;
    bool capture_contours = false;
    bool capture_poly_mesh = false;
    bool capture_detail_mesh = false;

    // Debug visualization flags
    bool show_input_mesh = false;
    bool show_heightfield = false;
    bool show_regions = false;
    bool show_distance_field = false;
    bool show_contours = false;
    bool show_poly_mesh = false;
    bool show_detail_mesh = false;

    // Apply agent type parameters (called from Python before build)
    void apply_agent_type(float height, float radius, float max_climb, float max_slope);

    // Build from entity's MeshRenderer (called by inspector button)
    void build_from_entity();

    // --- Runtime state ---

    // Captured debug data (filled during build if capture flags are set)
    RecastDebugData debug_data;

    // Last build result
    RecastBuildResult last_result;

    // --- Methods ---

    RecastNavMeshBuilderComponent();
    ~RecastNavMeshBuilderComponent() override;

    static void register_type();

    // Build navmesh from triangle soup
    // verts: float[nverts * 3] - vertex positions (x, y, z)
    // tris: int[ntris * 3] - triangle indices
    RecastBuildResult build(const float* verts, int nverts,
                            const int* tris, int ntris);

    // Free result meshes
    static void free_result(RecastBuildResult& result);

    // Clear debug data and meshes
    void clear_debug_data();

    // --- Drawable interface ---

    std::set<std::string> get_phase_marks() const override;
    void draw_geometry(const RenderContext& context, int geometry_id = 0) override;
    std::vector<GeometryDrawCall> get_geometry_draws(const std::string* phase_mark = nullptr) override;
    tc_mesh* get_mesh_for_phase(const std::string& phase_mark, int geometry_id) const override;

private:
    // Geometry IDs for different debug layers
    static constexpr int GEOMETRY_INPUT_MESH = 0;
    static constexpr int GEOMETRY_HEIGHTFIELD = 1;
    static constexpr int GEOMETRY_REGIONS = 2;
    static constexpr int GEOMETRY_DISTANCE_FIELD = 3;
    static constexpr int GEOMETRY_CONTOURS = 4;
    static constexpr int GEOMETRY_POLY_MESH = 5;
    static constexpr int GEOMETRY_DETAIL_MESH = 6;

    // Debug meshes
    TcMesh _input_mesh;
    TcMesh _heightfield_mesh;
    TcMesh _regions_mesh;
    TcMesh _distance_field_mesh;
    TcMesh _contours_mesh;
    TcMesh _poly_mesh_debug;
    TcMesh _detail_mesh_debug;

    // Debug material
    TcMaterial _debug_material;

    // Mesh generation from debug data
    void rebuild_debug_meshes();
    void build_input_mesh(const float* verts, int nverts, const int* tris, int ntris);
    void build_heightfield_mesh();
    void build_regions_mesh();
    void build_distance_field_mesh();
    void build_contours_mesh();
    void build_poly_mesh_debug();
    void build_detail_mesh_debug();

    // Get or create debug material
    TcMaterial get_debug_material();

    // Capture debug data from Recast structures
    void capture_heightfield_data(rcHeightfield* hf);
    void capture_compact_data(rcCompactHeightfield* chf);
    void capture_contour_data(rcContourSet* cset);
    void capture_poly_mesh_data(rcPolyMesh* pmesh);
    void capture_detail_mesh_data(rcPolyMeshDetail* dmesh);
    bool save_detour_asset(const RecastBuildResult& result);
};

} // namespace termin
