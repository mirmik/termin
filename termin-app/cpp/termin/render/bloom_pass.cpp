// bloom_pass.cpp - HDR bloom post-processing pass implementation
#include "bloom_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "tgfx/graphics_backend.hpp"
#include <tcbase/tc_log.hpp>

namespace termin {

// ================================================================
// GLSL Shader Sources
// ================================================================

static const char* BRIGHT_VERT = R"(
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
)";

static const char* BRIGHT_FRAG = R"(
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;
uniform float u_threshold;
uniform float u_soft_threshold;

out vec4 FragColor;

void main() {
    vec3 color = texture(u_texture, v_uv).rgb;

    // Calculate brightness (luminance)
    float brightness = dot(color, vec3(0.2126, 0.7152, 0.0722));

    // Soft threshold with knee
    float knee = u_threshold * u_soft_threshold;
    float soft = brightness - u_threshold + knee;
    soft = clamp(soft, 0.0, 2.0 * knee);
    soft = soft * soft / (4.0 * knee + 0.00001);

    float contribution = max(soft, brightness - u_threshold) / max(brightness, 0.00001);
    contribution = max(contribution, 0.0);

    FragColor = vec4(color * contribution, 1.0);
}
)";

static const char* DOWNSAMPLE_VERT = R"(
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
)";

static const char* DOWNSAMPLE_FRAG = R"(
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;
uniform vec2 u_texel_size;

out vec4 FragColor;

void main() {
    // 13-tap downsample (Karis average style)
    vec2 ts = u_texel_size;

    vec3 a = texture(u_texture, v_uv + vec2(-2.0, -2.0) * ts).rgb;
    vec3 b = texture(u_texture, v_uv + vec2( 0.0, -2.0) * ts).rgb;
    vec3 c = texture(u_texture, v_uv + vec2( 2.0, -2.0) * ts).rgb;

    vec3 d = texture(u_texture, v_uv + vec2(-2.0,  0.0) * ts).rgb;
    vec3 e = texture(u_texture, v_uv + vec2( 0.0,  0.0) * ts).rgb;
    vec3 f = texture(u_texture, v_uv + vec2( 2.0,  0.0) * ts).rgb;

    vec3 g = texture(u_texture, v_uv + vec2(-2.0,  2.0) * ts).rgb;
    vec3 h = texture(u_texture, v_uv + vec2( 0.0,  2.0) * ts).rgb;
    vec3 i = texture(u_texture, v_uv + vec2( 2.0,  2.0) * ts).rgb;

    vec3 j = texture(u_texture, v_uv + vec2(-1.0, -1.0) * ts).rgb;
    vec3 k = texture(u_texture, v_uv + vec2( 1.0, -1.0) * ts).rgb;
    vec3 l = texture(u_texture, v_uv + vec2(-1.0,  1.0) * ts).rgb;
    vec3 m = texture(u_texture, v_uv + vec2( 1.0,  1.0) * ts).rgb;

    // Weighted average
    vec3 result = e * 0.125;
    result += (a + c + g + i) * 0.03125;
    result += (b + d + f + h) * 0.0625;
    result += (j + k + l + m) * 0.125;

    FragColor = vec4(result, 1.0);
}
)";

static const char* UPSAMPLE_VERT = R"(
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
)";

static const char* UPSAMPLE_FRAG = R"(
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;      // Lower mip (being upsampled)
uniform sampler2D u_higher_mip;   // Higher mip (to blend with)
uniform vec2 u_texel_size;
uniform float u_blend_factor;

out vec4 FragColor;

void main() {
    // 9-tap tent filter for smooth upsampling
    vec2 ts = u_texel_size;

    vec3 a = texture(u_texture, v_uv + vec2(-1.0, -1.0) * ts).rgb;
    vec3 b = texture(u_texture, v_uv + vec2( 0.0, -1.0) * ts).rgb;
    vec3 c = texture(u_texture, v_uv + vec2( 1.0, -1.0) * ts).rgb;

    vec3 d = texture(u_texture, v_uv + vec2(-1.0,  0.0) * ts).rgb;
    vec3 e = texture(u_texture, v_uv + vec2( 0.0,  0.0) * ts).rgb;
    vec3 f = texture(u_texture, v_uv + vec2( 1.0,  0.0) * ts).rgb;

    vec3 g = texture(u_texture, v_uv + vec2(-1.0,  1.0) * ts).rgb;
    vec3 h = texture(u_texture, v_uv + vec2( 0.0,  1.0) * ts).rgb;
    vec3 i = texture(u_texture, v_uv + vec2( 1.0,  1.0) * ts).rgb;

    // Tent filter weights
    vec3 upsampled = e * 4.0;
    upsampled += (b + d + f + h) * 2.0;
    upsampled += (a + c + g + i);
    upsampled /= 16.0;

    // Blend with higher resolution mip
    vec3 higher = texture(u_higher_mip, v_uv).rgb;

    FragColor = vec4(higher + upsampled * u_blend_factor, 1.0);
}
)";

