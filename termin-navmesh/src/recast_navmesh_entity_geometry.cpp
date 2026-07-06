#include <termin/navmesh/recast_navmesh_builder_component.hpp>
#include "recast_navmesh_bake_space.hpp"
#include <termin/navmesh/navmesh_bake_source.hpp>
#include <termin/geom/mat44.hpp>
#include <vector>
#include <tcbase/tc_log.hpp>

namespace termin {

namespace {

void append_bake_geometry(
    const NavMeshBakeInput& input,
    std::vector<float>& verts,
    std::vector<int>& tris,
    std::vector<unsigned char>& area_ids)
{
    for (const NavMeshGeometryBatch& batch : input.geometry) {
        const int base_vert = static_cast<int>(verts.size() / 3);
        verts.insert(verts.end(), batch.verts.begin(), batch.verts.end());
        for (int index : batch.tris) {
            tris.push_back(index + base_vert);
        }
        area_ids.insert(area_ids.end(), batch.triangle_area_ids.begin(), batch.triangle_area_ids.end());
    }
}

void collect_builder_scope_entities(Entity root, bool include_descendants, std::vector<Entity>& out) {
    if (!root.valid()) {
        return;
    }
    out.push_back(root);
    if (!include_descendants) {
        return;
    }
    for (Entity child : root.children()) {
        collect_builder_scope_entities(child, true, out);
    }
}

} // namespace

RecastBuildResult RecastNavMeshBuilderComponent::build_from_entity_geometry() {
    if (!entity().valid()) {
        tc_log_error("RecastNavMeshBuilderComponent: no entity");
        RecastBuildResult result;
        result.success = false;
        result.error = "builder component has no entity";
        return result;
    }

    double b_data[16];
    entity().get_world_matrix(b_data);
    GeneralPose3 base_pose = entity().transform().global_pose();
    Mat44 base_inv = recast_navmesh_builder_frame_inverse(entity());

    bool recurse = (mesh_source == static_cast<int>(MeshSource::AllDescendants));
    tc_log_info("[NavMesh] Build mode: %s, base entity: %s",
        recurse ? "AllDescendants" : "CurrentMesh",
        entity().name() ? entity().name() : "(unnamed)");
    tc_log_info("[NavMesh] Base world matrix col0: (%.2f, %.2f, %.2f, %.2f)",
        b_data[0], b_data[1], b_data[2], b_data[3]);
    tc_log_info("[NavMesh] Base world matrix col1: (%.2f, %.2f, %.2f, %.2f)",
        b_data[4], b_data[5], b_data[6], b_data[7]);
    tc_log_info("[NavMesh] Base world matrix col2: (%.2f, %.2f, %.2f, %.2f)",
        b_data[8], b_data[9], b_data[10], b_data[11]);
    tc_log_info("[NavMesh] Base world matrix col3 (pos): (%.2f, %.2f, %.2f, %.2f)",
        b_data[12], b_data[13], b_data[14], b_data[15]);
    tc_log_info("[NavMesh] Base bake frame keeps TR only: position=(%.2f, %.2f, %.2f) "
                "scale_preserved_in_geometry=(%.2f, %.2f, %.2f)",
        base_pose.lin.x, base_pose.lin.y, base_pose.lin.z,
        base_pose.scale.x, base_pose.scale.y, base_pose.scale.z);

    NavMeshBakeContext context;
    context.builder_entity = entity();
    context.world_to_bake = base_inv;
    context.agent_type_name = agent_type_name;
    context.agent_radius = agent_radius;
    context.agent_height = agent_height;
    context.agent_max_climb = agent_max_climb;
    context.default_area_id = area_id;

    std::vector<Entity> source_entities;
    collect_builder_scope_entities(entity(), recurse, source_entities);
    NavMeshBakeInput bake_input = collect_navmesh_bake_input(context, source_entities);

    std::vector<float> verts;
    std::vector<int> tris;
    std::vector<unsigned char> area_ids;

    append_bake_geometry(bake_input, verts, tris, area_ids);
    tc_log_info("[NavMesh] Collected %d navmesh bake geometry batch(es), %d off-mesh link(s)",
                static_cast<int>(bake_input.geometry.size()),
                bake_input.off_mesh_link_count());

    last_bake_input = bake_input;

    if (verts.empty() || tris.empty()) {
        tc_log_error("RecastNavMeshBuilderComponent: no mesh geometry found");
        RecastBuildResult result;
        result.success = false;
        result.error = "no mesh geometry found";
        return result;
    }

    int nverts = static_cast<int>(verts.size() / 3);
    int ntris = static_cast<int>(tris.size() / 3);

    tc_log_info("RecastNavMeshBuilderComponent: building from %d vertices, %d triangles", nverts, ntris);

    RecastBuildResult result = build_internal(
        verts.data(),
        nverts,
        tris.data(),
        ntris,
        area_ids.empty() ? nullptr : area_ids.data(),
        false);

    if (result.success) {
        tc_log_info("RecastNavMeshBuilderComponent: build successful (%d polys)",
                    result.poly_mesh ? result.poly_mesh->npolys : 0);
    } else {
        tc_log_error("RecastNavMeshBuilderComponent: build failed - %s", result.error.c_str());
    }
    return result;
}

void RecastNavMeshBuilderComponent::build_from_entity() {
    RecastBuildResult result = build_from_entity_geometry();
    if (result.success) {
        save_detour_asset(result);
    }
}

} // namespace termin
