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

#include <algorithm>
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
//   u_depth_encoding    offset 136  (4 B)
//   pad                 offset 140  (4 B to 16-byte boundary)
// Total 144 bytes. Rounded up to 144 here; the GPU reads 16-byte
// aligned chunks so we pad the tail.
struct DepthPerFrameStd140 {
    float u_view[16];
    float u_projection[16];
    float u_near;
    float u_far;
    float u_depth_encoding;
    float _pad;
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
    float u_depth_encoding;
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
layout(location = 1) out float v_perspective_depth;
layout(location = 2) out float v_log_depth;

void main() {
    vec4 world_pos = pc.u_model * vec4(a_position, 1.0);
    vec4 view_pos  = u_view * world_pos;

    float view_depth = view_pos.y;
    float depth = (view_depth - u_near) / (u_far - u_near);

    vec4 clip_pos = u_projection * view_pos;
    float ndc_depth = clip_pos.z / max(abs(clip_pos.w), 1e-6);
    float perspective_depth = ndc_depth;

    v_linear_depth = depth;
    v_perspective_depth = perspective_depth;
    v_log_depth = log2(max(view_depth, 0.0) + 1.0) / log2(max(u_far, 1e-6) + 1.0);
    gl_Position = clip_pos;
}
)";

constexpr const char* DEPTH_PASS_FRAG_UBO = R"(#version 450 core
layout(location = 0) in float v_linear_depth;
layout(location = 1) in float v_perspective_depth;
layout(location = 2) in float v_log_depth;
layout(location = 0) out vec4 FragColor;

layout(std140, binding = 0) uniform PerFrame {
    mat4  u_view;
    mat4  u_projection;
    float u_near;
    float u_far;
    float u_depth_encoding;
};

void main() {
    int mode = int(u_depth_encoding + 0.5);
    float d = v_linear_depth;
    if (mode == 2 || mode == 3) {
        d = v_perspective_depth;
    } else if (mode == 4 || mode == 5) {
        d = v_log_depth;
    }
    d = clamp(d, 0.0, 1.0);
    if (mode == 1 || mode == 3 || mode == 5) {
        d = 1.0 - d;
    }
    FragColor = vec4(d, d, d, 1.0);
}
)";

constexpr const char* DEPTH_ONLY_VERT_UBO = R"(#version 450 core
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

void main() {
    vec4 world_pos = pc.u_model * vec4(a_position, 1.0);
    vec4 view_pos  = u_view * world_pos;
    gl_Position = u_projection * view_pos;
}
)";

constexpr const char* DEPTH_ONLY_FRAG_UBO = R"(#version 450 core
void main() {
}
)";

constexpr const char* DEPTH_TO_COLOR_FRAG = R"(
#version 330 core
in vec2 v_uv;
layout(binding = 9) uniform sampler2D u_depth_tex;
out vec4 FragColor;

void main() {
    float d = texture(u_depth_tex, v_uv).r;
    FragColor = vec4(vec3(d), 1.0);
}
)";

constexpr const char* COLOR_TO_DEPTH_FRAG = R"(
#version 330 core
in vec2 v_uv;
layout(binding = 9) uniform sampler2D u_color_tex;

void main() {
    float d = texture(u_color_tex, v_uv).r;
    gl_FragDepth = clamp(d, 0.0, 1.0);
}
)";

float depth_encoding_mode(const std::string& encoding) {
    if (encoding == "linear") return 0.0f;
    if (encoding == "linear_inverse") return 1.0f;
    if (encoding == "perspective") return 2.0f;
    if (encoding == "perspective_inverse") return 3.0f;
    if (encoding == "logarithmic") return 4.0f;
    if (encoding == "logarithmic_inverse") return 5.0f;
    tc::Log::warn(
        "DepthPass: unknown depth_encoding '%s', using 'linear'",
        encoding.c_str()
    );
    return 0.0f;
}

bool depth_encoding_is_inverse(const std::string& encoding) {
    return encoding == "linear_inverse" ||
           encoding == "perspective_inverse" ||
           encoding == "logarithmic_inverse";
}

} // anonymous namespace

void DepthPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;

    // Engine-shader: process-lifetime ownership via tc_shader registry.
    if (tc_shader_handle_is_invalid(depth_shader_handle_)) {
        depth_shader_handle_ = tc_shader_register_static(
            DEPTH_PASS_VERT_UBO, DEPTH_PASS_FRAG_UBO,
            nullptr, "DepthEngineVSFS_Encoding");
    }

}

