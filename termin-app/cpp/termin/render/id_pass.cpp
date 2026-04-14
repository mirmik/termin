#include <tcbase/tc_log.hpp>
#include <tgfx/tgfx_shader_handle.hpp>

#include "termin/render/id_pass.hpp"
#include "termin/camera/render_camera_utils.hpp"
#include "termin/render/tgfx2_bridge.hpp"

#include "tgfx2/render_context.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/opengl/opengl_render_device.hpp"

#include <cstdlib>
#include <cstring>
#include <optional>
#include <span>

extern "C" {
#include "tc_picking.h"
}

#include <termin/camera/camera_component.hpp>

namespace termin {

namespace {

// std140 layout for the IdPass parameter block.
//   u_model       mat4    offset  0
//   u_view        mat4    offset 64
//   u_projection  mat4    offset 128
//   u_pickColor   vec3    offset 192  (std140 pads vec3 to 16 bytes)
// Total: 208 bytes, naturally 16-byte aligned.
struct IdParamsStd140 {
    float u_model[16];
    float u_view[16];
    float u_projection[16];
    float u_pickColor[4];  // vec3 + pad
};
static_assert(sizeof(IdParamsStd140) == 208,
              "IdParamsStd140 must be 208 bytes for std140 compliance");

constexpr const char* ID_PASS_VERT_UBO = R"(
#version 330 core
#extension GL_ARB_shading_language_420pack : require

layout(location=0) in vec3 a_position;
layout(location=1) in vec3 a_normal;
layout(location=2) in vec2 a_texcoord;

layout(std140) uniform IdParams {
    mat4 u_model;
    mat4 u_view;
    mat4 u_projection;
    vec3 u_pickColor;
};

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
)";

constexpr const char* ID_PASS_FRAG_UBO = R"(
#version 330 core
#extension GL_ARB_shading_language_420pack : require

layout(std140) uniform IdParams {
    mat4 u_model;
    mat4 u_view;
    mat4 u_projection;
    vec3 u_pickColor;
};

out vec4 fragColor;

void main() {
    fragColor = vec4(u_pickColor, 1.0);
}
)";

bool tgfx2_id_enabled() {
    const char* env = std::getenv("TERMIN_TGFX2_ID");
    return env && env[0] && env[0] != '0';
}

} // anonymous namespace

const char* ID_PASS_VERT = R"(
#version 330 core

layout(location=0) in vec3 a_position;
layout(location=1) in vec3 a_normal;
layout(location=2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
)";

const char* ID_PASS_FRAG = R"(
#version 330 core

uniform vec3 u_pickColor;
out vec4 fragColor;

void main() {
    fragColor = vec4(u_pickColor, 1.0);
}
)";

void IdPass::id_to_rgb(int id, float& r, float& g, float& b) {
    tc_picking_id_to_rgb_float(id, &r, &g, &b);
}

void IdPass::ensure_tgfx2_resources(tgfx2::IRenderDevice& device) {
    if (device2_ == &device && id_vs2_ && id_fs2_ && params_ubo_) {
        return;
    }
    if (device2_ && device2_ != &device) {
        release_tgfx2_resources();
    }
    device2_ = &device;

    tgfx2::ShaderDesc vs_desc;
    vs_desc.stage = tgfx2::ShaderStage::Vertex;
    vs_desc.source = ID_PASS_VERT_UBO;
    id_vs2_ = device.create_shader(vs_desc);

    tgfx2::ShaderDesc fs_desc;
    fs_desc.stage = tgfx2::ShaderStage::Fragment;
    fs_desc.source = ID_PASS_FRAG_UBO;
    id_fs2_ = device.create_shader(fs_desc);

    tgfx2::BufferDesc ubo_desc;
    ubo_desc.size = sizeof(IdParamsStd140);
    ubo_desc.usage = tgfx2::BufferUsage::Uniform | tgfx2::BufferUsage::CopyDst;
    params_ubo_ = device.create_buffer(ubo_desc);
}

