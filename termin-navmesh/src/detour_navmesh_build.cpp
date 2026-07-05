#include <termin/navmesh/detour_navmesh_build.hpp>

#include <termin/navmesh/navmesh_bake_source.hpp>
#include <DetourAlloc.h>
#include <DetourNavMeshBuilder.h>
#include <Recast.h>
#include <algorithm>
#include <cstring>
#include <tcbase/tc_log.hpp>

namespace termin {

DetourNavMeshTileBuildResult build_detour_navmesh_tile_data(
    const RecastBuildResult& recast_result,
    const DetourNavMeshBuildConfig& config,
    const DetourOffMeshLinkData* off_mesh_links)
{
    DetourNavMeshTileBuildResult result;
    rcPolyMesh* pmesh = recast_result.poly_mesh;
    if (!recast_result.success || !pmesh) {
        result.error = "cannot build Detour tile without a successful Recast poly mesh";
        tc_log_error("[NavMesh] %s", result.error.c_str());
        return result;
    }
    if (pmesh->nverts <= 0 || pmesh->npolys <= 0 || !pmesh->verts || !pmesh->polys) {
        result.error = "cannot build Detour tile from invalid Recast poly mesh";
        tc_log_error("[NavMesh] %s (verts=%d polys=%d verts_ptr=%p polys_ptr=%p)",
                     result.error.c_str(),
                     pmesh ? pmesh->nverts : 0,
                     pmesh ? pmesh->npolys : 0,
                     pmesh ? static_cast<const void*>(pmesh->verts) : nullptr,
                     pmesh ? static_cast<const void*>(pmesh->polys) : nullptr);
        return result;
    }

    const int poly_area_id = std::clamp(config.area_id, 0, 63);
    if (poly_area_id != config.area_id) {
        tc_log_warn("[NavMesh] Detour area_id=%d is outside Detour range, using %d",
                    config.area_id, poly_area_id);
    }

    std::vector<unsigned short> poly_flags(static_cast<size_t>(pmesh->npolys), 0);
    std::vector<unsigned char> poly_areas(static_cast<size_t>(pmesh->npolys), 0);
    for (int i = 0; i < pmesh->npolys; ++i) {
        const unsigned char area = pmesh->areas
            ? pmesh->areas[i]
            : navmesh_detour_area_to_recast_area(poly_area_id);
        poly_areas[static_cast<size_t>(i)] =
            navmesh_recast_area_to_detour_area(area, poly_area_id);
        poly_flags[static_cast<size_t>(i)] = (area == RC_NULL_AREA) ? 0 : 1;
    }

    dtNavMeshCreateParams params;
    std::memset(&params, 0, sizeof(params));
    params.verts = pmesh->verts;
    params.vertCount = pmesh->nverts;
    params.polys = pmesh->polys;
    params.polyAreas = poly_areas.data();
    params.polyFlags = poly_flags.data();
    params.polyCount = pmesh->npolys;
    params.nvp = pmesh->nvp;

    if (off_mesh_links && off_mesh_links->count() > 0) {
        params.offMeshConVerts = off_mesh_links->verts.data();
        params.offMeshConRad = off_mesh_links->radii.data();
        params.offMeshConDir = off_mesh_links->dirs.data();
        params.offMeshConAreas = off_mesh_links->areas.data();
        params.offMeshConFlags = off_mesh_links->flags.data();
        params.offMeshConUserID = off_mesh_links->user_ids.data();
        params.offMeshConCount = off_mesh_links->count();
    }

    if (recast_result.detail_mesh) {
        params.detailMeshes = recast_result.detail_mesh->meshes;
        params.detailVerts = recast_result.detail_mesh->verts;
        params.detailVertsCount = recast_result.detail_mesh->nverts;
        params.detailTris = recast_result.detail_mesh->tris;
        params.detailTriCount = recast_result.detail_mesh->ntris;
    }

    rcVcopy(params.bmin, pmesh->bmin);
    rcVcopy(params.bmax, pmesh->bmax);
    params.walkableHeight = config.agent_height;
    params.walkableRadius = config.agent_radius;
    params.walkableClimb = config.agent_max_climb;
    params.cs = pmesh->cs;
    params.ch = pmesh->ch;
    params.buildBvTree = true;

    unsigned char* nav_data = nullptr;
    int nav_data_size = 0;
    if (!dtCreateNavMeshData(&params, &nav_data, &nav_data_size) || !nav_data || nav_data_size <= 0) {
        result.error = "dtCreateNavMeshData failed";
        tc_log_error("[NavMesh] %s (verts=%d polys=%d nvp=%d offmesh=%d detail_verts=%d detail_tris=%d)",
                     result.error.c_str(),
                     params.vertCount,
                     params.polyCount,
                     params.nvp,
                     params.offMeshConCount,
                     params.detailVertsCount,
                     params.detailTriCount);
        return result;
    }

    result.data.assign(nav_data, nav_data + nav_data_size);
    result.success = true;
    dtFree(nav_data);
    return result;
}

} // namespace termin
