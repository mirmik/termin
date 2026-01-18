#include "skinned_mesh_renderer.hpp"
#include "skeleton_controller.hpp"
#include "graphics_backend.hpp"
#include "termin/entity/entity.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "tc_log.hpp"
#include <iostream>
#include <algorithm>
#include <unordered_map>
#include <cstring>

namespace termin {

// Hash for TcShader (uses handle.index)
struct TcShaderHash {
    size_t operator()(const TcShader& s) const {
        return std::hash<uint32_t>()(s.handle.index);
    }
};

struct TcShaderEqual {
    bool operator()(const TcShader& a, const TcShader& b) const {
        return a.handle.index == b.handle.index && a.handle.generation == b.handle.generation;
    }
};

// Static cache: original shader -> skinned shader
static std::unordered_map<TcShader, TcShader, TcShaderHash, TcShaderEqual> s_skinned_shader_cache;

SkinnedMeshRenderer::SkinnedMeshRenderer()
    : MeshRenderer()
{
    set_type_name("SkinnedMeshRenderer");
}

void SkinnedMeshRenderer::set_skeleton_controller(SkeletonController* controller) {
    _skeleton_controller = controller;
}

SkeletonInstance* SkinnedMeshRenderer::skeleton_instance() {
    if (_skeleton_controller == nullptr) {
        return nullptr;
    }
    return _skeleton_controller->skeleton_instance();
}

void SkinnedMeshRenderer::update_bone_matrices() {
    SkeletonInstance* si = skeleton_instance();
    if (si == nullptr) {
        _bone_count = 0;
        _bone_matrices_flat.clear();
        return;
    }

    // Get bone count (skeleton was already updated in SkeletonController::before_render)
    _bone_count = si->bone_count();
    if (_bone_count == 0) {
        _bone_matrices_flat.clear();
        return;
    }

    // Resize buffer
    _bone_matrices_flat.resize(_bone_count * 16);

    // Copy matrices (column-major for OpenGL)
    for (int i = 0; i < _bone_count; ++i) {
        const Mat44& m = si->get_bone_matrix(i);
        // Mat44 is column-major, copy directly
        for (int j = 0; j < 16; ++j) {
            _bone_matrices_flat[i * 16 + j] = static_cast<float>(m.data[j]);
        }
    }
}

void SkinnedMeshRenderer::upload_bone_matrices(TcShader& shader) {
    if (_bone_count == 0 || _bone_matrices_flat.empty()) {
        return;
    }

    shader.set_uniform_mat4_array("u_bone_matrices", _bone_matrices_flat.data(), _bone_count, false);
    shader.set_uniform_int("u_bone_count", _bone_count);
}

TcShader SkinnedMeshRenderer::override_shader(
    const std::string& phase_mark,
    int geometry_id,
    TcShader original_shader
) {
    if (_skeleton_controller == nullptr || !original_shader.is_valid()) {
        return original_shader;
    }

    // Check if shader already has skinning
    const char* vert_source = original_shader.vertex_source();
    if (vert_source && std::strstr(vert_source, "u_bone_matrices") != nullptr) {
        return original_shader;
    }

    // Check C++ cache first
    auto it = s_skinned_shader_cache.find(original_shader);
    if (it != s_skinned_shader_cache.end()) {
        TcShader& cached = it->second;
        // Check if variant is stale (original shader was modified)
        if (!cached.variant_is_stale()) {
            return cached;
        }
        // Stale - need to recreate
        s_skinned_shader_cache.erase(it);
    }

    // Inject skinning via Python (only on cache miss)
    try {
        nb::object skinning_module = nb::module_::import_("termin.visualization.render.shader_skinning");
        nb::object skinned_obj = skinning_module.attr("get_skinned_shader_handle")(original_shader.handle);
        if (!skinned_obj.is_none()) {
            TcShader skinned = nb::cast<TcShader>(skinned_obj);
            // Cache the result
            s_skinned_shader_cache[original_shader] = skinned;
            return skinned;
        }
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "SkinnedMeshRenderer::override_shader");
        PyErr_Clear();
    }

    return original_shader;
}

void SkinnedMeshRenderer::draw_geometry(const RenderContext& context, int geometry_id) {
    if (!mesh.is_valid()) {
        return;
    }

    // Upload bone matrices if we have a skeleton
    if (_skeleton_controller != nullptr && context.current_tc_shader.is_valid()) {
        update_bone_matrices();
        if (_bone_count > 0) {
            // Use TcShader for uniform upload
            TcShader shader = context.current_tc_shader;
            upload_bone_matrices(shader);
        }
    }

    // Draw the mesh via GPU (uses inherited _mesh_gpu from MeshRenderer)
    _mesh_gpu.draw(context, mesh.get(), mesh.version());
}

std::vector<GeometryDrawCall> SkinnedMeshRenderer::get_geometry_draws(const std::string* phase_mark) {
    // Use parent implementation - shader override happens in override_shader()
    return MeshRenderer::get_geometry_draws(phase_mark);
}

void SkinnedMeshRenderer::start() {
    Component::start();

    // After deserialization, skeleton_controller may be null - try to find it
    if (_skeleton_controller == nullptr && entity.valid()) {
        // Look for SkeletonController by type name
        // Check parent entity first (typical for GLB structure)
        Entity parent_entity = entity.parent();

        if (parent_entity.valid()) {
            Component* controller = parent_entity.get_component_by_type("SkeletonController");
            if (controller != nullptr) {
                _skeleton_controller = dynamic_cast<SkeletonController*>(controller);
            }
        }

        // Also check current entity
        if (_skeleton_controller == nullptr) {
            Component* controller = entity.get_component_by_type("SkeletonController");
            if (controller != nullptr) {
                _skeleton_controller = dynamic_cast<SkeletonController*>(controller);
            }
        }
    }
}

} // namespace termin
