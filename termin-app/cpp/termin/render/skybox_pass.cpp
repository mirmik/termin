// skybox_pass.cpp - Skybox rendered fully through RenderContext2 + material UBO.
#include "skybox_pass.hpp"

#include "termin/render/execute_context.hpp"
#include "termin/render/material_ubo_apply.hpp"
#include "termin/render/shader_parser.hpp"
#include "termin/render/render_camera.hpp"

#include "tgfx2/render_context.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"

#include <core/tc_scene_render_state.h>
#include <core/tc_scene_skybox.h>

#include <tcbase/tc_log.hpp>

#include <span>
#include <vector>

namespace termin {

// ============================================================================
// Shader source
// ============================================================================
//
// Full @program .shader text. The parser processes it at load time and
// synthesizes a std140 MaterialParams block from the @property entries,
// strips the corresponding `uniform` decls from the stage sources, and
// injects the block declaration after #version. The layout, block size,
// and rewritten stage sources all come out of parse_shader_text()
// below — zero hand-coded duplication.
//
// A single fragment stage branches on u_skybox_type to cover both solid
// and gradient variants, so the program compiles to one pipeline.

static const char* SKYBOX_SHADER_TEXT = R"(
@program Skybox

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask false
@glCull false

@property Mat4  u_view
@property Mat4  u_projection
@property Int   u_skybox_type
@property Color u_skybox_color        = Color(0.5, 0.5, 0.5, 1.0)
@property Color u_skybox_top_color    = Color(0.3, 0.5, 1.0, 1.0)
@property Color u_skybox_bottom_color = Color(0.1, 0.1, 0.3, 1.0)

@stage vertex
#version 330 core
layout(location = 0) in vec3 a_position;

uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_dir;

void main() {
    mat4 view_no_translation = mat4(mat3(u_view));
    v_dir = a_position;
    gl_Position = u_projection * view_no_translation * vec4(a_position, 1.0);
}
@endstage

@stage fragment
#version 330 core

in vec3 v_dir;
out vec4 FragColor;

uniform int  u_skybox_type;
uniform vec4 u_skybox_color;
uniform vec4 u_skybox_top_color;
uniform vec4 u_skybox_bottom_color;

void main() {
    // 0 = gradient, 1 = solid — matches the TC_SKYBOX_* enum values in
    // core/tc_scene_skybox.h (TC_SKYBOX_GRADIENT=0, TC_SKYBOX_SOLID=1;
    // TC_SKYBOX_NONE is filtered out by the C++ caller before dispatch).
    if (u_skybox_type == 1) {
        FragColor = vec4(u_skybox_color.rgb, 1.0);
    } else {
        float t = normalize(v_dir).z * 0.5 + 0.5;
        vec3 c = mix(u_skybox_bottom_color.rgb, u_skybox_top_color.rgb, t);
        FragColor = vec4(c, 1.0);
    }
}
@endstage

@endphase
)";

// ============================================================================
// Cube geometry (position-only) — identical to tc_scene_skybox's mesh.
// ============================================================================

static const float CUBE_VERTICES[8 * 3] = {
    -1.0f, -1.0f, -1.0f,
     1.0f, -1.0f, -1.0f,
     1.0f,  1.0f, -1.0f,
    -1.0f,  1.0f, -1.0f,
    -1.0f, -1.0f,  1.0f,
     1.0f, -1.0f,  1.0f,
     1.0f,  1.0f,  1.0f,
    -1.0f,  1.0f,  1.0f,
};

static const uint32_t CUBE_INDICES[36] = {
    0, 1, 2,  0, 2, 3,   // back
    4, 6, 5,  4, 7, 6,   // front
    0, 4, 5,  0, 5, 1,   // bottom
    3, 2, 6,  3, 6, 7,   // top
    1, 5, 6,  1, 6, 2,   // right
    0, 3, 7,  0, 7, 4,   // left
};

// ============================================================================
// Construction
// ============================================================================

SkyBoxPass::SkyBoxPass(const std::string& input,
                       const std::string& output,
                       const std::string& pass_name)
    : input_res(input)
    , output_res(output)
{
    pass_name_set(pass_name.c_str());
    link_to_type_registry("SkyBoxPass");
}

std::set<const char*> SkyBoxPass::compute_reads() const {
    return {input_res.c_str()};
}

std::set<const char*> SkyBoxPass::compute_writes() const {
    return {output_res.c_str()};
}

