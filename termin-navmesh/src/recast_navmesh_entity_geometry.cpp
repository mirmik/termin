#include <termin/navmesh/recast_navmesh_builder_component.hpp>
#include "recast_navmesh_bake_space.hpp"
#include <components/mesh_component.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/tc_scene.hpp>
#include <cstring>
#include <vector>
#include <tcbase/tc_log.hpp>

namespace termin {

namespace {

Mat44 mat44_from_mat44f(const Mat44f& value) {
    Mat44 result;
    for (int i = 0; i < 16; ++i) {
        result.data[i] = static_cast<double>(value.data[i]);
    }
    return result;
}

bool extract_mesh_positions(
    const TcMesh& mesh,
    const Mat44& transform,
    std::vector<float>& out_verts,
    std::vector<int>& out_tris)
{
    tc_mesh* m = mesh.get();
    if (!m || !m->vertices || m->vertex_count == 0) return false;
    if (!m->indices || m->index_count == 0) return false;

    const tc_vertex_attrib* pos = tc_vertex_layout_find(&m->layout, "position");
    if (!pos || pos->size != 3) return false;

    size_t n = m->vertex_count;
    size_t stride = m->layout.stride;
    const uint8_t* src = static_cast<const uint8_t*>(m->vertices);

    size_t base_vert = out_verts.size() / 3;
    out_verts.resize(out_verts.size() + n * 3);
    float* dst = out_verts.data() + base_vert * 3;
    for (size_t i = 0; i < n; ++i) {
        const float* p = reinterpret_cast<const float*>(src + i * stride + pos->offset);
        Vec3 local_pos{p[0], p[1], p[2]};
        Vec3 bake_pos = transform.transform_point(local_pos);
        dst[i * 3] = static_cast<float>(bake_pos.x);
        dst[i * 3 + 1] = static_cast<float>(bake_pos.z);
        dst[i * 3 + 2] = static_cast<float>(bake_pos.y);

        if (i < 3) {
            tc_log_info(
                "[NavMesh] vert[%zu]: mesh_local=(%.2f, %.2f, %.2f) -> bake=(%.2f, %.2f, %.2f) -> recast=(%.2f, %.2f, %.2f)",
                i, p[0], p[1], p[2],
                bake_pos.x, bake_pos.y, bake_pos.z,
                dst[i * 3], dst[i * 3 + 1], dst[i * 3 + 2]);
        }
    }

    size_t num_tris = m->index_count / 3;
    size_t base_tri = out_tris.size();
    out_tris.resize(out_tris.size() + num_tris * 3);
    for (size_t i = 0; i < num_tris * 3; ++i) {
        out_tris[base_tri + i] = static_cast<int>(m->indices[i] + base_vert);
    }

    return true;
}

void collect_meshes_recursive(
    Entity ent,
    const Mat44& base_inv,
    std::vector<float>& verts,
    std::vector<int>& tris,
    bool recurse)
{
    if (!ent.valid()) return;

    double w_data[16];
    ent.get_world_matrix(w_data);
    Mat44 world;
    std::memcpy(world.ptr(), w_data, sizeof(w_data));

    Mat44 local_to_bake = base_inv * world;

    MeshComponent* mesh_component = ent.get_component<MeshComponent>();
    if (mesh_component && mesh_component->mesh.is_valid()) {
        Mat44 mesh_to_bake = local_to_bake * mat44_from_mat44f(mesh_component->get_mesh_offset_matrix());
        tc_log_info("[NavMesh] Processing entity: %s", ent.name() ? ent.name() : "(unnamed)");
        tc_log_info("[NavMesh]   world col0: (%.2f, %.2f, %.2f, %.2f)", w_data[0], w_data[1], w_data[2], w_data[3]);
        tc_log_info("[NavMesh]   world col3: (%.2f, %.2f, %.2f, %.2f)", w_data[12], w_data[13], w_data[14], w_data[15]);
        extract_mesh_positions(mesh_component->mesh, mesh_to_bake, verts, tris);
    }

    if (recurse) {
        for (Entity child : ent.children()) {
            collect_meshes_recursive(child, base_inv, verts, tris, true);
        }
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

    std::vector<float> verts;
    std::vector<int> tris;

    collect_meshes_recursive(entity(), base_inv, verts, tris, recurse);

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

    RecastBuildResult result = build(verts.data(), nverts, tris.data(), ntris);

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
