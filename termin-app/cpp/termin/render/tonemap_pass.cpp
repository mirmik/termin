// tonemap_pass.cpp - HDR to LDR tonemapping post-processing pass.
//
// Dual-path implementation (tgfx2 migration):
//   * execute_legacy() uses tgfx GraphicsBackend + TcShader.
//   * execute_tgfx2() goes through tgfx2::RenderContext2 end-to-end: built-in
//     FSQ, std140 UBO for parameters via bind_uniform_buffer, input texture
//     via bind_sampled_texture. No raw GL.
#include "tonemap_pass.hpp"
#include "termin/render/execute_context.hpp"

#include "tgfx/graphics_backend.hpp"

#include "tgfx2/render_context.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"

#include <span>
#include <tcbase/tc_log.hpp>

namespace termin {

static const char* TONEMAP_VERT = R"(
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
)";

// Legacy path — classic uniforms, paired with TcShader::set_uniform_* dispatch.
static const char* TONEMAP_FRAG_LEGACY = R"(
#version 330 core
in vec2 v_uv;

uniform sampler2D u_input;
uniform float u_exposure;
uniform int u_method;  // 0 = ACES, 1 = Reinhard, 2 = None

out vec4 FragColor;

vec3 aces_tonemap(vec3 x) {
    const float a = 2.51;
    const float b = 0.03;
    const float c = 2.43;
    const float d = 0.59;
    const float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

vec3 reinhard_tonemap(vec3 x) {
    return x / (x + vec3(1.0));
}

void main() {
    vec3 color = texture(u_input, v_uv).rgb;
    color *= u_exposure;
    if (u_method == 0) {
        color = aces_tonemap(color);
    } else if (u_method == 1) {
        color = reinhard_tonemap(color);
    }
    FragColor = vec4(color, 1.0);
}
)";

// tgfx2 path — parameters live in a std140 UBO bound at slot 0. The
// `u_input` sampler defaults to texture unit 0 at link time, lining up with
// bind_sampled_texture(0, ...). Varying name `vUV` matches the built-in
// FSQ vertex shader from RenderContext2; GLSL silently drops connections
// when the in/out names disagree, so this has to stay aligned.
static const char* TONEMAP_FRAG_UBO = R"(
#version 330 core
in vec2 vUV;

layout(std140) uniform TonemapParams {
    float u_exposure;
    int u_method;
};

uniform sampler2D u_input;

out vec4 FragColor;

vec3 aces_tonemap(vec3 x) {
    const float a = 2.51;
    const float b = 0.03;
    const float c = 2.43;
    const float d = 0.59;
    const float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

vec3 reinhard_tonemap(vec3 x) {
    return x / (x + vec3(1.0));
}

void main() {
    vec3 color = texture(u_input, vUV).rgb;
    color *= u_exposure;
    if (u_method == 0) {
        color = aces_tonemap(color);
    } else if (u_method == 1) {
        color = reinhard_tonemap(color);
    }
    FragColor = vec4(color, 1.0);
}
)";

// std140 layout for TonemapParams. Float at 0 (size 4), int at 4 (size 4),
// block padded to 16-byte vec4 boundary.
struct TonemapParamsStd140 {
    float exposure;
    int32_t method;
    float _pad[2];
};
static_assert(sizeof(TonemapParamsStd140) == 16,
              "TonemapParamsStd140 must be 16 bytes for std140 compliance");

TonemapPass::TonemapPass(
    const std::string& input,
    const std::string& output,
    float exposure_val,
    int method_val
)
    : input_res(input)
    , output_res(output)
    , exposure(exposure_val)
    , method(method_val)
{
    pass_name_set("Tonemap");
    link_to_type_registry("TonemapPass");
}

std::set<const char*> TonemapPass::compute_reads() const {
    return {input_res.c_str()};
}

std::set<const char*> TonemapPass::compute_writes() const {
    return {output_res.c_str()};
}

void TonemapPass::ensure_shader() {
    if (!shader_.is_valid()) {
        shader_ = TcShader::from_sources(TONEMAP_VERT, TONEMAP_FRAG_LEGACY, "", "TonemapPass");
    }
}

void TonemapPass::execute(ExecuteContext& ctx) {
    if (ctx.ctx2) {
        execute_tgfx2(ctx);
    } else {
        execute_legacy(ctx);
    }
}

// ----------------------------------------------------------------------------
// Legacy tgfx path
// ----------------------------------------------------------------------------