void IdPass::release_tgfx2_resources() {
    if (!device2_) return;
    if (id_vs2_) { device2_->destroy(id_vs2_); id_vs2_ = {}; }
    if (id_fs2_) { device2_->destroy(id_fs2_); id_fs2_ = {}; }
    if (params_ubo_) { device2_->destroy(params_ubo_); params_ubo_ = {}; }
    device2_ = nullptr;
}

// ----------------------------------------------------------------------------
// tgfx2 path — Stage 5.C.
// ----------------------------------------------------------------------------
//
// Writes a color attachment (RGBA-encoded pick IDs) and uses depth test +
// write for occlusion. Parameter block is a single 208-byte std140 UBO
// containing {model, view, projection, pickColor}. Non-mesh drawables
// fall back to legacy tc_component_draw_geometry inside the same pass,
// same pattern as ShadowPass.
void IdPass::execute_with_data_tgfx2(
    ExecuteContext& ctx,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    uint64_t layer_mask
) {
    if (!ctx.ctx2 || !ctx.graphics) {
        tc::Log::error("IdPass/tgfx2: ctx2 or graphics is null");
        return;
    }

    auto it = ctx.writes_fbos.find(output_res);
    if (it == ctx.writes_fbos.end() || it->second == nullptr) {
        return;
    }
    FramebufferHandle* fb = dynamic_cast<FramebufferHandle*>(it->second);
    if (!fb) {
        return;
    }

    auto* gl_dev = dynamic_cast<tgfx2::OpenGLRenderDevice*>(&ctx.ctx2->device());
    if (!gl_dev) {
        tc::Log::error("IdPass/tgfx2: device is not OpenGLRenderDevice");
        return;
    }

    ensure_tgfx2_resources(ctx.ctx2->device());

    // Resolve base shader via the legacy path first. collect_draw_calls
    // needs a tc_shader_handle to key overrides against; the TcShader
    // object itself stays in _shader for the legacy fallback branch of
    // the inner loop.
    TcShader& base_shader = get_shader(ctx.graphics);
    collect_draw_calls(scene, layer_mask, base_shader.handle);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    // Wrap legacy FBO attachments. Both color and depth must be
    // wrapped so begin_pass can open a proper render pass on them.
    tgfx2::TextureHandle color_tex2 = wrap_fbo_color_as_tgfx2(*gl_dev, fb);
    tgfx2::TextureHandle depth_tex2 = wrap_fbo_depth_as_tgfx2(*gl_dev, fb);
    if (!color_tex2) {
        tc::Log::error("IdPass/tgfx2: failed to wrap color texture");
        return;
    }

    auto cc = clear_color();
    float clear_rgba[4] = {cc[0], cc[1], cc[2], cc[3]};

    ctx.ctx2->begin_pass(color_tex2, depth_tex2, clear_rgba, 1.0f, true);
    ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx2::CullMode::Back);
    ctx.ctx2->set_color_format(tgfx2::PixelFormat::RGBA8_UNorm);
    ctx.ctx2->set_depth_format(tgfx2::PixelFormat::D32F);
    ctx.ctx2->bind_shader(id_vs2_, id_fs2_);

    // Staging UBO contents. view/projection written once, model and
    // pickColor overwritten per draw.
    IdParamsStd140 params{};
    std::memcpy(params.u_view, view.data, sizeof(float) * 16);
    std::memcpy(params.u_projection, projection.data, sizeof(float) * 16);

    // Legacy RenderContext used by the fallback branch.
    RenderContext legacy_ctx;
    legacy_ctx.view = view;
    legacy_ctx.projection = projection;
    legacy_ctx.graphics = ctx.graphics;
    legacy_ctx.phase = phase_name();

    const std::string& debug_symbol = get_debug_internal_point();
    int current_pick_id = -1;
    float pick_r = 0.0f;
    float pick_g = 0.0f;
    float pick_b = 0.0f;

    for (const auto& dc : cached_draw_calls_) {
        auto* drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        if (!drawable) continue;

        Mat44f model = drawable->get_model_matrix(dc.entity);

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        if (dc.pick_id != current_pick_id) {
            current_pick_id = dc.pick_id;
            id_to_rgb(dc.pick_id, pick_r, pick_g, pick_b);
        }

        tc_mesh* mesh = drawable->get_mesh_for_phase(phase_name(), dc.geometry_id);
        bool override_is_base = tc_shader_handle_eq(dc.final_shader, base_shader.handle);

        if (mesh && override_is_base) {
            // Fast path: tgfx2 draw.
            std::memcpy(params.u_model, model.data, sizeof(float) * 16);
            params.u_pickColor[0] = pick_r;
            params.u_pickColor[1] = pick_g;
            params.u_pickColor[2] = pick_b;
            params.u_pickColor[3] = 0.0f;  // std140 vec3 pad
            ctx.ctx2->device().upload_buffer(
                params_ubo_,
                std::span<const uint8_t>(
                    reinterpret_cast<const uint8_t*>(&params),
                    sizeof(params)));
            ctx.ctx2->bind_uniform_buffer(0, params_ubo_);

            Tgfx2MeshBinding bind = wrap_mesh_as_tgfx2(*gl_dev, mesh);
            if (bind.index_count == 0) continue;

            ctx.ctx2->set_vertex_layout(bind.layout);
            ctx.ctx2->set_topology(bind.topology);
            ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                           bind.index_count, bind.index_type);

            gl_dev->destroy(bind.vertex_buffer);
            gl_dev->destroy(bind.index_buffer);
        } else {
            // Fallback: shader override or non-mesh drawable. Legacy
            // GL calls land on the same FBO that begin_pass bound
            // through the tgfx2 fbo_cache.
            ctx.ctx2->flush_pipeline();

            tc_shader_handle shader_handle = dc.final_shader;
            TcShader shader_to_use(shader_handle);
            shader_to_use.use();
            shader_to_use.set_uniform_mat4("u_view", view.data, false);
            shader_to_use.set_uniform_mat4("u_projection", projection.data, false);
            shader_to_use.set_uniform_mat4("u_model", model.data, false);
            shader_to_use.set_uniform_vec3("u_pickColor", pick_r, pick_g, pick_b);
            legacy_ctx.model = model;
            legacy_ctx.current_tc_shader = shader_to_use;

            tc_component_draw_geometry(dc.component, &legacy_ctx, dc.geometry_id);
        }

        if (!debug_symbol.empty() && name && debug_symbol == name) {
            // maybe_blit_to_debugger touches raw GL on the FBO; close
            // the pass first so tgfx2 doesn't see mutation of state it
            // thinks it owns, then reopen. This is rare (only fires
            // when the debugger has pinned a specific entity).
            ctx.ctx2->end_pass();
            maybe_blit_to_debugger(ctx.graphics, fb, name, rect.width, rect.height);
            ctx.ctx2->begin_pass(color_tex2, depth_tex2, nullptr, 1.0f, false);
            ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
            ctx.ctx2->set_depth_test(true);
            ctx.ctx2->set_depth_write(true);
            ctx.ctx2->set_blend(false);
            ctx.ctx2->set_cull(tgfx2::CullMode::Back);
            ctx.ctx2->bind_shader(id_vs2_, id_fs2_);
        }
    }

    ctx.ctx2->end_pass();
    gl_dev->destroy(color_tex2);
    if (depth_tex2) gl_dev->destroy(depth_tex2);
}

