#include "ground_grid_pass.hpp"
#include "tgfx/handles.hpp"
#include "termin/camera/camera_component.hpp"
#include "tc_log.hpp"

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
    if (!ctx.graphics) return;

    // Get output FBO
    auto it = ctx.writes_fbos.find(output_res);
    if (it == ctx.writes_fbos.end() || it->second == nullptr) {
        return;
    }

    FramebufferHandle* fb = dynamic_cast<FramebufferHandle*>(it->second);
    if (!fb) return;

    // Need camera for matrices
    if (!ctx.camera) return;

    Mat44 view64  = ctx.camera->get_view_matrix();
    Mat44 proj64  = ctx.camera->get_projection_matrix();
    Mat44f view   = view64.to_float();
    Mat44f proj   = proj64.to_float();
    Mat44f vp     = proj * view;
    Mat44f inv_vp = vp.inverse();

    float near_clip = static_cast<float>(ctx.camera->near_clip);
    float far_clip  = static_cast<float>(ctx.camera->far_clip);

    // Bind FBO and set viewport
    ctx.graphics->bind_framebuffer(fb);
    ctx.graphics->set_viewport(0, 0, fb->get_width(), fb->get_height());

    // Setup state: depth test ON (for depth write), blending ON (alpha fade), cull OFF
    ctx.graphics->set_depth_test(true);
    ctx.graphics->set_depth_mask(true);
    ctx.graphics->set_blend(true);
    ctx.graphics->set_blend_func(BlendFactor::SrcAlpha, BlendFactor::OneMinusSrcAlpha);
    ctx.graphics->set_cull_face(false);

    // Compile and use shader
    _ensure_shader();
    _shader.ensure_ready();
    _shader.use();

    // Set uniforms
    _shader.set_uniform_mat4("u_inv_vp",     inv_vp.data);
    _shader.set_uniform_mat4("u_view",        view.data);
    _shader.set_uniform_mat4("u_projection",  proj.data);
    _shader.set_uniform_float("u_near",       near_clip);
    _shader.set_uniform_float("u_far",        far_clip);

    // Draw fullscreen quad
    ctx.graphics->draw_ui_textured_quad();

    // Restore state
    ctx.graphics->set_blend(false);
    ctx.graphics->set_cull_face(true);
}

// Register GroundGridPass in tc_pass_registry
TC_REGISTER_FRAME_PASS(GroundGridPass);

} // namespace termin
