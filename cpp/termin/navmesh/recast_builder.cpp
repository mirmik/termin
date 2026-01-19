#include "recast_builder.hpp"
#include <cstring>
#include <cmath>

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

RecastBuildResult RecastNavMeshBuilder::build(const float* verts, int nverts,
                                               const int* tris, int ntris) {
    RecastBuildResult result;
    debug_data.clear();

    if (verts == nullptr || nverts == 0 || tris == nullptr || ntris == 0) {
        result.error = "Invalid input: empty geometry";
        return result;
    }

    BuildContext ctx;

    // Calculate bounds
    float bmin[3], bmax[3];
    rcCalcBounds(verts, nverts, bmin, bmax);

    // Initialize config
    rcConfig cfg;
    memset(&cfg, 0, sizeof(cfg));

    cfg.cs = config.cell_size;
    cfg.ch = config.cell_height;
    cfg.walkableSlopeAngle = config.agent_max_slope;
    cfg.walkableHeight = static_cast<int>(std::ceil(config.agent_height / cfg.ch));
    cfg.walkableClimb = static_cast<int>(std::floor(config.agent_max_climb / cfg.ch));
    cfg.walkableRadius = static_cast<int>(std::ceil(config.agent_radius / cfg.cs));
    cfg.maxEdgeLen = static_cast<int>(config.max_edge_length / cfg.cs);
    cfg.maxSimplificationError = config.max_simplification_error;
    cfg.minRegionArea = config.min_region_area;
    cfg.mergeRegionArea = config.merge_region_area;
    cfg.maxVertsPerPoly = config.max_verts_per_poly;
    cfg.detailSampleDist = config.detail_sample_dist < 0.9f ? 0 : cfg.cs * config.detail_sample_dist;
    cfg.detailSampleMaxError = cfg.ch * config.detail_sample_max_error;

    rcVcopy(cfg.bmin, bmin);
    rcVcopy(cfg.bmax, bmax);
    rcCalcGridSize(cfg.bmin, cfg.bmax, cfg.cs, &cfg.width, &cfg.height);

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

    // Rasterize triangles
    if (!rcRasterizeTriangles(&ctx, verts, nverts, tris, tri_areas.data(), ntris,
                              *hf, cfg.walkableClimb)) {
        result.error = "Failed to rasterize triangles";
        rcFreeHeightField(hf);
        return result;
    }

    // Filter walkable surfaces
    rcFilterLowHangingWalkableObstacles(&ctx, cfg.walkableClimb, *hf);
    rcFilterLedgeSpans(&ctx, cfg.walkableHeight, cfg.walkableClimb, *hf);
    rcFilterWalkableLowHeightSpans(&ctx, cfg.walkableHeight, *hf);

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

    // Done with heightfield
    rcFreeHeightField(hf);
    hf = nullptr;

    // Erode walkable area by agent radius
    if (!rcErodeWalkableArea(&ctx, cfg.walkableRadius, *chf)) {
        result.error = "Failed to erode walkable area";
        rcFreeCompactHeightfield(chf);
        return result;
    }

    // Build distance field
    if (!rcBuildDistanceField(&ctx, *chf)) {
        result.error = "Failed to build distance field";
        rcFreeCompactHeightfield(chf);
        return result;
    }

    // Build regions (watershed algorithm)
    if (!rcBuildRegions(&ctx, *chf, cfg.borderSize, cfg.minRegionArea, cfg.mergeRegionArea)) {
        result.error = "Failed to build regions";
        rcFreeCompactHeightfield(chf);
        return result;
    }

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
    if (config.build_detail_mesh) {
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

    return result;
}

void RecastNavMeshBuilder::free_result(RecastBuildResult& result) {
    if (result.poly_mesh) {
        rcFreePolyMesh(result.poly_mesh);
        result.poly_mesh = nullptr;
    }
    if (result.detail_mesh) {
        rcFreePolyMeshDetail(result.detail_mesh);
        result.detail_mesh = nullptr;
    }
}

void RecastNavMeshBuilder::capture_heightfield_data(rcHeightfield* hf) {
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

void RecastNavMeshBuilder::capture_compact_data(rcCompactHeightfield* chf) {
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

void RecastNavMeshBuilder::capture_contour_data(rcContourSet* cset) {
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

void RecastNavMeshBuilder::capture_poly_mesh_data(rcPolyMesh* pmesh) {
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

void RecastNavMeshBuilder::capture_detail_mesh_data(rcPolyMeshDetail* dmesh) {
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

} // namespace termin