std::vector<ResourceSpec> SkyBoxPass::get_resource_specs() const {
    // Declare a dark-gray clear on the input resource so the framegraph
    // allocator gives us a well-defined initial state — identical intent
    // to the legacy Python pass's get_resource_specs.
    ResourceSpec spec;
    spec.resource = input_res;
    spec.clear_color = std::array<double, 4>{0.2, 0.2, 0.2, 1.0};
    spec.clear_depth = 1.0f;
    return { spec };
}

// ============================================================================
// Lazy resource creation
// ============================================================================

void SkyBoxPass::ensure_resources(ExecuteContext& ctx) {
    if (vs_) return;
    if (!ctx.ctx2) return;

    device2_ = &ctx.ctx2->device();

    // Parse the @program .shader text once. Parser auto-generates the
    // std140 MaterialParams block from the @property entries, rewrites
    // the stage sources to include the block declaration, and returns a
    // layout we can use directly for std140_pack / block_size sizing.
    ShaderMultyPhaseProgramm parsed = parse_shader_text(SKYBOX_SHADER_TEXT);
    if (parsed.phases.empty()) {
        tc::Log::error("[SkyBoxPass] failed to parse shader text");
        return;
    }
    const ShaderPhase& phase = parsed.phases.front();
    skybox_layout_ = phase.material_ubo_layout;
    if (skybox_layout_.block_size == 0) {
        tc::Log::error("[SkyBoxPass] parser produced empty material UBO layout");
        return;
    }

    const auto vs_it = phase.stages.find("vertex");
    const auto fs_it = phase.stages.find("fragment");
    if (vs_it == phase.stages.end() || fs_it == phase.stages.end()) {
        tc::Log::error("[SkyBoxPass] parser produced phase without vertex/fragment stage");
        return;
    }

    tgfx2::ShaderDesc vs_desc;
    vs_desc.stage = tgfx2::ShaderStage::Vertex;
    vs_desc.source = vs_it->second.source;
    vs_ = device2_->create_shader(vs_desc);

    tgfx2::ShaderDesc fs_desc;
    fs_desc.stage = tgfx2::ShaderStage::Fragment;
    fs_desc.source = fs_it->second.source;
    fs_ = device2_->create_shader(fs_desc);

    tgfx2::BufferDesc vbo_desc;
    vbo_desc.size = sizeof(CUBE_VERTICES);
    vbo_desc.usage = tgfx2::BufferUsage::Vertex | tgfx2::BufferUsage::CopyDst;
    cube_vbo_ = device2_->create_buffer(vbo_desc);
    device2_->upload_buffer(
        cube_vbo_,
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(CUBE_VERTICES),
            sizeof(CUBE_VERTICES)));

    tgfx2::BufferDesc ibo_desc;
    ibo_desc.size = sizeof(CUBE_INDICES);
    ibo_desc.usage = tgfx2::BufferUsage::Index | tgfx2::BufferUsage::CopyDst;
    cube_ibo_ = device2_->create_buffer(ibo_desc);
    device2_->upload_buffer(
        cube_ibo_,
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(CUBE_INDICES),
            sizeof(CUBE_INDICES)));

    // UBO sized from parser-computed block_size — no hand-coded duplicate.
    tgfx2::BufferDesc ubo_desc;
    ubo_desc.size = skybox_layout_.block_size;
    ubo_desc.usage = tgfx2::BufferUsage::Uniform | tgfx2::BufferUsage::CopyDst;
    params_ubo_ = device2_->create_buffer(ubo_desc);
}

// ============================================================================
// Execute
// ============================================================================

