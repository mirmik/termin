// grayscale_pass.cpp - Simple grayscale post-processing pass
//
// Dual-path implementation (Phase 2 tgfx2 migration):
//   * execute_legacy() uses tgfx GraphicsBackend + TcShader (the original code)
//   * execute_tgfx2() uses tgfx2::RenderContext2 for render-target setup,
//     state management, and the built-in fullscreen quad. Texture/uniform
//     binding is still done via direct GL because RenderContext2 does not
//     yet expose a ResourceSet API (placeholder comment in
//     tgfx2/src/render_context.cpp confirms this is the expected interim).
#include "grayscale_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "termin/render/tgfx2_bridge.hpp"
#include "tgfx/graphics_backend.hpp"

#include "tgfx2/render_context.hpp"
#include "tgfx2/opengl/opengl_render_device.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"

#include <glad/glad.h>
#include <tcbase/tc_log.hpp>

namespace termin {

// Varying name `vUV` matches both the legacy GRAYSCALE_VERT below and the
// built-in FSQ vertex shader used by RenderContext2 — so the same fragment
// shader source can be paired with either VS on the two migration paths.
static const char* GRAYSCALE_VERT = R"(
#version 330 core
layout(location=0) in vec2 aPos;
layout(location=1) in vec2 aUV;
out vec2 vUV;
void main() {
    vUV = aUV;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
)";

static const char* GRAYSCALE_FRAG = R"(
#version 330 core
in vec2 vUV;

uniform sampler2D u_input;
uniform float u_strength;

out vec4 FragColor;

void main() {
    vec3 color = texture(u_input, vUV).rgb;

    // Luminance weights (Rec. 709)
    float gray = dot(color, vec3(0.2126, 0.7152, 0.0722));

    // Mix between original and grayscale
    vec3 result = mix(color, vec3(gray), u_strength);

    FragColor = vec4(result, 1.0);
}
)";

GrayscalePass::GrayscalePass(
    const std::string& input,
    const std::string& output,
    float strength_val
)
    : input_res(input)
    , output_res(output)
    , strength(strength_val)
{
    pass_name_set("Grayscale");
    link_to_type_registry("GrayscalePass");
}

std::set<const char*> GrayscalePass::compute_reads() const {
    return {input_res.c_str()};
}

std::set<const char*> GrayscalePass::compute_writes() const {
    return {output_res.c_str()};
}

void GrayscalePass::ensure_shader() {
    if (!shader_.is_valid()) {
        shader_ = TcShader::from_sources(GRAYSCALE_VERT, GRAYSCALE_FRAG, "", "GrayscalePass");
    }
}

void GrayscalePass::execute(ExecuteContext& ctx) {
    if (ctx.ctx2) {
        execute_tgfx2(ctx);
    } else {
        execute_legacy(ctx);
    }
}

// ----------------------------------------------------------------------------
// Legacy tgfx path
// ----------------------------------------------------------------------------

void GrayscalePass::execute_legacy(ExecuteContext& ctx) {
    if (!ctx.graphics) return;

    auto* input_fbo = ctx.reads_fbos.count(input_res)
        ? dynamic_cast<FramebufferHandle*>(ctx.reads_fbos[input_res])
        : nullptr;
    auto* output_fbo = ctx.writes_fbos.count(output_res)
        ? dynamic_cast<FramebufferHandle*>(ctx.writes_fbos[output_res])
        : nullptr;

    if (!input_fbo) {
        tc::Log::error("[GrayscalePass] Missing input FBO '%s'", input_res.c_str());
        return;
    }

    GPUTextureHandle* input_tex = input_fbo->color_texture();
    if (!input_tex) {
        tc::Log::error("[GrayscalePass] Input FBO has no color texture");
        return;
    }

    int w = output_fbo ? output_fbo->get_width() : ctx.rect.width;
    int h = output_fbo ? output_fbo->get_height() : ctx.rect.height;

    if (w <= 0 || h <= 0) return;

    ensure_shader();

    // Setup state
    ctx.graphics->set_depth_test(false);
    ctx.graphics->set_depth_mask(false);
    ctx.graphics->set_blend(false);

    // Bind output
    ctx.graphics->bind_framebuffer(output_fbo);
    ctx.graphics->set_viewport(0, 0, w, h);

    // Draw
    shader_.ensure_ready();
    shader_.use();

    input_tex->bind(0);
    shader_.set_uniform_int("u_input", 0);
    shader_.set_uniform_float("u_strength", strength);

    ctx.graphics->draw_ui_textured_quad();

    // Restore state
    ctx.graphics->set_depth_test(true);
    ctx.graphics->set_depth_mask(true);
}

// ----------------------------------------------------------------------------
// tgfx2 path (Phase 2)
// ----------------------------------------------------------------------------

