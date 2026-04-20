#include <tcbase/tc_log.hpp>
#include <tgfx/tgfx_shader_handle.hpp>

#include "termin/render/id_pass.hpp"
#include "termin/camera/render_camera_utils.hpp"
#include "termin/render/tgfx2_bridge.hpp"

#include "tgfx2/render_context.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

#include <cstdlib>
#include <cstring>
#include <optional>
#include <span>

extern "C" {
#include "tc_picking.h"
#include <tgfx/resources/tc_shader_registry.h>
#include "core/tc_drawable_protocol.h"
}

#include <termin/camera/camera_component.hpp>

namespace termin {

namespace {

// PerFrame UBO (binding 0): view + projection. 128 bytes std140.
struct IdPerFrameStd140 {
    float u_view[16];
    float u_projection[16];
};
static_assert(sizeof(IdPerFrameStd140) == 128,
              "IdPerFrameStd140 must be 2 * mat4");

// PushConstants (binding 14): per-object model matrix + pick color.
// 64 + 16 = 80 bytes. vec4 used for pickColor because std140 pads
// vec3 to 16-byte alignment anyway.
struct IdPushStd140 {
    float u_model[16];
    float u_pickColor[4];  // vec3 + pad
};
static_assert(sizeof(IdPushStd140) == 80,
              "IdPushStd140 must be mat4 + vec4");
static_assert(sizeof(IdPushStd140) <= 128,
              "IdPushStd140 must fit within Vulkan min push constant size");

// PerFrame UBO at binding 0 (view+proj, uploaded once per pass).
// Per-draw data (model + pickColor, 80 bytes) rides on push_constants in
// Vulkan; under GL the same bytes land in the std140 emulation UBO at
// binding 14 managed by tgfx2's ring buffer.
constexpr const char* ID_PASS_VERT_UBO = R"(#version 450 core
layout(location=0) in vec3 a_position;
layout(location=1) in vec3 a_normal;
layout(location=2) in vec2 a_texcoord;

layout(std140, binding = 0) uniform PerFrame {
    mat4 u_view;
    mat4 u_projection;
};

struct IdPushData {
    mat4 u_model;
    vec4 u_pickColor;  // w ignored
};
#ifdef VULKAN
layout(push_constant) uniform IdPushBlock { IdPushData pc; };
#else
layout(std140, binding = 14) uniform IdPushBlock { IdPushData pc; };
#endif

void main() {
    gl_Position = u_projection * u_view * pc.u_model * vec4(a_position, 1.0);
}
)";

constexpr const char* ID_PASS_FRAG_UBO = R"(#version 450 core
struct IdPushData {
    mat4 u_model;
    vec4 u_pickColor;
};
#ifdef VULKAN
layout(push_constant) uniform IdPushBlock { IdPushData pc; };
#else
layout(std140, binding = 14) uniform IdPushBlock { IdPushData pc; };
#endif

layout(location=0) out vec4 fragColor;

void main() {
    fragColor = vec4(pc.u_pickColor.rgb, 1.0);
}
)";

// ID_PASS_VERT / ID_PASS_FRAG — referenced via vertex_shader_source() /
// fragment_shader_source() for legacy override keying (GeometryPassBase
// uses the source pointer as a registry key). Never actually compiled
// on the tgfx2 path — kept here so the sentinel values stay stable.
constexpr const char* ID_PASS_VERT = R"(#version 450 core
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

constexpr const char* ID_PASS_FRAG = R"(#version 450 core
uniform vec3 u_pickColor;
layout(location=0) out vec4 fragColor;

void main() {
    fragColor = vec4(u_pickColor, 1.0);
}
)";

} // anonymous namespace

const char* IdPass::vertex_shader_source() const { return ID_PASS_VERT; }
const char* IdPass::fragment_shader_source() const { return ID_PASS_FRAG; }

void IdPass::id_to_rgb(int id, float& r, float& g, float& b) {
    tc_picking_id_to_rgb_float(id, &r, &g, &b);
}

void IdPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;

    // Engine-shader cache via TcShader registry (see ShadowPass for the
    // rationale): hash-based dedup keeps the same handle across pass
    // re-creations, tc_shader_ensure_tgfx2 parks compiled VkShaderModules
    // on the tc_gpu_slot for zero-compile subsequent binds.
    if (tc_shader_handle_is_invalid(id_shader_handle_)) {
        id_shader_handle_ = tc_shader_from_sources(
            ID_PASS_VERT_UBO, ID_PASS_FRAG_UBO,
            nullptr, "IdEngineVSFS", nullptr, nullptr);
    }

    if (!per_frame_ubo_) {
        tgfx::BufferDesc ubo_desc;
        ubo_desc.size = sizeof(IdPerFrameStd140);
        ubo_desc.usage = tgfx::BufferUsage::Uniform | tgfx::BufferUsage::CopyDst;
        per_frame_ubo_ = device.create_buffer(ubo_desc);
    }
}