void DepthPass::release_tgfx2_resources() {
    if (!device2_) return;
    // depth_shader_handle_ NOT released — static engine shader, outlives
    // pass teardown so the render-device shader cache can reuse compiled
    // modules across Play/Stop. See tc_shader_register_static docs.
    device2_ = nullptr;
}

std::array<float, 4> DepthPass::clear_color() const {
    float far = depth_encoding_is_inverse(depth_encoding) ? 0.0f : 1.0f;
    return {far, far, far, 1.0f};
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

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};

    auto& device = ctx.ctx2->device();

    auto color_it = ctx.tex2_writes.find(output_res);
    tgfx::TextureHandle color_tex2 =
        (color_it != ctx.tex2_writes.end()) ? color_it->second : tgfx::TextureHandle{};
    if (color_tex2 && device.texture_desc(color_tex2).format == tgfx::PixelFormat::D32F) {
        color_tex2 = {};
    }
    if (!color_tex2 && !depth_tex2) {
        tc::Log::error("DepthPass/tgfx2: missing tgfx2 output texture for '%s'",
                       output_res.c_str());
        return;
    }

    ensure_tgfx2_resources(device);

    // Use the UBO-based engine shader as base_shader for skinning override.
    // The old source-based GeometryPassBase shader path has been removed;
    // this handle is the only base shader key for depth overrides.
    collect_draw_calls(scene, layer_mask, depth_shader_handle_);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    auto cc = clear_color();
    float clear_rgba[4] = {cc[0], cc[1], cc[2], cc[3]};

    ctx.ctx2->begin_pass(color_tex2, depth_tex2, clear_rgba, 1.0f, clear);
    ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::Back);

    tgfx::ShaderHandle depth_vs2, depth_fs2;
    {
        tc_shader* raw = tc_shader_get(depth_shader_handle_);
        if (!raw) {
            tc::Log::error("DepthPass: depth_shader_handle_ stale (index=%u gen=%u)",
                           depth_shader_handle_.index,
                           depth_shader_handle_.generation);
            return;
        }
        if (!tc_shader_ensure_tgfx2(raw, &device, &depth_vs2, &depth_fs2)) {
            tc::Log::error("DepthPass: tc_shader_ensure_tgfx2 failed for '%s'",
                           raw->name ? raw->name : raw->uuid);
            return;
        }
    }
    ctx.ctx2->bind_shader(depth_vs2, depth_fs2);

    // PerFrame UBO — uploaded ONCE per execute. view + projection +
    // near/far plane. Bound at slot 0.
    DepthPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
    per_frame.u_near = near_plane;
    per_frame.u_far = far_plane;
    per_frame.u_depth_encoding = depth_encoding_mode(depth_encoding);
    ctx.ctx2->bind_uniform_buffer_ring(0, &per_frame, sizeof(per_frame));

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

        bool override_is_base =
            tc_shader_handle_eq(dc.final_shader, depth_shader_handle_);

        // Both paths share push_constants + PerFrame UBO — the skinned
        // variant is just DEPTH_PASS_VERT_UBO with injected BoneBlock.
        DepthPushStd140 push{};
        std::memcpy(push.u_model, model.data, sizeof(float) * 16);
        ctx.ctx2->set_push_constants(&push, sizeof(push));

        if (override_is_base) {
            // Base depth VS only reads a_position. See IdPass / ShadowPass
            // for the rationale of stripping unused attributes.
            termin::draw_tc_mesh(*ctx.ctx2, mesh, {0});
        } else {
            // Skinning variant: compile via bridge, bind, upload BoneBlock
            // UBO from SkinnedMeshRenderer, draw.
            tc_shader* raw = tc_shader_get(dc.final_shader);
            if (!raw) {
                continue;
            }
            tgfx::ShaderHandle vs2, fs2;
            if (!tc_shader_ensure_tgfx2(raw, &device, &vs2, &fs2)) {
                continue;
            }
            ctx.ctx2->bind_shader(vs2, fs2);
            // Skinned depth VS uses a_position (0), a_normal (1),
            // a_joints (3), a_weights (4). a_texcoord (2) stays unused.

            drawable->upload_per_draw_uniforms_tgfx2(*ctx.ctx2, dc.geometry_id);

            termin::draw_tc_mesh(*ctx.ctx2, mesh, {0, 1, 6, 7});

            ctx.ctx2->bind_shader(depth_vs2, depth_fs2);
        }
    }

    ctx.ctx2->end_pass();
    // color_tex2/depth_tex2 are persistent FBOPool wrappers — do not destroy.
}

