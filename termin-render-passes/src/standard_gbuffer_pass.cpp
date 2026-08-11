#include <termin/render/standard_gbuffer_pass.hpp>

#include <algorithm>
#include <array>
#include <cstring>
#include <vector>

#include <tcbase/tc_log.hpp>

#include <termin/render/camera_capability.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/frame_uniforms.hpp>
#include <termin/render/material_pipeline.hpp>
#include <termin/render/render_item_submission.hpp>
#include <termin/render/render_scene_item_collector.hpp>
#include <termin/render/render_task.hpp>
#include <termin/render/scene_render_services.hpp>
#include <termin/render/tgfx2_bridge.hpp>

#include <tgfx/resources/tc_material.h>
#include <tgfx/resources/tc_shader.h>
#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>

extern "C" {
#include <core/tc_component.h>
#include <core/tc_drawable_protocol.h>
#include <core/tc_scene_drawable.h>
}

#include <termin/entity/entity.hpp>

namespace termin {
    namespace {

        constexpr const char* STANDARD_GBUFFER_CONSUMER = R"slang(
struct TerminStandardGBufferOutput {
    float4 base_ao : SV_Target0;
    float4 normal_rough : SV_Target1;
    float4 metal_emit : SV_Target2;
};

[shader("fragment")]
TerminStandardGBufferOutput termin_standard_gbuffer_fs(FragmentInput input) {
    TerminStandardSurfaceV1 surface = evaluate_standard_surface(input);
    TerminStandardGBufferOutput output;
    output.base_ao = float4(surface.base_color, saturate(surface.occlusion));
    output.normal_rough = float4(
        normalize(surface.normal_world),
        saturate(surface.perceptual_roughness));
    output.metal_emit = float4(saturate(surface.metallic), surface.emission);
    return output;
}
)slang";

        constexpr const char* OPAQUE_PHASE = "opaque";

        struct GBufferDrawData {
            float u_model[16];
        };

        struct GBufferTaskExtension final : RenderTaskExtension {
            GBufferDrawData draw_data{};
        };

        tc_material_phase* resolve_material_phase(const tc_render_item& item) {
            if (!tc_material_handle_is_invalid(item.material) && item.material_phase_index != SIZE_MAX) {
                tc_material* material = tc_material_get(item.material);
                if (material && item.material_phase_index < material->phase_count) {
                    return &material->phases[item.material_phase_index];
                }
            }
            return item.material_phase;
        }

        RenderItemTaskPlanningContract gbuffer_task_contract(tc_phase_mask phase,
                                                             const MaterialPipelinePassContract& shader_contract,
                                                             const char* pass_name) {
            RenderItemTaskPlanningContract contract{};
            contract.phase = phase;
            contract.material_phase_policy = RenderItemMaterialPhasePolicy::Required;
            contract.provided_input_mask = render_item_task_input_bit(RenderItemTaskInput::DrawContext);
            contract.required_input_mask = render_item_task_input_bit(RenderItemTaskInput::DrawContext);
            contract.accepted_vertex_transform_kind_mask =
                render_item_vertex_transform_kind_bit(VertexTransformKind::StaticMesh) |
                render_item_vertex_transform_kind_bit(VertexTransformKind::SkinnedMesh) |
                render_item_vertex_transform_kind_bit(VertexTransformKind::Foliage);
            contract.shader_contract = &shader_contract;
            contract.debug_pass_name = pass_name;
            return contract;
        }

        bool standard_gbuffer_routes_shader(const MaterialPipelinePassContract& contract,
                                            tc_shader_handle shader_handle) {
            return material_pipeline_pass_accepts_shader(contract, TcShader(shader_handle));
        }

        struct UsageCollectionData {
            tc_phase_mask phase = TC_PHASE_NONE;
            MaterialPipelinePassContract pass_contract;
            const std::function<void(TcShader)>* emit = nullptr;
        };