void SkyBoxPass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[SkyBoxPass] ctx2 is null — tgfx2 path required");
        return;
    }
    if (!ctx.camera) return;

    tc_scene_handle scene = ctx.scene.handle();
    if (!tc_scene_handle_valid(scene)) return;

    int skybox_type = tc_scene_get_skybox_type(scene);
    if (skybox_type == TC_SKYBOX_NONE) return;

    auto out_it = ctx.tex2_writes.find(output_res);
    if (out_it == ctx.tex2_writes.end() || !out_it->second) {
        tc::Log::error("[SkyBoxPass] no tgfx2 output texture for '%s'",
                       output_res.c_str());
        return;
    }
    tgfx2::TextureHandle output_tex2 = out_it->second;

    auto* output_fbo = ctx.writes_fbos.count(output_res)
        ? dynamic_cast<FramebufferHandle*>(ctx.writes_fbos[output_res])
        : nullptr;
    if (!output_fbo) return;
    const int w = output_fbo->get_width();
    const int h = output_fbo->get_height();
    if (w <= 0 || h <= 0) return;

    ensure_resources(ctx);
    if (!params_ubo_ || skybox_layout_.block_size == 0) return;

    // Collect material values: variant selector + camera matrices + colors.
    // u_skybox_type matches the TC_SKYBOX_* enum (0=gradient, 1=solid); the
    // fragment shader branches on it so we bind one pipeline regardless of
    // variant. u_skybox_type = Int here, not Bool, so the shader comparison
    // uses GLSL int semantics.
    int variant_int = (skybox_type == TC_SKYBOX_SOLID) ? 1 : 0;

    float solid_rgb[3] = {0, 0, 0};
    float top_rgb[3]   = {0, 0, 0};
    float bot_rgb[3]   = {0, 0, 0};
    tc_scene_get_skybox_color(scene,        &solid_rgb[0], &solid_rgb[1], &solid_rgb[2]);
    tc_scene_get_skybox_top_color(scene,    &top_rgb[0],   &top_rgb[1],   &top_rgb[2]);
    tc_scene_get_skybox_bottom_color(scene, &bot_rgb[0],   &bot_rgb[1],   &bot_rgb[2]);

    Mat44 view64 = ctx.camera->get_view_matrix();
    Mat44 proj64 = ctx.camera->get_projection_matrix();

    std::vector<double> view_data(view64.data, view64.data + 16);
    std::vector<double> proj_data(proj64.data, proj64.data + 16);

    std::vector<MaterialProperty> values;
    values.emplace_back("u_view",       "Mat4", std::move(view_data));
    values.emplace_back("u_projection", "Mat4", std::move(proj_data));
    values.emplace_back("u_skybox_type", "Int", variant_int);
    values.emplace_back(
        "u_skybox_color", "Color",
        std::vector<double>{solid_rgb[0], solid_rgb[1], solid_rgb[2], 1.0});
    values.emplace_back(
        "u_skybox_top_color", "Color",
        std::vector<double>{top_rgb[0], top_rgb[1], top_rgb[2], 1.0});
    values.emplace_back(
        "u_skybox_bottom_color", "Color",
        std::vector<double>{bot_rgb[0], bot_rgb[1], bot_rgb[2], 1.0});

    // Begin pass with LoadOp::Load — inplace alias means input_res already
    // holds whatever the framegraph allocator cleared it to.
    ctx.ctx2->begin_pass(output_tex2);
    ctx.ctx2->set_viewport(0, 0, w, h);

    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(false);
    ctx.ctx2->set_depth_func(tgfx2::CompareOp::LessEqual);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx2::CullMode::None);

    ctx.ctx2->bind_shader(vs_, fs_);
    ctx.ctx2->set_color_format(tgfx2::PixelFormat::RGBA8_UNorm);

    tgfx2::VertexBufferLayout cube_layout;
    cube_layout.stride = 3 * sizeof(float);
    cube_layout.attributes = {
        {0, tgfx2::VertexFormat::Float3, 0},  // a_position
    };
    ctx.ctx2->set_vertex_layout(cube_layout);

    bind_material_ubo(skybox_layout_, values, {}, params_ubo_, 0, *device2_, *ctx.ctx2);

    ctx.ctx2->draw(cube_vbo_, cube_ibo_, 36, tgfx2::IndexType::Uint32);
    ctx.ctx2->end_pass();
}

void SkyBoxPass::destroy() {
    if (device2_) {
        if (vs_)         { device2_->destroy(vs_);         vs_ = {}; }
        if (fs_)         { device2_->destroy(fs_);         fs_ = {}; }
        if (cube_vbo_)   { device2_->destroy(cube_vbo_);   cube_vbo_ = {}; }
        if (cube_ibo_)   { device2_->destroy(cube_ibo_);   cube_ibo_ = {}; }
        if (params_ubo_) { device2_->destroy(params_ubo_); params_ubo_ = {}; }
        device2_ = nullptr;
    }
    skybox_layout_ = MaterialUboLayout{};
}

TC_REGISTER_FRAME_PASS(SkyBoxPass);

} // namespace termin
