#include <termin/render/depth_pass.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/camera/render_camera_utils.hpp>
#include <termin/render/tgfx2_bridge.hpp>

#include <tgfx2/render_context.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/opengl/opengl_render_device.hpp>

#include <tcbase/tc_log.hpp>

#include <cstdlib>
#include <cstring>
#include <optional>
#include <span>

namespace termin {

namespace {

// PerFrame UBO (binding 0): view + projection + near/far plane. Uploaded
// ONCE per execute, bound as a regular uniform buffer. std140:
//   u_view       mat4   offset 0    (64 B)
//   u_projection mat4   offset 64   (64 B)
//   u_near       float  offset 128  (4 B)
//   u_far        float  offset 132  (4 B)
//   pad                 offset 136  (8 B to 16-byte boundary)
// Total 144 bytes. Rounded up to 144 here; the GPU reads 16-byte
// aligned chunks so we pad the tail.
struct DepthPerFrameStd140 {
    float u_view[16];
    float u_projection[16];
    float u_near;
    float u_far;
    float _pad[2];
};
static_assert(sizeof(DepthPerFrameStd140) == 144,
              "DepthPerFrameStd140 must be 144 bytes");

// PushConstants (binding 14): per-object model matrix.
struct DepthPushStd140 {
    float u_model[16];
};
static_assert(sizeof(DepthPushStd140) == 64,
              "DepthPushStd140 must be exactly one mat4");

constexpr const char* DEPTH_PASS_VERT_UBO = R"(
#version 330 core
#extension GL_ARB_shading_language_420pack : require

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

layout(std140, binding = 0) uniform PerFrame {
    mat4  u_view;
    mat4  u_projection;
    float u_near;
    float u_far;
};

layout(std140, binding = 14) uniform PushConstants {
    mat4 u_model;
};

out float v_linear_depth;

void main() {
    vec4 world_pos = u_model * vec4(a_position, 1.0);
    vec4 view_pos  = u_view * world_pos;

    float y = view_pos.y;
    float depth = (y - u_near) / (u_far - u_near);

    v_linear_depth = depth;
    gl_Position = u_projection * view_pos;
}
)";

constexpr const char* DEPTH_PASS_FRAG_UBO = R"(
#version 330 core

in float v_linear_depth;
out vec4 FragColor;

void main() {
    float d = clamp(v_linear_depth, 0.0, 1.0);
    FragColor = vec4(d, d, d, 1.0);
}
)";

bool tgfx2_depth_enabled() {
    const char* env = std::getenv("TERMIN_TGFX2_DEPTH");
    return env && env[0] && env[0] != '0';
}

} // anonymous namespace

const char* DEPTH_PASS_VERT = R"(
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_near;
uniform float u_far;

out float v_linear_depth;

void main()
{
    vec4 world_pos = u_model * vec4(a_position, 1.0);
    vec4 view_pos  = u_view * world_pos;

    float y = view_pos.y;
    float depth = (y - u_near) / (u_far - u_near);

    v_linear_depth = depth;
    gl_Position = u_projection * view_pos;
}
)";

const char* DEPTH_PASS_FRAG = R"(
#version 330 core

in float v_linear_depth;
out vec4 FragColor;

void main()
{
    float d = clamp(v_linear_depth, 0.0, 1.0);
    FragColor = vec4(d, d, d, 1.0);
}
)";

void DepthPass::execute_with_data(
    GraphicsBackend* graphics,
    const FBOMap& reads_fbos,
    const FBOMap& writes_fbos,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    float near_plane,
    float far_plane,
    uint64_t layer_mask
) {
    (void)reads_fbos;
    _near_plane = near_plane;
    _far_plane = far_plane;
    execute_geometry_pass(graphics, writes_fbos, rect, scene, view, projection, layer_mask);
}

void DepthPass::ensure_tgfx2_resources(tgfx2::IRenderDevice& device) {
    if (device2_ == &device && depth_vs2_ && depth_fs2_ && per_frame_ubo_) {
        return;
    }
    if (device2_ && device2_ != &device) {
        release_tgfx2_resources();
    }
    device2_ = &device;

    tgfx2::ShaderDesc vs_desc;
    vs_desc.stage = tgfx2::ShaderStage::Vertex;
    vs_desc.source = DEPTH_PASS_VERT_UBO;
    depth_vs2_ = device.create_shader(vs_desc);

    tgfx2::ShaderDesc fs_desc;
    fs_desc.stage = tgfx2::ShaderStage::Fragment;
    fs_desc.source = DEPTH_PASS_FRAG_UBO;
    depth_fs2_ = device.create_shader(fs_desc);

    tgfx2::BufferDesc ubo_desc;
    ubo_desc.size = sizeof(DepthPerFrameStd140);
    ubo_desc.usage = tgfx2::BufferUsage::Uniform | tgfx2::BufferUsage::CopyDst;
    per_frame_ubo_ = device.create_buffer(ubo_desc);
}

void DepthPass::release_tgfx2_resources() {
    if (!device2_) return;
    if (depth_vs2_) { device2_->destroy(depth_vs2_); depth_vs2_ = {}; }
    if (depth_fs2_) { device2_->destroy(depth_fs2_); depth_fs2_ = {}; }
    if (per_frame_ubo_) { device2_->destroy(per_frame_ubo_); per_frame_ubo_ = {}; }
    device2_ = nullptr;
}