        bool collect_gbuffer_shader_usages(tc_component* component, void* user_data) {
            auto* data = static_cast<UsageCollectionData*>(user_data);
            if (!component || !data || !data->emit) {
                tc::Log::error("[StandardGBufferPass] shader usage callback received invalid data");
                return true;
            }
            if (!tc_phase_mask_contains(tc_component_phase_mask(component), data->phase)) {
                return true;
            }

            tc_render_item_collect_context collect_context{};
            collect_context.phase = data->phase;
            collect_context.layer_mask = UINT64_MAX;
            collect_context.render_category_mask = UINT64_MAX;
            collect_context.debug_pass_name = "StandardGBufferPass/ShaderUsage";
            collect_context.pass_contract = &data->pass_contract;

            RenderItemCollection items;
            if (!collect_drawable_render_items(component, collect_context, items)) {
                return true;
            }

            const RenderItemTaskPlanningContract task_contract =
                gbuffer_task_contract(data->phase, data->pass_contract, "StandardGBufferPass/ShaderUsage");
            for (const tc_render_item& item : items.items) {
                tc_material_phase* phase = resolve_material_phase(item);
                if (!phase || !standard_gbuffer_routes_shader(data->pass_contract, phase->shader)) {
                    continue;
                }
                RenderTaskList tasks;
                RenderItemTaskPlanningRequest request{};
                request.item = &item;
                request.material_phase = phase;
                request.candidate_shader = phase->shader;
                request.contract = &task_contract;
                if (!plan_render_item_task(request, tasks).accepted()) {
                    continue;
                }
                for (const RenderTask& task : tasks) {
                    for (uint32_t index = 0; index < task.shader_usage_count; ++index) {
                        tc_shader* shader = tc_shader_get(task.shader_usages[index]);
                        if (tc_shader_is_executable(shader)) {
                            (*data->emit)(TcShader(task.shader_usages[index]));
                        }
                    }
                }
            }
            return true;
        }

    } // namespace

    MaterialPipelinePassContract standard_gbuffer_material_pass_contract() {
        MaterialPipelinePassContract contract;
        contract.debug_name = "standard_gbuffer";
        contract.allows_authored_vertex_stage = false;
        contract.fragment_composition = MaterialFragmentComposition::SurfaceConsumer;
        contract.vertex_output_adapter = material_pipeline_standard_material_vertex_output_adapter();
        contract.static_vertex_transform = material_pipeline_make_static_mesh_vertex_transform_provider(
            "static", MeshVertexTransformProfile::Material, "draw_data.u_model");
        contract.skinned_vertex_transform = material_pipeline_make_skinned_mesh_vertex_transform_provider(
            "skinned", MeshVertexTransformProfile::Material, "draw_data.u_model");
        contract.static_vertex_transform->resources.push_back(
            material_pipeline_draw_resource_decl("draw_data", TC_SHADER_STAGE_VERTEX, 64u));
        contract.skinned_vertex_transform->resources.push_back(
            material_pipeline_draw_resource_decl("draw_data", TC_SHADER_STAGE_VERTEX, 64u));
        contract.foliage_vertex_transform =
            material_pipeline_make_foliage_material_vertex_transform_provider("foliage");

        MaterialSurfaceConsumerContract consumer;
        consumer.accepted_surface = {
            TC_STANDARD_PBR_SURFACE_CONTRACT_ID,
            TC_STANDARD_PBR_SURFACE_CONTRACT_VERSION,
        };
        consumer.consumer_source = STANDARD_GBUFFER_CONSUMER;
        consumer.fragment_entry = "termin_standard_gbuffer_fs";
        consumer.source_identity = "termin.surface.standard-pbr@1:gbuffer-consumer:v1";
        contract.surface_consumer = std::move(consumer);
        return contract;
    }

    StandardGBufferPass::StandardGBufferPass(const StandardGBufferPassConfig& config)
        : base_ao_res(config.base_ao_res),
          normal_rough_res(config.normal_rough_res),
          metal_emit_res(config.metal_emit_res),
          depth_res(config.depth_res),
          camera_name(config.camera_name) {
        set_pass_name(config.pass_name);
    }

    std::set<const char*> StandardGBufferPass::compute_reads() const {
        return {};
    }

    std::set<const char*> StandardGBufferPass::compute_writes() const {
        return {base_ao_res.c_str(), normal_rough_res.c_str(), metal_emit_res.c_str(), depth_res.c_str()};
    }

    std::vector<ResourceSpec> StandardGBufferPass::get_resource_specs() const {
        ResourceSpec base_ao{base_ao_res, "color_texture"};
        ResourceSpec normal_rough{normal_rough_res, "color_texture"};
        ResourceSpec metal_emit{metal_emit_res, "color_texture"};
        ResourceSpec depth{depth_res, "depth_texture"};
        base_ao.format = "rgba16f";
        normal_rough.format = "rgba16f";
        metal_emit.format = "rgba16f";
        depth.format = "depth32f";
        depth.clear_depth = 1.0f;
        return {std::move(base_ao), std::move(normal_rough), std::move(metal_emit), std::move(depth)};
    }

    void StandardGBufferPass::collect_scene_shader_usages(tc_scene_handle scene,
                                                          const std::function<void(TcShader)>& emit) const {
        if (!emit) {
            return;
        }
        if (!tc_scene_handle_valid(scene)) {
            tc::Log::error("[StandardGBufferPass] cannot collect shader usages for an invalid scene");
            return;
        }
        const tc_phase_mask phase = tc_phase_find(OPAQUE_PHASE);
        if (phase == TC_PHASE_NONE) {
            tc::Log::error("[StandardGBufferPass] opaque phase is not registered");
            return;
        }
        UsageCollectionData data;
        data.phase = phase;
        data.pass_contract = standard_gbuffer_material_pass_contract();
        data.emit = &emit;
        tc_scene_foreach_drawable(scene, collect_gbuffer_shader_usages, &data, TC_SCENE_FILTER_NONE, 0);
    }

    void StandardGBufferPass::execute(ExecuteContext& ctx) {
        if (!ctx.ctx2) {
            tc::Log::error("[StandardGBufferPass] render context is unavailable");
            return;
        }
        const SceneRenderServices* services = require_scene_render_services(ctx, "StandardGBufferPass");
        if (!services) {
            return;
        }
        const RenderItemSnapshot* snapshot = require_render_item_snapshot(ctx, "StandardGBufferPass");
        if (!snapshot) {
            return;
        }

        const tc_phase_mask opaque_phase = tc_phase_find(OPAQUE_PHASE);
        if (opaque_phase == TC_PHASE_NONE) {
            tc::Log::error("[StandardGBufferPass] opaque phase is not registered");
            return;
        }

        const RenderCamera* camera = ctx.view.primary_view();
        RenderCameraSnapshot named_camera_snapshot;
        uint64_t layer_mask = services->layer_mask;
        uint64_t render_category_mask = services->render_category_mask;
        const tc_scene_handle scene = services->scene.handle();
        if (!camera_name.empty()) {
            if (!resolve_named_render_camera_for_pass(
                    scene, camera_name.c_str(), 0.0, "StandardGBufferPass", named_camera_snapshot)) {
                return;
            }
            camera = &named_camera_snapshot.camera;
            layer_mask = named_camera_snapshot.layer_mask;
            render_category_mask = named_camera_snapshot.render_category_mask;
        }
        if (!camera) {
            tc::Log::error("[StandardGBufferPass] no primary or named camera is available");
            return;
        }

        const auto base_output = ctx.tex2_writes.find(base_ao_res);
        if (base_output == ctx.tex2_writes.end() || !base_output->second) {
            tc::Log::error("[StandardGBufferPass] base/AO output '%s' is unavailable", base_ao_res.c_str());
            return;
        }
        const tgfx::TextureDesc base_desc = ctx.ctx2->device().texture_desc(base_output->second);
        Rect2i rect{0, 0, static_cast<int>(base_desc.width), static_cast<int>(base_desc.height)};
        if (rect.width <= 0 || rect.height <= 0) {
            tc::Log::error("[StandardGBufferPass] output extent is invalid");
            return;
        }
        if (!camera_name.empty()) {
            if (!resolve_named_render_camera_for_pass(scene,
                                                      camera_name.c_str(),
                                                      static_cast<double>(rect.width) / rect.height,
                                                      "StandardGBufferPass",
                                                      named_camera_snapshot)) {
                return;
            }
            camera = &named_camera_snapshot.camera;
            layer_mask = named_camera_snapshot.layer_mask;
            render_category_mask = named_camera_snapshot.render_category_mask;
        }

        const Mat44f view = camera->get_view_matrix().to_float();
        const Mat44f projection = camera->get_projection_matrix().to_float();
        const Vec3 camera_position = camera->get_position();
        EnginePerFrameStd140 per_frame = make_engine_per_frame_uniforms(view,
                                                                        projection,
                                                                        camera_position,
                                                                        static_cast<float>(rect.width),
                                                                        static_cast<float>(rect.height),
                                                                        static_cast<float>(camera->near_clip),
                                                                        static_cast<float>(camera->far_clip));

        const MaterialPipelinePassContract shader_contract = standard_gbuffer_material_pass_contract();
        const std::string pass_name = get_pass_name();
        const RenderItemTaskPlanningContract task_contract =
            gbuffer_task_contract(opaque_phase, shader_contract, pass_name.c_str());
        RenderTaskList tasks;
        const std::span<const size_t> routed_items = snapshot->phase_item_indices(opaque_phase);
        tasks.reserve(routed_items.size());

        for (size_t item_index : routed_items) {
            const tc_render_item* item = snapshot->item(item_index);
            if (!item) {
                tc::Log::error("[StandardGBufferPass] snapshot returned no item for index %zu", item_index);
                continue;
            }
            tc_material_phase* phase = resolve_material_phase(*item);
            if (!phase || !standard_gbuffer_routes_shader(shader_contract, phase->shader)) {
                continue;
            }

            RenderItemTaskPlanningRequest request{};
            request.item = item;
            request.item_index = item_index;
            request.source_draw_index = item_index;
            request.material_phase = phase;
            request.candidate_shader = phase->shader;
            request.contract = &task_contract;
            const RenderItemTaskPlanningResult planned = plan_render_item_task(request, tasks);
            if (!planned.accepted()) {
                continue;
            }

            GBufferTaskExtension& extension = tasks.emplace_extension<GBufferTaskExtension>();
            RenderTask& task = tasks.at(planned.task_index);
            task.extension = &extension;
            if ((item->flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) != 0u) {
                std::memcpy(extension.draw_data.u_model, item->model_matrix, sizeof(extension.draw_data.u_model));
            } else {
                const Mat44f identity = Mat44f::identity();
                std::memcpy(extension.draw_data.u_model, identity.data, sizeof(extension.draw_data.u_model));
            }
            std::memcpy(task.draw_context.model.data, extension.draw_data.u_model, sizeof(extension.draw_data.u_model));
            task.draw_context.view = view;
            task.draw_context.projection = projection;
            task.draw_context.phase = opaque_phase;
            task.draw_context.pass_contract = shader_contract;
            task.draw_context.current_tc_shader = TcShader(task.final_shader);
            task.draw_context.layer_mask = layer_mask;
            task.draw_context.render_category_mask = render_category_mask;
            task.draw_context.camera_position = camera_position;
            task.draw_context.viewport_width = rect.width;
            task.draw_context.viewport_height = rect.height;
            tc_component* component = render_scene_item_component(*item);
            Entity entity(component ? component->owner : TC_ENTITY_HANDLE_INVALID);
            const char* entity_name = entity.valid() ? entity.name() : nullptr;
            task.debug_name = entity_name ? entity_name : "";
        }

        std::array<FrameGraphColorAttachment, 3> colors{{
            {base_ao_res.c_str(), tgfx::LoadOp::Clear, tgfx::StoreOp::Store, {0, 0, 0, 0}},
            {normal_rough_res.c_str(), tgfx::LoadOp::Clear, tgfx::StoreOp::Store, {0, 0, 0, 0}},
            {metal_emit_res.c_str(), tgfx::LoadOp::Clear, tgfx::StoreOp::Store, {0, 0, 0, 0}},
        }};
        FrameGraphDepthAttachment depth;
        depth.resource_name = depth_res.c_str();
        depth.load = tgfx::LoadOp::Clear;
        depth.store = tgfx::StoreOp::Store;
        depth.clear_depth = 1.0f;
        tgfx::RenderPassDesc render_pass;
        if (!ctx.build_render_pass(colors, &depth, render_pass) || !ctx.ctx2->begin_pass(render_pass)) {
            tc::Log::error("[StandardGBufferPass] failed to begin ordered MRT pass");
            return;
        }

        ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
        ctx.ctx2->set_depth_test(true);
        ctx.ctx2->set_depth_write(true);
        ctx.ctx2->set_blend(false);
        ctx.ctx2->set_polygon_mode(tgfx::PolygonMode::Fill);

        MaterialPipelineResourceView material_resources{};
        material_resources.per_frame = &per_frame;
        material_resources.per_frame_size = static_cast<uint32_t>(sizeof(per_frame));
        material_resources.material_texture_sources = ctx.material_texture_sources;

        for (RenderTask& task : tasks) {
            auto& extension = *static_cast<GBufferTaskExtension*>(task.extension);
            const std::array<RenderItemNamedUniformBinding, 1> uniforms{{
                {"draw_data",
                 &extension.draw_data,
                 static_cast<uint32_t>(sizeof(extension.draw_data)),
                 "draw_data",
                 nullptr},
            }};
            task.set_resources(&material_resources, uniforms);

            ctx.ctx2->clear_resource_bindings();
            const tc_render_state& state = task.material_phase->state;
            ctx.ctx2->set_cull(state.cull ? tgfx::CullMode::Back : tgfx::CullMode::None);

            RenderItemDrawSubmitRequest submit{};
            submit.shader = tc_shader_get(task.final_shader);
            submit.shader_handle = task.final_shader;
            submit.device = &ctx.ctx2->device();
            submit.mesh_vertex_input = MaterialMeshVertexInput::FullMaterial;
            submit.draw_context = &task.draw_context;
            submit.material_phase = task.material_phase;
            submit.phase = opaque_phase;
            submit.debug_pass_name = pass_name.c_str();
            submit.debug_entity_name = task.debug_name.c_str();
            submit.resources = &task.resources;
            (void)submit_render_item_draw(*ctx.ctx2, *task.item, submit);
        }
        ctx.ctx2->end_pass();
    }

    void StandardGBufferPass::register_type() {
        auto descriptor =
            FramePassTypeDescriptorBuilder::native<StandardGBufferPass>("StandardGBufferPass", "termin-render-passes");
        auto& inspect = descriptor.inspect();
        _register_inspect_base_ao_res(inspect);
        _register_inspect_normal_rough_res(inspect);
        _register_inspect_metal_emit_res(inspect);
        _register_inspect_depth_res(inspect);
        _register_inspect_camera_name(inspect);
        _register_inspect_metadata_graph(inspect);
        (void)descriptor.commit();
    }

} // namespace termin
