#include "recast_navmesh_builder_component.hpp"
#include "../render/mesh_renderer.hpp"
#include <cstring>
#include <cmath>
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
    set_type_name("RecastNavMeshBuilderComponent");
    install_drawable_vtable(&_c);
}

RecastNavMeshBuilderComponent::~RecastNavMeshBuilderComponent() {
    free_result(last_result);
}

void RecastNavMeshBuilderComponent::clear_debug_data() {
    debug_data.clear();

    // Clear meshes (GPU resources are freed automatically via tc_mesh)
    _heightfield_mesh = TcMesh();
    _regions_mesh = TcMesh();
    _distance_field_mesh = TcMesh();
    _contours_mesh = TcMesh();
    _poly_mesh_debug = TcMesh();
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
    if (show_heightfield || show_regions || show_distance_field ||
        show_contours || show_poly_mesh) {
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
}

void RecastNavMeshBuilderComponent::build_heightfield_mesh() {
    // TODO: Create mesh from heightfield spans (voxel boxes)
    // Each span becomes a small box at (x * cs + bmin.x, smin * ch + bmin.y, z * cs + bmin.z)
}

void RecastNavMeshBuilderComponent::build_regions_mesh() {
    // TODO: Create mesh showing regions (colored by region ID)
    // Use compact heightfield spans with region coloring
}

void RecastNavMeshBuilderComponent::build_distance_field_mesh() {
    // TODO: Create mesh showing distance field (gradient coloring)
    // Use compact heightfield spans with distance-based colors
}

void RecastNavMeshBuilderComponent::build_contours_mesh() {
    // TODO: Create line mesh from contours
    // Each contour becomes a polyline
}

void RecastNavMeshBuilderComponent::build_poly_mesh_debug() {
    // TODO: Create mesh from poly mesh (triangulated polygons)
    // Convert rcPolyMesh polygons to triangles with region-based colors
}

TcMaterial RecastNavMeshBuilderComponent::get_debug_material() {
    if (!_debug_material.is_valid()) {
        // Try to find vertex_color material
        tc_material_handle h = tc_material_find_by_name("vertex_color");
        _debug_material = TcMaterial(h);
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

// Helper: extract positions from TcMesh into flat float array
static bool extract_mesh_positions(const TcMesh& mesh, std::vector<float>& out_verts, std::vector<int>& out_tris) {
    tc_mesh* m = mesh.get();
    if (!m || !m->vertices || m->vertex_count == 0) return false;
    if (!m->indices || m->index_count == 0) return false;

    const tc_vertex_attrib* pos = tc_vertex_layout_find(&m->layout, "position");
    if (!pos || pos->size != 3) return false;

    size_t n = m->vertex_count;
    size_t stride = m->layout.stride;
    const uint8_t* src = static_cast<const uint8_t*>(m->vertices);

    // Extract positions
    size_t base_vert = out_verts.size() / 3;
    out_verts.resize(out_verts.size() + n * 3);
    float* dst = out_verts.data() + base_vert * 3;
    for (size_t i = 0; i < n; ++i) {
        const float* p = reinterpret_cast<const float*>(src + i * stride + pos->offset);
        dst[i * 3] = p[0];
        dst[i * 3 + 1] = p[1];
        dst[i * 3 + 2] = p[2];
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
static void collect_meshes_recursive(Entity ent, std::vector<float>& verts, std::vector<int>& tris, bool recurse) {
    if (!ent.valid()) return;

    // Get MeshRenderer from this entity
    MeshRenderer* mr = ent.get_component<MeshRenderer>();
    if (mr && mr->mesh.is_valid()) {
        extract_mesh_positions(mr->mesh, verts, tris);
    }

    // Recurse into children
    if (recurse) {
        for (Entity child : ent.children()) {
            collect_meshes_recursive(child, verts, tris, true);
        }
    }
}

void RecastNavMeshBuilderComponent::build_from_entity() {
    if (!entity.valid()) {
        tc_log_error("RecastNavMeshBuilderComponent: no entity");
        return;
    }

    std::vector<float> verts;
    std::vector<int> tris;

    bool recurse = (mesh_source == static_cast<int>(MeshSource::AllDescendants));
    collect_meshes_recursive(entity, verts, tris, recurse);

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
