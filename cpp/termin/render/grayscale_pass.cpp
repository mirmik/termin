// grayscale_pass.cpp - Simple grayscale post-processing pass
#include "grayscale_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "termin/render/graphics_backend.hpp"
#include "tc_log.hpp"

namespace termin {

static const char* GRAYSCALE_VERT = R"(
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
)";

static const char* GRAYSCALE_FRAG = R"(
#version 330 core
in vec2 v_uv;

uniform sampler2D u_input;
uniform float u_strength;

out vec4 FragColor;

void main() {
    vec3 color = texture(u_input, v_uv).rgb;

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

void GrayscalePass::destroy() {
    shader_ = TcShader();
}

TC_REGISTER_FRAME_PASS(GrayscalePass);

} // namespace termin
