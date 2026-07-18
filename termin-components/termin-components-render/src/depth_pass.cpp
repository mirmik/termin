#include <termin/render/depth_pass.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/camera/render_camera_utils.hpp>
#include <termin/render/frame_graph_debugger_core.hpp>
#include <termin/render/material_pipeline.hpp>
#include <termin/render/render_item_submission.hpp>
#include <termin/render/render_task.hpp>
#include <termin/render/tgfx2_bridge.hpp>

#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

#include <tgfx/resources/tc_shader_registry.h>

#include <tcbase/tc_log.hpp>

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstring>
#include <optional>
#include <span>
#include <string>

namespace termin {

constexpr const char* DEPTH_ENGINE_SHADER_UUID = "termin-engine-depth";
constexpr const char* DEPTH_ONLY_ENGINE_SHADER_UUID = "termin-engine-depth-only";
constexpr const char* DEPTH_TO_COLOR_ENGINE_SHADER_UUID = "termin-engine-depth-to-color";
constexpr const char* COLOR_TO_DEPTH_ENGINE_SHADER_UUID = "termin-engine-color-to-depth";

namespace {

// PerFrame UBO payload: view + projection + near/far plane. Uploaded once per
// execute and bound through the shader's reflected per_frame resource layout.
// std140:
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

// Draw-scope per-object model matrix. The shader resource layout maps it to
// backend storage; render code binds it by reflected resource name.
struct DepthDrawStd140 {
    float u_model[16];
};
static_assert(sizeof(DepthDrawStd140) == 64,
              "DepthDrawStd140 must be exactly one mat4");

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

MaterialFragmentInterface depth_world_position_interface()
{
    MaterialFragmentInterface interface;
    interface.semantics.push_back(
        {"world_pos", MaterialPipelineValueType::Float3});
    return interface;
}

VertexOutputAdapter depth_vertex_output_adapter()
{
    VertexOutputAdapter adapter;
    adapter.debug_name = "depth_clip_output";
    adapter.source_module = {
        "termin_depth_vertex_output_adapter",
        "builtin_shaders/termin_depth_vertex_output_adapter.slang"};
    adapter.output_type_name = "VertexOutput";
    adapter.output_function = "termin_depth_vertex_output";
    adapter.consumed_world_semantics = depth_world_position_interface();
    adapter.produced_output_semantics.semantics = {
        {"clip_position", MaterialPipelineValueType::Float4},
        {"linear_depth", MaterialPipelineValueType::Float},
        {"perspective_depth", MaterialPipelineValueType::Float},
        {"log_depth", MaterialPipelineValueType::Float},
    };
    adapter.resources = material_pipeline_pass_vertex_resources("depth_draw");
    return adapter;
}

MaterialPipelinePassContract depth_material_pass_contract(const char* debug_name)
{
    MaterialPipelinePassContract contract;
    contract.debug_name = debug_name ? debug_name : "depth";
    contract.required_material_fragment_input = MaterialFragmentInterface{};
    contract.uses_material_fragment = true;
    contract.vertex_output_adapter = depth_vertex_output_adapter();
    contract.static_vertex_transform =
        material_pipeline_make_static_mesh_vertex_transform_provider(
            "static_depth",
            MeshVertexTransformProfile::Position,
            "depth_draw.u_model");
    contract.skinned_vertex_transform =
        material_pipeline_make_skinned_mesh_vertex_transform_provider(
            "skinned_depth",
            MeshVertexTransformProfile::Position,
            "depth_draw.u_model");
    return contract;
}

tc_material_phase* resolve_render_item_material_phase(const tc_render_item& item) {
    if (!tc_material_handle_is_invalid(item.material) &&
        item.material_phase_index != SIZE_MAX) {
        tc_material* material = tc_material_get(item.material);
        if (material && item.material_phase_index < material->phase_count) {
            return &material->phases[item.material_phase_index];
        }
    }
    return item.material_phase;
}

void fill_depth_draw_model(DepthDrawStd140& draw, const tc_render_item& item)
{
    if (item.flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) {
        std::memcpy(draw.u_model, item.model_matrix, sizeof(float) * 16);
        return;
    }
    Mat44f identity = Mat44f::identity();
    std::memcpy(draw.u_model, identity.data, sizeof(float) * 16);
}

RenderItemTaskPlanningContract depth_only_task_planning_contract(
    const MaterialPipelinePassContract& shader_contract,
    const char* debug_pass_name)
{
    RenderItemTaskPlanningContract contract{};
    contract.pass_semantic = RenderItemPassSemantic::DepthOnly;
    contract.material_phase_policy = RenderItemMaterialPhasePolicy::Optional;
    contract.provided_input_mask =
        render_item_task_input_bit(RenderItemTaskInput::DrawContext);
    contract.required_input_mask =
        render_item_task_input_bit(RenderItemTaskInput::DrawContext);
    contract.accepted_vertex_transform_kind_mask =
        render_item_vertex_transform_kind_bit(VertexTransformKind::StaticMesh)
        | render_item_vertex_transform_kind_bit(VertexTransformKind::SkinnedMesh);
    contract.shader_contract = &shader_contract;
    contract.debug_pass_name = debug_pass_name;
    return contract;
}

bool plan_depth_only_item_shader(
    const tc_render_item& item,
    tc_material_phase* phase,
    tc_shader_handle candidate_shader,
    const MaterialPipelinePassContract& shader_contract,
    const char* debug_pass_name,
    RenderTaskList& tasks)
{
    RenderItemTaskPlanningContract contract =
        depth_only_task_planning_contract(shader_contract, debug_pass_name);
    RenderItemTaskPlanningRequest request{};
    request.item = &item;
    request.material_phase = phase;
    request.candidate_shader = candidate_shader;
    request.contract = &contract;
    return plan_render_item_task(request, tasks).accepted();
}

} // anonymous namespace

MaterialPipelinePassContract DepthPass::shader_pass_contract() const {
    return depth_material_pass_contract("depth");
}

tc_shader_handle DepthPass::shader_usage_base_shader() const {
    if (tc_shader_handle_is_invalid(depth_shader_handle_)) {
        depth_shader_handle_ =
            tgfx::register_builtin_shader_from_catalog(DEPTH_ENGINE_SHADER_UUID);
    }
    return depth_shader_handle_;
}

void DepthPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;

