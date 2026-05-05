#include <termin/render/normal_pass.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/camera/render_camera_utils.hpp>
#include <termin/render/tgfx2_bridge.hpp>

#include <tgfx2/render_context.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
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

// PerFrame UBO (binding 0): view + projection. 128 bytes std140.
struct NormalPerFrameStd140 {
    float u_view[16];
    float u_projection[16];
};
static_assert(sizeof(NormalPerFrameStd140) == 128,
              "NormalPerFrameStd140 must be 2 * mat4");

// PushConstants (binding 14): per-object model matrix.
struct NormalPushStd140 {
    float u_model[16];
};
static_assert(sizeof(NormalPushStd140) == 64,
              "NormalPushStd140 must be exactly one mat4");

constexpr const char* NORMAL_PASS_VERT_UBO = R"(
#version 330 core
#extension GL_ARB_shading_language_420pack : require

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

layout(std140, binding = 0) uniform PerFrame {
    mat4 u_view;
    mat4 u_projection;
};

layout(std140, binding = 14) uniform PushConstants {
    mat4 u_model;
};

out vec3 v_world_normal;

void main() {
    mat3 normal_matrix = transpose(inverse(mat3(u_model)));
    v_world_normal = normalize(normal_matrix * a_normal);

    vec4 world_pos = u_model * vec4(a_position, 1.0);
    gl_Position = u_projection * u_view * world_pos;
}
)";

constexpr const char* NORMAL_PASS_FRAG_UBO = R"(
#version 330 core

in vec3 v_world_normal;
out vec4 FragColor;

void main() {
    vec3 encoded = normalize(v_world_normal) * 0.5 + 0.5;
    FragColor = vec4(encoded, 1.0);
}
)";

} // anonymous namespace

const char* NORMAL_PASS_VERT = R"(
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_world_normal;

void main()
{
    mat3 normal_matrix = transpose(inverse(mat3(u_model)));
    v_world_normal = normalize(normal_matrix * a_normal);

    vec4 world_pos = u_model * vec4(a_position, 1.0);
    gl_Position = u_projection * u_view * world_pos;
}
)";

const char* NORMAL_PASS_FRAG = R"(
#version 330 core

in vec3 v_world_normal;
out vec4 FragColor;

void main()
{
    vec3 encoded = normalize(v_world_normal) * 0.5 + 0.5;
    FragColor = vec4(encoded, 1.0);
}
)";

void NormalPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;

    if (tc_shader_handle_is_invalid(normal_shader_handle_)) {
        normal_shader_handle_ = tc_shader_register_static(
            NORMAL_PASS_VERT_UBO, NORMAL_PASS_FRAG_UBO,
            nullptr, "NormalEngineVSFS");
    }

}

void NormalPass::release_tgfx2_resources() {
    if (!device2_) return;
    // normal_shader_handle_ is static engine shader — not released here.
    device2_ = nullptr;
}

// ----------------------------------------------------------------------------
// tgfx2 path — Stage 5.E.
// ----------------------------------------------------------------------------
void NormalPass::execute_with_data_tgfx2(
    ExecuteContext& ctx,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    uint64_t layer_mask
) {
    if (!ctx.ctx2) {
        tc::Log::error("NormalPass/tgfx2: ctx2 is null");
        return;
    }

    auto color_it = ctx.tex2_writes.find(output_res);
    if (color_it == ctx.tex2_writes.end() || !color_it->second) {
        tc::Log::error("NormalPass/tgfx2: missing tgfx2 color texture for '%s'",
                       output_res.c_str());
        return;
    }
    tgfx::TextureHandle color_tex2 = color_it->second;

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};

    auto& device = ctx.ctx2->device();
    ensure_tgfx2_resources(device);

    // Use the UBO-based engine shader as base_shader for skinning override
    // (see DepthPass / ShadowPass for rationale).
    collect_draw_calls(scene, layer_mask, normal_shader_handle_);
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

    tgfx::ShaderHandle normal_vs2, normal_fs2;
    {
        tc_shader* raw = tc_shader_get(normal_shader_handle_);
        if (!raw || !tc_shader_ensure_tgfx2(raw, &device, &normal_vs2, &normal_fs2)) {
            tc::Log::error("NormalPass: tc_shader_ensure_tgfx2 failed for engine normal shader");
            return;
        }
    }
    ctx.ctx2->bind_shader(normal_vs2, normal_fs2);

    NormalPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
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
            tc_shader_handle_eq(dc.final_shader, normal_shader_handle_);

        Tgfx2MeshBinding bind = wrap_mesh_as_tgfx2(device, mesh);
        if (bind.index_count == 0) continue;

        NormalPushStd140 push{};
        std::memcpy(push.u_model, model.data, sizeof(float) * 16);
        ctx.ctx2->set_push_constants(&push, sizeof(push));

        if (override_is_base) {
            ctx.ctx2->set_vertex_layout(
                filter_vertex_layout_to_locations(bind.layout, {0, 1}));
            ctx.ctx2->set_topology(bind.topology);
            ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                           bind.index_count, bind.index_type);
        } else {
            // Skinning variant: compile via bridge, bind, rely on
            // SkinnedMeshRenderer to upload BoneBlock UBO.
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
            ctx.ctx2->set_vertex_layout(
                filter_vertex_layout_to_locations(bind.layout, {0, 1, 6, 7}));
            ctx.ctx2->set_topology(bind.topology);

            drawable->upload_per_draw_uniforms_tgfx2(*ctx.ctx2, dc.geometry_id);

            ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                           bind.index_count, bind.index_type);

            ctx.ctx2->bind_shader(normal_vs2, normal_fs2);
        }

        release_mesh_binding(device, bind);
    }

    ctx.ctx2->end_pass();
    // color_tex2/depth_tex2 are persistent FBOPool wrappers — do not destroy.
}

void NormalPass::execute(ExecuteContext& ctx) {
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

    if (!ctx.ctx2) {
        tc::Log::error("[NormalPass] ctx.ctx2 is null — NormalPass is tgfx2-only");
        return;
    }

    execute_with_data_tgfx2(
        ctx,
        rect,
        scene,
        view,
        projection,
        ctx.layer_mask
    );
}

TC_REGISTER_FRAME_PASS_DERIVED(NormalPass, GeometryPassBase);

} // namespace termin