void TonemapPass::execute_legacy(ExecuteContext& ctx) {
    if (!ctx.graphics) return;

    FramebufferHandle* input_fbo = nullptr;
    if (ctx.reads_fbos.count(input_res)) {
        FrameGraphResource* res = ctx.reads_fbos[input_res];
        input_fbo = dynamic_cast<FramebufferHandle*>(res);
    }

    FramebufferHandle* output_fbo = nullptr;
    if (ctx.writes_fbos.count(output_res)) {
        FrameGraphResource* res = ctx.writes_fbos[output_res];
        output_fbo = dynamic_cast<FramebufferHandle*>(res);
    }

    if (!input_fbo) {
        tc::Log::error("[TonemapPass] Missing input FBO '%s'", input_res.c_str());
        return;
    }

    GPUTextureHandle* input_tex = input_fbo->color_texture();
    if (!input_tex) {
        tc::Log::error("[TonemapPass] Input FBO has no color texture");
        return;
    }

    int w = output_fbo ? output_fbo->get_width() : ctx.rect.width;
    int h = output_fbo ? output_fbo->get_height() : ctx.rect.height;
    if (w <= 0 || h <= 0) return;

    ensure_shader();

    ctx.graphics->set_depth_test(false);
    ctx.graphics->set_depth_mask(false);
    ctx.graphics->set_blend(false);

    ctx.graphics->bind_framebuffer(output_fbo);
    ctx.graphics->set_viewport(0, 0, w, h);

    shader_.ensure_ready();
    shader_.use();

    input_tex->bind(0);
    shader_.set_uniform_int("u_input", 0);
    shader_.set_uniform_float("u_exposure", exposure);
    shader_.set_uniform_int("u_method", method);

    ctx.graphics->draw_ui_textured_quad();

    ctx.graphics->set_depth_test(true);
    ctx.graphics->set_depth_mask(true);
}

// ----------------------------------------------------------------------------
// tgfx2 path
// ----------------------------------------------------------------------------

void TonemapPass::execute_tgfx2(ExecuteContext& ctx) {
    auto* output_fbo = ctx.writes_fbos.count(output_res)
        ? dynamic_cast<FramebufferHandle*>(ctx.writes_fbos[output_res])
        : nullptr;
    if (!output_fbo) {
        tc::Log::error("[TonemapPass/tgfx2] Missing output FBO '%s'", output_res.c_str());
        return;
    }

    auto out_it = ctx.tex2_writes.find(output_res);
    if (out_it == ctx.tex2_writes.end() || !out_it->second) {
        tc::Log::error("[TonemapPass/tgfx2] Missing tgfx2 output texture handle for '%s'",
                       output_res.c_str());
        return;
    }
    tgfx2::TextureHandle output_tex2 = out_it->second;

    auto in_it = ctx.tex2_reads.find(input_res);
    if (in_it == ctx.tex2_reads.end() || !in_it->second) {
        tc::Log::error("[TonemapPass/tgfx2] Missing tgfx2 input texture handle for '%s'",
                       input_res.c_str());
        return;
    }
    tgfx2::TextureHandle input_tex2 = in_it->second;

    const int w = output_fbo->get_width();
    const int h = output_fbo->get_height();
    if (w <= 0 || h <= 0) return;

    if (!fs2_) {
        device2_ = &ctx.ctx2->device();

        tgfx2::ShaderDesc fs_desc;
        fs_desc.stage = tgfx2::ShaderStage::Fragment;
        fs_desc.source = TONEMAP_FRAG_UBO;
        fs2_ = device2_->create_shader(fs_desc);

        tgfx2::BufferDesc ubo_desc;
        ubo_desc.size = sizeof(TonemapParamsStd140);
        ubo_desc.usage = tgfx2::BufferUsage::Uniform | tgfx2::BufferUsage::CopyDst;
        params_ubo_ = device2_->create_buffer(ubo_desc);
    }

    // Upload parameters only when they change.
    if (uploaded_exposure_ != exposure || uploaded_method_ != method) {
        TonemapParamsStd140 params{};
        params.exposure = exposure;
        params.method = method;
        device2_->upload_buffer(
            params_ubo_,
            std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&params),
                                     sizeof(params)));
        uploaded_exposure_ = exposure;
        uploaded_method_ = method;
    }

    ctx.ctx2->begin_pass(output_tex2);
    ctx.ctx2->set_viewport(0, 0, w, h);

    ctx.ctx2->set_depth_test(false);
    ctx.ctx2->set_depth_write(false);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx2::CullMode::None);

    ctx.ctx2->bind_shader(ctx.ctx2->fsq_vertex_shader(), fs2_);
    ctx.ctx2->set_color_format(tgfx2::PixelFormat::RGBA8_UNorm);

    tgfx2::VertexBufferLayout fsq_layout;
    fsq_layout.stride = 4 * sizeof(float);
    fsq_layout.attributes = {
        {0, tgfx2::VertexFormat::Float2, 0},
        {1, tgfx2::VertexFormat::Float2, 2 * sizeof(float)},
    };
    ctx.ctx2->set_vertex_layout(fsq_layout);

    ctx.ctx2->bind_uniform_buffer(0, params_ubo_);
    ctx.ctx2->bind_sampled_texture(0, input_tex2);

    ctx.ctx2->draw_fullscreen_quad();
    ctx.ctx2->end_pass();
}

void TonemapPass::destroy() {
    shader_ = TcShader();
    if (device2_) {
        if (fs2_) {
            device2_->destroy(fs2_);
            fs2_ = {};
        }
        if (params_ubo_) {
            device2_->destroy(params_ubo_);
            params_ubo_ = {};
        }
        device2_ = nullptr;
    }
    uploaded_exposure_ = -1.0f;
    uploaded_method_ = -1;
}

TC_REGISTER_FRAME_PASS(TonemapPass);

} // namespace termin
