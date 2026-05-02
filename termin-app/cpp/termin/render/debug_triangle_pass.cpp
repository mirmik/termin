// debug_triangle_pass.cpp - Built-in pass that draws a diagnostic triangle.
#include "debug_triangle_pass.hpp"

#include "termin/render/execute_context.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

extern "C" {
#include <tgfx/resources/tc_shader.h>
}

#include <tcbase/tc_log.hpp>

namespace termin {

namespace {

const char* DEBUG_TRIANGLE_VERT = R"(
#version 450 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec4 a_color;

layout(location = 0) out vec4 v_color;

void main() {
    v_color = a_color;
    gl_Position = vec4(a_position, 1.0);
}
)";

const char* DEBUG_TRIANGLE_FRAG = R"(
#version 450 core

layout(location = 0) in vec4 v_color;
layout(location = 0) out vec4 fragColor;

void main() {
    fragColor = v_color;
}
)";

} // namespace

DebugTrianglePass::DebugTrianglePass(
    const std::string& output,
    const std::string& pass_name
) : output_res(output) {
    pass_name_set(pass_name);
    link_to_type_registry("DebugTrianglePass");
}

std::set<const char*> DebugTrianglePass::compute_reads() const {
    return {};
}

std::set<const char*> DebugTrianglePass::compute_writes() const {
    return {output_res.c_str()};
}

void DebugTrianglePass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[DebugTrianglePass] ctx.ctx2 is null");
        return;
    }

    auto out_it = ctx.tex2_writes.find(output_res);
    if (out_it == ctx.tex2_writes.end() || !out_it->second) {
        tc::Log::error("[DebugTrianglePass] missing tgfx2 output '%s'",
                       output_res.c_str());
        return;
    }

    tgfx::TextureHandle output_tex2 = out_it->second;
    auto out_desc = ctx.ctx2->device().texture_desc(output_tex2);
    const int w = static_cast<int>(out_desc.width);
    const int h = static_cast<int>(out_desc.height);
    if (w <= 0 || h <= 0) return;

    device2_ = &ctx.ctx2->device();
    if (tc_shader_handle_is_invalid(shader_handle_)) {
        shader_handle_ = tc_shader_register_static(
            DEBUG_TRIANGLE_VERT, DEBUG_TRIANGLE_FRAG, nullptr, "DebugTrianglePassVSFS");
    }

    tgfx::ShaderHandle vs;
    tgfx::ShaderHandle fs;
    {
        tc_shader* raw = tc_shader_get(shader_handle_);
        if (!raw || !tc_shader_ensure_tgfx2(raw, device2_, &vs, &fs)) {
            tc::Log::error("[DebugTrianglePass] tc_shader_ensure_tgfx2 failed");
            return;
        }
    }

    static const float vertices[] = {
         0.0f,  0.7f, 0.0f,  1.0f, 0.15f, 0.10f, 1.0f,
         0.7f, -0.6f, 0.0f,  0.10f, 0.35f, 1.0f, 1.0f,
        -0.7f, -0.6f, 0.0f,  0.10f, 0.75f, 0.20f, 1.0f,
    };

    const float clear_color[4] = {0.08f, 0.09f, 0.11f, 1.0f};
    ctx.ctx2->begin_pass(output_tex2, {}, clear_color, 1.0f, false);
    ctx.ctx2->set_viewport(0, 0, w, h);
    ctx.ctx2->set_depth_test(false);
    ctx.ctx2->set_depth_write(false);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::None);
    ctx.ctx2->bind_shader(vs, fs);
    ctx.ctx2->draw_immediate_triangles(vertices, 3);
    ctx.ctx2->end_pass();
}

void DebugTrianglePass::destroy() {
    shader_handle_ = tc_shader_handle_invalid();
    device2_ = nullptr;
}

TC_REGISTER_FRAME_PASS(DebugTrianglePass);

} // namespace termin