void DepthPass::execute(ExecuteContext& ctx) {
    tc_scene_handle scene = ctx.scene.handle();
    const RenderCamera* camera = ctx.camera;
    Rect4i rect = ctx.render_rect;
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

void DepthOnlyPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;
    if (tc_shader_handle_is_invalid(depth_shader_handle_)) {
        depth_shader_handle_ = tc_shader_register_static(
            DEPTH_ONLY_VERT_UBO, DEPTH_ONLY_FRAG_UBO,
            nullptr, "DepthOnlyEngineVSFS");
    }
}

void DepthOnlyPass::release_tgfx2_resources() {
    if (!device2_) return;
    device2_ = nullptr;
}

CameraComponent* DepthOnlyPass::find_camera_by_name(
    tc_scene_handle scene,
    const std::string& name
) const {
    if (name.empty() || !tc_scene_handle_valid(scene)) {
        return nullptr;
    }

    tc_entity_id eid = tc_scene_find_entity_by_name(scene, name.c_str());
    if (!tc_entity_id_valid(eid)) {
        return nullptr;
    }

    Entity ent(tc_scene_entity_pool(scene), eid);
    return ent.get_component<CameraComponent>();
}

void DepthOnlyPass::collect_draw_calls(tc_scene_handle scene, uint64_t layer_mask) const {
    cached_draw_calls_.clear();

    if (!tc_scene_handle_valid(scene)) {
        return;
    }

    struct CollectContext {
    public:
        const DepthOnlyPass* pass = nullptr;
        std::vector<DepthOnlyPass::DrawCall>* draw_calls = nullptr;
    };

    auto callback = [](tc_component* c, void* user_data) -> bool {
        auto* collect_ctx = static_cast<CollectContext*>(user_data);
        Entity ent(c->owner);

        DrawCall dc;
        dc.entity = ent;
        dc.component = c;
        dc.final_shader = tc_component_override_shader(
            c, "depth", 0, collect_ctx->pass->depth_shader_handle_);
        dc.geometry_id = 0;
        collect_ctx->draw_calls->push_back(dc);
        return true;
    };

    CollectContext collect_ctx{this, &cached_draw_calls_};

    int filter_flags = TC_SCENE_FILTER_ENABLED
                     | TC_SCENE_FILTER_VISIBLE
                     | TC_SCENE_FILTER_ENTITY_ENABLED;
    tc_scene_foreach_drawable(scene, callback, &collect_ctx, filter_flags, layer_mask);
}

void DepthOnlyPass::sort_draw_calls_by_shader() const {
    if (cached_draw_calls_.size() <= 1) {
        return;
    }

    std::sort(cached_draw_calls_.begin(), cached_draw_calls_.end(),
        [](const DrawCall& a, const DrawCall& b) {
            return a.final_shader.index < b.final_shader.index;
        });
}

