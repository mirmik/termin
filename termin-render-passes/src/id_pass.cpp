#include <tcbase/tc_log.hpp>
#include <tgfx/tgfx_shader_handle.hpp>

#include <termin/render/id_pass.hpp>
#include "termin/camera/render_camera_utils.hpp"
#include "termin/render/frame_graph_debugger_core.hpp"
#include "termin/render/material_pipeline.hpp"
#include "termin/render/tgfx2_bridge.hpp"

#include "tgfx2/builtin_shader_sources.hpp"
#include "tgfx2/clip_space.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

#include <cstdlib>
#include <array>
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

constexpr const char* ID_ENGINE_SHADER_UUID = "termin-engine-id";

namespace {

// PerFrame UBO (binding 0): view + projection. 128 bytes std140.
struct IdPerFrameStd140 {
    float u_view[16];
    float u_projection[16];
};
static_assert(sizeof(IdPerFrameStd140) == 128,
              "IdPerFrameStd140 must be 2 * mat4");

// Draw-scope per-object model matrix + pick color. The shader resource
// layout maps it to backend storage; render code binds it by reflected name.
// 64 + 16 = 80 bytes. vec4 used for pickColor because std140 pads
// vec3 to 16-byte alignment anyway.
struct IdPushStd140 {
    float u_model[16];
    float u_pickColor[4];  // vec3 + pad
};
static_assert(sizeof(IdPushStd140) == 80,
              "IdPushStd140 must be mat4 + vec4");

} // anonymous namespace

void IdPass::id_to_rgb(int id, float& r, float& g, float& b) {
    tc_picking_id_to_rgb_float(id, &r, &g, &b);
}

void IdPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;

    // Engine-shader cache via TcShader registry (see ShadowPass for the
    // rationale): hash-based dedup keeps the same handle across pass
    // re-creations, and the render device cache keeps compiled shader
    // modules live for zero-compile subsequent binds.
    if (tc_shader_handle_is_invalid(id_shader_handle_)) {
        id_shader_handle_ = tgfx::register_builtin_shader_from_catalog(ID_ENGINE_SHADER_UUID);
    }

}

