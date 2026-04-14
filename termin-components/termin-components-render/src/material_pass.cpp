// material_pass.cpp - Post-processing pass using a Material.
//
// Fully migrated to tgfx2: wraps the output FBO as a tgfx2 texture,
// opens a ctx2 render pass, binds the material's own VS/FS through
// tc_shader_ensure_tgfx2, applies @property UBO via
// tc_material_phase_apply_ubo_gl (the C-API callback), and draws the
// built-in fullscreen quad. No legacy GraphicsBackend draw calls.

#include <tcbase/tc_log.hpp>
#include <tgfx/tgfx_shader_handle.hpp>

#include <termin/render/material_pass.hpp>
#include <termin/render/tgfx2_bridge.hpp>

#include <tgfx2/render_context.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/opengl/opengl_render_device.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

namespace termin {

uint32_t MaterialPass::s_quad_vao = 0;
uint32_t MaterialPass::s_quad_vbo = 0;

MaterialPass::MaterialPass() {
    pass_name_set("MaterialPass");
    link_to_type_registry("MaterialPass");
}

MaterialPass::~MaterialPass() {
    destroy();
}

void MaterialPass::set_texture_resource(const std::string& uniform_name, const std::string& resource_name) {
    texture_resources[uniform_name] = resource_name;
}

void MaterialPass::add_resource(const std::string& resource_name, const std::string& uniform_name) {
    std::string uname;
    if (uniform_name.empty()) {
        uname = "u_" + resource_name;
    } else if (uniform_name.rfind("u_", 0) != 0) {
        uname = "u_" + uniform_name;
    } else {
        uname = uniform_name;
    }
    extra_resources[resource_name] = uname;
}

void MaterialPass::remove_resource(const std::string& resource_name) {
    extra_resources.erase(resource_name);
}

void MaterialPass::set_before_draw(BeforeDrawCallback callback) {
    before_draw_callback_ = std::move(callback);
}

std::set<const char*> MaterialPass::compute_reads() const {
    std::set<const char*> reads;

    for (const auto& [res_name, uniform_name] : extra_resources) {
        (void)uniform_name;
        reads.insert(res_name.c_str());
    }

    for (const auto& [uniform_name, res_name] : texture_resources) {
        (void)uniform_name;
        if (!res_name.empty()) {
            reads.insert(res_name.c_str());
        }
    }

    return reads;
}

std::set<const char*> MaterialPass::compute_writes() const {
    return {output_res.c_str()};
}

void MaterialPass::execute(ExecuteContext& ctx) {
    if (!enabled_get()) {
        return;
    }

    if (!ctx.ctx2) {
        tc::Log::error("[MaterialPass] '%s': ctx.ctx2 is null — MaterialPass is tgfx2-only",
                       get_pass_name().c_str());
        return;
    }
    auto* ctx2 = ctx.ctx2;
    auto& device = ctx2->device();
    auto* gl_dev = dynamic_cast<tgfx2::OpenGLRenderDevice*>(&device);
    if (!gl_dev) {
        tc::Log::error("[MaterialPass] '%s': tgfx2 device is not OpenGLRenderDevice",
                       get_pass_name().c_str());
        return;
    }

    FramebufferHandle* output_fbo = nullptr;
    auto it = ctx.writes_fbos.find(output_res);
    if (it != ctx.writes_fbos.end()) {
        output_fbo = dynamic_cast<FramebufferHandle*>(it->second);
    }
    if (!output_fbo) {
        tc::Log::error("[MaterialPass] '%s': output FBO '%s' not found",
                       get_pass_name().c_str(), output_res.c_str());
        return;
    }

    int w = output_fbo->get_width();
    int h = output_fbo->get_height();
    if (w <= 0 || h <= 0) return;

    tc_material* mat = material.get();
    if (!mat || mat->phase_count == 0) {
        tc::Log::error("[MaterialPass] '%s': material not set or has no phases",
            get_pass_name().c_str());
        return;
    }

    tc_material_phase* phase = &mat->phases[0];
    tc_shader* shader = tc_shader_get(phase->shader);
    if (!shader) {
        tc::Log::warn("[MaterialPass] '%s': material has no valid shader",
                      get_pass_name().c_str());
        return;
    }

    tgfx2::ShaderHandle vs2, fs2;
    if (!tc_shader_ensure_tgfx2(shader, &device, &vs2, &fs2)) {
        tc::Log::error("[MaterialPass] '%s': tc_shader_ensure_tgfx2 failed for shader '%s'",
                       get_pass_name().c_str(),
                       shader->name ? shader->name : shader->uuid);
        return;
    }

    // Wrap output FBO as a tgfx2 texture for the duration of the pass.
    tgfx2::TextureHandle color_tex2 = wrap_fbo_color_as_tgfx2(*gl_dev, output_fbo);
    if (!color_tex2) {
        tc::Log::error("[MaterialPass] '%s': failed to wrap output color attachment",
                       get_pass_name().c_str());
        return;
    }
    ctx2->defer_destroy(color_tex2);

    ctx2->begin_pass(color_tex2, /*depth=*/{},
                     /*clear_color=*/nullptr,
                     /*clear_depth=*/1.0f,
                     /*clear_depth_enabled=*/false);
    ctx2->set_viewport(0, 0, w, h);
    ctx2->set_depth_test(false);
    ctx2->set_depth_write(false);
    ctx2->set_blend(false);
    ctx2->set_cull(tgfx2::CullMode::None);
    ctx2->set_color_format(tgfx2::PixelFormat::RGBA8_UNorm);

    ctx2->bind_shader(vs2, fs2);

    // Slot 0 is reserved for the material UBO (TC_MATERIAL_UBO_BINDING_SLOT).
    // Texture bindings start at slot 1 to avoid clashing with sampler unit 0
    // when the shader also declares its own sampler uniforms. Material
    // phase textures (from @property Texture2D) stay on legacy units
    // through the phase->textures[] loop below, bound via set_uniform_int
    // against the currently-bound tgfx2 program.
    uint32_t tex_slot = 1;
    std::set<std::string> bound_uniforms;

    // extra_resources: read from reads_fbos, wrap color attachment.
    for (const auto& [res_name, uniform_name] : extra_resources) {
        auto res_it = ctx.reads_fbos.find(res_name);
        if (res_it == ctx.reads_fbos.end()) {
            tc::Log::warn("[MaterialPass] '%s': resource '%s' not found in reads_fbos",
                get_pass_name().c_str(), res_name.c_str());
            continue;
        }
        FramebufferHandle* fbo = dynamic_cast<FramebufferHandle*>(res_it->second);
        if (!fbo) continue;

        tgfx2::TextureHandle tex2 = wrap_fbo_color_as_tgfx2(*gl_dev, fbo);
        if (!tex2) continue;
        ctx2->defer_destroy(tex2);

        ctx2->bind_sampled_texture(tex_slot, tex2);
        ctx2->set_uniform_int(uniform_name.c_str(), static_cast<int>(tex_slot));
        bound_uniforms.insert(uniform_name);
        tex_slot++;
    }

    // texture_resources: same wrap path, keyed by uniform name.
    for (const auto& [uniform_name, res_name] : texture_resources) {
        if (res_name.empty()) continue;

        auto res_it = ctx.reads_fbos.find(res_name);
        if (res_it == ctx.reads_fbos.end()) continue;
        FramebufferHandle* fbo = dynamic_cast<FramebufferHandle*>(res_it->second);
        if (!fbo) continue;

        tgfx2::TextureHandle tex2 = wrap_fbo_color_as_tgfx2(*gl_dev, fbo);
        if (!tex2) continue;
        ctx2->defer_destroy(tex2);

        ctx2->bind_sampled_texture(tex_slot, tex2);
        ctx2->set_uniform_int(uniform_name.c_str(), static_cast<int>(tex_slot));
        bound_uniforms.insert(uniform_name);
        tex_slot++;
    }

    ctx2->set_uniform_vec2("u_resolution",
                           static_cast<float>(w), static_cast<float>(h));

    // Apply @property material UBO via the C-API callback (registered by
    // termin-app's material_ubo_apply.cpp). This packs phase->uniforms[]
    // and phase->textures[] into the shared std140 UBO and binds it at
    // TC_MATERIAL_UBO_BINDING_SLOT via glBindBufferRange. The call is
    // program-agnostic (glBindBufferRange is global state), so it works
    // whether the legacy TcShader or the tgfx2 variant is currently
    // bound — here it's the tgfx2 one.
    if (shader->material_ubo_block_size > 0) {
        if (tc_material_phase_apply_ubo_gl(
                phase, shader, TC_MATERIAL_UBO_BINDING_SLOT, gl_dev)) {
            ctx2->set_block_binding("MaterialParams", TC_MATERIAL_UBO_BINDING_SLOT);
        }
    }

    // Legacy plain-uniform uploads for non-@property uniforms (e.g.
    // u_resolution, per-pass state that hasn't moved to a UBO). These
    // run through ctx2->set_uniform_* which flush_pipeline's the tgfx2
    // program before raw glUniform*. phase->uniforms[] whose names also
    // appear in the material UBO layout are stripped from the GLSL so
    // glGetUniformLocation returns -1 and the call silently no-ops.
    for (size_t i = 0; i < phase->uniform_count; i++) {
        const tc_uniform_value* uniform = &phase->uniforms[i];
        if (bound_uniforms.count(uniform->name) > 0) continue;

        switch (uniform->type) {
            case TC_UNIFORM_BOOL:
            case TC_UNIFORM_INT:
                ctx2->set_uniform_int(uniform->name, uniform->data.i);
                break;
            case TC_UNIFORM_FLOAT:
                ctx2->set_uniform_float(uniform->name, uniform->data.f);
                break;
            case TC_UNIFORM_VEC2:
                ctx2->set_uniform_vec2(uniform->name,
                                       uniform->data.v2[0], uniform->data.v2[1]);
                break;
            case TC_UNIFORM_VEC3:
                ctx2->set_uniform_vec3(uniform->name,
                                       uniform->data.v3[0], uniform->data.v3[1],
                                       uniform->data.v3[2]);
                break;
            case TC_UNIFORM_VEC4:
                ctx2->set_uniform_vec4(uniform->name,
                                       uniform->data.v4[0], uniform->data.v4[1],
                                       uniform->data.v4[2], uniform->data.v4[3]);
                break;
            case TC_UNIFORM_MAT4:
                ctx2->set_uniform_mat4(uniform->name, uniform->data.m4, false);
                break;
            default:
                break;
        }
    }

    if (before_draw_callback_) {
        TcShader shader_wrapper(phase->shader);
        before_draw_callback_(&shader_wrapper);
    }

    // Built-in fullscreen quad VBO with layout (vec2 pos, vec2 uv) at
    // locations 0 and 1 — matches the canonical post-process VS.
    ctx2->draw_fullscreen_quad();

    ctx2->end_pass();
}

void MaterialPass::draw_fullscreen_quad(GraphicsBackend* graphics) {
    // Retained for API compatibility; the tgfx2 path uses
    // ctx2->draw_fullscreen_quad() directly in execute().
    (void)graphics;
}

void MaterialPass::destroy() {
    before_draw_callback_ = nullptr;
    material = TcMaterial();
    texture_resources.clear();
    extra_resources.clear();
}

TC_REGISTER_FRAME_PASS(MaterialPass);

} // namespace termin