void IdPass::release_tgfx2_resources() {
    if (!device2_) return;
    // Shader handle lives on the global tc_shader registry and is shared
    // across pass re-creations.
    if (per_frame_ubo_) { device2_->destroy(per_frame_ubo_); per_frame_ubo_ = {}; }
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
    if (!ctx.ctx2) {
        tc::Log::error("IdPass/tgfx2: ctx2 is null");
        return;
    }

    auto color_it = ctx.tex2_writes.find(output_res);
    if (color_it == ctx.tex2_writes.end() || !color_it->second) {
        tc::Log::error("IdPass/tgfx2: missing tgfx2 color texture for '%s'",
                       output_res.c_str());
        return;
    }
    tgfx::TextureHandle color_tex2 = color_it->second;

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};

    auto& device = ctx.ctx2->device();

    ensure_tgfx2_resources(device);

    // Resolve base shader for collect_draw_calls' override keying.
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

    tgfx::ShaderHandle id_vs2, id_fs2;
    {
        tc_shader* raw = tc_shader_get(id_shader_handle_);
        if (!raw || !tc_shader_ensure_tgfx2(raw, &device, &id_vs2, &id_fs2)) {
            tc::Log::error("IdPass: tc_shader_ensure_tgfx2 failed for engine id shader");
            return;
        }
    }
    ctx.ctx2->bind_shader(id_vs2, id_fs2);

    // PerFrame UBO: view + projection, uploaded once.
    IdPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
    ctx.ctx2->device().upload_buffer(
        per_frame_ubo_,
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(&per_frame),
            sizeof(per_frame)));
    ctx.ctx2->bind_uniform_buffer(0, per_frame_ubo_);

    const std::string& debug_symbol = get_debug_internal_point();
    int current_pick_id = -1;
    float pick_r = 0.0f;
    float pick_g = 0.0f;
    float pick_b = 0.0f;

    for (const auto& dc : cached_draw_calls_) {
        Drawable* drawable = nullptr;
        if (tc_component_get_drawable_vtable(dc.component) == &Drawable::cxx_drawable_vtable()) {
            drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        }
        if (!drawable) continue;

        tc_mesh* mesh = drawable->get_mesh_for_phase(phase_name(), dc.geometry_id);
        if (!mesh) continue;  // non-mesh drawables not pickable here

        Mat44f model = drawable->get_model_matrix(dc.entity);

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        if (dc.pick_id != current_pick_id) {
            current_pick_id = dc.pick_id;
            id_to_rgb(dc.pick_id, pick_r, pick_g, pick_b);
        }

        bool override_is_base = tc_shader_handle_eq(dc.final_shader, base_shader.handle);

        Tgfx2MeshBinding bind = wrap_mesh_as_tgfx2(device, mesh);
        if (bind.index_count == 0) continue;

        if (override_is_base) {
            // Fast path: push constants for model + pick color (80 B).
            IdPushStd140 push{};
            std::memcpy(push.u_model, model.data, sizeof(float) * 16);
            push.u_pickColor[0] = pick_r;
            push.u_pickColor[1] = pick_g;
            push.u_pickColor[2] = pick_b;
            push.u_pickColor[3] = 1.0f;
            ctx.ctx2->set_push_constants(&push, sizeof(push));

            // The base id VS only reads a_position (loc 0). shaderc strips
            // declared-but-unused a_normal / a_texcoord, so the SPIR-V
            // inputs are a_position only — trim the pipeline's vertex
            // layout to match, otherwise Vulkan logs performance warnings
            // about loc 1/2/3 for every pipeline variant.
            ctx.ctx2->set_vertex_layout(
                filter_vertex_layout_to_locations(bind.layout, {0}));
            ctx.ctx2->set_topology(bind.topology);
            ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                           bind.index_count, bind.index_type);
        } else {
            // Shader override (skinning): compile via bridge, upload
            // u_model/u_view/u_projection + u_pickColor through ctx2's
            // transitional plain-uniform helpers, draw, then re-bind
            // the base id shader for the next iteration.
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
            ctx.ctx2->set_uniform_vec3("u_pickColor",  pick_r, pick_g, pick_b);

            drawable->upload_per_draw_uniforms_tgfx2(*ctx.ctx2, dc.geometry_id);

            ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                           bind.index_count, bind.index_type);

            ctx.ctx2->bind_shader(id_vs2, id_fs2);
        }

        release_mesh_binding(device, bind);
    }

    ctx.ctx2->end_pass();
    // color_tex2/depth_tex2 are persistent FBOPool wrappers — do not destroy.
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

    // Override rect with output texture size (may differ from ctx.rect if
    // the pipeline routes to a non-default-sized target).
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
        tc::Log::error("[IdPass] ctx.ctx2 is null — IdPass is tgfx2-only");
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

TC_REGISTER_FRAME_PASS_DERIVED(IdPass, GeometryPassBase);

} // namespace termin