void IdPass::release_tgfx2_resources() {
    if (!device2_) return;
    // id_shader_handle_ is static engine shader — not released here.
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
    const Vec3& camera_position,
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
    const Mat44f backend_projection = tgfx::adapt_projection_for_backend(
        device.backend_type(),
        projection);

    ensure_tgfx2_resources(device);

    // Use the UBO-based engine shader as base_shader for skinning override
    // (see DepthPass / ShadowPass for rationale).
    collect_draw_calls(scene, layer_mask, id_shader_handle_);
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

    MaterialPipelineShaderBinding id_shader{};
    if (!ensure_material_pipeline_shader(
            *ctx.ctx2,
            device,
            id_shader_handle_,
            "IdPass",
            id_shader)) {
        return;
    }

    // PerFrame UBO: view + projection, one write per pass via the ring.
    IdPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, backend_projection.data, sizeof(float) * 16);
    std::array<MaterialPipelineUniformData, 1> per_frame_uniforms{{
        {"u_per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
    }};
    MaterialPipelineResourceContext id_resources{};
    id_resources.uniforms = per_frame_uniforms;
    prepare_material_pipeline_resources(
        *ctx.ctx2,
        device,
        id_shader.shader,
        nullptr,
        id_resources);

    auto restore_id_raster_state = [&]() {
        ctx.ctx2->set_depth_test(true);
        ctx.ctx2->set_depth_write(true);
        ctx.ctx2->set_blend(false);
        ctx.ctx2->set_cull(tgfx::CullMode::Back);
        ctx.ctx2->bind_shader(id_shader.vertex, id_shader.fragment);
        ctx.ctx2->use_shader_resource_layout(id_shader.shader);
    };

    const std::string& debug_symbol = get_debug_internal_point();
    int current_pick_id = -1;
    float pick_r = 0.0f;
    float pick_g = 0.0f;
    float pick_b = 0.0f;

    auto capture_debug_symbol = [&](const char* entity_name) {
        if (debug_symbol.empty() || !entity_name || debug_symbol != entity_name) {
            return;
        }
        FrameGraphCapture* capture = debug_capture();
        if (!capture) {
            return;
        }

        ctx.ctx2->end_pass();
        capture->capture_direct_via_ctx2(ctx.ctx2, color_tex2, rect.width, rect.height);
        ctx.ctx2->begin_pass(color_tex2, depth_tex2, nullptr, 1.0f, false);
        ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
        restore_id_raster_state();
        ctx.ctx2->clear_resource_bindings();
        prepare_material_pipeline_resources(
            *ctx.ctx2,
            device,
            id_shader.shader,
            nullptr,
            id_resources);
    };

    for (const auto& dc : cached_draw_calls_) {
        Drawable* drawable = nullptr;
        if (tc_component_get_drawable_vtable(dc.component) == &Drawable::cxx_drawable_vtable()) {
            drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        }
        if (!drawable) continue;

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        if (dc.pick_id != current_pick_id) {
            current_pick_id = dc.pick_id;
            id_to_rgb(dc.pick_id, pick_r, pick_g, pick_b);
        }

        tc_mesh* mesh = drawable->get_mesh_for_phase(phase_name(), dc.geometry_id);
        if (!mesh) {
            if (!drawable->supports_direct_tgfx2_draw(
                    phase_name(), dc.geometry_id, DirectTgfx2DrawKind::OverrideColor)) {
                continue;
            }

            RenderContext direct_context;
            direct_context.view = view;
            direct_context.projection = backend_projection;
            direct_context.model = drawable->get_model_matrix(dc.entity);
            direct_context.phase = phase_name();
            direct_context.current_tc_shader = TcShader(dc.final_shader);
            direct_context.layer_mask = layer_mask;
            direct_context.camera_position = camera_position;
            direct_context.viewport_width = rect.width;
            direct_context.viewport_height = rect.height;
            direct_context.has_override_color = true;
            direct_context.override_color = Vec4{pick_r, pick_g, pick_b, 1.0};

            drawable->draw_tgfx2(*ctx.ctx2, direct_context, phase_name(), nullptr, dc.geometry_id);
            capture_debug_symbol(name);
            restore_id_raster_state();
            ctx.ctx2->clear_resource_bindings();
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                id_shader.shader,
                nullptr,
                id_resources);
            continue;
        }

        Mat44f model = drawable->get_model_matrix(dc.entity);

        bool override_is_base =
            tc_shader_handle_eq(dc.final_shader, id_shader_handle_);

        // Push constants (u_model + u_pickColor) are shared between the
        // base and skinned paths. The skinned variant uses the same id
        // draw contract plus a reflected BoneBlock resource.
        IdPushStd140 push{};
        std::memcpy(push.u_model, model.data, sizeof(float) * 16);
        push.u_pickColor[0] = pick_r;
        push.u_pickColor[1] = pick_g;
        push.u_pickColor[2] = pick_b;
        push.u_pickColor[3] = 1.0f;

        std::array<MaterialPipelineUniformData, 2> draw_uniforms{{
            {"u_per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
            {"u_push", &push, static_cast<uint32_t>(sizeof(push))},
        }};
        MaterialPipelineResourceContext draw_resources{};
        draw_resources.uniforms = draw_uniforms;

        if (override_is_base) {
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                id_shader.shader,
                nullptr,
                draw_resources);
            draw_material_pipeline_mesh(
                *ctx.ctx2,
                mesh,
                material_mesh_vertex_input_for_shader(
                    id_shader.shader,
                    MaterialMeshVertexInput::Position));
            capture_debug_symbol(name);
        } else {
            MaterialPipelineShaderBinding skinned_shader{};
            if (!ensure_material_pipeline_shader(
                    *ctx.ctx2,
                    device,
                    dc.final_shader,
                    "IdPass/skinned",
                    skinned_shader)) {
                continue;
            }
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                skinned_shader.shader,
                nullptr,
                draw_resources);

            drawable->upload_per_draw_uniforms_tgfx2(*ctx.ctx2, dc.geometry_id);

            draw_material_pipeline_mesh(
                *ctx.ctx2,
                mesh,
                material_mesh_vertex_input_for_shader(
                    skinned_shader.shader,
                    MaterialMeshVertexInput::Position));
            capture_debug_symbol(name);

            ctx.ctx2->bind_shader(id_shader.vertex, id_shader.fragment);
            ctx.ctx2->use_shader_resource_layout(id_shader.shader);
            ctx.ctx2->clear_resource_bindings();
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                id_shader.shader,
                nullptr,
                draw_resources);
        }
    }

    ctx.ctx2->end_pass();
    // color_tex2/depth_tex2 are persistent FBOPool wrappers — do not destroy.
}

void IdPass::execute(ExecuteContext& ctx) {
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

    // Override rect with output texture size (may differ from ctx.render_rect if
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
    Vec3 camera_position = camera->get_position();

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
        camera_position,
        ctx.layer_mask
    );
}

TC_REGISTER_FRAME_PASS_DERIVED(IdPass, GeometryPassBase);

} // namespace termin
