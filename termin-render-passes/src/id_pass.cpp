#include <tcbase/tc_log.hpp>
#include <tgfx/tgfx_shader_handle.hpp>

#include <termin/render/id_pass.hpp>
#include "termin/render/camera_capability.hpp"
#include "termin/render/frame_graph_debugger_core.hpp"
#include "termin/render/material_pipeline.hpp"
#include "termin/render/render_item_submission.hpp"
#include "termin/render/tgfx2_bridge.hpp"

#include "tgfx2/builtin_shader_sources.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

#include <array>
#include <cstdint>
#include <cstring>
#include <set>
#include <string>

extern "C" {
#include "tc_picking.h"
}

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

MaterialFragmentInterface id_world_position_interface()
{
    MaterialFragmentInterface interface;
    interface.semantics.push_back(
        {"world_pos", MaterialPipelineValueType::Float3});
    return interface;
}

VertexOutputAdapter id_vertex_output_adapter()
{
    VertexOutputAdapter adapter;
    adapter.debug_name = "id_clip_output";
    adapter.source_module = {
        "termin_id_vertex_output_adapter",
        "builtin_shaders/termin_id_vertex_output_adapter.slang"};
    adapter.output_type_name = "VertexOutput";
    adapter.output_function = "termin_id_vertex_output";
    adapter.consumed_world_semantics = id_world_position_interface();
    adapter.produced_output_semantics.semantics.push_back(
        {"clip_position", MaterialPipelineValueType::Float4});
    adapter.resources = material_pipeline_pass_vertex_resources("id_draw", 80u);
    return adapter;
}

MaterialPipelinePassContract id_material_pass_contract()
{
    MaterialPipelinePassContract contract;
    contract.debug_name = "id";
    contract.required_material_fragment_input = MaterialFragmentInterface{};
    contract.uses_material_fragment = true;
    contract.vertex_output_adapter = id_vertex_output_adapter();
    contract.static_vertex_transform =
        material_pipeline_make_static_mesh_vertex_transform_provider(
            "static_id",
            MeshVertexTransformProfile::Position,
            "id_draw.model");
    contract.skinned_vertex_transform =
        material_pipeline_make_skinned_mesh_vertex_transform_provider(
            "skinned_id",
            MeshVertexTransformProfile::Position,
            "id_draw.model");
    contract.foliage_vertex_transform =
        material_pipeline_make_foliage_vertex_transform_provider(
            "foliage_id", MeshVertexTransformProfile::Position);
    return contract;
}

} // anonymous namespace

MaterialPipelinePassContract IdPass::shader_pass_contract() const {
    return id_material_pass_contract();
}