    // Engine-shader: process-lifetime ownership via tc_shader registry.
    if (tc_shader_handle_is_invalid(depth_shader_handle_)) {
        depth_shader_handle_ =
            tgfx::register_builtin_shader_from_catalog(DEPTH_ENGINE_SHADER_UUID);
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
    const DepthPassExecuteData& data
) {
    if (!ctx.ctx2) {
        tc::Log::error("DepthPass/tgfx2: ctx2 is null");
        return;
    }

    _near_plane = data.near_plane;
    _far_plane = data.far_plane;

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

    // Use the UBO-based engine shader as the base shader key for RenderItem
    // shader overrides. The old source-based GeometryPassBase shader path has
    // been removed.
    collect_draw_calls(data.scene, data.layer_mask, ctx.render_category_mask, depth_shader_handle_);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    auto cc = clear_color();
    float clear_rgba[4] = {cc[0], cc[1], cc[2], cc[3]};

    ctx.ctx2->begin_pass(color_tex2, depth_tex2, clear_rgba, 1.0f, clear);
    ctx.ctx2->set_viewport(0, 0, data.rect.width, data.rect.height);
    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::Back);

    MaterialPipelineShaderBinding depth_shader{};
    if (!ensure_material_pipeline_shader(
            *ctx.ctx2,
            device,
            depth_shader_handle_,
            "DepthPass",
            depth_shader)) {
        return;
    }

