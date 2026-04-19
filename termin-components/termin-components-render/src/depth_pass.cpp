#include <termin/render/depth_pass.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/camera/render_camera_utils.hpp>
#include <termin/render/tgfx2_bridge.hpp>

#include <tgfx2/render_context.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

#include <tgfx/resources/tc_shader_registry.h>
#include <core/tc_drawable_protocol.h>

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

constexpr const char* DEPTH_PASS_VERT_UBO = R"(#version 450 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

layout(std140, binding = 0) uniform PerFrame {
    mat4  u_view;
    mat4  u_projection;
    float u_near;
    float u_far;
};

struct DepthPushData {
    mat4 u_model;
};
#ifdef VULKAN
layout(push_constant) uniform DepthPushBlock { DepthPushData pc; };
#else
layout(std140, binding = 14) uniform DepthPushBlock { DepthPushData pc; };
#endif

layout(location = 0) out float v_linear_depth;

void main() {
    vec4 world_pos = pc.u_model * vec4(a_position, 1.0);
    vec4 view_pos  = u_view * world_pos;

    float y = view_pos.y;
    float depth = (y - u_near) / (u_far - u_near);

    v_linear_depth = depth;
    gl_Position = u_projection * view_pos;
}
)";

constexpr const char* DEPTH_PASS_FRAG_UBO = R"(#version 450 core
layout(location = 0) in float v_linear_depth;
layout(location = 0) out vec4 FragColor;

void main() {
    float d = clamp(v_linear_depth, 0.0, 1.0);
    FragColor = vec4(d, d, d, 1.0);
}
)";

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

void DepthPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    if (device2_ == &device && depth_vs2_ && depth_fs2_ && per_frame_ubo_) {
        return;
    }
    if (device2_ && device2_ != &device) {
        release_tgfx2_resources();
    }
    device2_ = &device;

    tgfx::ShaderDesc vs_desc;
    vs_desc.stage = tgfx::ShaderStage::Vertex;
    vs_desc.source = DEPTH_PASS_VERT_UBO;
    depth_vs2_ = device.create_shader(vs_desc);

    tgfx::ShaderDesc fs_desc;
    fs_desc.stage = tgfx::ShaderStage::Fragment;
    fs_desc.source = DEPTH_PASS_FRAG_UBO;
    depth_fs2_ = device.create_shader(fs_desc);

    tgfx::BufferDesc ubo_desc;
    ubo_desc.size = sizeof(DepthPerFrameStd140);
    ubo_desc.usage = tgfx::BufferUsage::Uniform | tgfx::BufferUsage::CopyDst;
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
    if (!ctx.ctx2) {
        tc::Log::error("DepthPass/tgfx2: ctx2 is null");
        return;
    }

    _near_plane = near_plane;
    _far_plane = far_plane;

    auto color_it = ctx.tex2_writes.find(output_res);
    if (color_it == ctx.tex2_writes.end() || !color_it->second) {
        tc::Log::error("DepthPass/tgfx2: missing tgfx2 color texture for '%s'",
                       output_res.c_str());
        return;
    }
    tgfx::TextureHandle color_tex2 = color_it->second;

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};

    auto& device = ctx.ctx2->device();
    ensure_tgfx2_resources(device);

    TcShader& base_shader = get_shader();
    collect_draw_calls(scene, layer_mask, base_shader.handle);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    auto cc = clear_color();
    float clear_rgba[4] = {cc[0], cc[1], cc[2], cc[3]};

    ctx.ctx2->begin_pass(color_tex2, depth_tex2, clear_rgba, 1.0f, true);
    ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::Back);
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

    const std::string& debug_symbol = get_debug_internal_point();

    for (const auto& dc : cached_draw_calls_) {
        Drawable* drawable = nullptr;
        if (tc_component_get_drawable_vtable(dc.component) == &Drawable::cxx_drawable_vtable()) {
            drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        }
        if (!drawable) continue;

        tc_mesh* mesh = drawable->get_mesh_for_phase(phase_name(), dc.geometry_id);
        if (!mesh) continue;  // non-mesh drawables skipped

        Mat44f model = drawable->get_model_matrix(dc.entity);

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        bool override_is_base = tc_shader_handle_eq(dc.final_shader, base_shader.handle);

        Tgfx2MeshBinding bind = wrap_mesh_as_tgfx2(device, mesh);
        if (bind.index_count == 0) continue;

        if (override_is_base) {
            // Fast path: push constants for model matrix.
            DepthPushStd140 push{};
            std::memcpy(push.u_model, model.data, sizeof(float) * 16);
            ctx.ctx2->set_push_constants(&push, sizeof(push));

            ctx.ctx2->set_vertex_layout(bind.layout);
            ctx.ctx2->set_topology(bind.topology);
            ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                           bind.index_count, bind.index_type);
        } else {
            // Shader override (skinning): compile via bridge, upload
            // transitional mat4 uniforms + near/far, draw, re-bind.
            tc_shader* raw = tc_shader_get(dc.final_shader);
            if (!raw) {
                release_mesh_binding(device, bind);
                continue;
            }
            tgfx::ShaderHandle vs2, fs2;
            if (!tc_shader_ensure_tgfx2(raw, &device, &vs2, &fs2)) {
                release_mesh_binding(device, bind);
                continue;
            }
            ctx.ctx2->bind_shader(vs2, fs2);
            ctx.ctx2->set_vertex_layout(bind.layout);
            ctx.ctx2->set_topology(bind.topology);

            ctx.ctx2->set_uniform_mat4("u_view",       view.data,       false);
            ctx.ctx2->set_uniform_mat4("u_projection", projection.data, false);
            ctx.ctx2->set_uniform_mat4("u_model",      model.data,      false);
            ctx.ctx2->set_uniform_float("u_near",      _near_plane);
            ctx.ctx2->set_uniform_float("u_far",       _far_plane);

            drawable->upload_per_draw_uniforms_tgfx2(*ctx.ctx2, dc.geometry_id);

            ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                           bind.index_count, bind.index_type);

            ctx.ctx2->bind_shader(depth_vs2_, depth_fs2_);
        }

        release_mesh_binding(device, bind);
    }

    ctx.ctx2->end_pass();
    // color_tex2/depth_tex2 are persistent FBOPool wrappers — do not destroy.
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

    if (ctx.ctx2) {
        auto it = ctx.tex2_writes.find(output_res);
        if (it != ctx.tex2_writes.end() && it->second) {
            auto desc = ctx.ctx2->device().texture_desc(it->second);
            int w = static_cast<int>(desc.width);
            int h = static_cast<int>(desc.height);
            if (w > 0 && h > 0) {
                rect = Rect4i(0, 0, w, h);
                if (!camera_name.empty()) {
                    CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
                    if (named_camera) {
                        named_camera_snapshot = make_render_camera(
                            *named_camera, static_cast<double>(w) / std::max(1, h));
                        camera = &*named_camera_snapshot;
                    }
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

    if (!ctx.ctx2) {
        tc::Log::error("[DepthPass] ctx.ctx2 is null — DepthPass is tgfx2-only");
        return;
    }

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
}

TC_REGISTER_FRAME_PASS_DERIVED(DepthPass, GeometryPassBase);

} // namespace termin
