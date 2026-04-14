#include "ground_grid_pass.hpp"
#include "tgfx/handles.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/render/tgfx2_bridge.hpp"
#include <tcbase/tc_log.hpp>

#include <tgfx2/render_context.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/opengl/opengl_render_device.hpp>
#include <tgfx2/tc_shader_bridge.hpp>
#include <tgfx2/enums.hpp>

namespace termin {

// ---------------------------------------------------------------------------
// Shaders (inline)
// ---------------------------------------------------------------------------

static const char* GRID_VERT = R"(
#version 330 core
layout(location = 0) in vec2 a_pos;

uniform mat4 u_inv_vp;

out vec3 v_near_point;
out vec3 v_far_point;

vec3 unproject(vec2 xy, float z) {
    vec4 p = u_inv_vp * vec4(xy, z, 1.0);
    return p.xyz / p.w;
}

void main() {
    v_near_point = unproject(a_pos, 0.0);
    v_far_point  = unproject(a_pos, 1.0);
    gl_Position  = vec4(a_pos, 0.0, 1.0);
}
)";

static const char* GRID_FRAG = R"(
#version 330 core
in vec3 v_near_point;
in vec3 v_far_point;

uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_near;
uniform float u_far;

out vec4 fragColor;

// Procedural grid lines for given world XY coordinates
vec4 grid(vec3 pos, float scale, vec4 color) {
    vec2 coord = pos.xy / scale;
    vec2 d = fwidth(coord);
    vec2 grid_line = abs(fract(coord - 0.5) - 0.5) / d;
    float line = min(grid_line.x, grid_line.y);
    float alpha = 1.0 - min(line, 1.0);
    return vec4(color.rgb, color.a * alpha);
}

// Compute depth value for gl_FragDepth
float compute_depth(vec3 pos) {
    vec4 clip = u_projection * u_view * vec4(pos, 1.0);
    return (clip.z / clip.w) * 0.5 + 0.5;
}

// Fade based on linear depth
float compute_fade(vec3 pos) {
    vec4 clip = u_projection * u_view * vec4(pos, 1.0);
    float ndc_depth = clip.z / clip.w;
    float linear_depth = (2.0 * u_near * u_far) / (u_far + u_near - ndc_depth * (u_far - u_near));
    return max(0.0, 1.0 - linear_depth / u_far);
}

void main() {
    // Ray from near to far
    vec3 ray = v_far_point - v_near_point;

    // Intersect with z=0 plane (XY horizontal, Z up)
    float t = -v_near_point.z / ray.z;

    // Discard if no intersection or behind camera
    if (t < 0.0) discard;

    vec3 world_pos = v_near_point + t * ray;

    // Two grid levels
    vec4 small_grid = grid(world_pos, 1.0,  vec4(0.5, 0.5, 0.5, 0.3));   // 1m, grey
    vec4 large_grid = grid(world_pos, 10.0, vec4(0.5, 0.5, 0.5, 0.5));   // 10m, brighter

    // X axis (red) and Y axis (green) highlights
    vec2 dxy = fwidth(vec2(world_pos.y, world_pos.x));
    float x_axis = 1.0 - min(abs(world_pos.y) / dxy.x, 1.0);  // X axis: y=0
    float y_axis = 1.0 - min(abs(world_pos.x) / dxy.y, 1.0);  // Y axis: x=0

    // Combine: large grid on top of small grid
    vec4 color = small_grid + large_grid * (1.0 - small_grid.a);

    // Add axis lines
    color.rgb = mix(color.rgb, vec3(0.8, 0.2, 0.2), x_axis * 0.8);
    color.rgb = mix(color.rgb, vec3(0.2, 0.8, 0.2), y_axis * 0.8);
    color.a   = max(color.a, max(x_axis * 0.8, y_axis * 0.8));

    // Fade by distance
    float fade = compute_fade(world_pos);
    color.a *= fade;

    // Write depth
    gl_FragDepth = compute_depth(world_pos);

    fragColor = color;
}
)";

// ---------------------------------------------------------------------------
// GroundGridPass implementation
// ---------------------------------------------------------------------------

