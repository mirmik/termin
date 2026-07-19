// tonemap_pass.cpp - HDR to LDR tonemapping post-processing pass.
//
// Draws through tgfx::RenderContext2 end-to-end: built-in FSQ,
// std140 UBO for parameters via bind_uniform_buffer, input texture
// via reflected texture binding. No raw GL. Legacy tgfx1 dual-path
// removed in Stage 8.1.
#include <termin/render/tonemap_pass.hpp>
#include "termin/render/execute_context.hpp"

#include "tgfx2/builtin_shader_sources.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

extern "C" {
#include <tgfx/resources/tc_shader.h>
}

#include <span>
#include <tcbase/tc_log.hpp>

namespace termin {

constexpr const char* TONEMAP_ENGINE_SHADER_UUID = "termin-engine-tonemap";

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
    std::set<const char*> reads;
    if (!input_res.empty()) {
        reads.insert(input_res.c_str());
    }
    if (!output_res_target.empty()) {
        reads.insert(output_res_target.c_str());
    }
    return reads;
}

std::set<const char*> TonemapPass::compute_writes() const {
    return {output_res.c_str()};
}

std::vector<std::pair<std::string, std::string>> TonemapPass::get_inplace_aliases() const {
    if (output_res_target.empty()) {
        return {};
    }
    return {{output_res_target, output_res}};
}

void TonemapPass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[TonemapPass] ctx.ctx2 is null — TonemapPass is tgfx2-only");
        return;
    }

    auto out_it = ctx.tex2_writes.find(output_res);
    if (out_it == ctx.tex2_writes.end() || !out_it->second) {
        tc::Log::error("[TonemapPass/tgfx2] Missing tgfx2 output texture handle for '%s'",
                       output_res.c_str());
        return;
    }
    tgfx::TextureHandle output_tex2 = out_it->second;

    auto in_it = ctx.tex2_reads.find(input_res);
    if (in_it == ctx.tex2_reads.end() || !in_it->second) {
        tc::Log::error("[TonemapPass/tgfx2] Missing tgfx2 input texture handle for '%s'",
                       input_res.c_str());
        return;
    }
    tgfx::TextureHandle input_tex2 = in_it->second;

    auto out_desc = ctx.ctx2->device().texture_desc(output_tex2);
    const int w = static_cast<int>(out_desc.width);
    const int h = static_cast<int>(out_desc.height);
    if (w <= 0 || h <= 0) return;

    device2_ = &ctx.ctx2->device();
    if (tc_shader_handle_is_invalid(shader_handle_)) {
        shader_handle_ = tgfx::register_builtin_shader_from_catalog(TONEMAP_ENGINE_SHADER_UUID);
        if (tc_shader_handle_is_invalid(shader_handle_)) return;
    }
    if (!params_ubo_) {
        tgfx::BufferDesc ubo_desc;
        ubo_desc.size = sizeof(TonemapParamsStd140);
        ubo_desc.usage = tgfx::BufferUsage::Uniform | tgfx::BufferUsage::CopyDst;
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
    ctx.ctx2->set_cull(tgfx::CullMode::None);

    tgfx::ShaderHandle tm_fs;
    tc_shader* raw = nullptr;
    {
        raw = tc_shader_get(shader_handle_);
        if (!raw || !tc_shader_ensure_tgfx2(raw, device2_, nullptr, &tm_fs)) {
            tc::Log::error("TonemapPass: tc_shader_ensure_tgfx2 failed");
            ctx.ctx2->end_pass();
            return;
        }
    }
    ctx.ctx2->bind_shader(ctx.ctx2->fsq_vertex_shader(), tm_fs);

    tgfx::VertexLayoutDesc fsq_layout;
    fsq_layout.stride = 4 * sizeof(float);
    fsq_layout.attribute_count = 2;
    fsq_layout.attributes[0] = {0, tgfx::VertexFormat::Float2, 0, tgfx::intern_vertex_semantic("position")};
    fsq_layout.attributes[1] = {1, tgfx::VertexFormat::Float2, 2 * sizeof(float), tgfx::intern_vertex_semantic("uv")};
    ctx.ctx2->set_vertex_layout(fsq_layout);

    ctx.ctx2->use_shader_resource_layout(raw);
    ctx.ctx2->bind_uniform("u_params", params_ubo_);
    ctx.ctx2->bind_texture("u_input", input_tex2);

    ctx.ctx2->draw_fullscreen_quad();
    ctx.ctx2->end_pass();
}

void TonemapPass::destroy() {
    if (device2_) {
        // Shader lives on the tc_shader registry (`shader_handle_`) — not owned.
        if (params_ubo_) {
            device2_->destroy(params_ubo_);
            params_ubo_ = {};
        }
        device2_ = nullptr;
    }
    uploaded_exposure_ = -1.0f;
    uploaded_method_ = -1;
}

void TonemapPass::register_type() {
    auto descriptor = FramePassTypeDescriptorBuilder::native<TonemapPass>(
        "TonemapPass", "termin-render-passes");
    auto& inspect = descriptor.inspect();
    _register_inspect_input_res(inspect);
    _register_inspect_output_res(inspect);
    _register_inspect_output_res_target(inspect);
    _register_inspect_exposure(inspect);
    _register_inspect_method(inspect);
    _register_inspect_metadata_graph(inspect);
    (void)descriptor.commit();
}

} // namespace termin