// ----------------------------------------------------------------------------
// tgfx2 path — Stage 5.D.
// ----------------------------------------------------------------------------
void DepthPass::execute_with_data_tgfx2(
    ExecuteContext& ctx,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    float near_plane,
    float far_plane,
    uint64_t layer_mask
) {
    if (!ctx.ctx2 || !ctx.graphics) {
        tc::Log::error("DepthPass/tgfx2: ctx2 or graphics is null");
        return;
    }

    _near_plane = near_plane;
    _far_plane = far_plane;

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
        tc::Log::error("DepthPass/tgfx2: device is not OpenGLRenderDevice");
        return;
    }

    ensure_tgfx2_resources(ctx.ctx2->device());

    TcShader& base_shader = get_shader(ctx.graphics);
    collect_draw_calls(scene, layer_mask, base_shader.handle);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    tgfx2::TextureHandle color_tex2 = wrap_fbo_color_as_tgfx2(*gl_dev, fb);
    tgfx2::TextureHandle depth_tex2 = wrap_fbo_depth_as_tgfx2(*gl_dev, fb);
    if (!color_tex2) {
        tc::Log::error("DepthPass/tgfx2: failed to wrap color texture");
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
    // DepthPass writes to a legacy r16f FBO. The tgfx2 pipeline key only
    // uses color_format for cache matching, not for the actual GL write
    // path — the underlying FBO is already configured as r16f by the
    // legacy FBOPool and the GL driver clamps/converts on write.
    ctx.ctx2->set_color_format(tgfx2::PixelFormat::R16F);
    ctx.ctx2->set_depth_format(tgfx2::PixelFormat::D32F);
    ctx.ctx2->bind_shader(depth_vs2_, depth_fs2_);

    // PerFrame UBO — uploaded ONCE per execute. view + projection +
    // near/far plane. Bound at slot 0.
    DepthPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
    per_frame.u_near = near_plane;
    per_frame.u_far = far_plane;
    ctx.ctx2->device().upload_buffer(
        per_frame_ubo_,
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(&per_frame),
            sizeof(per_frame)));
    ctx.ctx2->bind_uniform_buffer(0, per_frame_ubo_);

    RenderContext legacy_ctx;
    legacy_ctx.view = view;
    legacy_ctx.projection = projection;
    legacy_ctx.graphics = ctx.graphics;
    legacy_ctx.phase = phase_name();

    const std::string& debug_symbol = get_debug_internal_point();

    for (const auto& dc : cached_draw_calls_) {
        auto* drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        if (!drawable) continue;

        Mat44f model = drawable->get_model_matrix(dc.entity);

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        tc_mesh* mesh = drawable->get_mesh_for_phase(phase_name(), dc.geometry_id);
        bool override_is_base = tc_shader_handle_eq(dc.final_shader, base_shader.handle);

        if (mesh && override_is_base) {
            // Fast path: push constants for model matrix.
            DepthPushStd140 push{};
            std::memcpy(push.u_model, model.data, sizeof(float) * 16);
            ctx.ctx2->set_push_constants(&push, sizeof(push));

            Tgfx2MeshBinding bind = wrap_mesh_as_tgfx2(*gl_dev, mesh);
            if (bind.index_count == 0) continue;

            ctx.ctx2->set_vertex_layout(bind.layout);
            ctx.ctx2->set_topology(bind.topology);
            ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                           bind.index_count, bind.index_type);

            gl_dev->destroy(bind.vertex_buffer);
            gl_dev->destroy(bind.index_buffer);
        } else {
            ctx.ctx2->flush_pipeline();

            tc_shader_handle shader_handle = dc.final_shader;
            TcShader shader_to_use(shader_handle);
            shader_to_use.use();
            shader_to_use.set_uniform_mat4("u_view", view.data, false);
            shader_to_use.set_uniform_mat4("u_projection", projection.data, false);
            shader_to_use.set_uniform_mat4("u_model", model.data, false);
            shader_to_use.set_uniform_float("u_near", _near_plane);
            shader_to_use.set_uniform_float("u_far", _far_plane);
            legacy_ctx.model = model;
            legacy_ctx.current_tc_shader = shader_to_use;

            tc_component_draw_geometry(dc.component, &legacy_ctx, dc.geometry_id);
        }

        if (!debug_symbol.empty() && name && debug_symbol == name) {
            ctx.ctx2->end_pass();
            maybe_blit_to_debugger(ctx.graphics, fb, name, rect.width, rect.height);
            ctx.ctx2->begin_pass(color_tex2, depth_tex2, nullptr, 1.0f, false);
            ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
            ctx.ctx2->set_depth_test(true);
            ctx.ctx2->set_depth_write(true);
            ctx.ctx2->set_blend(false);
            ctx.ctx2->set_cull(tgfx2::CullMode::Back);
            ctx.ctx2->bind_shader(depth_vs2_, depth_fs2_);
        }
    }

    ctx.ctx2->end_pass();
    gl_dev->destroy(color_tex2);
    if (depth_tex2) gl_dev->destroy(depth_tex2);
}

void DepthPass::execute(ExecuteContext& ctx) {
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

    float near_plane = static_cast<float>(camera->near_clip);
    float far_plane = static_cast<float>(camera->far_clip);

    if (ctx.ctx2 && tgfx2_depth_enabled()) {
        execute_with_data_tgfx2(
            ctx,
            rect,
            scene,
            view,
            projection,
            near_plane,
            far_plane,
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
            near_plane,
            far_plane,
            ctx.layer_mask
        );
    }
}

TC_REGISTER_FRAME_PASS_DERIVED(DepthPass, GeometryPassBase);

} // namespace termin
