#include <termin/render/normal_pass.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/camera/render_camera_utils.hpp>
#include <termin/render/material_pipeline.hpp>
#include <termin/render/tgfx2_bridge.hpp>

#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

#include <tgfx/resources/tc_shader_registry.h>
#include <core/tc_drawable_protocol.h>

#include <tcbase/tc_log.hpp>

#include <array>
#include <cstdlib>
#include <cstring>
#include <optional>
#include <span>

namespace termin {

constexpr const char* NORMAL_ENGINE_SHADER_UUID = "termin-engine-normal";

namespace {

// PerFrame UBO (binding 0): view + projection. 128 bytes std140.
struct NormalPerFrameStd140 {
    float u_view[16];
    float u_projection[16];
};
static_assert(sizeof(NormalPerFrameStd140) == 128,
              "NormalPerFrameStd140 must be 2 * mat4");

// Draw-scope per-object model matrix. The shader resource layout maps it to
// backend storage; render code binds it by reflected resource name.
struct NormalDrawStd140 {
    float u_model[16];
};
static_assert(sizeof(NormalDrawStd140) == 64,
              "NormalDrawStd140 must be exactly one mat4");

MaterialPipelinePassContract normal_material_pass_contract()
{
    MaterialPipelinePassContract contract;
    contract.debug_name = "normal";
    contract.required_material_fragment_input = MaterialFragmentInterface{};
    contract.uses_material_fragment = true;

    MaterialFragmentInterface fragment_input =
        material_pipeline_standard_material_fragment_interface();
    contract.static_vertex_transform =
        material_pipeline_make_static_vertex_transform_contract(
            "static_normal",
            material_pipeline_position_normal_mesh_input(),
            fragment_input,
            material_pipeline_common_vertex_resources("normal_draw"));
    contract.skinned_vertex_transform =
        material_pipeline_make_skinned_vertex_transform_contract(
            *contract.static_vertex_transform,
            "skinned_normal",
            "termin-engine-skinned-normal",
            material_pipeline_skinned_position_normal_mesh_input());
    return contract;
}

} // anonymous namespace

MaterialPipelinePassContract NormalPass::shader_pass_contract() const {
    return normal_material_pass_contract();
}

tc_shader_handle NormalPass::shader_usage_base_shader() const {
    if (tc_shader_handle_is_invalid(normal_shader_handle_)) {
        normal_shader_handle_ =
            tgfx::register_builtin_shader_from_catalog(NORMAL_ENGINE_SHADER_UUID);
    }
    return normal_shader_handle_;
}

void NormalPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;

    if (tc_shader_handle_is_invalid(normal_shader_handle_)) {
        normal_shader_handle_ =
            tgfx::register_builtin_shader_from_catalog(NORMAL_ENGINE_SHADER_UUID);
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
    collect_draw_calls(scene, layer_mask, ctx.render_category_mask, normal_shader_handle_);
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

    MaterialPipelineShaderBinding normal_shader{};
    if (!ensure_material_pipeline_shader(
            *ctx.ctx2,
            device,
            normal_shader_handle_,
            "NormalPass",
            normal_shader)) {
        return;
    }

    NormalPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
    std::array<MaterialPipelineUniformData, 1> per_frame_uniforms{{
        {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
    }};
    MaterialPipelineResourceContext normal_resources{};
    normal_resources.uniforms = per_frame_uniforms;
    prepare_material_pipeline_resources(
        *ctx.ctx2,
        device,
        normal_shader.shader,
        nullptr,
        normal_resources);

    const std::string& debug_symbol = get_debug_internal_point();

    for (const auto& dc : cached_draw_calls_) {
        Drawable* drawable = nullptr;
        if (tc_component_get_drawable_vtable(dc.component) == &Drawable::cxx_drawable_vtable()) {
            drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        }
        if (!drawable) continue;

        MeshDrawGeometry mesh_geometry{};
        if (!drawable->resolve_mesh_geometry(phase_mark(), dc.geometry_id, mesh_geometry)) {
            continue;  // non-mesh drawables skipped
        }

        Mat44f model = drawable->get_model_matrix(dc.entity);

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        bool override_is_base =
            tc_shader_handle_eq(dc.final_shader, normal_shader_handle_);
        tc_material_phase* material_phase = dc.resolve_material_phase();

        NormalDrawStd140 draw{};
        std::memcpy(draw.u_model, model.data, sizeof(float) * 16);
        std::array<MaterialPipelineUniformData, 2> draw_uniforms{{
            {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
            {"normal_draw", &draw, static_cast<uint32_t>(sizeof(draw))},
        }};
        MaterialPipelineResourceContext draw_resources{};
        draw_resources.uniforms = draw_uniforms;

        if (override_is_base) {
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                normal_shader.shader,
                nullptr,
                draw_resources);
            draw_material_pipeline_submesh(
                *ctx.ctx2,
                mesh_geometry.mesh,
                mesh_geometry.submesh_index,
                material_mesh_vertex_input_for_shader(
                    normal_shader.shader,
                    MaterialMeshVertexInput::PositionNormal));
        } else {
            // Non-base shader: compile via bridge, bind reflected resources,
            // and let the drawable upload optional per-draw data such as BoneBlock.
            MaterialPipelineShaderBinding skinned_shader{};
            if (!ensure_material_pipeline_shader(
                    *ctx.ctx2,
                    device,
                    dc.final_shader,
                    "NormalPass/skinned",
                    skinned_shader)) {
                continue;
            }
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                skinned_shader.shader,
                material_phase,
                draw_resources);

            drawable->upload_per_draw_uniforms_tgfx2(*ctx.ctx2, dc.geometry_id);

            draw_material_pipeline_submesh(
                *ctx.ctx2,
                mesh_geometry.mesh,
                mesh_geometry.submesh_index,
                material_mesh_vertex_input_for_shader(
                    skinned_shader.shader,
                    MaterialMeshVertexInput::PositionNormal));

            ctx.ctx2->bind_shader(normal_shader.vertex, normal_shader.fragment);
            ctx.ctx2->use_shader_resource_layout(normal_shader.shader);
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                normal_shader.shader,
                nullptr,
                normal_resources);
        }
    }

    ctx.ctx2->end_pass();
    // color_tex2/depth_tex2 are persistent FBOPool wrappers — do not destroy.
}

void NormalPass::execute(ExecuteContext& ctx) {
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