void DepthOnlyPass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[DepthOnlyPass] ctx.ctx2 is null — DepthOnlyPass is tgfx2-only");
        return;
    }

    tc_scene_handle scene = ctx.scene.handle();
    const RenderCamera* camera = ctx.camera;
    Rect4i rect = ctx.render_rect;
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

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};
    if (!depth_tex2) {
        auto texture_it = ctx.tex2_writes.find(output_res);
        depth_tex2 = (texture_it != ctx.tex2_writes.end())
            ? texture_it->second
            : tgfx::TextureHandle{};
    }
    if (!depth_tex2) {
        tc::Log::error("DepthOnlyPass/tgfx2: missing tgfx2 depth texture for '%s'",
                       output_res.c_str());
        return;
    }

    auto desc = ctx.ctx2->device().texture_desc(depth_tex2);
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

    Mat44 view_d = camera->get_view_matrix();
    Mat44 proj_d = camera->get_projection_matrix();
    Mat44f view = view_d.to_float();
    Mat44f projection = proj_d.to_float();

    float near_plane = static_cast<float>(camera->near_clip);
    float far_plane = static_cast<float>(camera->far_clip);
    _near_plane = near_plane;
    _far_plane = far_plane;

    auto& device = ctx.ctx2->device();
    ensure_tgfx2_resources(device);
    collect_draw_calls(scene, ctx.layer_mask);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    ctx.ctx2->begin_pass({}, depth_tex2, nullptr, 1.0f, true);
    ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::Back);

    tgfx::ShaderHandle depth_vs2, depth_fs2;
    {
        tc_shader* raw = tc_shader_get(depth_shader_handle_);
        if (!raw) {
            tc::Log::error("DepthOnlyPass: depth_shader_handle_ stale (index=%u gen=%u)",
                           depth_shader_handle_.index,
                           depth_shader_handle_.generation);
            return;
        }
        if (!tc_shader_ensure_tgfx2(raw, &device, &depth_vs2, &depth_fs2)) {
            tc::Log::error("DepthOnlyPass: tc_shader_ensure_tgfx2 failed for '%s'",
                           raw->name ? raw->name : raw->uuid);
            return;
        }
    }
    ctx.ctx2->bind_shader(depth_vs2, depth_fs2);

    DepthPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
    per_frame.u_near = near_plane;
    per_frame.u_far = far_plane;
    ctx.ctx2->bind_uniform_buffer_ring(0, &per_frame, sizeof(per_frame));

    for (const auto& dc : cached_draw_calls_) {
        Drawable* drawable = nullptr;
        if (tc_component_get_drawable_vtable(dc.component) == &Drawable::cxx_drawable_vtable()) {
            drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        }
        if (!drawable) continue;

        tc_mesh* mesh = drawable->get_mesh_for_phase("depth", dc.geometry_id);
        if (!mesh) continue;

        Mat44f model = drawable->get_model_matrix(dc.entity);

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        bool override_is_base =
            tc_shader_handle_eq(dc.final_shader, depth_shader_handle_);

        DepthPushStd140 push{};
        std::memcpy(push.u_model, model.data, sizeof(float) * 16);
        ctx.ctx2->set_push_constants(&push, sizeof(push));

        if (override_is_base) {
            termin::draw_tc_mesh(*ctx.ctx2, mesh, {0});
        } else {
            tc_shader* raw = tc_shader_get(dc.final_shader);
            if (!raw) {
                continue;
            }
            tgfx::ShaderHandle vs2, fs2;
            if (!tc_shader_ensure_tgfx2(raw, &device, &vs2, &fs2)) {
                continue;
            }
            ctx.ctx2->bind_shader(vs2, fs2);

            drawable->upload_per_draw_uniforms_tgfx2(*ctx.ctx2, dc.geometry_id);

            termin::draw_tc_mesh(*ctx.ctx2, mesh, {0, 1, 6, 7});

            ctx.ctx2->bind_shader(depth_vs2, depth_fs2);
        }
    }

    ctx.ctx2->end_pass();
}

void DepthToColorPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;
    if (tc_shader_handle_is_invalid(shader_handle_)) {
        shader_handle_ = tc_shader_register_static(
            nullptr, DEPTH_TO_COLOR_FRAG, nullptr, "DepthToColorFS");
    }
}

void DepthToColorPass::release_tgfx2_resources() {
    device2_ = nullptr;
}