tc_shader_handle IdPass::shader_usage_base_shader() const {
    if (tc_shader_handle_is_invalid(id_shader_handle_)) {
        id_shader_handle_ = tgfx::register_builtin_shader_from_catalog(ID_ENGINE_SHADER_UUID);
    }
    return id_shader_handle_;
}

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
// write for occlusion. Mesh-backed drawables are collected by GeometryPassBase
// and submitted through RenderItems.
void IdPass::execute_with_data_tgfx2(
    ExecuteContext& ctx,
    const Rect2i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    const Vec3& camera_position,
    uint64_t layer_mask,
    uint64_t render_category_mask
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

    RenderSceneItemSnapshot* snapshot = ensure_render_item_snapshot(ctx, "IdPass");
    if (!snapshot) {
        return;
    }
    collect_draw_calls(
        scene,
        layer_mask,
        render_category_mask,
        id_shader_handle_,
        *snapshot);
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
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
    std::array<MaterialPipelineUniformUpload, 1> per_frame_uniforms{{
        {
            tc_shader_find_resource_binding(id_shader.shader, "per_frame"),
            &per_frame,
            static_cast<uint32_t>(sizeof(per_frame)),
        },
    }};
    MaterialPipelineResourceView id_resources{};
    id_resources.uniforms = per_frame_uniforms.data();
    id_resources.uniform_count = static_cast<uint32_t>(per_frame_uniforms.size());
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

    auto draw_item = [&](const DrawCall& dc) {
        const tc_render_item& item = dc.item;
        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        if (dc.pick_id != current_pick_id) {
            current_pick_id = dc.pick_id;
            id_to_rgb(dc.pick_id, pick_r, pick_g, pick_b);
        }

        IdPushStd140 push{};
        if (item.flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) {
            std::memcpy(push.u_model, item.model_matrix, sizeof(float) * 16);
        } else {
            Mat44f identity = Mat44f::identity();
            std::memcpy(push.u_model, identity.data, sizeof(float) * 16);
        }
        push.u_pickColor[0] = pick_r;
        push.u_pickColor[1] = pick_g;
        push.u_pickColor[2] = pick_b;
        push.u_pickColor[3] = 1.0f;

        std::array<RenderItemNamedUniformBinding, 2> base_draw_uniforms{{
            {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
            {"id_draw", &push, static_cast<uint32_t>(sizeof(push))},
        }};

        MaterialPipelineResourceView draw_material_resources{};
        RenderItemResourceBinding resource_binding{};
        resource_binding.material_resources = &draw_material_resources;
        resource_binding.named_uniforms = base_draw_uniforms.data();
        resource_binding.named_uniform_count = static_cast<uint32_t>(base_draw_uniforms.size());

        RenderContext draw_context;
        draw_context.view = view;
        draw_context.projection = projection;
        std::memcpy(draw_context.model.data, push.u_model, sizeof(push.u_model));
        draw_context.phase = TC_PHASE_ID;
        draw_context.pass_contract = shader_pass_contract();
        draw_context.current_tc_shader = dc.final_shader;
        draw_context.layer_mask = layer_mask;
        draw_context.render_category_mask = render_category_mask;
        draw_context.camera_position = camera_position;
        draw_context.viewport_width = rect.width;
        draw_context.viewport_height = rect.height;
        draw_context.has_override_color = true;
        draw_context.override_color = Vec4{pick_r, pick_g, pick_b, 1.0};

        RenderItemDrawSubmitRequest encode_request{};
        encode_request.shader_handle = dc.final_shader.handle;
        encode_request.device = &device;
        encode_request.mesh_vertex_input = MaterialMeshVertexInput::Position;
        encode_request.draw_context = &draw_context;
        encode_request.resources = &resource_binding;
        encode_request.debug_pass_name = "IdPass";
        encode_request.debug_entity_name = name;
        const bool submitted = submit_render_item_draw(
            *ctx.ctx2,
            item,
            encode_request);
        restore_id_raster_state();
        if (!submitted) {
            return;
        }
        capture_debug_symbol(name);
        restore_id_raster_state();
    };

    for (const DrawCall& dc : cached_draw_calls_) {
        draw_item(dc);
    }

    ctx.ctx2->end_pass();
    // color_tex2/depth_tex2 are persistent FBOPool wrappers — do not destroy.
}

void IdPass::execute(ExecuteContext& ctx) {
    tc_scene_handle scene = ctx.scene.handle();
    const RenderCamera* camera = ctx.camera;
    Rect2i rect = ctx.render_rect;
    RenderCameraSnapshot named_camera_snapshot;
    uint64_t camera_layer_mask = ctx.layer_mask;
    uint64_t camera_render_category_mask = ctx.render_category_mask;

    if (!camera_name.empty()) {
        if (!resolve_named_render_camera_for_pass(
                scene, camera_name.c_str(), 0.0, "IdPass", named_camera_snapshot)) {
            return;
        }
        camera = &named_camera_snapshot.camera;
        camera_layer_mask = named_camera_snapshot.layer_mask;
        camera_render_category_mask = named_camera_snapshot.render_category_mask;
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
                rect = Rect2i(0, 0, w, h);
                if (!camera_name.empty()) {
                    if (!resolve_named_render_camera_for_pass(
                            scene,
                            camera_name.c_str(),
                            static_cast<double>(w) / std::max(1, h),
                            "IdPass",
                            named_camera_snapshot)) {
                        return;
                    }
                    camera = &named_camera_snapshot.camera;
                    camera_layer_mask = named_camera_snapshot.layer_mask;
                    camera_render_category_mask = named_camera_snapshot.render_category_mask;
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
        camera->get_position(),
        camera_layer_mask,
        camera_render_category_mask
    );
}

void IdPass::register_type() {
    auto descriptor = FramePassTypeDescriptorBuilder::native<IdPass>(
        "IdPass", "termin-render-passes", "GeometryPassBase");
    (void)descriptor.commit();
}

} // namespace termin