void GrayscalePass::execute_tgfx2(ExecuteContext& ctx) {
    // Resources — both legacy FBOs (for reading the input texture's GL id
    // and for size metadata) and tgfx2 texture wrappers for the output
    // target — are owned and prepared by RenderEngine. The pass just
    // consumes them.
    auto* input_fbo = ctx.reads_fbos.count(input_res)
        ? dynamic_cast<FramebufferHandle*>(ctx.reads_fbos[input_res])
        : nullptr;
    auto* output_fbo = ctx.writes_fbos.count(output_res)
        ? dynamic_cast<FramebufferHandle*>(ctx.writes_fbos[output_res])
        : nullptr;
    if (!input_fbo || !output_fbo) {
        tc::Log::error("[GrayscalePass/tgfx2] Missing input or output FBO");
        return;
    }

    auto out_it = ctx.tex2_writes.find(output_res);
    if (out_it == ctx.tex2_writes.end() || !out_it->second) {
        tc::Log::error("[GrayscalePass/tgfx2] Missing tgfx2 output texture handle for '%s'",
                       output_res.c_str());
        return;
    }
    tgfx2::TextureHandle output_tex2 = out_it->second;

    GPUTextureHandle* input_tex = input_fbo->color_texture();
    if (!input_tex || !input_tex->is_valid()) {
        tc::Log::error("[GrayscalePass/tgfx2] Input FBO has no color texture");
        return;
    }

    const int w = output_fbo->get_width();
    const int h = output_fbo->get_height();
    if (w <= 0 || h <= 0) return;

    // Lazily compile the fragment shader once via tgfx2. We only need the
    // device reference for this one-time compile; once fs2_ is valid, we
    // never touch the device directly again.
    if (!fs2_) {
        auto* dev = dynamic_cast<tgfx2::OpenGLRenderDevice*>(&ctx.ctx2->device());
        if (!dev) {
            tc::Log::error("[GrayscalePass/tgfx2] device is not an OpenGLRenderDevice");
            return;
        }
        tgfx2::ShaderDesc fs_desc;
        fs_desc.stage = tgfx2::ShaderStage::Fragment;
        fs_desc.source = GRAYSCALE_FRAG;
        fs2_ = dev->create_shader(fs_desc);
    }

    // Begin render pass targeting the output color texture. Passing nullptr
    // for clear_color means LoadOp::Load — we do not want to wipe the
    // buffer before filling it with the grayscale result.
    ctx.ctx2->begin_pass(output_tex2);
    ctx.ctx2->set_viewport(0, 0, w, h);

    ctx.ctx2->set_depth_test(false);
    ctx.ctx2->set_depth_write(false);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx2::CullMode::None);

    // Bind the built-in FSQ vertex shader explicitly together with our
    // grayscale fragment shader so flush_pipeline() below produces a
    // valid program with both stages present — draw_fullscreen_quad()'s
    // internal VS substitution would happen too late for the pre-draw
    // uniform setup we need.
    ctx.ctx2->bind_shader(ctx.ctx2->fsq_vertex_shader(), fs2_);
    ctx.ctx2->set_color_format(tgfx2::PixelFormat::RGBA8_UNorm);

    tgfx2::VertexBufferLayout fsq_layout;
    fsq_layout.stride = 4 * sizeof(float);
    fsq_layout.attributes = {
        {0, tgfx2::VertexFormat::Float2, 0},
        {1, tgfx2::VertexFormat::Float2, 2 * sizeof(float)},
    };
    ctx.ctx2->set_vertex_layout(fsq_layout);

    // Force-flush the pipeline so the underlying GL program becomes active.
    // Phase 2 escape hatch — RenderContext2::bind_texture() is a placeholder
    // and there is no ResourceSet API yet, so texture/uniform binding still
    // uses raw GL against the GL_CURRENT_PROGRAM.
    ctx.ctx2->flush_pipeline();

    GLint current_program = 0;
    glGetIntegerv(GL_CURRENT_PROGRAM, &current_program);
    if (current_program > 0) {
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, static_cast<GLuint>(input_tex->get_id()));

        GLint loc_input = glGetUniformLocation(current_program, "u_input");
        if (loc_input >= 0) glUniform1i(loc_input, 0);

        GLint loc_strength = glGetUniformLocation(current_program, "u_strength");
        if (loc_strength >= 0) glUniform1f(loc_strength, strength);
    } else {
        tc::Log::error("[GrayscalePass/tgfx2] no GL program bound after flush_pipeline");
    }

    ctx.ctx2->draw_fullscreen_quad();
    ctx.ctx2->end_pass();
}

void GrayscalePass::destroy() {
    shader_ = TcShader();
    // fs2_ is not destroyed here — we do not have the device reference.
    // It leaks one tgfx2 shader object per pass instance until the device
    // is torn down. Acceptable for Phase 2; revisit when the pass lifecycle
    // gains a proper on_device_destroyed hook.
}

TC_REGISTER_FRAME_PASS(GrayscalePass);

} // namespace termin