static const char* COMPOSITE_VERT = R"(
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
)";

static const char* COMPOSITE_FRAG = R"(
#version 330 core
in vec2 v_uv;

uniform sampler2D u_original;
uniform sampler2D u_bloom;
uniform float u_intensity;

out vec4 FragColor;

void main() {
    vec3 original = texture(u_original, v_uv).rgb;
    vec3 bloom = texture(u_bloom, v_uv).rgb;

    // Additive blend
    vec3 result = original + bloom * u_intensity;

    FragColor = vec4(result, 1.0);
}
)";

// ================================================================
// BloomPass Implementation
// ================================================================

BloomPass::BloomPass(
    const std::string& input,
    const std::string& output,
    float threshold_val,
    float soft_threshold_val,
    float intensity_val,
    int mip_levels_val
)
    : input_res(input)
    , output_res(output)
    , threshold(threshold_val)
    , soft_threshold(soft_threshold_val)
    , intensity(intensity_val)
    , mip_levels(mip_levels_val)
{
    pass_name_set("Bloom");
    link_to_type_registry("BloomPass");
}

std::set<const char*> BloomPass::compute_reads() const {
    return {input_res.c_str()};
}

std::set<const char*> BloomPass::compute_writes() const {
    return {output_res.c_str()};
}

void BloomPass::ensure_shaders() {
    if (!bright_shader_.is_valid()) {
        bright_shader_ = TcShader::from_sources(BRIGHT_VERT, BRIGHT_FRAG, "", "BloomPassBright");
    }
    if (!downsample_shader_.is_valid()) {
        downsample_shader_ = TcShader::from_sources(DOWNSAMPLE_VERT, DOWNSAMPLE_FRAG, "", "BloomPassDownsample");
    }
    if (!upsample_shader_.is_valid()) {
        upsample_shader_ = TcShader::from_sources(UPSAMPLE_VERT, UPSAMPLE_FRAG, "", "BloomPassUpsample");
    }
    if (!composite_shader_.is_valid()) {
        composite_shader_ = TcShader::from_sources(COMPOSITE_VERT, COMPOSITE_FRAG, "", "BloomPassComposite");
    }
}

void BloomPass::ensure_mip_fbos(GraphicsBackend* graphics, int width, int height) {
    int count = mip_levels;

    // Check if we need to recreate
    bool need_recreate = (width != last_width_) ||
                         (height != last_height_) ||
                         (count != last_mip_levels_);

    if (!need_recreate && !mip_fbos_.empty()) {
        return;
    }

    last_width_ = width;
    last_height_ = height;
    last_mip_levels_ = count;

    // Clear existing FBOs
    mip_fbos_.clear();

    // Create FBOs for each mip level
    int w = width;
    int h = height;
    for (int i = 0; i < count; i++) {
        int mip_w = std::max(1, w >> i);
        int mip_h = std::max(1, h >> i);

        auto fbo = graphics->create_framebuffer(mip_w, mip_h, 1, "rgba16f");
        mip_fbos_.push_back(std::move(fbo));
    }
}

