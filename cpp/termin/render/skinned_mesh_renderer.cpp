#include "skinned_mesh_renderer.hpp"
#include "skeleton_controller.hpp"
#include "graphics_backend.hpp"
#include "termin/entity/entity.hpp"
#include "tc_log.hpp"
#include <iostream>
#include <algorithm>

namespace termin {

SkinnedMeshRenderer::SkinnedMeshRenderer()
    : MeshRenderer()
{
    _type_name = "SkinnedMeshRenderer";
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

void SkinnedMeshRenderer::upload_bone_matrices(ShaderProgram& shader) {
    if (_bone_count == 0 || _bone_matrices_flat.empty()) {
        return;
    }

    shader.set_uniform_matrix4_array("u_bone_matrices", _bone_matrices_flat.data(), _bone_count, false);
    shader.set_uniform_int("u_bone_count", _bone_count);
}

Material* SkinnedMeshRenderer::get_skinned_material() {
    Material* base_mat = get_material();
    if (base_mat == nullptr) {
        return nullptr;
    }

    // Check if cache is still valid
    int base_mat_id = reinterpret_cast<intptr_t>(base_mat);
    if (_skinned_material_cache != nullptr && _cached_base_material_id == base_mat_id) {
        return _skinned_material_cache;
    }

    // Check if shader already has skinning
    if (!base_mat->phases.empty() && base_mat->phases[0].shader) {
        const std::string& vert_source = base_mat->phases[0].shader->vertex_source();
        if (vert_source.find("u_bone_matrices") != std::string::npos) {
            // Already has skinning, use as-is
            _skinned_material_cache = base_mat;
            _cached_base_material_id = base_mat_id;
            return base_mat;
        }
    }

    // Create skinned variant via Python
    try {
        nb::object skinning_module = nb::module_::import_("termin.visualization.render.shader_skinning");
        nb::object skinned_mat_obj = skinning_module.attr("get_skinned_material")(base_mat);
        if (!skinned_mat_obj.is_none()) {
            _skinned_material_cache = nb::cast<Material*>(skinned_mat_obj);
            _cached_base_material_id = base_mat_id;
            return _skinned_material_cache;
        }
    } catch (const nb::python_error& e) {
        tc::Log::warn(e, "SkinnedMeshRenderer::get_skinned_material");
        PyErr_Clear();
    }

    tc::Log::warn("[SkinnedMeshRenderer::get_skinned_material] failed to inject skinning into '%s'",
        base_mat->name.c_str());
    return base_mat;
}

void SkinnedMeshRenderer::draw_geometry(const RenderContext& context, const std::string& geometry_id) {
    if (!mesh.is_valid()) {
        return;
    }

    ShaderProgram* shader_to_use = context.current_shader;

    // Check if current shader needs skinning injection
    if (_skeleton_controller != nullptr && context.current_shader != nullptr) {
        update_bone_matrices();

        if (_bone_count > 0) {
            // Check if shader already has skinning
            const std::string& vert_source = context.current_shader->vertex_source();
            bool has_skinning = vert_source.find("u_bone_matrices") != std::string::npos;

            if (!has_skinning) {
                // Need to inject skinning into this shader
                try {
                    nb::object skinning_module = nb::module_::import_("termin.visualization.render.shader_skinning");
                    nb::object skinned_shader_obj = skinning_module.attr("get_skinned_shader")(context.current_shader);
                    if (!skinned_shader_obj.is_none()) {
                        shader_to_use = nb::cast<ShaderProgram*>(skinned_shader_obj);
                        // Ensure shader is compiled
                        GraphicsBackend* graphics = context.graphics;
                        shader_to_use->ensure_ready([graphics](const char* v, const char* f, const char* g) {
                            return graphics->create_shader(v, f, g);
                        });
                        // Use the skinned shader
                        shader_to_use->use();
                        // Re-apply uniforms from original shader context
                        shader_to_use->set_uniform_matrix4("u_view", context.view, false);
                        shader_to_use->set_uniform_matrix4("u_projection", context.projection, false);
                        shader_to_use->set_uniform_matrix4("u_model", context.model, false);

                        // Apply extra_uniforms (e.g., u_pickColor for IdPass)
                        if (context.extra_uniforms.ptr() != nullptr &&
                            !context.extra_uniforms.is_none() &&
                            nb::isinstance<nb::dict>(context.extra_uniforms)) {
                            nb::dict extra = nb::cast<nb::dict>(context.extra_uniforms);
                            for (auto item : extra) {
                                std::string name = nb::cast<std::string>(nb::str(item.first));
                                nb::tuple val_tuple = nb::cast<nb::tuple>(item.second);
                                if (nb::len(val_tuple) >= 2) {
                                    std::string type_name = nb::cast<std::string>(val_tuple[0]);
                                    if (type_name == "vec3") {
                                        nb::tuple val = nb::cast<nb::tuple>(val_tuple[1]);
                                        float x = nb::cast<float>(val[0]);
                                        float y = nb::cast<float>(val[1]);
                                        float z = nb::cast<float>(val[2]);
                                        shader_to_use->set_uniform_vec3(name.c_str(), x, y, z);
                                    } else if (type_name == "float") {
                                        float val = nb::cast<float>(val_tuple[1]);
                                        shader_to_use->set_uniform_float(name.c_str(), val);
                                    } else if (type_name == "int") {
                                        int val = nb::cast<int>(val_tuple[1]);
                                        shader_to_use->set_uniform_int(name.c_str(), val);
                                    }
                                }
                            }
                        }
                    }
                } catch (const nb::python_error& e) {
                    tc::Log::warn(e, "SkinnedMeshRenderer::draw_geometry skinning injection");
                    PyErr_Clear();
                }
            }

            upload_bone_matrices(*shader_to_use);
        }
    }

    // Draw the mesh via GPU (uses inherited _mesh_gpu from MeshRenderer)
    _mesh_gpu.draw(context, mesh.get(), mesh.version());
}

std::vector<GeometryDrawCall> SkinnedMeshRenderer::get_geometry_draws(const std::string* phase_mark) {
    Material* mat = get_skinned_material();
    if (mat == nullptr) {
        return {};
    }

    std::vector<GeometryDrawCall> result;
    for (auto& phase : mat->phases) {
        if (phase_mark == nullptr || phase_mark->empty() || phase.phase_mark == *phase_mark) {
            result.emplace_back(&phase, "");
        }
    }

    std::sort(result.begin(), result.end(), [](const GeometryDrawCall& a, const GeometryDrawCall& b) {
        return a.phase->priority < b.phase->priority;
    });

    return result;
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
