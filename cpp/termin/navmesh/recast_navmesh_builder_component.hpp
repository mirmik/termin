#pragma once

// RecastNavMeshBuilderComponent - C++ component for building NavMesh using Recast.
// Provides debug data capture and visualization of intermediate stages.

#include "../entity/component.hpp"
#include "../entity/component_registry.hpp"
#include "../render/drawable.hpp"
#include "../mesh/tc_mesh_handle.hpp"
#include "../material/tc_material_handle.hpp"
#include "recast_debug_data.hpp"
#include <Recast.h>
#include <string>

namespace termin {

// Source of mesh geometry for navmesh building
enum class MeshSource : int {
    CurrentMesh = 0,      // Only current entity mesh
    AllDescendants = 1,   // All descendant meshes (including current entity)
};

// Result of navmesh build
struct RecastBuildResult {
    bool success = false;
    std::string error;

    // Resulting meshes (caller takes ownership, must call free_result)
    rcPolyMesh* poly_mesh = nullptr;
    rcPolyMeshDetail* detail_mesh = nullptr;
};

// NavMesh builder component using Recast library
class RecastNavMeshBuilderComponent : public CxxComponent, public Drawable {
public:
    // --- Configuration fields (exposed to inspector) ---

    // Agent type selection (from Navigation Settings)
    std::string agent_type_name = "Human";

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

    // Inspector field declarations - Configuration
    INSPECT_FIELD(RecastNavMeshBuilderComponent, agent_type_name, "Agent Type", "agent_type")
    INSPECT_FIELD(RecastNavMeshBuilderComponent, cell_size, "Cell Size", "float", 0.05, 2.0, 0.05)
    INSPECT_FIELD(RecastNavMeshBuilderComponent, cell_height, "Cell Height", "float", 0.05, 2.0, 0.05)
    INSPECT_FIELD(RecastNavMeshBuilderComponent, min_region_area, "Min Region Area", "int", 0, 100, 1)
    INSPECT_FIELD(RecastNavMeshBuilderComponent, merge_region_area, "Merge Region Area", "int", 0, 100, 1)
    INSPECT_FIELD(RecastNavMeshBuilderComponent, max_edge_length, "Max Edge Length", "float", 0.0, 50.0, 0.5)
    INSPECT_FIELD(RecastNavMeshBuilderComponent, max_simplification_error, "Max Simplification Error", "float", 0.0, 5.0, 0.1)
    INSPECT_FIELD(RecastNavMeshBuilderComponent, max_verts_per_poly, "Max Verts Per Poly", "int", 3, 6, 1)
    INSPECT_FIELD(RecastNavMeshBuilderComponent, build_detail_mesh, "Build Detail Mesh", "bool")

    // Mesh source selection
    INSPECT_FIELD_CHOICES(RecastNavMeshBuilderComponent, mesh_source, "Mesh Source", "enum",
        {"0", "Current Mesh"}, {"1", "All Descendants"})

    // Inspector field declarations - Debug capture
    INSPECT_FIELD(RecastNavMeshBuilderComponent, capture_heightfield, "Capture Heightfield (1)", "bool")
    INSPECT_FIELD(RecastNavMeshBuilderComponent, capture_compact, "Capture Compact (2)", "bool")
    INSPECT_FIELD(RecastNavMeshBuilderComponent, capture_contours, "Capture Contours (3)", "bool")
    INSPECT_FIELD(RecastNavMeshBuilderComponent, capture_poly_mesh, "Capture Poly Mesh (4)", "bool")
    INSPECT_FIELD(RecastNavMeshBuilderComponent, capture_detail_mesh, "Capture Detail Mesh (5)", "bool")

    // Inspector field declarations - Debug visualization
    INSPECT_FIELD(RecastNavMeshBuilderComponent, show_input_mesh, "Show Input Mesh (0)", "bool")
    INSPECT_FIELD(RecastNavMeshBuilderComponent, show_heightfield, "Show Heightfield (1)", "bool")
    INSPECT_FIELD(RecastNavMeshBuilderComponent, show_regions, "Show Regions (2)", "bool")
    INSPECT_FIELD(RecastNavMeshBuilderComponent, show_distance_field, "Show Distance Field (3)", "bool")
    INSPECT_FIELD(RecastNavMeshBuilderComponent, show_contours, "Show Contours (4)", "bool")
    INSPECT_FIELD(RecastNavMeshBuilderComponent, show_poly_mesh, "Show Poly Mesh (5)", "bool")
    INSPECT_FIELD(RecastNavMeshBuilderComponent, show_detail_mesh, "Show Detail Mesh (6)", "bool")

    // Apply agent type parameters (called from Python before build)
    void apply_agent_type(float height, float radius, float max_climb, float max_slope);

    // Build from entity's MeshRenderer (called by inspector button)
    void build_from_entity();

    INSPECT_BUTTON(RecastNavMeshBuilderComponent, build_btn, "Build NavMesh", &RecastNavMeshBuilderComponent::build_from_entity)

    // --- Runtime state ---

    // Captured debug data (filled during build if capture flags are set)
    RecastDebugData debug_data;

    // Last build result
    RecastBuildResult last_result;

    // --- Methods ---

    RecastNavMeshBuilderComponent();
    ~RecastNavMeshBuilderComponent() override;

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
};

REGISTER_COMPONENT(RecastNavMeshBuilderComponent, Component);

} // namespace termin