void IdPass::execute_with_data(
    GraphicsBackend* graphics,
    const FBOMap& reads_fbos,
    const FBOMap& writes_fbos,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    uint64_t layer_mask
) {
    (void)reads_fbos;

    auto it = writes_fbos.find(output_res);
    if (it == writes_fbos.end() || it->second == nullptr) {
        return;
    }
    FramebufferHandle* fb = dynamic_cast<FramebufferHandle*>(it->second);
    if (!fb) {
        return;
    }

    bind_and_clear(graphics, fb, rect);
    apply_default_render_state(graphics);

    TcShader& base_shader = get_shader(graphics);
    collect_draw_calls(scene, layer_mask, base_shader.handle);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    RenderContext context;
    context.view = view;
    context.projection = projection;
    context.graphics = graphics;
    context.phase = phase_name();

    const std::string& debug_symbol = get_debug_internal_point();
    tc_shader_handle last_shader = tc_shader_handle_invalid();
    int current_pick_id = -1;
    float pick_r = 0.0f;
    float pick_g = 0.0f;
    float pick_b = 0.0f;

    for (const auto& dc : cached_draw_calls_) {
        auto* drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        if (!drawable) {
            continue;
        }
        Mat44f model = drawable->get_model_matrix(dc.entity);
        context.model = model;

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        if (dc.pick_id != current_pick_id) {
            current_pick_id = dc.pick_id;
            id_to_rgb(dc.pick_id, pick_r, pick_g, pick_b);
        }

        tc_shader_handle shader_handle = dc.final_shader;
        bool shader_changed = !tc_shader_handle_eq(shader_handle, last_shader);

        TcShader shader_to_use(shader_handle);
        if (shader_changed) {
            shader_to_use.use();
            shader_to_use.set_uniform_mat4("u_view", view.data, false);
            shader_to_use.set_uniform_mat4("u_projection", projection.data, false);
            last_shader = shader_handle;
        }

        shader_to_use.set_uniform_mat4("u_model", model.data, false);
        shader_to_use.set_uniform_vec3("u_pickColor", pick_r, pick_g, pick_b);

        context.current_tc_shader = shader_to_use;
        tc_component_draw_geometry(dc.component, &context, dc.geometry_id);

        if (!debug_symbol.empty() && name && debug_symbol == name) {
            maybe_blit_to_debugger(graphics, fb, name, rect.width, rect.height);
        }
    }
}

