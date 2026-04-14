// grayscale_pass.cpp - Simple grayscale post-processing pass.
//
// Draws through tgfx2::RenderContext2 end-to-end: built-in FSQ,
// std140 UBO for parameters via bind_uniform_buffer, input texture
// via bind_sampled_texture. Legacy tgfx1 dual-path removed in Stage 8.1.
#include "grayscale_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "termin/render/tgfx2_bridge.hpp"

#include "tgfx2/render_context.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"

#include <span>
#include <tcbase/tc_log.hpp>

namespace termin {

// tgfx2 path — parameters live in a std140 UBO bound at slot 0. The sampler
// is still a plain GL 3.3 `uniform sampler2D` which defaults to texture unit 0
// at link time, so binding the input texture at resource slot 0 lines up.
static const char* GRAYSCALE_FRAG_UBO = R"(
#version 330 core
in vec2 vUV;

layout(std140) uniform GrayscaleParams {
    float u_strength;
};

uniform sampler2D u_input;

out vec4 FragColor;

void main() {
    vec3 color = texture(u_input, vUV).rgb;
    float gray = dot(color, vec3(0.2126, 0.7152, 0.0722));
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

// std140-padded parameter block matching the shader's GrayscaleParams.
// A single float rounds up to vec4 alignment, so the UBO is 16 bytes.
struct GrayscaleParamsStd140 {
    float strength;
    float _pad[3];
};
static_assert(sizeof(GrayscaleParamsStd140) == 16,
              "GrayscaleParamsStd140 must be 16 bytes for std140 compliance");

void GrayscalePass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[GrayscalePass] ctx.ctx2 is null — GrayscalePass is tgfx2-only");
        return;
    }
    auto out_it = ctx.tex2_writes.find(output_res);
    if (out_it == ctx.tex2_writes.end() || !out_it->second) {
        tc::Log::error("[GrayscalePass/tgfx2] Missing tgfx2 output texture handle for '%s'",
                       output_res.c_str());
        return;
    }
    tgfx2::TextureHandle output_tex2 = out_it->second;

    auto in_it = ctx.tex2_reads.find(input_res);
    if (in_it == ctx.tex2_reads.end() || !in_it->second) {
        tc::Log::error("[GrayscalePass/tgfx2] Missing tgfx2 input texture handle for '%s'",
                       input_res.c_str());
        return;
    }
    tgfx2::TextureHandle input_tex2 = in_it->second;

    auto out_desc = ctx.ctx2->device().texture_desc(output_tex2);
    const int w = static_cast<int>(out_desc.width);
    const int h = static_cast<int>(out_desc.height);
    if (w <= 0 || h <= 0) return;

    // Lazily create the tgfx2 fragment shader and the params UBO. The device
    // pointer is captured on first use so destroy() can release both without
    // an ExecuteContext.
    if (!fs2_) {
        device2_ = &ctx.ctx2->device();

        tgfx2::ShaderDesc fs_desc;
        fs_desc.stage = tgfx2::ShaderStage::Fragment;
        fs_desc.source = GRAYSCALE_FRAG_UBO;
        fs2_ = device2_->create_shader(fs_desc);

        tgfx2::BufferDesc ubo_desc;
        ubo_desc.size = sizeof(GrayscaleParamsStd140);
        ubo_desc.usage = tgfx2::BufferUsage::Uniform | tgfx2::BufferUsage::CopyDst;
        params_ubo_ = device2_->create_buffer(ubo_desc);
    }

    // Upload parameters only when they change — avoids a GPU round-trip on
    // every frame when strength is static.
    if (uploaded_strength_ != strength) {
        GrayscaleParamsStd140 params{};
        params.strength = strength;
        device2_->upload_buffer(
            params_ubo_,
            std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&params),
                                     sizeof(params)));
        uploaded_strength_ = strength;
    }

    // Begin pass with LoadOp::Load — we fill the output, not clear it.
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

    // GrayscaleParams UBO at binding 0; input texture at sampler slot 0
    // (matches the default unit for the shader's sole `sampler2D u_input`).
    ctx.ctx2->bind_uniform_buffer(0, params_ubo_);
    ctx.ctx2->bind_sampled_texture(0, input_tex2);

    ctx.ctx2->draw_fullscreen_quad();
    ctx.ctx2->end_pass();
}

void GrayscalePass::destroy() {
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
    uploaded_strength_ = -1.0f;
}

TC_REGISTER_FRAME_PASS(GrayscalePass);

} // namespace termin
