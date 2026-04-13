// bloom_pass.cpp - HDR bloom post-processing pass implementation.
//
// Dual-path during the tgfx2 migration:
//   * execute_legacy() uses tgfx GraphicsBackend + TcShader (the original).
//   * execute_tgfx2() does four sub-passes end-to-end through RenderContext2
//     with an HDR (RGBA16F) mip chain allocated as tgfx2 textures, std140
//     UBOs for parameters, and bind_sampled_texture for all sampler slots.
#include "bloom_pass.hpp"
#include "termin/render/execute_context.hpp"

#include "tgfx/graphics_backend.hpp"

#include "tgfx2/render_context.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"

#include <span>
#include <tcbase/tc_log.hpp>

namespace termin {

// ================================================================
// Legacy GLSL shader sources (used by execute_legacy)
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

static const char* BRIGHT_FRAG_LEGACY = R"(
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;
uniform float u_threshold;
uniform float u_soft_threshold;

out vec4 FragColor;

void main() {
    vec3 color = texture(u_texture, v_uv).rgb;
    float brightness = dot(color, vec3(0.2126, 0.7152, 0.0722));
    float knee = u_threshold * u_soft_threshold;
    float soft = brightness - u_threshold + knee;
    soft = clamp(soft, 0.0, 2.0 * knee);
    soft = soft * soft / (4.0 * knee + 0.00001);
    float contribution = max(soft, brightness - u_threshold) / max(brightness, 0.00001);
    contribution = max(contribution, 0.0);
    FragColor = vec4(color * contribution, 1.0);
}
)";

static const char* DOWNSAMPLE_VERT = BRIGHT_VERT;

static const char* DOWNSAMPLE_FRAG_LEGACY = R"(
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;
uniform vec2 u_texel_size;

out vec4 FragColor;

void main() {
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
    vec3 result = e * 0.125;
    result += (a + c + g + i) * 0.03125;
    result += (b + d + f + h) * 0.0625;
    result += (j + k + l + m) * 0.125;
    FragColor = vec4(result, 1.0);
}
)";

static const char* UPSAMPLE_VERT = BRIGHT_VERT;

static const char* UPSAMPLE_FRAG_LEGACY = R"(
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;
uniform sampler2D u_higher_mip;
uniform vec2 u_texel_size;
uniform float u_blend_factor;

out vec4 FragColor;

void main() {
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
    vec3 upsampled = e * 4.0;
    upsampled += (b + d + f + h) * 2.0;
    upsampled += (a + c + g + i);
    upsampled /= 16.0;
    vec3 higher = texture(u_higher_mip, v_uv).rgb;
    FragColor = vec4(higher + upsampled * u_blend_factor, 1.0);
}
)";

static const char* COMPOSITE_VERT = BRIGHT_VERT;

static const char* COMPOSITE_FRAG_LEGACY = R"(
#version 330 core
in vec2 v_uv;

uniform sampler2D u_original;
uniform sampler2D u_bloom;
uniform float u_intensity;

out vec4 FragColor;

void main() {
    vec3 original = texture(u_original, v_uv).rgb;
    vec3 bloom = texture(u_bloom, v_uv).rgb;
    vec3 result = original + bloom * u_intensity;
    FragColor = vec4(result, 1.0);
}
)";

// ================================================================
// tgfx2 GLSL shader sources (used by execute_tgfx2)
//
// Paired with RenderContext2's built-in FSQ vertex shader → varying
// name is `vUV` (not `v_uv` — mismatches silently drop the connection).
// Multi-sampler shaders use `layout(binding = N)` with the
// GL_ARB_shading_language_420pack extension so explicit texture-unit
// binding works without a post-link glUniform1i.
// ================================================================

static const char* BRIGHT_FRAG_UBO = R"(
#version 330 core
#extension GL_ARB_shading_language_420pack : require

in vec2 vUV;

layout(std140) uniform BloomBrightParams {
    float u_threshold;
    float u_soft_threshold;
};