void IdPass::execute(ExecuteContext& ctx) {
    tc_scene_handle scene = ctx.scene.handle();
    const RenderCamera* camera = ctx.camera;
    Rect4i rect = ctx.rect;
    std::optional<RenderCamera> named_camera_snapshot;

    if (!camera_name.empty()) {
        CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
        if (!named_camera) {
            return;
        }
        named_camera_snapshot = make_render_camera(*named_camera);
        camera = &*named_camera_snapshot;
    }

    if (!camera) {
        return;
    }

    auto it = ctx.writes_fbos.find(output_res);
    if (it != ctx.writes_fbos.end() && it->second != nullptr) {
        FramebufferHandle* fb = dynamic_cast<FramebufferHandle*>(it->second);
        if (fb) {
            auto fbo_size = fb->get_size();
            rect = Rect4i(0, 0, fbo_size.width, fbo_size.height);
            if (!camera_name.empty()) {
                CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
                if (named_camera) {
                    named_camera_snapshot = make_render_camera(*named_camera, static_cast<double>(fbo_size.width) / std::max(1, fbo_size.height));
                    camera = &*named_camera_snapshot;
                }
            }
        }
    }

    Mat44 view_d = camera->get_view_matrix();
    Mat44 proj_d = camera->get_projection_matrix();
    Mat44f view = view_d.to_float();
    Mat44f projection = proj_d.to_float();

    if (ctx.ctx2 && tgfx2_id_enabled()) {
        execute_with_data_tgfx2(
            ctx,
            rect,
            scene,
            view,
            projection,
            ctx.layer_mask
        );
    } else {
        execute_with_data(
            ctx.graphics,
            ctx.reads_fbos,
            ctx.writes_fbos,
            rect,
            scene,
            view,
            projection,
            ctx.layer_mask
        );
    }
}

TC_REGISTER_FRAME_PASS_DERIVED(IdPass, GeometryPassBase);

} // namespace termin