    // PerFrame UBO — uploaded ONCE per execute. view + projection +
    // near/far plane. Bound by shader resource name so Slang scope metadata
    // owns the physical binding.
    DepthPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, data.view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, data.projection.data, sizeof(float) * 16);
    per_frame.u_near = data.near_plane;
    per_frame.u_far = data.far_plane;
    per_frame.u_depth_encoding = depth_encoding_mode(depth_encoding);
    std::array<MaterialPipelineUniformUpload, 1> per_frame_uniforms{{
        {
            tc_shader_find_resource_binding(depth_shader.shader, "per_frame"),
            &per_frame,
            static_cast<uint32_t>(sizeof(per_frame)),
        },
    }};
    MaterialPipelineResourceView depth_resources{};
    depth_resources.uniforms = per_frame_uniforms.data();
    depth_resources.uniform_count = static_cast<uint32_t>(per_frame_uniforms.size());
    prepare_material_pipeline_resources(
        *ctx.ctx2,
        device,
        depth_shader.shader,
        nullptr,
        depth_resources);

    const std::string& debug_symbol = get_debug_internal_point();
    auto capture_debug_symbol = [&](const char* entity_name) {
        if (debug_symbol.empty() || !entity_name || debug_symbol != entity_name) {
            return;
        }
        FrameGraphCapture* capture = debug_capture();
        if (!capture) {
            return;
        }

        tgfx::TextureHandle capture_tex = color_tex2 ? color_tex2 : depth_tex2;
        if (!capture_tex) {
            return;
        }

        ctx.ctx2->end_pass();
        capture->capture_direct_via_ctx2(
            ctx.ctx2,
            capture_tex,
            data.rect.width,
            data.rect.height);
        ctx.ctx2->begin_pass(color_tex2, depth_tex2, clear_rgba, 1.0f, false);
        ctx.ctx2->set_viewport(0, 0, data.rect.width, data.rect.height);
        ctx.ctx2->set_depth_test(true);
        ctx.ctx2->set_depth_write(true);
        ctx.ctx2->set_blend(false);
        ctx.ctx2->set_cull(tgfx::CullMode::Back);
        ctx.ctx2->bind_shader(depth_shader.vertex, depth_shader.fragment);
        ctx.ctx2->use_shader_resource_layout(depth_shader.shader);
        prepare_material_pipeline_resources(
            *ctx.ctx2,
            device,
            depth_shader.shader,
            nullptr,
            depth_resources);
    };
    for (const auto& dc : cached_draw_calls_) {
        const char* name = dc.entity.name();
        const tc_render_item& item = dc.item;

        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        tc_material_phase* material_phase =
            tc_shader_handle_eq(dc.final_shader.handle, depth_shader_handle_)
                ? nullptr
                : dc.resolve_material_phase();

        // All depth shader variants share the same pass-owned draw-scope model
        // matrix + PerFrame UBO. The mesh submit path binds payload-specific
        // resources such as BoneBlock.
        DepthDrawStd140 draw{};
        fill_depth_draw_model(draw, item);
        std::array<RenderItemNamedUniformBinding, 2> draw_uniforms{{
            {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
            {"depth_draw", &draw, static_cast<uint32_t>(sizeof(draw))},
        }};
        MaterialPipelineResourceView draw_material_resources{};
        RenderItemResourceBinding resource_binding{};
        resource_binding.material_resources = &draw_material_resources;
        resource_binding.named_uniforms = draw_uniforms.data();
        resource_binding.named_uniform_count = static_cast<uint32_t>(draw_uniforms.size());
        RenderItemDrawSubmitRequest encode_request{};
        encode_request.shader_handle = dc.final_shader.handle;
        encode_request.device = &device;
        encode_request.mesh_vertex_input = MaterialMeshVertexInput::Position;
        encode_request.material_phase = material_phase;
        encode_request.resources = &resource_binding;
        encode_request.debug_pass_name = "DepthPass";
        encode_request.debug_entity_name = name;
        if (!submit_render_item_draw(
            *ctx.ctx2,
            item,
            encode_request)) {
            continue;
        }
        capture_debug_symbol(name);
    }

    ctx.ctx2->end_pass();
    // color_tex2/depth_tex2 are persistent FBOPool wrappers — do not destroy.
}

