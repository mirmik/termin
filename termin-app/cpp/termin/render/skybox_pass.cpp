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
// Shaders
// ============================================================================
//
// All three shaders declare an identical `SkyboxParams` std140 uniform block
// so the same UBO binding (slot 0) feeds every variant. Colors live in vec4
// slots (xyz = color, w = unused / 1.0) to sidestep the std140 vec3 quirk.

static const char* SKYBOX_UBO_BLOCK = R"(
layout(std140) uniform SkyboxParams {
    mat4 u_view;
    mat4 u_projection;
    vec4 u_skybox_color;
    vec4 u_skybox_top_color;
    vec4 u_skybox_bottom_color;
};
)";

static const char* SKYBOX_VS = R"(
#version 330 core
layout(location = 0) in vec3 a_position;

layout(std140) uniform SkyboxParams {
    mat4 u_view;
    mat4 u_projection;
    vec4 u_skybox_color;
    vec4 u_skybox_top_color;
    vec4 u_skybox_bottom_color;
};

out vec3 v_dir;

void main() {
    mat4 view_no_translation = mat4(mat3(u_view));
    v_dir = a_position;
    gl_Position = u_projection * view_no_translation * vec4(a_position, 1.0);
}
)";

static const char* SKYBOX_FS_GRADIENT = R"(
#version 330 core

in vec3 v_dir;
out vec4 FragColor;

layout(std140) uniform SkyboxParams {
    mat4 u_view;
    mat4 u_projection;
    vec4 u_skybox_color;
    vec4 u_skybox_top_color;
    vec4 u_skybox_bottom_color;
};

void main() {
    float t = normalize(v_dir).z * 0.5 + 0.5;
    vec3 c = mix(u_skybox_bottom_color.rgb, u_skybox_top_color.rgb, t);
    FragColor = vec4(c, 1.0);
}
)";

static const char* SKYBOX_FS_SOLID = R"(
#version 330 core

in vec3 v_dir;
out vec4 FragColor;

layout(std140) uniform SkyboxParams {
    mat4 u_view;
    mat4 u_projection;
    vec4 u_skybox_color;
    vec4 u_skybox_top_color;
    vec4 u_skybox_bottom_color;
};

void main() {
    FragColor = vec4(u_skybox_color.rgb, 1.0);
}
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

    tgfx2::ShaderDesc vs_desc;
    vs_desc.stage = tgfx2::ShaderStage::Vertex;
    vs_desc.source = SKYBOX_VS;
    vs_ = device2_->create_shader(vs_desc);

    tgfx2::ShaderDesc fs_grad_desc;
    fs_grad_desc.stage = tgfx2::ShaderStage::Fragment;
    fs_grad_desc.source = SKYBOX_FS_GRADIENT;
    fs_gradient_ = device2_->create_shader(fs_grad_desc);

    tgfx2::ShaderDesc fs_solid_desc;
    fs_solid_desc.stage = tgfx2::ShaderStage::Fragment;
    fs_solid_desc.source = SKYBOX_FS_SOLID;
    fs_solid_ = device2_->create_shader(fs_solid_desc);

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

    // UBO sized to hold all five fields. Block layout is constructed by
    // hand below; 2 * mat4 + 3 * vec4 = 128 + 48 = 176, rounded to 176.
    tgfx2::BufferDesc ubo_desc;
    ubo_desc.size = 2u * 64u + 3u * 16u;
    ubo_desc.usage = tgfx2::BufferUsage::Uniform | tgfx2::BufferUsage::CopyDst;
    params_ubo_ = device2_->create_buffer(ubo_desc);
}

// ============================================================================
// Hand-written layout for SkyboxParams block
// ============================================================================

static MaterialUboLayout make_skybox_layout() {
    MaterialUboLayout layout;

    auto add = [&](const char* name, const char* type, uint32_t offset, uint32_t size) {
        MaterialUboEntry e;
        e.name = name;
        e.property_type = type;
        e.offset = offset;
        e.size = size;
        layout.entries.push_back(e);
    };

    add("u_view",                "Mat4", 0,   64);
    add("u_projection",          "Mat4", 64,  64);
    add("u_skybox_color",        "Vec4", 128, 16);
    add("u_skybox_top_color",    "Vec4", 144, 16);
    add("u_skybox_bottom_color", "Vec4", 160, 16);
    layout.block_size = 176;
    return layout;
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
    if (!params_ubo_) return;

    // Collect material values: camera matrices + skybox colors. Both color
    // arrays are filled even though only one variant uses each — the other
    // gets zeros, which is harmless.
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
    values.emplace_back(
        "u_skybox_color", "Vec4",
        std::vector<double>{solid_rgb[0], solid_rgb[1], solid_rgb[2], 1.0});
    values.emplace_back(
        "u_skybox_top_color", "Vec4",
        std::vector<double>{top_rgb[0], top_rgb[1], top_rgb[2], 1.0});
    values.emplace_back(
        "u_skybox_bottom_color", "Vec4",
        std::vector<double>{bot_rgb[0], bot_rgb[1], bot_rgb[2], 1.0});

    static const MaterialUboLayout layout = make_skybox_layout();

    // Begin pass with LoadOp::Load — inplace alias means input_res already
    // holds whatever the framegraph allocator cleared it to.
    ctx.ctx2->begin_pass(output_tex2);
    ctx.ctx2->set_viewport(0, 0, w, h);

    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(false);
    ctx.ctx2->set_depth_func(tgfx2::CompareOp::LessEqual);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx2::CullMode::None);

    tgfx2::ShaderHandle fs =
        (skybox_type == TC_SKYBOX_SOLID) ? fs_solid_ : fs_gradient_;
    ctx.ctx2->bind_shader(vs_, fs);
    ctx.ctx2->set_color_format(tgfx2::PixelFormat::RGBA8_UNorm);

    tgfx2::VertexBufferLayout cube_layout;
    cube_layout.stride = 3 * sizeof(float);
    cube_layout.attributes = {
        {0, tgfx2::VertexFormat::Float3, 0},  // a_position
    };
    ctx.ctx2->set_vertex_layout(cube_layout);

    bind_material_ubo(layout, values, {}, params_ubo_, 0, *device2_, *ctx.ctx2);

    ctx.ctx2->draw(cube_vbo_, cube_ibo_, 36, tgfx2::IndexType::Uint32);
    ctx.ctx2->end_pass();
}

void SkyBoxPass::destroy() {
    if (device2_) {
        if (vs_)          { device2_->destroy(vs_);          vs_ = {}; }
        if (fs_gradient_) { device2_->destroy(fs_gradient_); fs_gradient_ = {}; }
        if (fs_solid_)    { device2_->destroy(fs_solid_);    fs_solid_ = {}; }
        if (cube_vbo_)    { device2_->destroy(cube_vbo_);    cube_vbo_ = {}; }
        if (cube_ibo_)    { device2_->destroy(cube_ibo_);    cube_ibo_ = {}; }
        if (params_ubo_)  { device2_->destroy(params_ubo_);  params_ubo_ = {}; }
        device2_ = nullptr;
    }
}

TC_REGISTER_FRAME_PASS(SkyBoxPass);

} // namespace termin