void BloomPass::execute(ExecuteContext& ctx) {
    if (!ctx.graphics) return;

    auto* input_fbo = ctx.reads_fbos.count(input_res)
        ? dynamic_cast<FramebufferHandle*>(ctx.reads_fbos[input_res])
        : nullptr;
    auto* output_fbo = ctx.writes_fbos.count(output_res)
        ? dynamic_cast<FramebufferHandle*>(ctx.writes_fbos[output_res])
        : nullptr;

    if (!input_fbo) {
        tc::Log::error("[BloomPass] Missing input FBO '%s'", input_res.c_str());
        return;
    }

    GPUTextureHandle* input_tex = input_fbo->color_texture();
    if (!input_tex) {
        tc::Log::error("[BloomPass] Input FBO has no color texture");
        return;
    }

    int w = output_fbo ? output_fbo->get_width() : ctx.rect.width;
    int h = output_fbo ? output_fbo->get_height() : ctx.rect.height;

    if (w <= 0 || h <= 0) return;

    int count = std::max(1, std::min(mip_levels, 8));

    // Ensure resources
    ensure_shaders();
    ensure_mip_fbos(ctx.graphics, w, h);

    if (mip_fbos_.empty()) {
        tc::Log::error("[BloomPass] Failed to create mip FBOs");
        return;
    }

    // Setup state
    ctx.graphics->set_depth_test(false);
    ctx.graphics->set_depth_mask(false);
    ctx.graphics->set_blend(false);

    // === 1. Bright Pass -> mip[0] ===
    auto* mip0 = mip_fbos_[0].get();
    ctx.graphics->bind_framebuffer(mip0);
    ctx.graphics->set_viewport(0, 0, w, h);

    bright_shader_.ensure_ready();
    bright_shader_.use();

    input_tex->bind(0);
    bright_shader_.set_uniform_int("u_texture", 0);
    bright_shader_.set_uniform_float("u_threshold", threshold);
    bright_shader_.set_uniform_float("u_soft_threshold", soft_threshold);

    ctx.graphics->draw_ui_textured_quad();

    // === 2. Progressive Downsample ===
    downsample_shader_.ensure_ready();
    downsample_shader_.use();

    for (int i = 1; i < count && i < (int)mip_fbos_.size(); i++) {
        auto* src_fbo = mip_fbos_[i - 1].get();
        auto* dst_fbo = mip_fbos_[i].get();

        int src_w = std::max(1, w >> (i - 1));
        int src_h = std::max(1, h >> (i - 1));
        int dst_w = std::max(1, w >> i);
        int dst_h = std::max(1, h >> i);

        ctx.graphics->bind_framebuffer(dst_fbo);
        ctx.graphics->set_viewport(0, 0, dst_w, dst_h);

        src_fbo->color_texture()->bind(0);
        downsample_shader_.set_uniform_int("u_texture", 0);
        downsample_shader_.set_uniform_vec2("u_texel_size",
            1.0f / std::max(1, src_w),
            1.0f / std::max(1, src_h));

        ctx.graphics->draw_ui_textured_quad();
    }

    // === 3. Progressive Upsample (accumulate bloom) ===
    upsample_shader_.ensure_ready();
    upsample_shader_.use();

    for (int i = count - 2; i >= 0; i--) {
        if (i + 1 >= (int)mip_fbos_.size()) continue;

        auto* src_fbo = mip_fbos_[i + 1].get();  // Lower mip (upsampling from)
        auto* dst_fbo = mip_fbos_[i].get();      // Higher mip (upsampling to)

        int src_w = std::max(1, w >> (i + 1));
        int src_h = std::max(1, h >> (i + 1));
        int dst_w = std::max(1, w >> i);
        int dst_h = std::max(1, h >> i);

        ctx.graphics->bind_framebuffer(dst_fbo);
        ctx.graphics->set_viewport(0, 0, dst_w, dst_h);

        src_fbo->color_texture()->bind(0);
        dst_fbo->color_texture()->bind(1);

        upsample_shader_.set_uniform_int("u_texture", 0);
        upsample_shader_.set_uniform_int("u_higher_mip", 1);
        upsample_shader_.set_uniform_vec2("u_texel_size",
            1.0f / std::max(1, src_w),
            1.0f / std::max(1, src_h));
        upsample_shader_.set_uniform_float("u_blend_factor", 1.0f);

        ctx.graphics->draw_ui_textured_quad();
    }

    // === 4. Composite Pass (to output FBO) ===
    ctx.graphics->bind_framebuffer(output_fbo);
    ctx.graphics->set_viewport(0, 0, w, h);

    composite_shader_.ensure_ready();
    composite_shader_.use();

    input_tex->bind(0);
    mip_fbos_[0]->color_texture()->bind(1);

    composite_shader_.set_uniform_int("u_original", 0);
    composite_shader_.set_uniform_int("u_bloom", 1);
    composite_shader_.set_uniform_float("u_intensity", intensity);

    ctx.graphics->draw_ui_textured_quad();

    // Restore state
    ctx.graphics->set_depth_test(true);
    ctx.graphics->set_depth_mask(true);
}

void BloomPass::destroy() {
    mip_fbos_.clear();
    bright_shader_ = TcShader();
    downsample_shader_ = TcShader();
    upsample_shader_ = TcShader();
    composite_shader_ = TcShader();
}

TC_REGISTER_FRAME_PASS(BloomPass);

} // namespace termin