void DepthPass::execute(ExecuteContext& ctx) {
    tc_scene_handle scene = ctx.scene.handle();
    const RenderCamera* camera = ctx.camera;
    Rect2i rect = ctx.render_rect;
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
                rect = Rect2i(0, 0, w, h);
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

    DepthPassExecuteData data;
    data.rect = rect;
    data.scene = scene;
    data.view = view;
    data.projection = projection;
    data.near_plane = near_plane;
    data.far_plane = far_plane;
    data.layer_mask = ctx.layer_mask;
    execute_with_data_tgfx2(ctx, data);
}

void DepthOnlyPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;
    if (tc_shader_handle_is_invalid(depth_shader_handle_)) {
        depth_shader_handle_ =
            tgfx::register_builtin_shader_from_catalog(DEPTH_ONLY_ENGINE_SHADER_UUID);
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

void DepthOnlyPass::collect_draw_calls(
    tc_scene_handle scene,
    uint64_t layer_mask,
    uint64_t render_category_mask
) const {
    cached_draw_calls_.clear();

    if (!tc_scene_handle_valid(scene)) {
        return;
    }

    if (pass_phase_mark.empty()) {
        tc::Log::error(
            "[DepthOnlyPass] pass '%s' has empty phase mark; geometry collection requires an explicit phase",
            get_pass_name().c_str());
        return;
    }

    struct CollectContext {
    public:
        const DepthOnlyPass* pass = nullptr;
        std::vector<DepthOnlyPass::DrawCall>* draw_calls = nullptr;
        MaterialPipelinePassContract pass_contract;
        RenderContext* render_context = nullptr;
        std::string pass_name;
    };

    auto callback = [](tc_component* c, void* user_data) -> bool {
        auto* collect_ctx = static_cast<CollectContext*>(user_data);
        Entity ent(c->owner);

        tc_render_item_collect_context item_context{};
        item_context.phase_mark = collect_ctx->pass->pass_phase_mark.c_str();
        item_context.flags = TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE;
        item_context.layer_mask = collect_ctx->render_context
            ? collect_ctx->render_context->layer_mask
            : UINT64_MAX;
        item_context.render_category_mask = collect_ctx->render_context
            ? collect_ctx->render_context->render_category_mask
            : UINT64_MAX;
        item_context.pass_semantic =
            static_cast<uint32_t>(RenderItemPassSemantic::DepthOnly);
        item_context.debug_pass_name = collect_ctx->pass_name.c_str();
        item_context.pass_contract = &collect_ctx->pass_contract;
        item_context.camera = collect_ctx->render_context
            ? collect_ctx->render_context->camera
            : nullptr;

        RenderItemCollection items;
        if (!collect_drawable_render_items(c, item_context, items)) {
            return true;
        }

        for (const tc_render_item& item : items.items) {
            if (!render_item_encoder_supports_pass(
                    item.kind,
                    RenderItemPassSemantic::DepthOnly)) {
                continue;
            }

            tc_shader_handle original_shader =
                collect_ctx->pass->depth_shader_handle_;
            tc_material_phase* selected_phase = resolve_render_item_material_phase(item);
            if (selected_phase &&
                !tc_shader_handle_is_invalid(selected_phase->shader)) {
                original_shader = selected_phase->shader;
            }

            DrawCall dc;
            dc.entity = ent;
            dc.component = c;
            dc.item = item;
            RenderTaskList planned_shader;
            if (!plan_depth_only_item_shader(
                    item,
                    selected_phase,
                    original_shader,
                    collect_ctx->pass_contract,
                    "DepthOnlyPass/Collect",
                    planned_shader)) {
                continue;
            }
            dc.final_shader = TcShader(planned_shader.at(0).final_shader);
            dc.geometry_id = item.geometry_id;
            if (selected_phase) {
                dc.material_phase = selected_phase;
                dc.material = item.material;
                dc.phase_index = item.material_phase_index;
            }
            collect_ctx->draw_calls->push_back(dc);
        }
        return true;
    };

    RenderContext render_context;
    render_context.phase = pass_phase_mark;
    render_context.pass_contract = depth_material_pass_contract("depth_only");
    render_context.layer_mask = layer_mask;
    render_context.render_category_mask = render_category_mask;
    render_context.scene = TcSceneRef(scene);

    CollectContext collect_ctx{
        this,
        &cached_draw_calls_,
        depth_material_pass_contract("depth_only"),
        &render_context,
        get_pass_name()};

    int filter_flags = TC_SCENE_FILTER_ENABLED
                     | TC_SCENE_FILTER_VISIBLE
                     | TC_SCENE_FILTER_ENTITY_ENABLED;
    tc_scene_foreach_drawable(scene, callback, &collect_ctx, filter_flags, layer_mask);
}

void DepthOnlyPass::collect_shader_usages(
    tc_scene_handle scene,
    const std::function<void(TcShader)>& emit
) const {
    if (!emit) {
        return;
    }
    if (!tc_scene_handle_valid(scene)) {
        tc::Log::error("[DepthOnlyPass] cannot collect shader usages for invalid scene");
        return;
    }
    if (pass_phase_mark.empty()) {
        tc::Log::error(
            "[DepthOnlyPass] pass '%s' has empty phase mark; shader usage collection requires an explicit phase",
            get_pass_name().c_str());
        return;
    }

    if (tc_shader_handle_is_invalid(depth_shader_handle_)) {
        depth_shader_handle_ =
            tgfx::register_builtin_shader_from_catalog(DEPTH_ONLY_ENGINE_SHADER_UUID);
    }
    if (tc_shader_handle_is_invalid(depth_shader_handle_)) {
        tc::Log::error("[DepthOnlyPass] cannot collect shader usages without a valid base shader");
        return;
    }

    struct UsageContext {
    public:
        const DepthOnlyPass* pass = nullptr;
        const std::function<void(TcShader)>* emit = nullptr;
        MaterialPipelinePassContract pass_contract;
    };

    auto callback = [](tc_component* c, void* user_data) -> bool {
        auto* collect_ctx = static_cast<UsageContext*>(user_data);
        if (!collect_ctx || !collect_ctx->pass || !collect_ctx->emit || !c) {
            return true;
        }

        tc_render_item_collect_context item_context{};
        item_context.phase_mark = collect_ctx->pass->pass_phase_mark.c_str();
        item_context.flags = TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE;
        item_context.layer_mask = UINT64_MAX;
        item_context.render_category_mask = UINT64_MAX;
        item_context.pass_semantic =
            static_cast<uint32_t>(RenderItemPassSemantic::DepthOnly);
        item_context.debug_pass_name = "DepthOnlyPass/ShaderUsage";
        item_context.pass_contract = &collect_ctx->pass_contract;

        RenderItemCollection items;
        if (!collect_drawable_render_items(c, item_context, items)) {
            return true;
        }

        for (const tc_render_item& item : items.items) {
            if (!render_item_encoder_supports_pass(
                    item.kind,
                    RenderItemPassSemantic::DepthOnly)) {
                continue;
            }

            tc_shader_handle original_shader =
                collect_ctx->pass->depth_shader_handle_;
            tc_material_phase* phase = resolve_render_item_material_phase(item);
            if (phase && !tc_shader_handle_is_invalid(phase->shader)) {
                original_shader = phase->shader;
            }

            RenderTaskList tasks;
            if (!plan_depth_only_item_shader(
                    item,
                    phase,
                    original_shader,
                    collect_ctx->pass_contract,
                    "DepthOnlyPass/ShaderUsage",
                    tasks)) {
                continue;
            }
            const RenderTask& task = tasks.at(0);
            for (uint32_t i = 0; i < task.shader_usage_count; ++i) {
                (*collect_ctx->emit)(TcShader(task.shader_usages[i]));
            }
        }

        return true;
    };

    UsageContext collect_ctx{
        this,
        &emit,
        depth_material_pass_contract("depth_only")};

    tc_scene_foreach_drawable(scene, callback, &collect_ctx, TC_SCENE_FILTER_NONE, 0);
}

void DepthOnlyPass::sort_draw_calls_by_shader() const {
    if (cached_draw_calls_.size() <= 1) {
        return;
    }

    std::sort(cached_draw_calls_.begin(), cached_draw_calls_.end(),
        [](const DrawCall& a, const DrawCall& b) {
            return a.final_shader.handle.index < b.final_shader.handle.index;
        });
}

void DepthOnlyPass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[DepthOnlyPass] ctx.ctx2 is null — DepthOnlyPass is tgfx2-only");
        return;
    }

    tc_scene_handle scene = ctx.scene.handle();
    const RenderCamera* camera = ctx.camera;
    Rect2i rect = ctx.render_rect;
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
        rect = Rect2i(0, 0, w, h);
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
    collect_draw_calls(scene, ctx.layer_mask, ctx.render_category_mask);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    ctx.ctx2->begin_pass({}, depth_tex2, nullptr, 1.0f, true);
    ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::Back);

    MaterialPipelineShaderBinding depth_shader{};
    if (!ensure_material_pipeline_shader(
            *ctx.ctx2,
            device,
            depth_shader_handle_,
            "DepthOnlyPass",
            depth_shader)) {
        return;
    }

    DepthPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
    per_frame.u_near = near_plane;
    per_frame.u_far = far_plane;
    std::array<MaterialPipelineUniformUpload, 1> per_frame_uniforms{{
        {
            tc_shader_find_resource_binding(depth_shader.shader, "per_frame"),
            &per_frame,
            static_cast<uint32_t>(sizeof(per_frame)),
        },
    }};
    MaterialPipelineResourceView depth_resources{};
    depth_resources.uniforms = per_frame_uniforms.data();
    depth_resources.uniform_count = static_cast<uint32_t>(per_frame_uniforms.size());
    prepare_material_pipeline_resources(
        *ctx.ctx2,
        device,
        depth_shader.shader,
        nullptr,
        depth_resources);

    const std::string& debug_symbol = get_debug_internal_point();
    auto capture_debug_symbol = [&](const char* entity_name) {
        if (debug_symbol.empty() || !entity_name || debug_symbol != entity_name) {
            return;
        }
        FrameGraphCapture* capture = debug_capture();
        if (!capture || !depth_tex2) {
            return;
        }

        ctx.ctx2->end_pass();
        capture->capture_direct_via_ctx2(
            ctx.ctx2,
            depth_tex2,
            rect.width,
            rect.height);
        ctx.ctx2->begin_pass({}, depth_tex2, nullptr, 1.0f, false);
        ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
        ctx.ctx2->set_depth_test(true);
        ctx.ctx2->set_depth_write(true);
        ctx.ctx2->set_blend(false);
        ctx.ctx2->set_cull(tgfx::CullMode::Back);
        ctx.ctx2->bind_shader(depth_shader.vertex, depth_shader.fragment);
        ctx.ctx2->use_shader_resource_layout(depth_shader.shader);
        prepare_material_pipeline_resources(
            *ctx.ctx2,
            device,
            depth_shader.shader,
            nullptr,
            depth_resources);
    };
    for (const auto& dc : cached_draw_calls_) {
        const char* name = dc.entity.name();
        const tc_render_item& item = dc.item;

        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        tc_material_phase* material_phase =
            tc_shader_handle_eq(dc.final_shader.handle, depth_shader_handle_)
                ? nullptr
                : dc.resolve_material_phase();

        DepthDrawStd140 draw{};
        fill_depth_draw_model(draw, item);
        std::array<RenderItemNamedUniformBinding, 2> draw_uniforms{{
            {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
            {"depth_draw", &draw, static_cast<uint32_t>(sizeof(draw))},
        }};
        MaterialPipelineResourceView draw_material_resources{};
        RenderItemResourceBinding resource_binding{};
        resource_binding.material_resources = &draw_material_resources;
        resource_binding.named_uniforms = draw_uniforms.data();
        resource_binding.named_uniform_count = static_cast<uint32_t>(draw_uniforms.size());
        RenderItemDrawSubmitRequest encode_request{};
        encode_request.shader_handle = dc.final_shader.handle;
        encode_request.device = &device;
        encode_request.mesh_vertex_input = MaterialMeshVertexInput::Position;
        encode_request.material_phase = material_phase;
        encode_request.resources = &resource_binding;
        encode_request.debug_pass_name = "DepthOnlyPass";
        encode_request.debug_entity_name = name;
        if (!submit_render_item_draw(
            *ctx.ctx2,
            item,
            encode_request)) {
            continue;
        }
        capture_debug_symbol(name);
    }

    ctx.ctx2->end_pass();
}

void DepthToColorPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;
    if (tc_shader_handle_is_invalid(shader_handle_)) {
        shader_handle_ =
            tgfx::register_builtin_shader_from_catalog(DEPTH_TO_COLOR_ENGINE_SHADER_UUID);
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
    ctx.ctx2->use_shader_resource_layout(raw);
    ctx.ctx2->clear_resource_bindings();
    ctx.ctx2->bind_texture("u_depth_tex", depth_tex);
    ctx.ctx2->draw_fullscreen_quad();
    ctx.ctx2->end_pass();
}

void ColorToDepthPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;
    if (tc_shader_handle_is_invalid(shader_handle_)) {
        shader_handle_ =
            tgfx::register_builtin_shader_from_catalog(COLOR_TO_DEPTH_ENGINE_SHADER_UUID);
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
    ctx.ctx2->use_shader_resource_layout(raw);
    ctx.ctx2->clear_resource_bindings();
    ctx.ctx2->bind_texture("u_color_tex", color_tex);
    ctx.ctx2->draw_fullscreen_quad();
    ctx.ctx2->end_pass();
}

TC_DEFINE_FRAME_PASS_FACTORY_DERIVED(DepthPass, GeometryPassBase);
TC_DEFINE_FRAME_PASS_FACTORY_DERIVED(DepthOnlyPass, CxxFramePass);
TC_DEFINE_FRAME_PASS_FACTORY_DERIVED(DepthToColorPass, CxxFramePass);
TC_DEFINE_FRAME_PASS_FACTORY_DERIVED(ColorToDepthPass, CxxFramePass);

void DepthPass::register_type() {
    register_frame_pass_DepthPass();
    _register_inspect_pass_phase_mark();
    _register_inspect_depth_encoding();
    _register_inspect_clear();
}

void DepthOnlyPass::register_type() {
    register_frame_pass_DepthOnlyPass();
    _register_inspect_output_res();
    _register_inspect_output_res_target();
    _register_inspect_camera_name();
    _register_inspect_pass_phase_mark();
    _register_inspect_metadata_graph();
}

void DepthToColorPass::register_type() {
    register_frame_pass_DepthToColorPass();
    _register_inspect_input_res();
    _register_inspect_output_res();
    _register_inspect_output_res_target();
    _register_inspect_metadata_graph();
}

void ColorToDepthPass::register_type() {
    register_frame_pass_ColorToDepthPass();
    _register_inspect_input_res();
    _register_inspect_output_res();
    _register_inspect_output_res_target();
    _register_inspect_metadata_graph();
}

} // namespace termin