layout(binding = 0) uniform sampler2D u_texture;

out vec4 FragColor;

void main() {
    vec3 color = texture(u_texture, vUV).rgb;
    float brightness = dot(color, vec3(0.2126, 0.7152, 0.0722));
    float knee = u_threshold * u_soft_threshold;
    float soft = brightness - u_threshold + knee;
    soft = clamp(soft, 0.0, 2.0 * knee);
    soft = soft * soft / (4.0 * knee + 0.00001);
    float contribution = max(soft, brightness - u_threshold) / max(brightness, 0.00001);
    contribution = max(contribution, 0.0);
    FragColor = vec4(color * contribution, 1.0);
}
)";

static const char* DOWNSAMPLE_FRAG_UBO = R"(
#version 330 core
#extension GL_ARB_shading_language_420pack : require

in vec2 vUV;

layout(std140) uniform BloomDownsampleParams {
    vec2 u_texel_size;
};

layout(binding = 0) uniform sampler2D u_texture;

out vec4 FragColor;

void main() {
    vec2 ts = u_texel_size;
    vec3 a = texture(u_texture, vUV + vec2(-2.0, -2.0) * ts).rgb;
    vec3 b = texture(u_texture, vUV + vec2( 0.0, -2.0) * ts).rgb;
    vec3 c = texture(u_texture, vUV + vec2( 2.0, -2.0) * ts).rgb;
    vec3 d = texture(u_texture, vUV + vec2(-2.0,  0.0) * ts).rgb;
    vec3 e = texture(u_texture, vUV + vec2( 0.0,  0.0) * ts).rgb;
    vec3 f = texture(u_texture, vUV + vec2( 2.0,  0.0) * ts).rgb;
    vec3 g = texture(u_texture, vUV + vec2(-2.0,  2.0) * ts).rgb;
    vec3 h = texture(u_texture, vUV + vec2( 0.0,  2.0) * ts).rgb;
    vec3 i = texture(u_texture, vUV + vec2( 2.0,  2.0) * ts).rgb;
    vec3 j = texture(u_texture, vUV + vec2(-1.0, -1.0) * ts).rgb;
    vec3 k = texture(u_texture, vUV + vec2( 1.0, -1.0) * ts).rgb;
    vec3 l = texture(u_texture, vUV + vec2(-1.0,  1.0) * ts).rgb;
    vec3 m = texture(u_texture, vUV + vec2( 1.0,  1.0) * ts).rgb;
    vec3 result = e * 0.125;
    result += (a + c + g + i) * 0.03125;
    result += (b + d + f + h) * 0.0625;
    result += (j + k + l + m) * 0.125;
    FragColor = vec4(result, 1.0);
}
)";

static const char* UPSAMPLE_FRAG_UBO = R"(
#version 330 core
#extension GL_ARB_shading_language_420pack : require

in vec2 vUV;

layout(std140) uniform BloomUpsampleParams {
    vec2 u_texel_size;
    float u_blend_factor;
};

layout(binding = 0) uniform sampler2D u_texture;
layout(binding = 1) uniform sampler2D u_higher_mip;

out vec4 FragColor;

void main() {
    vec2 ts = u_texel_size;
    vec3 a = texture(u_texture, vUV + vec2(-1.0, -1.0) * ts).rgb;
    vec3 b = texture(u_texture, vUV + vec2( 0.0, -1.0) * ts).rgb;
    vec3 c = texture(u_texture, vUV + vec2( 1.0, -1.0) * ts).rgb;
    vec3 d = texture(u_texture, vUV + vec2(-1.0,  0.0) * ts).rgb;
    vec3 e = texture(u_texture, vUV + vec2( 0.0,  0.0) * ts).rgb;
    vec3 f = texture(u_texture, vUV + vec2( 1.0,  0.0) * ts).rgb;
    vec3 g = texture(u_texture, vUV + vec2(-1.0,  1.0) * ts).rgb;
    vec3 h = texture(u_texture, vUV + vec2( 0.0,  1.0) * ts).rgb;
    vec3 i = texture(u_texture, vUV + vec2( 1.0,  1.0) * ts).rgb;
    vec3 upsampled = e * 4.0;
    upsampled += (b + d + f + h) * 2.0;
    upsampled += (a + c + g + i);
    upsampled /= 16.0;
    vec3 higher = texture(u_higher_mip, vUV).rgb;
    FragColor = vec4(higher + upsampled * u_blend_factor, 1.0);
}
)";

