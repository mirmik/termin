#include <termin/render/ground_grid_pass.hpp>
#include <termin/camera/camera_component.hpp>
#include <tcbase/tc_log.hpp>

#include <tgfx2/render_context.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

extern "C" {
#include <tgfx/resources/tc_shader.h>
}

#include <cstring>

namespace termin {

namespace {

constexpr const char* GROUND_GRID_ENGINE_SHADER_UUID = "termin-engine-ground-grid";

} // namespace

// ---------------------------------------------------------------------------
// GroundGridPass implementation
// ---------------------------------------------------------------------------

// std140 layout for GridParams: 3 mat4 + 2 float padded to 16-byte
// block boundary. Matches the built-in ground grid GLSL declaration.
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
    // Shader handles live on the tc_shader registry (see `_shader_handle`),
    // shared across pass re-creations.
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
    _device = device;

    if (tc_shader_handle_is_invalid(_shader_handle)) {
        _shader_handle =
            tgfx::register_builtin_shader_from_catalog(GROUND_GRID_ENGINE_SHADER_UUID);
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
    if (tc_shader_handle_is_invalid(_shader_handle)) return;

    tgfx::ShaderHandle grid_vs, grid_fs;
    tc_shader* raw = nullptr;
    {
        raw = tc_shader_get(_shader_handle);
        if (!raw || !tc_shader_ensure_tgfx2(raw, _device, &grid_vs, &grid_fs)) {
            tc::Log::error("GroundGridPass: tc_shader_ensure_tgfx2 failed for engine grid shader");
            return;
        }
    }

    GridParamsStd140 params{};
    std::memcpy(params.u_inv_vp,     inv_vp.data, sizeof(params.u_inv_vp));
    std::memcpy(params.u_view,       view.data,   sizeof(params.u_view));
    std::memcpy(params.u_projection, proj.data,   sizeof(params.u_projection));
    params.u_near = near_clip;
    params.u_far  = far_clip;

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
    // built-in fullscreen quad.
    ctx2->bind_shader(grid_vs, grid_fs);
    ctx2->use_shader_resource_layout(raw);
    ctx2->bind_uniform_data("GridParams", &params, sizeof(params));

    ctx2->draw_fullscreen_quad_with_bound_shader();
    ctx2->end_pass();
}

// Register GroundGridPass in tc_pass_registry
TC_REGISTER_FRAME_PASS(GroundGridPass);

} // namespace termin
