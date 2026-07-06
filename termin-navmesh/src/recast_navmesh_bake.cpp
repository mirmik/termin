#include <termin/navmesh/recast_navmesh_bake.hpp>

#include <termin/navmesh/navmesh_bake_source.hpp>
#include <cmath>
#include <cstring>
#include <vector>

#include <tcbase/tc_log.hpp>

namespace termin {

namespace {

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

} // namespace

RecastBuildResult build_recast_navmesh(
    const float* verts,
    int nverts,
    const int* tris,
    int ntris,
    const unsigned char* triangle_area_ids,
    const RecastNavMeshBuildConfig& build_config,
    const RecastNavMeshBuildDebugHooks* debug_hooks)
{
    RecastBuildResult result;

    if (verts == nullptr || nverts == 0 || tris == nullptr || ntris == 0) {
        result.error = "Invalid input: empty geometry";
        return result;
    }

    if (debug_hooks && debug_hooks->build_input_mesh) {
        debug_hooks->build_input_mesh(verts, nverts, tris, ntris);
    }

    BuildContext ctx;

    float bmin[3], bmax[3];
    rcCalcBounds(verts, nverts, bmin, bmax);
    tc_log_info("[NavMesh] Bounds: min=(%.2f, %.2f, %.2f) max=(%.2f, %.2f, %.2f)",
        bmin[0], bmin[1], bmin[2], bmax[0], bmax[1], bmax[2]);

    rcConfig cfg;
    memset(&cfg, 0, sizeof(cfg));

    cfg.cs = build_config.cell_size;
    cfg.ch = build_config.cell_height;
    cfg.walkableSlopeAngle = build_config.agent_max_slope;
    cfg.walkableHeight = static_cast<int>(std::ceil(build_config.agent_height / cfg.ch));
    cfg.walkableClimb = static_cast<int>(std::floor(build_config.agent_max_climb / cfg.ch));
    cfg.walkableRadius = static_cast<int>(std::ceil(build_config.agent_radius / cfg.cs));
    cfg.maxEdgeLen = static_cast<int>(build_config.max_edge_length / cfg.cs);
    cfg.maxSimplificationError = build_config.max_simplification_error;
    cfg.minRegionArea = build_config.min_region_area;
    cfg.mergeRegionArea = build_config.merge_region_area;
    cfg.maxVertsPerPoly = build_config.max_verts_per_poly;
    cfg.detailSampleDist = build_config.detail_sample_dist < 0.9f ? 0 : cfg.cs * build_config.detail_sample_dist;
    cfg.detailSampleMaxError = cfg.ch * build_config.detail_sample_max_error;

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

    std::vector<unsigned char> tri_areas(
        ntris,
        navmesh_detour_area_to_recast_area(build_config.default_area_id));
    rcMarkWalkableTriangles(&ctx, cfg.walkableSlopeAngle,
                            verts, nverts, tris, ntris, tri_areas.data());
    for (int i = 0; i < ntris; ++i) {
        if (tri_areas[i] == RC_NULL_AREA) {
            continue;
        }
        const int area_id = triangle_area_ids
            ? static_cast<int>(triangle_area_ids[i])
            : build_config.default_area_id;
        tri_areas[i] = navmesh_detour_area_to_recast_area(area_id);
    }

    int walkable_count = 0;
    for (int i = 0; i < ntris; i++) {
        if (tri_areas[i] != RC_NULL_AREA) walkable_count++;
    }
    tc_log_info("[NavMesh] Walkable triangles: %d / %d", walkable_count, ntris);

    if (!rcRasterizeTriangles(&ctx, verts, nverts, tris, tri_areas.data(), ntris,
                              *hf, cfg.walkableClimb)) {
        result.error = "Failed to rasterize triangles";
        rcFreeHeightField(hf);
        return result;
    }

    int span_count_before = 0;
    for (int i = 0; i < hf->width * hf->height; i++) {
        for (rcSpan* s = hf->spans[i]; s; s = s->next) span_count_before++;
    }
    tc_log_info("[NavMesh] Heightfield spans after rasterize: %d", span_count_before);

    rcFilterLowHangingWalkableObstacles(&ctx, cfg.walkableClimb, *hf);
    rcFilterLedgeSpans(&ctx, cfg.walkableHeight, cfg.walkableClimb, *hf);
    rcFilterWalkableLowHeightSpans(&ctx, cfg.walkableHeight, *hf);

    int span_count_after = 0;
    int walkable_spans = 0;
    for (int i = 0; i < hf->width * hf->height; i++) {
        for (rcSpan* s = hf->spans[i]; s; s = s->next) {
            span_count_after++;
            if (s->area != RC_NULL_AREA) walkable_spans++;
        }
    }
    tc_log_info("[NavMesh] After filtering: %d spans, %d walkable", span_count_after, walkable_spans);

    if (debug_hooks && debug_hooks->capture_heightfield) {
        debug_hooks->capture_heightfield(hf);
    }

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

    rcFreeHeightField(hf);
    hf = nullptr;

    if (!rcErodeWalkableArea(&ctx, cfg.walkableRadius, *chf)) {
        result.error = "Failed to erode walkable area";
        rcFreeCompactHeightfield(chf);
        return result;
    }

    int walkable_after_erode = 0;
    for (int i = 0; i < chf->spanCount; i++) {
        if (chf->areas[i] != RC_NULL_AREA) walkable_after_erode++;
    }
    tc_log_info("[NavMesh] After erode (radius=%d): %d walkable spans", cfg.walkableRadius, walkable_after_erode);

    if (!rcBuildDistanceField(&ctx, *chf)) {
        result.error = "Failed to build distance field";
        rcFreeCompactHeightfield(chf);
        return result;
    }

    tc_log_info("[NavMesh] Distance field built, maxDistance=%d", chf->maxDistance);

    if (!rcBuildRegions(&ctx, *chf, cfg.borderSize, cfg.minRegionArea, cfg.mergeRegionArea)) {
        result.error = "Failed to build regions";
        rcFreeCompactHeightfield(chf);
        return result;
    }

    int max_region = 0;
    for (int i = 0; i < chf->spanCount; i++) {
        if (chf->spans[i].reg > max_region) max_region = chf->spans[i].reg;
    }
    tc_log_info("[NavMesh] Regions built: %d regions", max_region);

    if (debug_hooks && debug_hooks->capture_compact) {
        debug_hooks->capture_compact(chf);
    }

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

    if (debug_hooks && debug_hooks->capture_contours) {
        debug_hooks->capture_contours(cset);
    }

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

    if (pmesh->nverts <= 0 || pmesh->npolys <= 0) {
        result.error = "Recast produced an empty polygon mesh; check agent radius, cell size, region area, and source mesh scale";
        tc_log_error("[NavMesh] %s", result.error.c_str());
        rcFreePolyMesh(pmesh);
        rcFreeContourSet(cset);
        rcFreeCompactHeightfield(chf);
        return result;
    }

    rcFreeContourSet(cset);
    cset = nullptr;

    if (debug_hooks && debug_hooks->capture_poly_mesh) {
        debug_hooks->capture_poly_mesh(pmesh);
    }

    rcPolyMeshDetail* dmesh = nullptr;
    if (build_config.build_detail_mesh) {
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

        if (dmesh->nverts > 0 && pmesh->nverts > 0) {
            tc_log_info("[NavMesh] PolyMesh vert[0] (voxel): (%d, %d, %d) -> world: (%.2f, %.2f, %.2f)",
                pmesh->verts[0], pmesh->verts[1], pmesh->verts[2],
                pmesh->bmin[0] + pmesh->verts[0] * pmesh->cs,
                pmesh->bmin[1] + pmesh->verts[1] * pmesh->ch,
                pmesh->bmin[2] + pmesh->verts[2] * pmesh->cs);
            tc_log_info("[NavMesh] DetailMesh vert[0] (float): (%.2f, %.2f, %.2f)",
                dmesh->verts[0], dmesh->verts[1], dmesh->verts[2]);
        }

        if (debug_hooks && debug_hooks->capture_detail_mesh) {
            debug_hooks->capture_detail_mesh(dmesh);
        }
    }

    rcFreeCompactHeightfield(chf);

    result.success = true;
    result.poly_mesh = pmesh;
    result.detail_mesh = dmesh;
    return result;
}

RecastBuildResult build_recast_navmesh(
    const float* verts,
    int nverts,
    const int* tris,
    int ntris,
    const RecastNavMeshBuildConfig& build_config,
    const RecastNavMeshBuildDebugHooks* debug_hooks)
{
    return build_recast_navmesh(
        verts,
        nverts,
        tris,
        ntris,
        nullptr,
        build_config,
        debug_hooks);
}

void free_recast_build_result(RecastBuildResult& result) {
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

} // namespace termin