static const char* COMPOSITE_FRAG_UBO = R"(
#version 330 core
#extension GL_ARB_shading_language_420pack : require

in vec2 vUV;

layout(std140) uniform BloomCompositeParams {
    float u_intensity;
};

layout(binding = 0) uniform sampler2D u_original;
layout(binding = 1) uniform sampler2D u_bloom;

out vec4 FragColor;

void main() {
    vec3 original = texture(u_original, vUV).rgb;
    vec3 bloom = texture(u_bloom, vUV).rgb;
    vec3 result = original + bloom * u_intensity;
    FragColor = vec4(result, 1.0);
}
)";

// ================================================================
// std140-packed UBO structs
// ================================================================

struct BloomBrightParamsStd140 {
    float threshold;
    float soft_threshold;
    float _pad[2];
};
static_assert(sizeof(BloomBrightParamsStd140) == 16, "std140 alignment");

struct BloomDownsampleParamsStd140 {
    float texel_x;
    float texel_y;
    float _pad[2];
};
static_assert(sizeof(BloomDownsampleParamsStd140) == 16, "std140 alignment");

struct BloomUpsampleParamsStd140 {
    float texel_x;
    float texel_y;
    float blend_factor;
    float _pad;
};
static_assert(sizeof(BloomUpsampleParamsStd140) == 16, "std140 alignment");

struct BloomCompositeParamsStd140 {
    float intensity;
    float _pad[3];
};
static_assert(sizeof(BloomCompositeParamsStd140) == 16, "std140 alignment");

// ================================================================
// BloomPass implementation
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
        bright_shader_ = TcShader::from_sources(BRIGHT_VERT, BRIGHT_FRAG_LEGACY, "", "BloomPassBright");
    }
    if (!downsample_shader_.is_valid()) {
        downsample_shader_ = TcShader::from_sources(DOWNSAMPLE_VERT, DOWNSAMPLE_FRAG_LEGACY, "", "BloomPassDownsample");
    }
    if (!upsample_shader_.is_valid()) {
        upsample_shader_ = TcShader::from_sources(UPSAMPLE_VERT, UPSAMPLE_FRAG_LEGACY, "", "BloomPassUpsample");
    }
    if (!composite_shader_.is_valid()) {
        composite_shader_ = TcShader::from_sources(COMPOSITE_VERT, COMPOSITE_FRAG_LEGACY, "", "BloomPassComposite");
    }
}

void BloomPass::ensure_mip_fbos(GraphicsBackend* graphics, int width, int height) {
    int count = mip_levels;
    bool need_recreate = (width != last_width_) ||
                         (height != last_height_) ||
                         (count != last_mip_levels_);
    if (!need_recreate && !mip_fbos_.empty()) return;

    last_width_ = width;
    last_height_ = height;
    last_mip_levels_ = count;

    mip_fbos_.clear();

    for (int i = 0; i < count; i++) {
        int mip_w = std::max(1, width >> i);
        int mip_h = std::max(1, height >> i);
        auto fbo = graphics->create_framebuffer(mip_w, mip_h, 1, "rgba16f");
        mip_fbos_.push_back(std::move(fbo));
    }
}

void BloomPass::execute(ExecuteContext& ctx) {
    if (ctx.ctx2) {
        execute_tgfx2(ctx);
    } else {
        execute_legacy(ctx);
    }
}

// ----------------------------------------------------------------------------
// Legacy tgfx path
// ----------------------------------------------------------------------------

