#pragma once

#include <algorithm>
#include <cmath>
#include <set>
#include <string>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include <termin/geom/general_transform3.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <termin/render/drawable.hpp>
#include <tc_log.h>

#include <termin/navmesh/detour_navmesh_asset_utils.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>

namespace termin {

inline constexpr const char* OFF_MESH_LINK_DEBUG_PHASE = "editor_debug_transparent";
inline constexpr const char* OFF_MESH_LINK_DEBUG_SHADER_UUID = "termin-engine-off-mesh-link-debug";

enum class OffMeshLinkType : int {
    Generic = 0,
    JumpDown = 1,
    Jump = 2,
    Climb = 3,
};

class TERMIN_NAVMESH_COMPONENTS_API OffMeshLinkComponent : public CxxComponent, public Drawable {
public:
    bool enabled = true;
    int link_type = static_cast<int>(OffMeshLinkType::JumpDown);
    std::string agent_type = "Human";
    int area_id = 0;
    tc_vec3 start_local = {0.0, 0.0, 0.0};
    tc_vec3 end_local = {0.0, 1.0, -1.0};
    double radius = 0.35;
    bool bidirectional = false;

    void center_entity();

    OffMeshLinkComponent()
        : CxxComponent("OffMeshLinkComponent")
    {
        install_drawable_vtable(&_c);
    }

    static void register_type();

    OffMeshLinkType type() const {
        if (link_type == static_cast<int>(OffMeshLinkType::Generic)) {
            return OffMeshLinkType::Generic;
        }
        if (link_type == static_cast<int>(OffMeshLinkType::JumpDown)) {
            return OffMeshLinkType::JumpDown;
        }
        if (link_type == static_cast<int>(OffMeshLinkType::Jump)) {
            return OffMeshLinkType::Jump;
        }
        if (link_type == static_cast<int>(OffMeshLinkType::Climb)) {
            return OffMeshLinkType::Climb;
        }
        tc_log(TC_LOG_ERROR, "[OffMeshLinkComponent] invalid link_type=%d, using Generic", link_type);
        return OffMeshLinkType::Generic;
    }

    Vec3 start_world() const {
        return local_to_world(start_local);
    }

    Vec3 end_world() const {
        return local_to_world(end_local);
    }

    std::set<std::string> get_phase_marks() const override {
        return {OFF_MESH_LINK_DEBUG_PHASE};
    }

    void draw_geometry(const RenderContext& context, int geometry_id = 0) override {
        (void)context;
        (void)geometry_id;
        ensure_debug_resources();
    }

    std::vector<GeometryDrawCall> get_geometry_draws(const std::string* phase_mark = nullptr) override {
        std::vector<GeometryDrawCall> result;
        if (!enabled) {
            return result;
        }
        if (phase_mark && *phase_mark != OFF_MESH_LINK_DEBUG_PHASE) {
            return result;
        }
        if (!ensure_debug_resources()) {
            return result;
        }

        tc_material* material = _debug_material.get();
        if (!material) {
            return result;
        }

        for (size_t i = 0; i < material->phase_count; ++i) {
            tc_material_phase* phase = &material->phases[i];
            if (phase_mark && phase->phase_mark != *phase_mark) {
                continue;
            }
            result.emplace_back(phase, 0);
        }
        return result;
    }

    tc_mesh* get_mesh_for_phase(const std::string& phase_mark, int geometry_id) const override {
        (void)geometry_id;
        if (!enabled && phase_mark != "pick") {
            return nullptr;
        }
        if (phase_mark == "pick") {
            return ensure_debug_mesh() && _debug_mesh.is_valid() ? _debug_mesh.get() : nullptr;
        }
        if (phase_mark != OFF_MESH_LINK_DEBUG_PHASE) {
            return nullptr;
        }
        return ensure_debug_resources() && _debug_mesh.is_valid() ? _debug_mesh.get() : nullptr;
    }

private:
    struct Vertex {
        float position[3];
        float normal[3];
        float uv[2];
    };

    mutable TcMesh _debug_mesh;
    mutable TcMaterial _debug_material;
    mutable tc_vec3 _mesh_start = {0.0, 0.0, 0.0};
    mutable tc_vec3 _mesh_end = {0.0, 0.0, 0.0};
    mutable bool _mesh_bidirectional = false;

    Vec3 local_to_world(const tc_vec3& value) const {
        Entity ent = entity();
        if (!ent.valid()) {
            tc_log(TC_LOG_ERROR, "[OffMeshLinkComponent] cannot convert point: entity is invalid");
            return Vec3{value.x, value.y, value.z};
        }
        return ent.transform().transform_point(Vec3{value.x, value.y, value.z});
    }

    bool ensure_debug_resources() const {
        return ensure_debug_mesh() && ensure_debug_material();
    }

    bool ensure_debug_mesh() const {
        if (!_debug_mesh.is_valid()) {
            tc_mesh_handle handle = tc_mesh_create(nullptr);
            _debug_mesh = TcMesh(handle);
            if (!_debug_mesh.is_valid()) {
                tc_log(TC_LOG_ERROR, "[OffMeshLinkComponent] failed to create debug mesh");
                return false;
            }
        }

        if (same_vec3(_mesh_start, start_local) &&
            same_vec3(_mesh_end, end_local) &&
            _mesh_bidirectional == bidirectional) {
            return true;
        }

        return rebuild_debug_mesh();
    }

