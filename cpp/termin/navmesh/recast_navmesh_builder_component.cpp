#include "recast_navmesh_builder_component.hpp"
#include "../render/mesh_renderer.hpp"
#include "../geom/mat44.hpp"
#include <array>
#include <cstring>
#include <cmath>
#include <set>
#include <tc_log.hpp>

namespace termin {

// Simple context for logging
class BuildContext : public rcContext {
public:
    std::string last_error;

protected:
    void doLog(const rcLogCategory category, const char* msg, const int len) override {
        if (category == RC_LOG_ERROR) {
            last_error = std::string(msg, len);
        }
    }
};

RecastNavMeshBuilderComponent::RecastNavMeshBuilderComponent() {
    // type_entry is set by registry when component is created via factory
    install_drawable_vtable(&_c);
}

RecastNavMeshBuilderComponent::~RecastNavMeshBuilderComponent() {
    free_result(last_result);
}

void RecastNavMeshBuilderComponent::apply_agent_type(float height, float radius, float max_climb, float max_slope) {
    agent_height = height;
    agent_radius = radius;
    agent_max_climb = max_climb;
    agent_max_slope = max_slope;
    tc_log_info("[NavMesh] Applied agent type: height=%.2f, radius=%.2f, max_climb=%.2f, max_slope=%.1f",
        height, radius, max_climb, max_slope);
}

void RecastNavMeshBuilderComponent::clear_debug_data() {
    debug_data.clear();

    // Clear meshes (GPU resources are freed automatically via tc_mesh)
    _heightfield_mesh = TcMesh();
    _regions_mesh = TcMesh();
    _distance_field_mesh = TcMesh();
    _contours_mesh = TcMesh();
    _poly_mesh_debug = TcMesh();
    _detail_mesh_debug = TcMesh();
}

RecastBuildResult RecastNavMeshBuilderComponent::build(const float* verts, int nverts,
                                                        const int* tris, int ntris) {
    // Free previous result
    free_result(last_result);
    clear_debug_data();

    RecastBuildResult result;

    if (verts == nullptr || nverts == 0 || tris == nullptr || ntris == 0) {
        result.error = "Invalid input: empty geometry";
        return result;
    }

    // Build debug mesh from input geometry (in Recast coordinates)
    build_input_mesh(verts, nverts, tris, ntris);

    BuildContext ctx;

    // Calculate bounds
    float bmin[3], bmax[3];
    rcCalcBounds(verts, nverts, bmin, bmax);
    tc_log_info("[NavMesh] Bounds: min=(%.2f, %.2f, %.2f) max=(%.2f, %.2f, %.2f)",
        bmin[0], bmin[1], bmin[2], bmax[0], bmax[1], bmax[2]);

    // Initialize config
    rcConfig cfg;
    memset(&cfg, 0, sizeof(cfg));

    cfg.cs = cell_size;
    cfg.ch = cell_height;
    cfg.walkableSlopeAngle = agent_max_slope;
    cfg.walkableHeight = static_cast<int>(std::ceil(agent_height / cfg.ch));
    cfg.walkableClimb = static_cast<int>(std::floor(agent_max_climb / cfg.ch));
    cfg.walkableRadius = static_cast<int>(std::ceil(agent_radius / cfg.cs));
    cfg.maxEdgeLen = static_cast<int>(max_edge_length / cfg.cs);
    cfg.maxSimplificationError = max_simplification_error;
    cfg.minRegionArea = min_region_area;
    cfg.mergeRegionArea = merge_region_area;
    cfg.maxVertsPerPoly = max_verts_per_poly;
    cfg.detailSampleDist = detail_sample_dist < 0.9f ? 0 : cfg.cs * detail_sample_dist;
    cfg.detailSampleMaxError = cfg.ch * detail_sample_max_error;

    rcVcopy(cfg.bmin, bmin);
    rcVcopy(cfg.bmax, bmax);
    rcCalcGridSize(cfg.bmin, cfg.bmax, cfg.cs, &cfg.width, &cfg.height);

    tc_log_info("[NavMesh] Config: cs=%.3f ch=%.3f grid=%dx%d",
        cfg.cs, cfg.ch, cfg.width, cfg.height);
    tc_log_info("[NavMesh] Agent: height=%d climb=%d radius=%d slope=%.1f",
        cfg.walkableHeight, cfg.walkableClimb, cfg.walkableRadius, cfg.walkableSlopeAngle);
    tc_log_info("[NavMesh] Region: minArea=%d mergeArea=%d", cfg.minRegionArea, cfg.mergeRegionArea);
    tc_log_info("[NavMesh] Edge: maxLen=%d maxSimplErr=%.2f maxVertsPerPoly=%d",
        cfg.maxEdgeLen, cfg.maxSimplificationError, cfg.maxVertsPerPoly);

    // Stage 1: Create heightfield
    rcHeightfield* hf = rcAllocHeightfield();
    if (!hf) {
        result.error = "Failed to allocate heightfield";
        return result;
    }

    if (!rcCreateHeightfield(&ctx, *hf, cfg.width, cfg.height,
                             cfg.bmin, cfg.bmax, cfg.cs, cfg.ch)) {
        result.error = "Failed to create heightfield";
        rcFreeHeightField(hf);
        return result;
    }

    // Mark walkable triangles
    std::vector<unsigned char> tri_areas(ntris, RC_WALKABLE_AREA);
    rcMarkWalkableTriangles(&ctx, cfg.walkableSlopeAngle,
                            verts, nverts, tris, ntris, tri_areas.data());

    // Count walkable triangles
    int walkable_count = 0;
    for (int i = 0; i < ntris; i++) {
        if (tri_areas[i] != RC_NULL_AREA) walkable_count++;
    }
    tc_log_info("[NavMesh] Walkable triangles: %d / %d", walkable_count, ntris);

    // Rasterize triangles
    if (!rcRasterizeTriangles(&ctx, verts, nverts, tris, tri_areas.data(), ntris,
                              *hf, cfg.walkableClimb)) {
        result.error = "Failed to rasterize triangles";
        rcFreeHeightField(hf);
        return result;
    }

    // Count spans before filtering
    int span_count_before = 0;
    for (int i = 0; i < hf->width * hf->height; i++) {
        for (rcSpan* s = hf->spans[i]; s; s = s->next) span_count_before++;
    }
    tc_log_info("[NavMesh] Heightfield spans after rasterize: %d", span_count_before);

    // Filter walkable surfaces
    rcFilterLowHangingWalkableObstacles(&ctx, cfg.walkableClimb, *hf);
    rcFilterLedgeSpans(&ctx, cfg.walkableHeight, cfg.walkableClimb, *hf);
    rcFilterWalkableLowHeightSpans(&ctx, cfg.walkableHeight, *hf);

    // Count spans after filtering
    int span_count_after = 0;
    int walkable_spans = 0;
    for (int i = 0; i < hf->width * hf->height; i++) {
        for (rcSpan* s = hf->spans[i]; s; s = s->next) {
            span_count_after++;
            if (s->area != RC_NULL_AREA) walkable_spans++;
        }
    }
    tc_log_info("[NavMesh] After filtering: %d spans, %d walkable", span_count_after, walkable_spans);

    // Capture heightfield debug data
    if (capture_heightfield) {
        capture_heightfield_data(hf);
    }

    // Stage 2: Build compact heightfield
    rcCompactHeightfield* chf = rcAllocCompactHeightfield();
    if (!chf) {
        result.error = "Failed to allocate compact heightfield";
        rcFreeHeightField(hf);
        return result;
    }

    if (!rcBuildCompactHeightfield(&ctx, cfg.walkableHeight, cfg.walkableClimb, *hf, *chf)) {
        result.error = "Failed to build compact heightfield";
        rcFreeCompactHeightfield(chf);
        rcFreeHeightField(hf);
        return result;
    }

    tc_log_info("[NavMesh] Compact heightfield: %d spans", chf->spanCount);

    // Done with heightfield
    rcFreeHeightField(hf);
    hf = nullptr;

    // Erode walkable area by agent radius
    if (!rcErodeWalkableArea(&ctx, cfg.walkableRadius, *chf)) {
        result.error = "Failed to erode walkable area";
        rcFreeCompactHeightfield(chf);
        return result;
    }

    // Count walkable after erode
    int walkable_after_erode = 0;
    for (int i = 0; i < chf->spanCount; i++) {
        if (chf->areas[i] != RC_NULL_AREA) walkable_after_erode++;
    }
    tc_log_info("[NavMesh] After erode (radius=%d): %d walkable spans", cfg.walkableRadius, walkable_after_erode);

    // Build distance field
    if (!rcBuildDistanceField(&ctx, *chf)) {
        result.error = "Failed to build distance field";
        rcFreeCompactHeightfield(chf);
        return result;
    }

    tc_log_info("[NavMesh] Distance field built, maxDistance=%d", chf->maxDistance);

    // Build regions (watershed algorithm)
    if (!rcBuildRegions(&ctx, *chf, cfg.borderSize, cfg.minRegionArea, cfg.mergeRegionArea)) {
        result.error = "Failed to build regions";
        rcFreeCompactHeightfield(chf);
        return result;
    }

    // Count regions
    int max_region = 0;
    for (int i = 0; i < chf->spanCount; i++) {
        if (chf->spans[i].reg > max_region) max_region = chf->spans[i].reg;
    }
    tc_log_info("[NavMesh] Regions built: %d regions", max_region);

    // Capture compact heightfield debug data
    if (capture_compact) {
        capture_compact_data(chf);
    }

    // Stage 3: Build contours
    rcContourSet* cset = rcAllocContourSet();
    if (!cset) {
        result.error = "Failed to allocate contour set";
        rcFreeCompactHeightfield(chf);
        return result;
    }

    if (!rcBuildContours(&ctx, *chf, cfg.maxSimplificationError, cfg.maxEdgeLen, *cset)) {
        result.error = "Failed to build contours";
        rcFreeContourSet(cset);
        rcFreeCompactHeightfield(chf);
        return result;
    }

    tc_log_info("[NavMesh] Contours built: %d contours", cset->nconts);
    for (int i = 0; i < cset->nconts && i < 5; i++) {
        tc_log_info("[NavMesh]   contour[%d]: %d verts, region=%d, area=%d",
            i, cset->conts[i].nverts, cset->conts[i].reg, cset->conts[i].area);
    }
    if (cset->nconts > 5) {
        tc_log_info("[NavMesh]   ... and %d more contours", cset->nconts - 5);
    }

    // Capture contours debug data
    if (capture_contours) {
        capture_contour_data(cset);
    }

    // Stage 4: Build polygon mesh
    rcPolyMesh* pmesh = rcAllocPolyMesh();
    if (!pmesh) {
        result.error = "Failed to allocate polygon mesh";
        rcFreeContourSet(cset);
        rcFreeCompactHeightfield(chf);
        return result;
    }

    if (!rcBuildPolyMesh(&ctx, *cset, cfg.maxVertsPerPoly, *pmesh)) {
        result.error = "Failed to build polygon mesh";
        rcFreePolyMesh(pmesh);
        rcFreeContourSet(cset);
        rcFreeCompactHeightfield(chf);
        return result;
    }

    tc_log_info("[NavMesh] PolyMesh built: %d verts, %d polys (nvp=%d)",
        pmesh->nverts, pmesh->npolys, pmesh->nvp);

    // Done with contours
    rcFreeContourSet(cset);
    cset = nullptr;

    // Capture poly mesh debug data
    if (capture_poly_mesh) {
        capture_poly_mesh_data(pmesh);
    }

    // Stage 5: Build detail mesh (optional)
    rcPolyMeshDetail* dmesh = nullptr;
    if (build_detail_mesh) {
        dmesh = rcAllocPolyMeshDetail();
        if (!dmesh) {
            result.error = "Failed to allocate detail mesh";
            rcFreePolyMesh(pmesh);
            rcFreeCompactHeightfield(chf);
            return result;
        }

        if (!rcBuildPolyMeshDetail(&ctx, *pmesh, *chf,
                                   cfg.detailSampleDist, cfg.detailSampleMaxError, *dmesh)) {
            result.error = "Failed to build detail mesh";
            rcFreePolyMeshDetail(dmesh);
            rcFreePolyMesh(pmesh);
            rcFreeCompactHeightfield(chf);
            return result;
        }

        tc_log_info("[NavMesh] DetailMesh built: %d meshes, %d verts, %d tris",
            dmesh->nmeshes, dmesh->nverts, dmesh->ntris);
        tc_log_info("[NavMesh] DetailMesh params: sampleDist=%.2f, sampleMaxError=%.2f",
            cfg.detailSampleDist, cfg.detailSampleMaxError);

        // Log first few detail verts vs poly verts for comparison
        if (dmesh->nverts > 0 && pmesh->nverts > 0) {
            tc_log_info("[NavMesh] PolyMesh vert[0] (voxel): (%d, %d, %d) -> world: (%.2f, %.2f, %.2f)",
                pmesh->verts[0], pmesh->verts[1], pmesh->verts[2],
                pmesh->bmin[0] + pmesh->verts[0] * pmesh->cs,
                pmesh->bmin[1] + pmesh->verts[1] * pmesh->ch,
                pmesh->bmin[2] + pmesh->verts[2] * pmesh->cs);
            tc_log_info("[NavMesh] DetailMesh vert[0] (float): (%.2f, %.2f, %.2f)",
                dmesh->verts[0], dmesh->verts[1], dmesh->verts[2]);
        }

        // Capture detail mesh debug data
        if (capture_detail_mesh) {
            capture_detail_mesh_data(dmesh);
        }
    }

    // Done with compact heightfield
    rcFreeCompactHeightfield(chf);

    // Success
    result.success = true;
    result.poly_mesh = pmesh;
    result.detail_mesh = dmesh;

    // Store as last result
    last_result = result;

    // Rebuild debug meshes
    rebuild_debug_meshes();

    return result;
}

void RecastNavMeshBuilderComponent::free_result(RecastBuildResult& result) {
    if (result.poly_mesh) {
        rcFreePolyMesh(result.poly_mesh);
        result.poly_mesh = nullptr;
    }
    if (result.detail_mesh) {
        rcFreePolyMeshDetail(result.detail_mesh);
        result.detail_mesh = nullptr;
    }
    result.success = false;
}

// --- Drawable interface ---

std::set<std::string> RecastNavMeshBuilderComponent::get_phase_marks() const {
    std::set<std::string> marks;

    // Only participate in rendering if we have something to show
    if (show_input_mesh || show_heightfield || show_regions || show_distance_field ||
        show_contours || show_poly_mesh || show_detail_mesh) {
        marks.insert("opaque");
    }

    return marks;
}

void RecastNavMeshBuilderComponent::draw_geometry(const RenderContext& context, int geometry_id) {
    auto draw_mesh = [](TcMesh& mesh) {
        tc_mesh* m = mesh.get();
        if (m) {
            tc_mesh_upload_gpu(m);
            tc_mesh_draw_gpu(m);
        }
    };

    if (geometry_id == GEOMETRY_INPUT_MESH) {
        if (show_input_mesh && _input_mesh.is_valid()) {
            draw_mesh(_input_mesh);
        }
    }

    if (geometry_id == 0 || geometry_id == GEOMETRY_HEIGHTFIELD) {
        if (show_heightfield && _heightfield_mesh.is_valid()) {
            draw_mesh(_heightfield_mesh);
        }
    }

    if (geometry_id == 0 || geometry_id == GEOMETRY_REGIONS) {
        if (show_regions && _regions_mesh.is_valid()) {
            draw_mesh(_regions_mesh);
        }
    }

    if (geometry_id == 0 || geometry_id == GEOMETRY_DISTANCE_FIELD) {
        if (show_distance_field && _distance_field_mesh.is_valid()) {
            draw_mesh(_distance_field_mesh);
        }
    }

    if (geometry_id == 0 || geometry_id == GEOMETRY_CONTOURS) {
        if (show_contours && _contours_mesh.is_valid()) {
            draw_mesh(_contours_mesh);
        }
    }

    if (geometry_id == 0 || geometry_id == GEOMETRY_POLY_MESH) {
        if (show_poly_mesh && _poly_mesh_debug.is_valid()) {
            draw_mesh(_poly_mesh_debug);
        }
    }

    if (geometry_id == 0 || geometry_id == GEOMETRY_DETAIL_MESH) {
        if (show_detail_mesh && _detail_mesh_debug.is_valid()) {
            draw_mesh(_detail_mesh_debug);
        }
    }
}

std::vector<GeometryDrawCall> RecastNavMeshBuilderComponent::get_geometry_draws(const std::string* phase_mark) {
    std::vector<GeometryDrawCall> result;

    // Only support opaque phase for now
    if (phase_mark && *phase_mark != "opaque") {
        return result;
    }

    TcMaterial mat = get_debug_material();
    if (!mat.is_valid()) {
        return result;
    }

    // Get phases from material
    tc_material* m = mat.get();
    if (!m) return result;

    for (size_t i = 0; i < m->phase_count; ++i) {
        tc_material_phase* phase = &m->phases[i];
        if (phase_mark && phase->phase_mark != *phase_mark) {
            continue;
        }

        if (show_input_mesh && _input_mesh.is_valid()) {
            result.emplace_back(phase, GEOMETRY_INPUT_MESH);
        }
        if (show_heightfield && _heightfield_mesh.is_valid()) {
            result.emplace_back(phase, GEOMETRY_HEIGHTFIELD);
        }
        if (show_regions && _regions_mesh.is_valid()) {
            result.emplace_back(phase, GEOMETRY_REGIONS);
        }
        if (show_distance_field && _distance_field_mesh.is_valid()) {
            result.emplace_back(phase, GEOMETRY_DISTANCE_FIELD);
        }
        if (show_contours && _contours_mesh.is_valid()) {
            result.emplace_back(phase, GEOMETRY_CONTOURS);
        }
        if (show_poly_mesh && _poly_mesh_debug.is_valid()) {
            result.emplace_back(phase, GEOMETRY_POLY_MESH);
        }
        if (show_detail_mesh && _detail_mesh_debug.is_valid()) {
            result.emplace_back(phase, GEOMETRY_DETAIL_MESH);
        }
    }

    return result;
}

// --- Mesh generation ---

void RecastNavMeshBuilderComponent::rebuild_debug_meshes() {
    if (debug_data.heightfield) {
        build_heightfield_mesh();
    }
    if (debug_data.compact) {
        build_regions_mesh();
        build_distance_field_mesh();
    }
    if (debug_data.contours) {
        build_contours_mesh();
    }
    if (debug_data.poly_mesh) {
        build_poly_mesh_debug();
    }
    if (debug_data.detail_mesh) {
        build_detail_mesh_debug();
    }
}

void RecastNavMeshBuilderComponent::build_input_mesh(const float* verts, int nverts, const int* tris, int ntris) {
    if (!verts || nverts == 0 || !tris || ntris == 0) return;

    // Vertex layout: position (vec3) + color (vec4)
    // Standard attribute locations: 0=position, 1=normal, 2=uv, 3=tangent/joints, 4=weights, 5=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 5);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    const float input_color[4] = {0.3f, 0.6f, 0.9f, 0.5f};  // blue, semi-transparent

    std::vector<Vertex> vertices;
    vertices.reserve(nverts);

    // Vertices are in base entity local space (after B^-1 @ W transform)
    // Just convert from Recast (Y-up) back to termin (Z-up): (x, y, z) -> (x, z, y)
    // Note: these coords are LOCAL to the base entity, so they will be
    // transformed by entity's world matrix when drawn
    for (int i = 0; i < nverts; i++) {
        float rc_x = verts[i * 3 + 0];
        float rc_y = verts[i * 3 + 1];
        float rc_z = verts[i * 3 + 2];

        float tm_x = rc_x;
        float tm_y = rc_z;  // Recast Z -> termin Y
        float tm_z = rc_y;  // Recast Y -> termin Z

        if (i < 3) {
            tc_log_info("[NavMesh] InputMesh vert[%d]: recast=(%.2f, %.2f, %.2f) -> termin=(%.2f, %.2f, %.2f)",
                i, rc_x, rc_y, rc_z, tm_x, tm_y, tm_z);
        }

        vertices.push_back({
            {tm_x, tm_y, tm_z},
            {input_color[0], input_color[1], input_color[2], input_color[3]}
        });
    }

    // Copy indices
    std::vector<uint32_t> indices;
    indices.reserve(ntris * 3);
    for (int i = 0; i < ntris * 3; i++) {
        indices.push_back(static_cast<uint32_t>(tris[i]));
    }

    // Compute UUID
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* m = tc_mesh_get(h);
    if (!m) return;

    // Set data if mesh is new
    if (m->vertex_count == 0) {
        tc_mesh_set_data(m,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_input");
    }

    _input_mesh = TcMesh(h);

    tc_log_info("[NavMesh] Input mesh debug: %d verts, %d tris", nverts, ntris);
}

void RecastNavMeshBuilderComponent::build_heightfield_mesh() {
    if (!debug_data.heightfield) return;

    const auto& hf = *debug_data.heightfield;
    if (hf.width == 0 || hf.height == 0) return;

    tc_log_info("[NavMesh] HF debug: Recast bmin=(%.2f, %.2f, %.2f) bmax not stored",
        hf.bmin[0], hf.bmin[1], hf.bmin[2]);
    tc_log_info("[NavMesh] HF debug: grid %dx%d, cs=%.3f ch=%.3f",
        hf.width, hf.height, hf.cs, hf.ch);

    // Vertex layout: position (vec3) + color (vec4)
    // Standard attribute locations: 0=position, 1=normal, 2=uv, 3=tangent/joints, 4=weights, 5=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 5);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;

    // Colors
    const float walkable_color[4] = {0.2f, 0.8f, 0.3f, 0.8f};    // green
    const float unwalkable_color[4] = {0.8f, 0.3f, 0.2f, 0.6f};  // red

    // For each cell, create a quad on top of each span
    // Convert from Recast (Y-up) back to termin (Z-up): swap Y and Z
    for (int rz = 0; rz < hf.height; rz++) {
        for (int rx = 0; rx < hf.width; rx++) {
            const auto& cell_spans = hf.spans[rz * hf.width + rx];

            for (const auto& span : cell_spans) {
                // Recast coordinates (Y-up)
                float rc_x0 = hf.bmin[0] + rx * hf.cs;
                float rc_x1 = rc_x0 + hf.cs;
                float rc_z0 = hf.bmin[2] + rz * hf.cs;
                float rc_z1 = rc_z0 + hf.cs;
                float rc_y = hf.bmin[1] + span.smax * hf.ch;

                // Convert to termin (Z-up): (x, y, z) -> (x, z, y)
                float x0 = rc_x0, x1 = rc_x1;
                float y0 = rc_z0, y1 = rc_z1;  // Recast Z -> termin Y
                float z = rc_y;                 // Recast Y -> termin Z

                // Select color based on walkability
                const float* color = (span.area != 0) ? walkable_color : unwalkable_color;

                // Add 4 vertices for quad
                uint32_t base = static_cast<uint32_t>(vertices.size());

                vertices.push_back({{x0, y0, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x1, y0, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x1, y1, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x0, y1, z}, {color[0], color[1], color[2], color[3]}});

                // Two triangles
                indices.push_back(base + 0);
                indices.push_back(base + 1);
                indices.push_back(base + 2);

                indices.push_back(base + 0);
                indices.push_back(base + 2);
                indices.push_back(base + 3);
            }
        }
    }

    if (vertices.empty()) return;

    // Compute UUID from vertex data
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* m = tc_mesh_get(h);
    if (!m) return;

    // Set data if mesh is new
    if (m->vertex_count == 0) {
        tc_mesh_set_data(m,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_heightfield");
    }

    _heightfield_mesh = TcMesh(h);

    tc_log_info("[NavMesh] Heightfield mesh: %zu verts, %zu tris",
        vertices.size(), indices.size() / 3);
}

void RecastNavMeshBuilderComponent::build_regions_mesh() {
    if (!debug_data.compact) return;

    const auto& chf = *debug_data.compact;
    if (chf.width == 0 || chf.height == 0 || chf.span_count == 0) return;

    tc_log_info("[NavMesh] Regions debug: grid %dx%d, %d spans",
        chf.width, chf.height, chf.span_count);

    // Vertex layout: position (vec3) + color (vec4)
    // Standard attribute locations: 0=position, 1=normal, 2=uv, 3=tangent/joints, 4=weights, 5=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 5);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;

    // Generate color from region ID using golden ratio hue distribution
    auto region_color = [](uint16_t region) -> std::array<float, 4> {
        if (region == 0) {
            // Region 0 = no region (unwalkable or filtered out)
            return {0.2f, 0.2f, 0.2f, 0.3f};
        }
        // Golden ratio for even hue distribution
        float hue = std::fmod(region * 0.618033988749895f, 1.0f);
        float saturation = 0.7f;
        float value = 0.9f;

        // HSV to RGB conversion
        float h = hue * 6.0f;
        int i = static_cast<int>(h);
        float f = h - i;
        float p = value * (1.0f - saturation);
        float q = value * (1.0f - saturation * f);
        float t = value * (1.0f - saturation * (1.0f - f));

        float r, g, b;
        switch (i % 6) {
            case 0: r = value; g = t; b = p; break;
            case 1: r = q; g = value; b = p; break;
            case 2: r = p; g = value; b = t; break;
            case 3: r = p; g = q; b = value; break;
            case 4: r = t; g = p; b = value; break;
            default: r = value; g = p; b = q; break;
        }
        return {r, g, b, 0.8f};
    };

    // Iterate through all cells
    for (int rz = 0; rz < chf.height; rz++) {
        for (int rx = 0; rx < chf.width; rx++) {
            const auto& cell = chf.cells[rz * chf.width + rx];
            uint32_t first_span = cell.first;
            uint8_t span_count = cell.second;

            for (uint8_t s = 0; s < span_count; s++) {
                uint32_t span_idx = first_span + s;
                if (span_idx >= static_cast<uint32_t>(chf.span_count)) continue;

                uint16_t region = chf.regions[span_idx];
                uint16_t y_val = chf.y[span_idx];

                // Recast coordinates (Y-up)
                float rc_x0 = chf.bmin[0] + rx * chf.cs;
                float rc_x1 = rc_x0 + chf.cs;
                float rc_z0 = chf.bmin[2] + rz * chf.cs;
                float rc_z1 = rc_z0 + chf.cs;
                float rc_y = chf.bmin[1] + y_val * chf.ch;

                // Convert to termin (Z-up): (x, y, z) -> (x, z, y)
                float x0 = rc_x0, x1 = rc_x1;
                float y0 = rc_z0, y1 = rc_z1;  // Recast Z -> termin Y
                float z = rc_y;                 // Recast Y -> termin Z

                // Get color for this region
                auto color = region_color(region);

                // Add 4 vertices for quad
                uint32_t base = static_cast<uint32_t>(vertices.size());

                vertices.push_back({{x0, y0, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x1, y0, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x1, y1, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x0, y1, z}, {color[0], color[1], color[2], color[3]}});

                // Two triangles
                indices.push_back(base + 0);
                indices.push_back(base + 1);
                indices.push_back(base + 2);

                indices.push_back(base + 0);
                indices.push_back(base + 2);
                indices.push_back(base + 3);
            }
        }
    }

    if (vertices.empty()) return;

    // Compute UUID from vertex data
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* m = tc_mesh_get(h);
    if (!m) return;

    // Set data if mesh is new
    if (m->vertex_count == 0) {
        tc_mesh_set_data(m,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_regions");
    }

    _regions_mesh = TcMesh(h);

    // Count unique regions
    std::set<uint16_t> unique_regions;
    for (uint16_t r : chf.regions) {
        if (r != 0) unique_regions.insert(r);
    }

    tc_log_info("[NavMesh] Regions mesh: %zu verts, %zu tris, %zu unique regions",
        vertices.size(), indices.size() / 3, unique_regions.size());
}

void RecastNavMeshBuilderComponent::build_distance_field_mesh() {
    if (!debug_data.compact) return;

    const auto& chf = *debug_data.compact;
    if (chf.width == 0 || chf.height == 0 || chf.span_count == 0) return;
    if (chf.distances.empty()) return;

    // Find max distance for normalization
    uint16_t max_dist = 1;
    for (uint16_t d : chf.distances) {
        if (d > max_dist) max_dist = d;
    }

    tc_log_info("[NavMesh] Distance field debug: grid %dx%d, %d spans, maxDist=%d",
        chf.width, chf.height, chf.span_count, max_dist);

    // Vertex layout: position (vec3) + color (vec4)
    // Standard attribute locations: 0=position, 1=normal, 2=uv, 3=tangent/joints, 4=weights, 5=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 5);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;

    // Color gradient: blue (boundary, dist=0) -> cyan -> green -> yellow -> red (center, max dist)
    auto distance_color = [max_dist](uint16_t dist) -> std::array<float, 4> {
        float t = static_cast<float>(dist) / static_cast<float>(max_dist);
        float r, g, b;

        if (t < 0.25f) {
            // Blue to Cyan
            float tt = t / 0.25f;
            r = 0.0f;
            g = tt;
            b = 1.0f;
        } else if (t < 0.5f) {
            // Cyan to Green
            float tt = (t - 0.25f) / 0.25f;
            r = 0.0f;
            g = 1.0f;
            b = 1.0f - tt;
        } else if (t < 0.75f) {
            // Green to Yellow
            float tt = (t - 0.5f) / 0.25f;
            r = tt;
            g = 1.0f;
            b = 0.0f;
        } else {
            // Yellow to Red
            float tt = (t - 0.75f) / 0.25f;
            r = 1.0f;
            g = 1.0f - tt;
            b = 0.0f;
        }

        return {r, g, b, 0.8f};
    };

    // Iterate through all cells
    for (int rz = 0; rz < chf.height; rz++) {
        for (int rx = 0; rx < chf.width; rx++) {
            const auto& cell = chf.cells[rz * chf.width + rx];
            uint32_t first_span = cell.first;
            uint8_t span_count = cell.second;

            for (uint8_t s = 0; s < span_count; s++) {
                uint32_t span_idx = first_span + s;
                if (span_idx >= static_cast<uint32_t>(chf.span_count)) continue;

                uint16_t dist = chf.distances[span_idx];
                uint16_t y_val = chf.y[span_idx];

                // Recast coordinates (Y-up)
                float rc_x0 = chf.bmin[0] + rx * chf.cs;
                float rc_x1 = rc_x0 + chf.cs;
                float rc_z0 = chf.bmin[2] + rz * chf.cs;
                float rc_z1 = rc_z0 + chf.cs;
                float rc_y = chf.bmin[1] + y_val * chf.ch;

                // Convert to termin (Z-up): (x, y, z) -> (x, z, y)
                float x0 = rc_x0, x1 = rc_x1;
                float y0 = rc_z0, y1 = rc_z1;  // Recast Z -> termin Y
                float z = rc_y;                 // Recast Y -> termin Z

                // Get color for this distance
                auto color = distance_color(dist);

                // Add 4 vertices for quad
                uint32_t base = static_cast<uint32_t>(vertices.size());

                vertices.push_back({{x0, y0, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x1, y0, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x1, y1, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x0, y1, z}, {color[0], color[1], color[2], color[3]}});

                // Two triangles
                indices.push_back(base + 0);
                indices.push_back(base + 1);
                indices.push_back(base + 2);

                indices.push_back(base + 0);
                indices.push_back(base + 2);
                indices.push_back(base + 3);
            }
        }
    }

    if (vertices.empty()) return;

    // Compute UUID from vertex data
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* m = tc_mesh_get(h);
    if (!m) return;

    // Set data if mesh is new
    if (m->vertex_count == 0) {
        tc_mesh_set_data(m,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_distance_field");
    }

    _distance_field_mesh = TcMesh(h);

    tc_log_info("[NavMesh] Distance field mesh: %zu verts, %zu tris",
        vertices.size(), indices.size() / 3);
}

void RecastNavMeshBuilderComponent::build_contours_mesh() {
    if (!debug_data.contours) return;

    const auto& cset = *debug_data.contours;
    if (cset.contours.empty()) return;

    tc_log_info("[NavMesh] Contours debug: %zu contours", cset.contours.size());

    // Vertex layout: position (vec3) + color (vec4)
    // Standard attribute locations: 0=position, 1=normal, 2=uv, 3=tangent/joints, 4=weights, 5=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 5);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;

    // Generate color from region ID using golden ratio hue distribution
    auto region_color = [](uint16_t region) -> std::array<float, 4> {
        if (region == 0) {
            return {0.5f, 0.5f, 0.5f, 1.0f};
        }
        float hue = std::fmod(region * 0.618033988749895f, 1.0f);
        float saturation = 0.8f;
        float value = 1.0f;

        // HSV to RGB conversion
        float h = hue * 6.0f;
        int i = static_cast<int>(h);
        float f = h - i;
        float p = value * (1.0f - saturation);
        float q = value * (1.0f - saturation * f);
        float t = value * (1.0f - saturation * (1.0f - f));

        float r, g, b;
        switch (i % 6) {
            case 0: r = value; g = t; b = p; break;
            case 1: r = q; g = value; b = p; break;
            case 2: r = p; g = value; b = t; break;
            case 3: r = p; g = q; b = value; break;
            case 4: r = t; g = p; b = value; break;
            default: r = value; g = p; b = q; break;
        }
        return {r, g, b, 1.0f};
    };

    for (const auto& contour : cset.contours) {
        if (contour.nverts < 2) continue;

        auto color = region_color(contour.region);

        // Contour vertices are stored as (x, y, z, region_id) in voxel space
        // 4 int32 values per vertex
        for (int i = 0; i < contour.nverts; i++) {
            int vx = contour.verts[i * 4 + 0];
            int vy = contour.verts[i * 4 + 1];
            int vz = contour.verts[i * 4 + 2];

            // Convert voxel coords to Recast world coords (Y-up)
            float rc_x = cset.bmin[0] + vx * cset.cs;
            float rc_y = cset.bmin[1] + vy * cset.ch;
            float rc_z = cset.bmin[2] + vz * cset.cs;

            // Convert to termin (Z-up): (x, y, z) -> (x, z, y)
            float tm_x = rc_x;
            float tm_y = rc_z;  // Recast Z -> termin Y
            float tm_z = rc_y;  // Recast Y -> termin Z

            vertices.push_back({{tm_x, tm_y, tm_z}, {color[0], color[1], color[2], color[3]}});
        }
    }

    if (vertices.empty()) return;

    // Build line indices: each contour is a closed loop
    uint32_t vertex_offset = 0;
    for (const auto& contour : cset.contours) {
        if (contour.nverts < 2) continue;

        for (int i = 0; i < contour.nverts; i++) {
            int next = (i + 1) % contour.nverts;
            indices.push_back(vertex_offset + i);
            indices.push_back(vertex_offset + next);
        }
        vertex_offset += contour.nverts;
    }

    // Compute UUID from vertex data
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* m = tc_mesh_get(h);
    if (!m) return;

    // Set data if mesh is new
    if (m->vertex_count == 0) {
        tc_mesh_set_data(m,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_contours");
        m->draw_mode = TC_DRAW_LINES;
    }

    _contours_mesh = TcMesh(h);

    tc_log_info("[NavMesh] Contours mesh: %zu verts, %zu lines",
        vertices.size(), indices.size() / 2);
}

void RecastNavMeshBuilderComponent::build_poly_mesh_debug() {
    if (!debug_data.poly_mesh) return;

    const auto& pmesh = *debug_data.poly_mesh;
    if (pmesh.nverts == 0 || pmesh.npolys == 0) return;

    tc_log_info("[NavMesh] PolyMesh debug: %d verts, %d polys (nvp=%d)",
        pmesh.nverts, pmesh.npolys, pmesh.nvp);

    // Vertex layout: position (vec3) + color (vec4)
    // Standard attribute locations: 0=position, 1=normal, 2=uv, 3=tangent/joints, 4=weights, 5=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 5);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;

    // Generate color from region ID using golden ratio hue distribution
    auto region_color = [](uint16_t region) -> std::array<float, 4> {
        if (region == 0) {
            return {0.3f, 0.3f, 0.3f, 0.8f};
        }
        float hue = std::fmod(region * 0.618033988749895f, 1.0f);
        float saturation = 0.6f;
        float value = 0.9f;

        // HSV to RGB conversion
        float h = hue * 6.0f;
        int i = static_cast<int>(h);
        float f = h - i;
        float p = value * (1.0f - saturation);
        float q = value * (1.0f - saturation * f);
        float t = value * (1.0f - saturation * (1.0f - f));

        float r, g, b;
        switch (i % 6) {
            case 0: r = value; g = t; b = p; break;
            case 1: r = q; g = value; b = p; break;
            case 2: r = p; g = value; b = t; break;
            case 3: r = p; g = q; b = value; break;
            case 4: r = t; g = p; b = value; break;
            default: r = value; g = p; b = q; break;
        }
        return {r, g, b, 0.8f};
    };

    // For each polygon, triangulate using fan triangulation
    for (int p = 0; p < pmesh.npolys; p++) {
        const uint16_t* poly = &pmesh.polys[p * pmesh.nvp * 2];
        uint16_t region = pmesh.regions[p];

        // Count vertices in this polygon (stop at 0xFFFF)
        int nv = 0;
        for (int i = 0; i < pmesh.nvp; i++) {
            if (poly[i] == 0xFFFF) break;
            nv++;
        }
        if (nv < 3) continue;

        // Color by polygon index to see individual polygons (not by region)
        auto color = region_color(static_cast<uint16_t>(p + 1));

        // Add vertices for this polygon
        uint32_t base_vertex = static_cast<uint32_t>(vertices.size());

        for (int i = 0; i < nv; i++) {
            uint16_t vi = poly[i];
            // Vertices are stored as (x, y, z) uint16 in voxel coords
            uint16_t vx = pmesh.verts[vi * 3 + 0];
            uint16_t vy = pmesh.verts[vi * 3 + 1];
            uint16_t vz = pmesh.verts[vi * 3 + 2];

            // Convert voxel coords to Recast world coords (Y-up)
            float rc_x = pmesh.bmin[0] + vx * pmesh.cs;
            float rc_y = pmesh.bmin[1] + vy * pmesh.ch;
            float rc_z = pmesh.bmin[2] + vz * pmesh.cs;

            // Convert to termin (Z-up): (x, y, z) -> (x, z, y)
            float tm_x = rc_x;
            float tm_y = rc_z;  // Recast Z -> termin Y
            float tm_z = rc_y;  // Recast Y -> termin Z

            vertices.push_back({{tm_x, tm_y, tm_z}, {color[0], color[1], color[2], color[3]}});
        }

        // Fan triangulation: (0, 1, 2), (0, 2, 3), (0, 3, 4), ...
        for (int i = 2; i < nv; i++) {
            indices.push_back(base_vertex);
            indices.push_back(base_vertex + i - 1);
            indices.push_back(base_vertex + i);
        }
    }

    if (vertices.empty()) return;

    // Compute UUID from vertex data
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* m = tc_mesh_get(h);
    if (!m) return;

    // Set data if mesh is new
    if (m->vertex_count == 0) {
        tc_mesh_set_data(m,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_poly_mesh");
    }

    _poly_mesh_debug = TcMesh(h);

    tc_log_info("[NavMesh] PolyMesh debug mesh: %zu verts, %zu tris",
        vertices.size(), indices.size() / 3);
}

void RecastNavMeshBuilderComponent::build_detail_mesh_debug() {
    if (!debug_data.detail_mesh) return;

    const auto& dmesh = *debug_data.detail_mesh;
    if (dmesh.nmeshes == 0 || dmesh.nverts == 0 || dmesh.ntris == 0) return;

    tc_log_info("[NavMesh] DetailMesh debug: %d meshes, %d verts, %d tris",
        dmesh.nmeshes, dmesh.nverts, dmesh.ntris);

    // Vertex layout: position (vec3) + color (vec4)
    // Standard attribute locations: 0=position, 1=normal, 2=uv, 3=tangent/joints, 4=weights, 5=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 5);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;

    // Generate color from mesh index using golden ratio hue distribution
    auto mesh_color = [](int mesh_idx) -> std::array<float, 4> {
        float hue = std::fmod(mesh_idx * 0.618033988749895f, 1.0f);
        float saturation = 0.5f;
        float value = 1.0f;

        // HSV to RGB conversion
        float h = hue * 6.0f;
        int i = static_cast<int>(h);
        float f = h - i;
        float p = value * (1.0f - saturation);
        float q = value * (1.0f - saturation * f);
        float t = value * (1.0f - saturation * (1.0f - f));

        float r, g, b;
        switch (i % 6) {
            case 0: r = value; g = t; b = p; break;
            case 1: r = q; g = value; b = p; break;
            case 2: r = p; g = value; b = t; break;
            case 3: r = p; g = q; b = value; break;
            case 4: r = t; g = p; b = value; break;
            default: r = value; g = p; b = q; break;
        }
        return {r, g, b, 0.9f};
    };

    // Process each sub-mesh (one per polygon)
    for (int m = 0; m < dmesh.nmeshes; m++) {
        // meshes array: (vert_base, vert_count, tri_base, tri_count) per mesh
        uint32_t vert_base = dmesh.meshes[m * 4 + 0];
        uint32_t vert_count = dmesh.meshes[m * 4 + 1];
        uint32_t tri_base = dmesh.meshes[m * 4 + 2];
        uint32_t tri_count = dmesh.meshes[m * 4 + 3];

        if (vert_count == 0 || tri_count == 0) continue;

        auto color = mesh_color(m);
        uint32_t base_vertex = static_cast<uint32_t>(vertices.size());

        // Add vertices for this sub-mesh
        // Detail mesh vertices are already in Recast world coords (float, Y-up)
        for (uint32_t v = 0; v < vert_count; v++) {
            uint32_t vi = vert_base + v;
            float rc_x = dmesh.verts[vi * 3 + 0];
            float rc_y = dmesh.verts[vi * 3 + 1];
            float rc_z = dmesh.verts[vi * 3 + 2];

            // Convert to termin (Z-up): (x, y, z) -> (x, z, y)
            float tm_x = rc_x;
            float tm_y = rc_z;  // Recast Z -> termin Y
            float tm_z = rc_y;  // Recast Y -> termin Z

            vertices.push_back({{tm_x, tm_y, tm_z}, {color[0], color[1], color[2], color[3]}});
        }

        // Add triangles for this sub-mesh
        // Detail triangles: (v0, v1, v2, flags) as uint8, indices are local to sub-mesh
        for (uint32_t t = 0; t < tri_count; t++) {
            uint32_t ti = tri_base + t;
            uint8_t v0 = dmesh.tris[ti * 4 + 0];
            uint8_t v1 = dmesh.tris[ti * 4 + 1];
            uint8_t v2 = dmesh.tris[ti * 4 + 2];
            // uint8_t flags = dmesh.tris[ti * 4 + 3]; // not used for visualization

            indices.push_back(base_vertex + v0);
            indices.push_back(base_vertex + v1);
            indices.push_back(base_vertex + v2);
        }
    }

    if (vertices.empty()) return;

    // Compute UUID from vertex data
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* mesh = tc_mesh_get(h);
    if (!mesh) return;

    // Set data if mesh is new
    if (mesh->vertex_count == 0) {
        tc_mesh_set_data(mesh,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_detail_mesh");
    }

    _detail_mesh_debug = TcMesh(h);

    tc_log_info("[NavMesh] DetailMesh debug mesh: %zu verts, %zu tris",
        vertices.size(), indices.size() / 3);
}

TcMaterial RecastNavMeshBuilderComponent::get_debug_material() {
    if (!_debug_material.is_valid()) {
        // Create material programmatically with vertex color shader
        _debug_material = TcMaterial::create("navmesh_debug_material");
        if (!_debug_material.is_valid()) {
            tc_log_error("[NavMesh] Failed to create debug material");
            return _debug_material;
        }

        // Simple vertex color shader
        const char* vertex_source = R"(
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 5) in vec4 a_color;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec4 v_color;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
    v_color = a_color;
}
)";

        const char* fragment_source = R"(
#version 330 core

in vec4 v_color;
out vec4 frag_color;

void main() {
    frag_color = v_color;
}
)";

        tc_render_state state = tc_render_state_opaque();
        state.depth_test = 1;
        state.depth_write = 1;
        state.cull = 0;  // No culling for debug mesh
        state.blend = 0;

        tc_material_phase* phase = _debug_material.add_phase_from_sources(
            vertex_source,
            fragment_source,
            nullptr,  // no geometry shader
            "navmesh_debug_shader",
            "opaque",
            0,  // priority
            state
        );

        if (!phase) {
            tc_log_error("[NavMesh] Failed to add phase to debug material");
        }
    }
    return _debug_material;
}

// --- Capture functions ---

void RecastNavMeshBuilderComponent::capture_heightfield_data(rcHeightfield* hf) {
    if (!hf) return;

    auto& data = debug_data.heightfield.emplace();
    data.width = hf->width;
    data.height = hf->height;
    data.cs = hf->cs;
    data.ch = hf->ch;
    rcVcopy(data.bmin, hf->bmin);
    rcVcopy(data.bmax, hf->bmax);

    data.spans.resize(hf->width * hf->height);

    for (int z = 0; z < hf->height; z++) {
        for (int x = 0; x < hf->width; x++) {
            auto& cell_spans = data.spans[z * hf->width + x];
            for (rcSpan* s = hf->spans[z * hf->width + x]; s; s = s->next) {
                RecastSpan span;
                span.smin = static_cast<uint16_t>(s->smin);
                span.smax = static_cast<uint16_t>(s->smax);
                span.area = static_cast<uint8_t>(s->area);
                cell_spans.push_back(span);
            }
        }
    }
}

void RecastNavMeshBuilderComponent::capture_compact_data(rcCompactHeightfield* chf) {
    if (!chf) return;

    auto& data = debug_data.compact.emplace();
    data.width = chf->width;
    data.height = chf->height;
    data.span_count = chf->spanCount;
    data.cs = chf->cs;
    data.ch = chf->ch;
    rcVcopy(data.bmin, chf->bmin);
    rcVcopy(data.bmax, chf->bmax);

    // Per-span data
    data.y.resize(chf->spanCount);
    data.distances.resize(chf->spanCount);
    data.regions.resize(chf->spanCount);
    data.areas.resize(chf->spanCount);

    for (int i = 0; i < chf->spanCount; i++) {
        data.y[i] = chf->spans[i].y;
        data.distances[i] = chf->dist ? chf->dist[i] : 0;
        data.regions[i] = chf->spans[i].reg;
        data.areas[i] = chf->areas[i];
    }

    // Cell index
    data.cells.resize(chf->width * chf->height);
    for (int i = 0; i < chf->width * chf->height; i++) {
        data.cells[i] = {chf->cells[i].index, static_cast<uint8_t>(chf->cells[i].count)};
    }
}

void RecastNavMeshBuilderComponent::capture_contour_data(rcContourSet* cset) {
    if (!cset) return;

    auto& data = debug_data.contours.emplace();
    data.cs = cset->cs;
    data.ch = cset->ch;
    rcVcopy(data.bmin, cset->bmin);
    rcVcopy(data.bmax, cset->bmax);

    data.contours.resize(cset->nconts);
    for (int i = 0; i < cset->nconts; i++) {
        const rcContour& src = cset->conts[i];
        RecastDebugData::Contour& dst = data.contours[i];

        dst.region = src.reg;
        dst.area = src.area;

        // Simplified vertices
        dst.nverts = src.nverts;
        dst.verts.resize(src.nverts * 4);
        memcpy(dst.verts.data(), src.verts, src.nverts * 4 * sizeof(int));

        // Raw vertices
        dst.nraw_verts = src.nrverts;
        dst.raw_verts.resize(src.nrverts * 4);
        memcpy(dst.raw_verts.data(), src.rverts, src.nrverts * 4 * sizeof(int));
    }
}

void RecastNavMeshBuilderComponent::capture_poly_mesh_data(rcPolyMesh* pmesh) {
    if (!pmesh) return;

    auto& data = debug_data.poly_mesh.emplace();
    data.nverts = pmesh->nverts;
    data.npolys = pmesh->npolys;
    data.nvp = pmesh->nvp;
    data.cs = pmesh->cs;
    data.ch = pmesh->ch;
    rcVcopy(data.bmin, pmesh->bmin);
    rcVcopy(data.bmax, pmesh->bmax);

    // Vertices
    data.verts.resize(pmesh->nverts * 3);
    memcpy(data.verts.data(), pmesh->verts, pmesh->nverts * 3 * sizeof(uint16_t));

    // Polygons
    data.polys.resize(pmesh->npolys * pmesh->nvp * 2);
    memcpy(data.polys.data(), pmesh->polys, pmesh->npolys * pmesh->nvp * 2 * sizeof(uint16_t));

    // Per-polygon data
    data.regions.resize(pmesh->npolys);
    data.flags.resize(pmesh->npolys);
    data.areas.resize(pmesh->npolys);
    memcpy(data.regions.data(), pmesh->regs, pmesh->npolys * sizeof(uint16_t));
    memcpy(data.flags.data(), pmesh->flags, pmesh->npolys * sizeof(uint16_t));
    memcpy(data.areas.data(), pmesh->areas, pmesh->npolys * sizeof(uint8_t));
}

void RecastNavMeshBuilderComponent::capture_detail_mesh_data(rcPolyMeshDetail* dmesh) {
    if (!dmesh) return;

    auto& data = debug_data.detail_mesh.emplace();
    data.nmeshes = dmesh->nmeshes;
    data.nverts = dmesh->nverts;
    data.ntris = dmesh->ntris;

    // Meshes: (vert_base, vert_count, tri_base, tri_count)
    data.meshes.resize(dmesh->nmeshes * 4);
    memcpy(data.meshes.data(), dmesh->meshes, dmesh->nmeshes * 4 * sizeof(uint32_t));

    // Vertices
    data.verts.resize(dmesh->nverts * 3);
    memcpy(data.verts.data(), dmesh->verts, dmesh->nverts * 3 * sizeof(float));

    // Triangles
    data.tris.resize(dmesh->ntris * 4);
    memcpy(data.tris.data(), dmesh->tris, dmesh->ntris * 4 * sizeof(uint8_t));
}

// Helper: extract positions from TcMesh into flat float array, applying transform
static bool extract_mesh_positions(const TcMesh& mesh, const Mat44& transform, std::vector<float>& out_verts, std::vector<int>& out_tris) {
    tc_mesh* m = mesh.get();
    if (!m || !m->vertices || m->vertex_count == 0) return false;
    if (!m->indices || m->index_count == 0) return false;

    const tc_vertex_attrib* pos = tc_vertex_layout_find(&m->layout, "position");
    if (!pos || pos->size != 3) return false;

    size_t n = m->vertex_count;
    size_t stride = m->layout.stride;
    const uint8_t* src = static_cast<const uint8_t*>(m->vertices);

    // Extract positions with transform
    // Convert from termin (Z-up) to Recast (Y-up): swap Y and Z
    size_t base_vert = out_verts.size() / 3;
    out_verts.resize(out_verts.size() + n * 3);
    float* dst = out_verts.data() + base_vert * 3;
    for (size_t i = 0; i < n; ++i) {
        const float* p = reinterpret_cast<const float*>(src + i * stride + pos->offset);
        Vec3 local_pos{p[0], p[1], p[2]};
        Vec3 transformed = transform.transform_point(local_pos);
        // Termin: X-right, Y-forward, Z-up
        // Recast: X-right, Y-up, Z-forward
        dst[i * 3] = static_cast<float>(transformed.x);
        dst[i * 3 + 1] = static_cast<float>(transformed.z);  // Z-up -> Y-up
        dst[i * 3 + 2] = static_cast<float>(transformed.y);  // Y-forward -> Z-forward

        // Debug: log first few vertices
        if (i < 3) {
            tc_log_info("[NavMesh] vert[%zu]: local=(%.2f, %.2f, %.2f) -> world=(%.2f, %.2f, %.2f) -> recast=(%.2f, %.2f, %.2f)",
                i, p[0], p[1], p[2],
                transformed.x, transformed.y, transformed.z,
                dst[i * 3], dst[i * 3 + 1], dst[i * 3 + 2]);
        }
    }

    // Extract triangles (adjust indices by base_vert)
    size_t num_tris = m->index_count / 3;
    size_t base_tri = out_tris.size();
    out_tris.resize(out_tris.size() + num_tris * 3);
    for (size_t i = 0; i < num_tris * 3; ++i) {
        out_tris[base_tri + i] = static_cast<int>(m->indices[i] + base_vert);
    }

    return true;
}

// Helper: collect meshes from entity (and optionally children)
// base_inv is inverse of base entity world transform (B^-1)
// All vertices are transformed to base entity local space: B^-1 @ W @ p
static void collect_meshes_recursive(Entity ent, const Mat44& base_inv, std::vector<float>& verts, std::vector<int>& tris, bool recurse) {
    if (!ent.valid()) return;

    // Get world transform of this entity (W)
    // world_matrix outputs column-major, same as Mat44
    double w_data[16];
    ent.get_world_matrix(w_data);
    Mat44 world;
    std::memcpy(world.ptr(), w_data, sizeof(w_data));

    // Compute local_to_base = B^-1 @ W
    Mat44 local_to_base = base_inv * world;

    // Get MeshRenderer from this entity
    MeshRenderer* mr = ent.get_component<MeshRenderer>();
    if (mr && mr->mesh.is_valid()) {
        tc_log_info("[NavMesh] Processing entity: %s", ent.name() ? ent.name() : "(unnamed)");
        tc_log_info("[NavMesh]   world col0: (%.2f, %.2f, %.2f, %.2f)", w_data[0], w_data[1], w_data[2], w_data[3]);
        tc_log_info("[NavMesh]   world col3: (%.2f, %.2f, %.2f, %.2f)", w_data[12], w_data[13], w_data[14], w_data[15]);
        extract_mesh_positions(mr->mesh, local_to_base, verts, tris);
    }

    // Recurse into children
    if (recurse) {
        for (Entity child : ent.children()) {
            collect_meshes_recursive(child, base_inv, verts, tris, true);
        }
    }
}

void RecastNavMeshBuilderComponent::build_from_entity() {
    if (!entity.valid()) {
        tc_log_error("RecastNavMeshBuilderComponent: no entity");
        return;
    }

    // Get base entity world transform and compute its inverse (B^-1)
    double b_data[16];
    entity.get_world_matrix(b_data);
    Mat44 base_world;
    std::memcpy(base_world.ptr(), b_data, sizeof(b_data));
    Mat44 base_inv = base_world.inverse();

    bool recurse = (mesh_source == static_cast<int>(MeshSource::AllDescendants));
    tc_log_info("[NavMesh] Build mode: %s, base entity: %s",
        recurse ? "AllDescendants" : "CurrentMesh",
        entity.name() ? entity.name() : "(unnamed)");
    tc_log_info("[NavMesh] Base world matrix col0: (%.2f, %.2f, %.2f, %.2f)",
        b_data[0], b_data[1], b_data[2], b_data[3]);
    tc_log_info("[NavMesh] Base world matrix col1: (%.2f, %.2f, %.2f, %.2f)",
        b_data[4], b_data[5], b_data[6], b_data[7]);
    tc_log_info("[NavMesh] Base world matrix col2: (%.2f, %.2f, %.2f, %.2f)",
        b_data[8], b_data[9], b_data[10], b_data[11]);
    tc_log_info("[NavMesh] Base world matrix col3 (pos): (%.2f, %.2f, %.2f, %.2f)",
        b_data[12], b_data[13], b_data[14], b_data[15]);

    std::vector<float> verts;
    std::vector<int> tris;

    collect_meshes_recursive(entity, base_inv, verts, tris, recurse);

    if (verts.empty() || tris.empty()) {
        tc_log_error("RecastNavMeshBuilderComponent: no mesh geometry found");
        return;
    }

    int nverts = static_cast<int>(verts.size() / 3);
    int ntris = static_cast<int>(tris.size() / 3);

    tc_log_info("RecastNavMeshBuilderComponent: building from %d vertices, %d triangles", nverts, ntris);

    auto result = build(verts.data(), nverts, tris.data(), ntris);

    if (result.success) {
        tc_log_info("RecastNavMeshBuilderComponent: build successful (%d polys)",
                    result.poly_mesh ? result.poly_mesh->npolys : 0);
    } else {
        tc_log_error("RecastNavMeshBuilderComponent: build failed - %s", result.error.c_str());
    }
}

} // namespace termin
