// tonemap_pass.cpp - HDR to LDR tonemapping post-processing pass
#include "tonemap_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "tgfx/graphics_backend.hpp"
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

static const char* TONEMAP_FRAG = R"(
#version 330 core
in vec2 v_uv;

uniform sampler2D u_input;
uniform float u_exposure;
uniform int u_method;  // 0 = ACES, 1 = Reinhard, 2 = None

out vec4 FragColor;

// ACES Filmic Tone Mapping
vec3 aces_tonemap(vec3 x) {
    const float a = 2.51;
    const float b = 0.03;
    const float c = 2.43;
    const float d = 0.59;
    const float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

// Reinhard tone mapping
vec3 reinhard_tonemap(vec3 x) {
    return x / (x + vec3(1.0));
}

void main() {
    vec3 color = texture(u_input, v_uv).rgb;

    // Apply exposure
    color *= u_exposure;

    // Apply tonemapping
    if (u_method == 0) {
        color = aces_tonemap(color);
    } else if (u_method == 1) {
        color = reinhard_tonemap(color);
    }
    // method == 2: no tonemapping (passthrough)

    FragColor = vec4(color, 1.0);
}
)";

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
        shader_ = TcShader::from_sources(TONEMAP_VERT, TONEMAP_FRAG, "", "TonemapPass");
    }
}

void TonemapPass::execute(ExecuteContext& ctx) {
    if (!ctx.graphics) return;

    FramebufferHandle* input_fbo = nullptr;
    if (ctx.reads_fbos.count(input_res)) {
        FrameGraphResource* res = ctx.reads_fbos[input_res];
        try {
            input_fbo = dynamic_cast<FramebufferHandle*>(res);
        } catch (const std::exception& e) {
            tc::Log::error("[TonemapPass] input dynamic_cast failed: %s", e.what());
        }
    }

    FramebufferHandle* output_fbo = nullptr;
    if (ctx.writes_fbos.count(output_res)) {
        FrameGraphResource* res = ctx.writes_fbos[output_res];
        try {
            output_fbo = dynamic_cast<FramebufferHandle*>(res);
        } catch (const std::exception& e) {
            tc::Log::error("[TonemapPass] output dynamic_cast failed: %s", e.what());
        }
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
    shader_.set_uniform_float("u_exposure", exposure);
    shader_.set_uniform_int("u_method", method);

    ctx.graphics->draw_ui_textured_quad();

    // Restore state
    ctx.graphics->set_depth_test(true);
    ctx.graphics->set_depth_mask(true);
}

void TonemapPass::destroy() {
    shader_ = TcShader();
}

TC_REGISTER_FRAME_PASS(TonemapPass);

} // namespace termin
