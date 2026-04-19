#include "ground_grid_pass.hpp"
#include "termin/camera/camera_component.hpp"
#include <tcbase/tc_log.hpp>

#include <tgfx2/render_context.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>

#include <cstring>
#include <span>

namespace termin {

// ---------------------------------------------------------------------------
// Shaders (inline)
// ---------------------------------------------------------------------------

// Shared parameter block — declared inline in both stages below.
// std140 aligns every mat4 to 16 bytes and each float to 4 bytes with
// the final block rounded up to 16. Layout: u_inv_vp(64) u_view(64)
// u_projection(64) u_near(4) u_far(4) + 8 bytes tail pad = 208 bytes.

static const char* GRID_VERT = R"(#version 450 core
layout(std140, binding = 0) uniform GridParams {
    mat4 u_inv_vp;
    mat4 u_view;
    mat4 u_projection;
    float u_near;
    float u_far;
};
layout(location = 0) in vec2 a_pos;
layout(location = 0) out vec3 v_near_point;
layout(location = 1) out vec3 v_far_point;

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

static const char* GRID_FRAG = R"(#version 450 core
layout(std140, binding = 0) uniform GridParams {
    mat4 u_inv_vp;
    mat4 u_view;
    mat4 u_projection;
    float u_near;
    float u_far;
};
layout(location = 0) in vec3 v_near_point;
layout(location = 1) in vec3 v_far_point;
layout(location = 0) out vec4 fragColor;

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

// std140 layout for GridParams: 3 mat4 + 2 float padded to 16-byte
// block boundary. Matches the GLSL declaration in GRID_VERT/GRID_FRAG.
struct GridParamsStd140 {
    float u_inv_vp[16];
    float u_view[16];
    float u_projection[16];
    float u_near;
    float u_far;
    float _pad[2];
};
static_assert(sizeof(GridParamsStd140) == 208,
              "GridParamsStd140 must be 208 bytes for std140 compliance");

GroundGridPass::GroundGridPass(
    const std::string& input_res,
    const std::string& output_res,
    const std::string& pass_name
) : input_res(input_res),
    output_res(output_res)
{
    set_pass_name(pass_name);
}

GroundGridPass::~GroundGridPass() {
    if (_device) {
        if (_vs)         _device->destroy(_vs);
        if (_fs)         _device->destroy(_fs);
        if (_params_ubo) _device->destroy(_params_ubo);
    }
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

void GroundGridPass::_ensure_resources(tgfx::IRenderDevice* device) {
    if (_vs && _fs && _params_ubo && _device == device) return;
    _device = device;

    if (!_vs) {
        tgfx::ShaderDesc vs_desc;
        vs_desc.stage = tgfx::ShaderStage::Vertex;
        vs_desc.source = GRID_VERT;
        _vs = device->create_shader(vs_desc);
    }
    if (!_fs) {
        tgfx::ShaderDesc fs_desc;
        fs_desc.stage = tgfx::ShaderStage::Fragment;
        fs_desc.source = GRID_FRAG;
        _fs = device->create_shader(fs_desc);
    }
    if (!_params_ubo) {
        tgfx::BufferDesc ubo_desc;
        ubo_desc.size = sizeof(GridParamsStd140);
        ubo_desc.usage = tgfx::BufferUsage::Uniform | tgfx::BufferUsage::CopyDst;
        _params_ubo = device->create_buffer(ubo_desc);
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
    tgfx::TextureHandle color_tex2 = color_it->second;

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};

    Mat44 view64  = ctx.camera->get_view_matrix();
    Mat44 proj64  = ctx.camera->get_projection_matrix();
    Mat44f view   = view64.to_float();
    Mat44f proj   = proj64.to_float();
    Mat44f vp     = proj * view;
    Mat44f inv_vp = vp.inverse();

    float near_clip = static_cast<float>(ctx.camera->near_clip);
    float far_clip  = static_cast<float>(ctx.camera->far_clip);

    _ensure_resources(&ctx2->device());
    if (!_vs || !_fs || !_params_ubo) return;

    // Upload the param block BEFORE begin_pass — Vulkan forbids
    // vkCmdCopyBuffer inside a render pass, and tgfx2's upload_buffer
    // on the GL path is a trivial glBufferSubData so either order is fine.
    GridParamsStd140 params{};
    std::memcpy(params.u_inv_vp,     inv_vp.data, sizeof(params.u_inv_vp));
    std::memcpy(params.u_view,       view.data,   sizeof(params.u_view));
    std::memcpy(params.u_projection, proj.data,   sizeof(params.u_projection));
    params.u_near = near_clip;
    params.u_far  = far_clip;
    ctx2->device().upload_buffer(
        _params_ubo,
        std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&params),
                                 sizeof(params)));

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
    ctx2->set_blend_func(tgfx::BlendFactor::SrcAlpha,
                         tgfx::BlendFactor::OneMinusSrcAlpha);
    ctx2->set_cull(tgfx::CullMode::None);

    // Bind our grid VS/FS (NOT the built-in FSQ VS) and draw the
    // built-in fullscreen quad. The grid VS declares `a_pos` at
    // location 0 — compatible with ctx2's FSQ VBO layout (aPos/aUV);
    // aUV at location 1 is simply ignored by the VS.
    ctx2->bind_shader(_vs, _fs);
    ctx2->bind_uniform_buffer(0, _params_ubo);

    ctx2->draw_fullscreen_quad();
    ctx2->end_pass();
}

// Register GroundGridPass in tc_pass_registry
TC_REGISTER_FRAME_PASS(GroundGridPass);

} // namespace termin