void BloomPass::execute_legacy(ExecuteContext& ctx) {
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

    ensure_shaders();
    ensure_mip_fbos(ctx.graphics, w, h);

    if (mip_fbos_.empty()) {
        tc::Log::error("[BloomPass] Failed to create mip FBOs");
        return;
    }

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

        auto* src_fbo = mip_fbos_[i + 1].get();
        auto* dst_fbo = mip_fbos_[i].get();

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

    ctx.graphics->set_depth_test(true);
    ctx.graphics->set_depth_mask(true);
}

// ----------------------------------------------------------------------------
// tgfx2 path
// ----------------------------------------------------------------------------

void BloomPass::ensure_tgfx2_shaders() {
    if (bright_fs2_) return;

    auto compile = [&](const char* src) -> tgfx2::ShaderHandle {
        tgfx2::ShaderDesc desc;
        desc.stage = tgfx2::ShaderStage::Fragment;
        desc.source = src;
        return device2_->create_shader(desc);
    };

    bright_fs2_     = compile(BRIGHT_FRAG_UBO);
    downsample_fs2_ = compile(DOWNSAMPLE_FRAG_UBO);
    upsample_fs2_   = compile(UPSAMPLE_FRAG_UBO);
    composite_fs2_  = compile(COMPOSITE_FRAG_UBO);

    auto make_ubo = [&](uint64_t size) -> tgfx2::BufferHandle {
        tgfx2::BufferDesc desc;
        desc.size = size;
        desc.usage = tgfx2::BufferUsage::Uniform | tgfx2::BufferUsage::CopyDst;
        return device2_->create_buffer(desc);
    };

    bright_ubo_     = make_ubo(sizeof(BloomBrightParamsStd140));
    downsample_ubo_ = make_ubo(sizeof(BloomDownsampleParamsStd140));
    upsample_ubo_   = make_ubo(sizeof(BloomUpsampleParamsStd140));
    composite_ubo_  = make_ubo(sizeof(BloomCompositeParamsStd140));
}

void BloomPass::destroy_tgfx2_mip_textures() {
    if (!device2_) {
        mip_textures_.clear();
        return;
    }
    for (auto& t : mip_textures_) {
        if (t) device2_->destroy(t);
    }
    mip_textures_.clear();
}

void BloomPass::ensure_tgfx2_mip_textures(int width, int height) {
    int count = std::max(1, std::min(mip_levels, 8));
    bool need_recreate = (width != last_tgfx2_width_) ||
                         (height != last_tgfx2_height_) ||
                         (count != last_tgfx2_mip_levels_);
    if (!need_recreate && !mip_textures_.empty()) return;

    destroy_tgfx2_mip_textures();

    last_tgfx2_width_ = width;
    last_tgfx2_height_ = height;
    last_tgfx2_mip_levels_ = count;

    for (int i = 0; i < count; i++) {
        int mip_w = std::max(1, width >> i);
        int mip_h = std::max(1, height >> i);

        tgfx2::TextureDesc desc;
        desc.width = mip_w;
        desc.height = mip_h;
        desc.mip_levels = 1;
        desc.sample_count = 1;
        desc.format = tgfx2::PixelFormat::RGBA16F;
        desc.usage = tgfx2::TextureUsage::ColorAttachment | tgfx2::TextureUsage::Sampled;
        mip_textures_.push_back(device2_->create_texture(desc));
    }
}