    bool rebuild_debug_mesh() const {
        tc_mesh* mesh = _debug_mesh.get();
        if (!mesh) {
            tc_log(TC_LOG_ERROR, "[OffMeshLinkComponent] failed to rebuild debug mesh: mesh is null");
            return false;
        }

        std::vector<Vertex> vertices;
        std::vector<uint32_t> indices;
        vertices.reserve(bidirectional ? 10 : 6);
        indices.reserve(bidirectional ? 10 : 6);

        append_segment(vertices, indices, start_local, end_local);
        append_arrow(vertices, indices, start_local, end_local);
        if (bidirectional) {
            append_arrow(vertices, indices, end_local, start_local);
        }

        tc_vertex_layout layout = tc_vertex_layout_pos_normal_uv();
        if (!tc_mesh_set_data(
                mesh,
                vertices.data(),
                vertices.size(),
                &layout,
                indices.data(),
                indices.size(),
                "termin_off_mesh_link_debug_mesh")) {
            tc_log(TC_LOG_ERROR, "[OffMeshLinkComponent] failed to set debug mesh data");
            return false;
        }

        mesh->draw_mode = TC_DRAW_LINES;
        _mesh_start = start_local;
        _mesh_end = end_local;
        _mesh_bidirectional = bidirectional;
        return true;
    }

    static bool same_vec3(const tc_vec3& a, const tc_vec3& b) {
        return a.x == b.x && a.y == b.y && a.z == b.z;
    }

    static void append_vertex(std::vector<Vertex>& vertices, const tc_vec3& p) {
        vertices.push_back(Vertex{
            {static_cast<float>(p.x), static_cast<float>(p.y), static_cast<float>(p.z)},
            {0.0f, 0.0f, 1.0f},
            {0.0f, 0.0f},
        });
    }

    static void append_segment(std::vector<Vertex>& vertices, std::vector<uint32_t>& indices,
                               const tc_vec3& a, const tc_vec3& b) {
        uint32_t base = static_cast<uint32_t>(vertices.size());
        append_vertex(vertices, a);
        append_vertex(vertices, b);
        indices.push_back(base);
        indices.push_back(base + 1);
    }

    static void append_arrow(std::vector<Vertex>& vertices, std::vector<uint32_t>& indices,
                             const tc_vec3& from, const tc_vec3& to) {
        double dx = to.x - from.x;
        double dy = to.y - from.y;
        double dz = to.z - from.z;
        double len = std::sqrt(dx * dx + dy * dy + dz * dz);
        if (len <= 0.0001) {
            return;
        }

        dx /= len;
        dy /= len;
        dz /= len;

        double side_x = -dy;
        double side_y = dx;
        double side_z = 0.0;
        double side_len = std::sqrt(side_x * side_x + side_y * side_y);
        if (side_len <= 0.0001) {
            side_x = 1.0;
            side_y = 0.0;
        } else {
            side_x /= side_len;
            side_y /= side_len;
        }

        double head_len = std::max(0.15, std::min(0.6, len * 0.2));
        double head_width = head_len * 0.45;
        tc_vec3 left = {
            to.x - dx * head_len + side_x * head_width,
            to.y - dy * head_len + side_y * head_width,
            to.z - dz * head_len + side_z * head_width,
        };
        tc_vec3 right = {
            to.x - dx * head_len - side_x * head_width,
            to.y - dy * head_len - side_y * head_width,
            to.z - dz * head_len - side_z * head_width,
        };

        append_segment(vertices, indices, to, left);
        append_segment(vertices, indices, to, right);
    }

    bool ensure_debug_material() const {
        if (_debug_material.is_valid()) {
            return _debug_material.find_phase(OFF_MESH_LINK_DEBUG_PHASE) != nullptr;
        }

        _debug_material = TcMaterial::create("termin_off_mesh_link_debug_material");
        if (!_debug_material.is_valid()) {
            tc_log(TC_LOG_ERROR, "[OffMeshLinkComponent] failed to create debug material");
            return false;
        }
        if (_debug_material.find_phase(OFF_MESH_LINK_DEBUG_PHASE)) {
            return true;
        }

        tc_render_state state = tc_render_state_transparent();
        state.depth_test = 1;
        state.depth_write = 0;
        state.cull = 0;

        tc_material_phase* phase = add_builtin_slang_debug_phase(
            _debug_material,
            OFF_MESH_LINK_DEBUG_SHADER_UUID,
            "termin_off_mesh_link_debug_shader",
            OFF_MESH_LINK_DEBUG_PHASE,
            30,
            state);

        if (!phase) {
            tc_log(TC_LOG_ERROR, "[OffMeshLinkComponent] failed to add debug material phase");
            return false;
        }
        return true;
    }
};

inline void OffMeshLinkComponent::center_entity() {
    Entity ent = entity();
    if (!ent.valid()) {
        tc_log(TC_LOG_ERROR, "[OffMeshLinkComponent] cannot center entity: entity is invalid");
        return;
    }

    Vec3 old_start = start_world();
    Vec3 old_end = end_world();
    Vec3 center = (old_start + old_end) * 0.5;

    GeneralPose3 new_pose = ent.transform().global_pose();
    new_pose.lin = center;
    ent.transform().relocate_global(new_pose);

    GeneralPose3 centered_pose = ent.transform().global_pose();
    Vec3 new_start_local = centered_pose.inverse_transform_point(old_start);
    Vec3 new_end_local = centered_pose.inverse_transform_point(old_end);
    start_local = tc_vec3{new_start_local.x, new_start_local.y, new_start_local.z};
    end_local = tc_vec3{new_end_local.x, new_end_local.y, new_end_local.z};

    tc_log(TC_LOG_INFO,
           "[OffMeshLinkComponent] centered entity '%s' at (%.3f, %.3f, %.3f)",
           ent.name(), center.x, center.y, center.z);
}

} // namespace termin