void DepthToColorPass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[DepthToColorPass] ctx.ctx2 is null");
        return;
    }

    auto depth_it = ctx.tex2_depth_reads.find(input_res);
    tgfx::TextureHandle depth_tex =
        (depth_it != ctx.tex2_depth_reads.end()) ? depth_it->second : tgfx::TextureHandle{};
    if (!depth_tex) {
        auto texture_it = ctx.tex2_reads.find(input_res);
        depth_tex = (texture_it != ctx.tex2_reads.end()) ? texture_it->second : tgfx::TextureHandle{};
    }
    if (!depth_tex) {
        tc::Log::error("[DepthToColorPass] missing depth input '%s'", input_res.c_str());
        return;
    }

    auto color_it = ctx.tex2_writes.find(output_res);
    tgfx::TextureHandle color_tex =
        (color_it != ctx.tex2_writes.end()) ? color_it->second : tgfx::TextureHandle{};
    if (!color_tex) {
        tc::Log::error("[DepthToColorPass] missing color output '%s'", output_res.c_str());
        return;
    }

    auto& device = ctx.ctx2->device();
    ensure_tgfx2_resources(device);

    tgfx::ShaderHandle fs;
    tc_shader* raw = tc_shader_get(shader_handle_);
    if (!raw || !tc_shader_ensure_tgfx2(raw, &device, nullptr, &fs)) {
        tc::Log::error("[DepthToColorPass] failed to prepare shader");
        return;
    }

    tgfx::TextureDesc desc = device.texture_desc(color_tex);
    int w = static_cast<int>(desc.width);
    int h = static_cast<int>(desc.height);
    if (w <= 0 || h <= 0) {
        tc::Log::error("[DepthToColorPass] invalid output size for '%s'", output_res.c_str());
        return;
    }

    ctx.ctx2->begin_pass(color_tex, {}, nullptr, 1.0f, false);
    ctx.ctx2->set_viewport(0, 0, w, h);
    ctx.ctx2->set_depth_test(false);
    ctx.ctx2->set_depth_write(false);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::None);
    ctx.ctx2->bind_shader(ctx.ctx2->fsq_vertex_shader(), fs);
    ctx.ctx2->clear_resource_bindings();
    ctx.ctx2->bind_sampled_texture(9, depth_tex);
    ctx.ctx2->draw_fullscreen_quad();
    ctx.ctx2->end_pass();
}

void ColorToDepthPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;
    if (tc_shader_handle_is_invalid(shader_handle_)) {
        shader_handle_ = tc_shader_register_static(
            nullptr, COLOR_TO_DEPTH_FRAG, nullptr, "ColorToDepthFS");
    }
}

void ColorToDepthPass::release_tgfx2_resources() {
    device2_ = nullptr;
}

void ColorToDepthPass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[ColorToDepthPass] ctx.ctx2 is null");
        return;
    }

    auto color_it = ctx.tex2_reads.find(input_res);
    tgfx::TextureHandle color_tex =
        (color_it != ctx.tex2_reads.end()) ? color_it->second : tgfx::TextureHandle{};
    if (!color_tex) {
        tc::Log::error("[ColorToDepthPass] missing color input '%s'", input_res.c_str());
        return;
    }

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};
    if (!depth_tex) {
        auto texture_it = ctx.tex2_writes.find(output_res);
        depth_tex = (texture_it != ctx.tex2_writes.end()) ? texture_it->second : tgfx::TextureHandle{};
    }
    if (!depth_tex) {
        tc::Log::error("[ColorToDepthPass] missing depth output '%s'", output_res.c_str());
        return;
    }

    auto& device = ctx.ctx2->device();
    ensure_tgfx2_resources(device);

    tgfx::ShaderHandle fs;
    tc_shader* raw = tc_shader_get(shader_handle_);
    if (!raw || !tc_shader_ensure_tgfx2(raw, &device, nullptr, &fs)) {
        tc::Log::error("[ColorToDepthPass] failed to prepare shader");
        return;
    }

    tgfx::TextureDesc desc = device.texture_desc(depth_tex);
    int w = static_cast<int>(desc.width);
    int h = static_cast<int>(desc.height);
    if (w <= 0 || h <= 0) {
        tc::Log::error("[ColorToDepthPass] invalid output size for '%s'", output_res.c_str());
        return;
    }

    ctx.ctx2->begin_pass({}, depth_tex, nullptr, 1.0f, true);
    ctx.ctx2->set_viewport(0, 0, w, h);
    ctx.ctx2->set_depth_test(false);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::None);
    ctx.ctx2->bind_shader(ctx.ctx2->fsq_vertex_shader(), fs);
    ctx.ctx2->clear_resource_bindings();
    ctx.ctx2->bind_sampled_texture(9, color_tex);
    ctx.ctx2->draw_fullscreen_quad();
    ctx.ctx2->end_pass();
}

TC_REGISTER_FRAME_PASS_DERIVED(DepthPass, GeometryPassBase);
TC_REGISTER_FRAME_PASS_DERIVED(DepthOnlyPass, CxxFramePass);
TC_REGISTER_FRAME_PASS_DERIVED(DepthToColorPass, CxxFramePass);
TC_REGISTER_FRAME_PASS_DERIVED(ColorToDepthPass, CxxFramePass);

} // namespace termin
