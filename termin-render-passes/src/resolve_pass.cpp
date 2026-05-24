#include <termin/render/resolve_pass.hpp>

#include "termin/render/execute_context.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

extern "C" {
#include <tgfx/resources/tc_shader.h>
}

#include <algorithm>
#include <cctype>
#include <sstream>
#include <tcbase/tc_log.hpp>

namespace termin {
namespace {

std::string normalize_strategy(const std::string& value) {
    std::string mode;
    mode.reserve(value.size());
    for (char c : value) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            mode.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
        }
    }
    return mode.empty() ? "average" : mode;
}

bool supported_shader_samples(int samples) {
    return samples == 1 || samples == 2 || samples == 4 || samples == 8;
}

std::string make_resolve_frag(const std::string& mode, int samples) {
    const char* combine = mode == "max" ? "max" : "min";
    std::ostringstream ss;
    ss << R"(#version 450 core
layout(location=0) in vec2 v_uv;
layout(binding=4) uniform sampler2DMS u_tex;
layout(location=0) out vec4 FragColor;

const int SAMPLE_COUNT = )" << samples << R"(;

void main() {
    ivec2 tex_size = textureSize(u_tex);
    vec2 uv = clamp(v_uv, vec2(0.0), vec2(0.999999));
    ivec2 pixel = ivec2(uv * vec2(tex_size));

    vec4 value = texelFetch(u_tex, pixel, 0);
    for (int i = 1; i < SAMPLE_COUNT; ++i) {
        value = )" << combine << R"((value, texelFetch(u_tex, pixel, i));
    }

    FragColor = value;
}
)";
    return ss.str();
}

} // namespace

ResolvePass::ResolvePass(
    const std::string& input,
    const std::string& output,
    const std::string& strategy_value
)
    : input_res(input)
    , output_res(output)
    , strategy(strategy_value)
{
    pass_name_set("Resolve");
    link_to_type_registry("ResolvePass");
}

std::set<const char*> ResolvePass::compute_reads() const {
    std::set<const char*> reads;
    if (!input_res.empty()) {
        reads.insert(input_res.c_str());
    }
    if (!output_res_target.empty()) {
        reads.insert(output_res_target.c_str());
    }
    return reads;
}

std::set<const char*> ResolvePass::compute_writes() const {
    return {output_res.c_str()};
}

std::vector<std::pair<std::string, std::string>> ResolvePass::get_inplace_aliases() const {
    if (output_res_target.empty()) {
        return {};
    }
    return {{output_res_target, output_res}};
}

tgfx::ShaderHandle ResolvePass::shader_for(
    tgfx::IRenderDevice& device,
    const std::string& mode,
    int samples
) {
    const std::string key = mode + "_" + std::to_string(samples);
    auto it = shader_handles_.find(key);
    if (it == shader_handles_.end()) {
        const std::string source = make_resolve_frag(mode, samples);
        const std::string name = "ResolvePass_" + key + "_FS";
        tc_shader_handle handle = tc_shader_register_static(
            nullptr, source.c_str(), nullptr, name.c_str());
        it = shader_handles_.emplace(key, handle).first;
    }

    tgfx::ShaderHandle fs;
    tc_shader* raw = tc_shader_get(it->second);
    if (!raw || !tc_shader_ensure_tgfx2(raw, &device, nullptr, &fs)) {
        tc::Log::error("[ResolvePass] failed to create shader for strategy='%s', samples=%d",
                       mode.c_str(), samples);
        return {};
    }
    return fs;
}

void ResolvePass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[ResolvePass] ctx.ctx2 is null — ResolvePass is tgfx2-only");
        return;
    }

    auto in_it = ctx.tex2_reads.find(input_res);
    if (in_it == ctx.tex2_reads.end() || !in_it->second) {
        tc::Log::warn("[ResolvePass] missing tgfx2 input '%s'", input_res.c_str());
        return;
    }

    auto out_it = ctx.tex2_writes.find(output_res);
    if (out_it == ctx.tex2_writes.end() || !out_it->second) {
        tc::Log::warn("[ResolvePass] missing tgfx2 output '%s'", output_res.c_str());
        return;
    }

    tgfx::TextureHandle input_tex = in_it->second;
    tgfx::TextureHandle output_tex = out_it->second;
    const std::string mode = normalize_strategy(strategy);
    if (mode == "average") {
        ctx.ctx2->blit(input_tex, output_tex);
        return;
    }

    if (mode != "min" && mode != "max") {
        tc::Log::error("[ResolvePass] unsupported strategy '%s' in pass '%s'",
                       strategy.c_str(), get_pass_name().c_str());
        return;
    }

    device2_ = &ctx.ctx2->device();
    const auto input_desc = device2_->texture_desc(input_tex);
    const auto output_desc = device2_->texture_desc(output_tex);
    const int samples = static_cast<int>(input_desc.sample_count);
    if (!supported_shader_samples(samples)) {
        tc::Log::error("[ResolvePass] unsupported input sample count %d in pass '%s'",
                       samples, get_pass_name().c_str());
        return;
    }

    if (samples == 1) {
        ctx.ctx2->blit(input_tex, output_tex);
        return;
    }

    tgfx::ShaderHandle fs = shader_for(*device2_, mode, samples);
    if (!fs) {
        return;
    }

    const int w = static_cast<int>(output_desc.width);
    const int h = static_cast<int>(output_desc.height);
    if (w <= 0 || h <= 0) {
        return;
    }

    ctx.ctx2->begin_pass(output_tex);
    ctx.ctx2->set_viewport(0, 0, w, h);
    ctx.ctx2->set_depth_test(false);
    ctx.ctx2->set_depth_write(false);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::None);
    ctx.ctx2->bind_shader(ctx.ctx2->fsq_vertex_shader(), fs);

    tgfx::VertexBufferLayout fsq_layout;
    fsq_layout.stride = 4 * sizeof(float);
    fsq_layout.attributes = {
        {0, tgfx::VertexFormat::Float2, 0},
        {1, tgfx::VertexFormat::Float2, 2 * sizeof(float)},
    };
    ctx.ctx2->set_vertex_layout(fsq_layout);
    ctx.ctx2->bind_sampled_texture(4, input_tex);
    ctx.ctx2->draw_fullscreen_quad();
    ctx.ctx2->end_pass();
}

void ResolvePass::destroy() {
    // Shader handles live in the tc_shader registry and are shared/deduped.
    shader_handles_.clear();
    device2_ = nullptr;
}

TC_REGISTER_FRAME_PASS(ResolvePass);

} // namespace termin
