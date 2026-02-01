// material_pass.cpp - Post-processing pass using a Material

#include "material_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/material/tc_material_handle.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "tc_log.hpp"

extern "C" {
#include "termin_core.h"
}

namespace termin {

// Static quad VAO/VBO
uint32_t MaterialPass::s_quad_vao = 0;
uint32_t MaterialPass::s_quad_vbo = 0;

MaterialPass::MaterialPass() {
    pass_name_set("MaterialPass");
    link_to_type_registry("MaterialPass");
}

MaterialPass::~MaterialPass() {
    destroy();
}

void MaterialPass::set_material_name(const std::string& name) {
    material_name_ = name;
    if (!name.empty() && name != "(None)") {
        load_material();
    } else {
        material_handle_ = tc_material_handle_invalid();
    }
}

void MaterialPass::set_texture_resource(const std::string& uniform_name, const std::string& resource_name) {
    texture_resources_[uniform_name] = resource_name;
}

void MaterialPass::add_resource(const std::string& resource_name, const std::string& uniform_name) {
    std::string uname = uniform_name.empty() ? ("u_" + resource_name) : uniform_name;
    extra_resources_[resource_name] = uname;
}

void MaterialPass::remove_resource(const std::string& resource_name) {
    extra_resources_.erase(resource_name);
}

void MaterialPass::set_before_draw(BeforeDrawCallback callback) {
    before_draw_callback_ = std::move(callback);
}

void MaterialPass::load_material() {
    material_handle_ = tc_material_find_by_name(material_name_.c_str());
    if (tc_material_handle_is_invalid(material_handle_)) {
        tc::Log::warn("[MaterialPass] Material '%s' not found", material_name_.c_str());
    }
}

std::set<const char*> MaterialPass::compute_reads() const {
    std::set<const char*> reads;

    // Add extra resources
    for (const auto& [res_name, uniform_name] : extra_resources_) {
        reads.insert(res_name.c_str());
    }

    // Add texture resources
    for (const auto& [uniform_name, res_name] : texture_resources_) {
        if (!res_name.empty()) {
            reads.insert(res_name.c_str());
        }
    }

    return reads;
}

std::set<const char*> MaterialPass::compute_writes() const {
    return {output_res_.c_str()};
}

void MaterialPass::execute(ExecuteContext& ctx) {
    if (!enabled_get()) {
        return;
    }

    // Get output FBO
    FramebufferHandle* output_fbo = nullptr;
    auto it = ctx.writes_fbos.find(output_res_);
    if (it != ctx.writes_fbos.end()) {
        output_fbo = dynamic_cast<FramebufferHandle*>(it->second);
    }

    // Get output size
    int w, h;
    if (output_fbo != nullptr) {
        w = output_fbo->get_width();
        h = output_fbo->get_height();
    } else {
        w = ctx.rect.width;
        h = ctx.rect.height;
    }

    // Bind output FBO
    ctx.graphics->bind_framebuffer(output_fbo);
    ctx.graphics->set_viewport(0, 0, w, h);

    // Standard post-effect state
    ctx.graphics->set_depth_test(false);
    ctx.graphics->set_depth_mask(false);
    ctx.graphics->set_blend(false);

    // Get material
    tc_material* mat = tc_material_get(material_handle_);
    if (!mat || mat->phase_count == 0) {
        // No material - just clear or skip
        ctx.graphics->set_depth_test(true);
        ctx.graphics->set_depth_mask(true);
        return;
    }

    // Get first phase
    tc_material_phase* phase = &mat->phases[0];
    tc_shader* shader = tc_shader_get(phase->shader);
    if (!shader) {
        tc::Log::warn("[MaterialPass] Material '%s' has no valid shader", material_name_.c_str());
        ctx.graphics->set_depth_test(true);
        ctx.graphics->set_depth_mask(true);
        return;
    }

    // Compile and use shader
    if (tc_shader_compile_gpu(shader) == 0) {
        tc::Log::error("[MaterialPass] Failed to compile shader for material '%s'", material_name_.c_str());
        ctx.graphics->set_depth_test(true);
        ctx.graphics->set_depth_mask(true);
        return;
    }
    tc_shader_use_gpu(shader);

    int texture_unit = 0;
    std::set<std::string> bound_uniforms;

    // Bind extra resources
    for (const auto& [res_name, uniform_name] : extra_resources_) {
        auto res_it = ctx.reads_fbos.find(res_name);
        if (res_it == ctx.reads_fbos.end()) continue;

        FramebufferHandle* fbo = dynamic_cast<FramebufferHandle*>(res_it->second);
        if (!fbo) continue;

        GPUTextureHandle* tex = fbo->color_texture();
        if (tex) {
            tex->bind(texture_unit);
            tc_shader_set_int(shader, uniform_name.c_str(), texture_unit);
            texture_unit++;
            bound_uniforms.insert(uniform_name);
        }
    }

    // Bind texture resources (uniform_name -> resource_name)
    for (const auto& [uniform_name, res_name] : texture_resources_) {
        if (res_name.empty()) continue;

        auto res_it = ctx.reads_fbos.find(res_name);
        if (res_it == ctx.reads_fbos.end()) continue;

        FramebufferHandle* fbo = dynamic_cast<FramebufferHandle*>(res_it->second);
        if (!fbo) continue;

        GPUTextureHandle* tex = fbo->color_texture();
        if (tex) {
            tex->bind(texture_unit);
            tc_shader_set_int(shader, uniform_name.c_str(), texture_unit);
            texture_unit++;
            bound_uniforms.insert(uniform_name);
        }
    }

    // Set u_resolution
    tc_shader_set_vec2(shader, "u_resolution", static_cast<float>(w), static_cast<float>(h));

    // Bind material textures (skip those already bound from framegraph)
    for (size_t i = 0; i < phase->texture_count; i++) {
        const tc_material_texture* mat_tex = &phase->textures[i];
        if (bound_uniforms.count(mat_tex->name) > 0) continue;

        tc_texture* tex = tc_texture_get(mat_tex->texture);
        if (tex) {
            tc_texture_upload_gpu(tex);
            tc_texture_bind_gpu(tex, texture_unit);
            tc_shader_set_int(shader, mat_tex->name, texture_unit);
            texture_unit++;
        }
    }

    // Set material uniforms
    for (size_t i = 0; i < phase->uniform_count; i++) {
        const tc_uniform_value* uniform = &phase->uniforms[i];
        switch (uniform->type) {
            case TC_UNIFORM_BOOL:
            case TC_UNIFORM_INT:
                tc_shader_set_int(shader, uniform->name, uniform->data.i);
                break;
            case TC_UNIFORM_FLOAT:
                tc_shader_set_float(shader, uniform->name, uniform->data.f);
                break;
            case TC_UNIFORM_VEC2:
                tc_shader_set_vec2(shader, uniform->name, uniform->data.v2[0], uniform->data.v2[1]);
                break;
            case TC_UNIFORM_VEC3:
                tc_shader_set_vec3(shader, uniform->name, uniform->data.v3[0], uniform->data.v3[1], uniform->data.v3[2]);
                break;
            case TC_UNIFORM_VEC4:
                tc_shader_set_vec4(shader, uniform->name, uniform->data.v4[0], uniform->data.v4[1], uniform->data.v4[2], uniform->data.v4[3]);
                break;
            case TC_UNIFORM_MAT4:
                tc_shader_set_mat4(shader, uniform->name, uniform->data.m4, false);
                break;
            default:
                break;
        }
    }

    // Call before_draw callback
    if (before_draw_callback_) {
        TcShader shader_wrapper(phase->shader);
        before_draw_callback_(&shader_wrapper);
    }

    // Draw fullscreen quad
    draw_fullscreen_quad(ctx.graphics);

    // Restore state
    ctx.graphics->set_depth_test(true);
    ctx.graphics->set_depth_mask(true);
}

void MaterialPass::draw_fullscreen_quad(GraphicsBackend* graphics) {
    graphics->draw_ui_textured_quad();
}

void MaterialPass::destroy() {
    before_draw_callback_ = nullptr;
    material_handle_ = tc_material_handle_invalid();
    texture_resources_.clear();
    extra_resources_.clear();
}

TC_REGISTER_FRAME_PASS(MaterialPass);

} // namespace termin