// Helper — common FSQ draw setup for tgfx2 sub-passes. Sets render state,
// binds the built-in FSQ VS + the provided FS, sets color format + vertex
// layout. Caller is responsible for begin_pass / set_viewport /
// bind_uniform_buffer / bind_sampled_texture / draw_fullscreen_quad /
// end_pass around this.
static void setup_fsq_state(tgfx2::RenderContext2& ctx,
                            tgfx2::ShaderHandle fs,
                            tgfx2::PixelFormat color_fmt) {
    ctx.set_depth_test(false);
    ctx.set_depth_write(false);
    ctx.set_blend(false);
    ctx.set_cull(tgfx2::CullMode::None);

    ctx.bind_shader(ctx.fsq_vertex_shader(), fs);
    ctx.set_color_format(color_fmt);

    tgfx2::VertexBufferLayout fsq_layout;
    fsq_layout.stride = 4 * sizeof(float);
    fsq_layout.attributes = {
        {0, tgfx2::VertexFormat::Float2, 0},
        {1, tgfx2::VertexFormat::Float2, 2 * sizeof(float)},
    };
    ctx.set_vertex_layout(fsq_layout);
}

void BloomPass::execute_tgfx2(ExecuteContext& ctx) {
    auto* input_fbo = ctx.reads_fbos.count(input_res)
        ? dynamic_cast<FramebufferHandle*>(ctx.reads_fbos[input_res])
        : nullptr;
    auto* output_fbo = ctx.writes_fbos.count(output_res)
        ? dynamic_cast<FramebufferHandle*>(ctx.writes_fbos[output_res])
        : nullptr;
    if (!input_fbo || !output_fbo) {
        tc::Log::error("[BloomPass/tgfx2] Missing input or output FBO");
        return;
    }

    auto in_it = ctx.tex2_reads.find(input_res);
    if (in_it == ctx.tex2_reads.end() || !in_it->second) {
        tc::Log::error("[BloomPass/tgfx2] Missing tgfx2 input texture handle '%s'",
                       input_res.c_str());
        return;
    }
    tgfx2::TextureHandle input_tex2 = in_it->second;

    auto out_it = ctx.tex2_writes.find(output_res);
    if (out_it == ctx.tex2_writes.end() || !out_it->second) {
        tc::Log::error("[BloomPass/tgfx2] Missing tgfx2 output texture handle '%s'",
                       output_res.c_str());
        return;
    }
    tgfx2::TextureHandle output_tex2 = out_it->second;

    const int w = output_fbo->get_width();
    const int h = output_fbo->get_height();
    if (w <= 0 || h <= 0) return;

    const int count = std::max(1, std::min(mip_levels, 8));

    if (!device2_) {
        device2_ = &ctx.ctx2->device();
    }
    ensure_tgfx2_shaders();
    ensure_tgfx2_mip_textures(w, h);
    if (mip_textures_.empty()) {
        tc::Log::error("[BloomPass/tgfx2] Failed to create mip textures");
        return;
    }

    auto& c2 = *ctx.ctx2;

    // === 1. Bright Pass -> mip[0] ===
    {
        BloomBrightParamsStd140 p{};
        p.threshold = threshold;
        p.soft_threshold = soft_threshold;
        device2_->upload_buffer(
            bright_ubo_,
            std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&p), sizeof(p)));

        c2.begin_pass(mip_textures_[0]);
        c2.set_viewport(0, 0, w, h);
        setup_fsq_state(c2, bright_fs2_, tgfx2::PixelFormat::RGBA16F);
        c2.bind_uniform_buffer(0, bright_ubo_);
        c2.bind_sampled_texture(0, input_tex2);
        c2.draw_fullscreen_quad();
        c2.end_pass();
    }

    // === 2. Progressive Downsample ===
    for (int i = 1; i < count && i < (int)mip_textures_.size(); i++) {
        int src_w = std::max(1, w >> (i - 1));
        int src_h = std::max(1, h >> (i - 1));
        int dst_w = std::max(1, w >> i);
        int dst_h = std::max(1, h >> i);

        BloomDownsampleParamsStd140 p{};
        p.texel_x = 1.0f / static_cast<float>(src_w);
        p.texel_y = 1.0f / static_cast<float>(src_h);
        device2_->upload_buffer(
            downsample_ubo_,
            std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&p), sizeof(p)));

        c2.begin_pass(mip_textures_[i]);
        c2.set_viewport(0, 0, dst_w, dst_h);
        setup_fsq_state(c2, downsample_fs2_, tgfx2::PixelFormat::RGBA16F);
        c2.bind_uniform_buffer(0, downsample_ubo_);
        c2.bind_sampled_texture(0, mip_textures_[i - 1]);
        c2.draw_fullscreen_quad();
        c2.end_pass();
    }

    // === 3. Progressive Upsample (accumulate bloom) ===
    for (int i = count - 2; i >= 0; i--) {
        if (i + 1 >= (int)mip_textures_.size()) continue;

        int src_w = std::max(1, w >> (i + 1));
        int src_h = std::max(1, h >> (i + 1));
        int dst_w = std::max(1, w >> i);
        int dst_h = std::max(1, h >> i);

        BloomUpsampleParamsStd140 p{};
        p.texel_x = 1.0f / static_cast<float>(src_w);
        p.texel_y = 1.0f / static_cast<float>(src_h);
        p.blend_factor = 1.0f;
        device2_->upload_buffer(
            upsample_ubo_,
            std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&p), sizeof(p)));

        // Note: mip_textures_[i] is bound both as the render target and
        // as u_higher_mip sampler — same read-write feedback pattern as
        // the legacy path. OpenGL tolerates it since the shader only reads
        // the current texel (no cross-pixel sample).
        c2.begin_pass(mip_textures_[i]);
        c2.set_viewport(0, 0, dst_w, dst_h);
        setup_fsq_state(c2, upsample_fs2_, tgfx2::PixelFormat::RGBA16F);
        c2.bind_uniform_buffer(0, upsample_ubo_);
        c2.bind_sampled_texture(0, mip_textures_[i + 1]);
        c2.bind_sampled_texture(1, mip_textures_[i]);
        c2.draw_fullscreen_quad();
        c2.end_pass();
    }

    // === 4. Composite Pass (input + mip[0] -> output) ===
    {
        BloomCompositeParamsStd140 p{};
        p.intensity = intensity;
        device2_->upload_buffer(
            composite_ubo_,
            std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&p), sizeof(p)));

        c2.begin_pass(output_tex2);
        c2.set_viewport(0, 0, w, h);
        setup_fsq_state(c2, composite_fs2_, tgfx2::PixelFormat::RGBA8_UNorm);
        c2.bind_uniform_buffer(0, composite_ubo_);
        c2.bind_sampled_texture(0, input_tex2);
        c2.bind_sampled_texture(1, mip_textures_[0]);
        c2.draw_fullscreen_quad();
        c2.end_pass();
    }
}