GroundGridPass::GroundGridPass(
    const std::string& input_res,
    const std::string& output_res,
    const std::string& pass_name
) : input_res(input_res),
    output_res(output_res)
{
    set_pass_name(pass_name);
}

std::set<const char*> GroundGridPass::compute_reads() const {
    return {input_res.c_str()};
}

std::set<const char*> GroundGridPass::compute_writes() const {
    return {output_res.c_str()};
}

std::vector<std::pair<std::string, std::string>> GroundGridPass::get_inplace_aliases() const {
    return {{input_res, output_res}};
}

void GroundGridPass::_ensure_shader() {
    if (!_shader.is_valid()) {
        _shader = TcShader::from_sources(GRID_VERT, GRID_FRAG, "", "GroundGridPass");
    }
}

void GroundGridPass::execute(ExecuteContext& ctx) {
    auto* ctx2 = ctx.ctx2;
    if (!ctx2) {
        tc::Log::error("[GroundGridPass] ctx.ctx2 is null — GroundGridPass is tgfx2-only");
        return;
    }
    if (!ctx.camera) return;

    auto color_it = ctx.tex2_writes.find(output_res);
    if (color_it == ctx.tex2_writes.end() || !color_it->second) return;
    tgfx2::TextureHandle color_tex2 = color_it->second;

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx2::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx2::TextureHandle{};

    Mat44 view64  = ctx.camera->get_view_matrix();
    Mat44 proj64  = ctx.camera->get_projection_matrix();
    Mat44f view   = view64.to_float();
    Mat44f proj   = proj64.to_float();
    Mat44f vp     = proj * view;
    Mat44f inv_vp = vp.inverse();

    float near_clip = static_cast<float>(ctx.camera->near_clip);
    float far_clip  = static_cast<float>(ctx.camera->far_clip);

    // Compile the grid shader via the bridge (tgfx2 ShaderHandle pair).
    _ensure_shader();
    tc_shader* raw = tc_shader_get(_shader.handle);
    if (!raw) return;
    tgfx2::ShaderHandle vs2, fs2;
    if (!tc_shader_ensure_tgfx2(raw, &ctx2->device(), &vs2, &fs2)) return;

    auto out_desc = ctx2->device().texture_desc(color_tex2);
    const int w = static_cast<int>(out_desc.width);
    const int h = static_cast<int>(out_desc.height);

    ctx2->begin_pass(color_tex2, depth_tex2,
                     /*clear_color=*/nullptr,
                     /*clear_depth=*/1.0f,
                     /*clear_depth_enabled=*/false);
    ctx2->set_viewport(0, 0, w, h);

    // Depth test ON + write, blend ON (alpha fade), no culling.
    ctx2->set_depth_test(true);
    ctx2->set_depth_write(true);
    ctx2->set_blend(true);
    ctx2->set_blend_func(tgfx2::BlendFactor::SrcAlpha,
                         tgfx2::BlendFactor::OneMinusSrcAlpha);
    ctx2->set_cull(tgfx2::CullMode::None);
    ctx2->set_color_format(tgfx2::PixelFormat::RGBA8_UNorm);
    ctx2->set_depth_format(tgfx2::PixelFormat::D24_UNorm_S8_UInt);

    // Bind our grid VS/FS (NOT the built-in FSQ VS) and draw the
    // built-in fullscreen quad. The grid VS declares `a_pos` at
    // location 0 — compatible with ctx2's FSQ VBO layout (aPos/aUV);
    // aUV at location 1 is simply ignored by the VS.
    ctx2->bind_shader(vs2, fs2);

    // Grid uniforms via the transitional plain-uniform helpers.
    ctx2->set_uniform_mat4("u_inv_vp",    inv_vp.data, /*transpose=*/false);
    ctx2->set_uniform_mat4("u_view",      view.data,   /*transpose=*/false);
    ctx2->set_uniform_mat4("u_projection", proj.data,  /*transpose=*/false);
    ctx2->set_uniform_float("u_near", near_clip);
    ctx2->set_uniform_float("u_far",  far_clip);

    ctx2->draw_fullscreen_quad();
    ctx2->end_pass();
}

// Register GroundGridPass in tc_pass_registry
TC_REGISTER_FRAME_PASS(GroundGridPass);

} // namespace termin