void BloomPass::destroy() {
    // Legacy resources.
    mip_fbos_.clear();
    bright_shader_ = TcShader();
    downsample_shader_ = TcShader();
    upsample_shader_ = TcShader();
    composite_shader_ = TcShader();

    // tgfx2 resources.
    if (device2_) {
        destroy_tgfx2_mip_textures();
        if (bright_fs2_)     device2_->destroy(bright_fs2_);
        if (downsample_fs2_) device2_->destroy(downsample_fs2_);
        if (upsample_fs2_)   device2_->destroy(upsample_fs2_);
        if (composite_fs2_)  device2_->destroy(composite_fs2_);
        if (bright_ubo_)     device2_->destroy(bright_ubo_);
        if (downsample_ubo_) device2_->destroy(downsample_ubo_);
        if (upsample_ubo_)   device2_->destroy(upsample_ubo_);
        if (composite_ubo_)  device2_->destroy(composite_ubo_);
        bright_fs2_ = {};
        downsample_fs2_ = {};
        upsample_fs2_ = {};
        composite_fs2_ = {};
        bright_ubo_ = {};
        downsample_ubo_ = {};
        upsample_ubo_ = {};
        composite_ubo_ = {};
        device2_ = nullptr;
    }
    last_tgfx2_width_ = 0;
    last_tgfx2_height_ = 0;
    last_tgfx2_mip_levels_ = 0;
}

TC_REGISTER_FRAME_PASS(BloomPass);

} // namespace termin
