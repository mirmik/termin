#include "termin/render/shadow_pass.hpp"
#include <tgfx/tgfx_shader_handle.hpp>
#include <tcbase/tc_log.hpp>
#include "termin/camera/camera_component.hpp"

#include "tgfx2/builtin_shader_sources.hpp"
#include "termin/render/frame_graph_debugger_core.hpp"
#include "termin/render/frame_uniforms.hpp"
#include "termin/render/material_pipeline.hpp"
#include "termin/render/material_pipeline_shader_assembler.hpp"
#include "termin/render/render_item_submission.hpp"
#include "termin/render/render_task.hpp"
#include "termin/render/tgfx2_bridge.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
#include "tc_profiler.h"
#include "core/tc_drawable_protocol.h"
#include "core/tc_scene_drawable.h"
#include "core/tc_scene_render_state.h"
}

#include <cmath>
#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstring>
#include <set>
#include <span>
#include <string>

namespace termin {

constexpr const char* SHADOW_ENGINE_SHADER_UUID = "termin-engine-shadow";
constexpr const char* SHADOW_STATIC_TRANSFORM_MODULE = "termin_shadow_static_transform";
constexpr const char* SHADOW_SKINNED_TRANSFORM_MODULE = "termin_shadow_skinned_transform";
constexpr const char* SHADOW_OUTPUT_ADAPTER_MODULE = "termin_shadow_vertex_output_adapter";

namespace {

// PerFrame UBO (binding 0): view + projection. Uploaded ONCE per
// cascade, bound as a regular uniform buffer. 128 bytes, std140
// mat4-aligned.
struct ShadowPerFrameStd140 {
    float u_view[16];
    float u_projection[16];
};
static_assert(sizeof(ShadowPerFrameStd140) == 128,
              "ShadowPerFrameStd140 must be 2 * mat4");

// Draw-scope per-object model matrix. The shader resource layout maps it to
// the backend-specific storage, while this pass binds by resource name.
struct ShadowPushStd140 {
    float u_model[16];
};
static_assert(sizeof(ShadowPushStd140) == 64,
              "ShadowPushStd140 must be mat4");

struct ShadowTaskExtension final : RenderTaskExtension {
    ShadowPushStd140 draw_data{};
};

MaterialFragmentInterface shadow_world_position_interface()
{
    MaterialFragmentInterface interface;
    interface.semantics.push_back(
        {"world_pos", MaterialPipelineValueType::Float3});
    return interface;
}

std::vector<MaterialPipelineResourceDecl> shadow_adapter_resources()
{
    std::vector<MaterialPipelineResourceDecl> resources =
        material_pipeline_common_vertex_resources("shadow_draw");
    for (MaterialPipelineResourceDecl& resource : resources) {
        resource.owner = MaterialPipelineResourceOwner::Pass;
    }
    return resources;
}

VertexOutputAdapter shadow_vertex_output_adapter()
{
    VertexOutputAdapter adapter;
    adapter.debug_name = "shadow_clip_output";
    adapter.source_module = {
        SHADOW_OUTPUT_ADAPTER_MODULE,
        "builtin_shaders/termin_shadow_vertex_output_adapter.slang"};
    adapter.output_type_name = "VertexOutput";
    adapter.output_function = "termin_shadow_clip_output";
    adapter.consumed_world_semantics = shadow_world_position_interface();
    adapter.produced_output_semantics.semantics.push_back(
        {"clip_position", MaterialPipelineValueType::Float4});
    adapter.resources = shadow_adapter_resources();
    return adapter;
}

void configure_shadow_static_provider(VertexTransformProvider& provider)
{
    provider.source_module = {
        SHADOW_STATIC_TRANSFORM_MODULE,
        "builtin_shaders/termin_shadow_static_transform.slang"};
    provider.entry_input_declaration = R"(
struct VertexInput {
    float3 position : POSITION;
};)";
    provider.adapter_input_expression =
        "termin_shadow_static_world_position(input.position, shadow_draw.u_model)";
    provider.produced_world_semantics = shadow_world_position_interface();
}

void configure_shadow_skinned_provider(VertexTransformProvider& provider)
{
    provider.source_module = {
        SHADOW_SKINNED_TRANSFORM_MODULE,
        "builtin_shaders/termin_shadow_skinned_transform.slang"};
    provider.entry_input_declaration = R"(
struct VertexInput {
    float3 position : POSITION;
    float4 joints : TEXCOORD0;
    float4 weights : TEXCOORD1;
};)";
    provider.adapter_input_expression =
        "termin_shadow_skinned_world_position("
        "input.position, input.joints, input.weights, shadow_draw.u_model, bone_block)";
    provider.produced_world_semantics = shadow_world_position_interface();
}

MaterialPipelinePassContract shadow_material_pass_contract()
{
    MaterialPipelinePassContract contract;
    contract.debug_name = "shadow";
    contract.required_material_fragment_input = MaterialFragmentInterface{};
    contract.uses_material_fragment = true;
    contract.vertex_output_adapter = shadow_vertex_output_adapter();

    MaterialFragmentInterface fragment_input =
        material_pipeline_standard_material_fragment_interface();
    contract.static_vertex_transform =
        material_pipeline_make_static_vertex_transform_contract(
            "static_shadow",
            material_pipeline_position_mesh_input(),
            fragment_input,
            {});
    configure_shadow_static_provider(*contract.static_vertex_transform);
    contract.skinned_vertex_transform =
        material_pipeline_make_skinned_vertex_transform_contract(
            *contract.static_vertex_transform,
            "skinned_shadow",
            std::nullopt,
            material_pipeline_skinned_position_mesh_input());
    configure_shadow_skinned_provider(*contract.skinned_vertex_transform);
    contract.foliage_vertex_transform =
        material_pipeline_make_foliage_vertex_transform_contract(
            VertexTransformKind::FoliageShadow,
            "foliage_shadow",
            "termin-engine-foliage-shadow",
            material_pipeline_position_mesh_input(),
            fragment_input,
            material_pipeline_foliage_vertex_resources());
    return contract;
}

tc_shader_handle register_modular_shadow_shader()
{
    const std::string shadow_fragment_source =
        tgfx::load_builtin_shader_stage_source_from_catalog(
            SHADOW_ENGINE_SHADER_UUID,
            "fragment");
    if (shadow_fragment_source.empty()) {
        tc::Log::error(
            "[ShadowPass] failed to load shadow fragment source '%s'",
            SHADOW_ENGINE_SHADER_UUID);
        return tc_shader_handle_invalid();
    }

    TcShaderCreateInfo fragment_create_info{};
    fragment_create_info.sources.fragment = shadow_fragment_source;
    fragment_create_info.sources.name = "ShadowEngineFragmentSource";
    fragment_create_info.sources.source_path =
        "builtin_shaders/termin-engine-shadow.slang";
    fragment_create_info.sources.fragment_entry = "fs_main";
    fragment_create_info.uuid = "termin-engine-shadow-fragment-source";
    fragment_create_info.language = TC_SHADER_LANGUAGE_SLANG;
    fragment_create_info.artifact_policy = TC_SHADER_ARTIFACT_REQUIRED;
    TcShader base_shader = TcShader::from_sources(fragment_create_info);
    if (!base_shader.is_valid()) {
        tc::Log::error("[ShadowPass] failed to register shadow fragment source");
        return tc_shader_handle_invalid();
    }
    MaterialPipelinePassContract pass_contract = shadow_material_pass_contract();
    if (!pass_contract.static_vertex_transform.has_value()) {
        tc::Log::error("[ShadowPass] static shadow transform provider is missing");
        return tc_shader_handle_invalid();
    }

    MaterialPipelineShaderAssemblyRequest request{};
    request.material = material_pipeline_material_contract_from_shader(
        base_shader,
        pass_contract.required_material_fragment_input);
    request.vertex_transform = *pass_contract.static_vertex_transform;
    request.pass = pass_contract;
    request.shader_name = "ShadowEngineModular";
    request.shader_uuid = material_pipeline_shader_intent_fingerprint(
        base_shader,
        TC_SHADER_VARIANT_NONE,
        request.vertex_transform,
        request.pass);
    request.language = base_shader.language();
    request.artifact_policy = base_shader.artifact_policy();

    MaterialPipelineShaderAssemblyResult result =
        material_pipeline_assemble_shader(request);
    if (!result.ok()) {
        for (const MaterialPipelineDiagnostic& diagnostic : result.diagnostics) {
            tc::Log::error(
                "[ShadowPass] modular shadow shader assembly failed: %s: %s",
                material_pipeline_diagnostic_code_name(diagnostic.code),
                diagnostic.message.c_str());
        }
        return tc_shader_handle_invalid();
    }
    // The assembly result owns a transient RAII reference. ShadowPass caches a
    // raw handle and is recreated with the framegraph, so transfer the
    // assembled engine shader to the registry's process-lifetime ownership
    // before the local result releases its reference.
    if (!tc_shader_retain_static(result.shader.handle)) {
        tc::Log::error("[ShadowPass] failed to retain modular shadow shader");
        return tc_shader_handle_invalid();
    }
    return result.shader.handle;
}

} // anonymous namespace



ShadowPass::ShadowPass(
    const std::string& output_res,
    const std::string& pass_name,
    float caster_offset
) : output_res(output_res),
    caster_offset(caster_offset)
{
    set_pass_name(pass_name);
}


void ShadowPass::destroy() {
    if (depth_pool_device_) {
        for (auto& [_, slot] : depth_pool_) {
            if (slot.tex) depth_pool_device_->destroy(slot.tex);
        }
    }
    depth_pool_.clear();
    depth_pool_device_ = nullptr;
    release_tgfx2_resources();
}

void ShadowPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;

    // Assemble and register the modular shadow VS plus the engine fragment
    // source as a TcShader so the global hash-based registry dedups it across
    // pass re-creations.
    // When the editor toggles Play/Stop and the frame-graph rebuilds its
    // ShadowPass, `tc_shader_from_sources` returns the existing handle
    // (same source -> same hash -> same slot), and `tc_shader_ensure_tgfx2`
    // below finds cached VkShaderModules on the slot — no shaderc recompile.
    // Used to live as direct `device.create_shader()` calls owned by this
    // pass; every ShadowPass destruction destroyed the shader modules,
    // every construction re-ran shaderc (~35 ms × 19 engine shaders on
    // Play/Stop = ~700 ms lag).
    if (!tc_shader_is_valid(shadow_shader_handle_)) {
        // Process-lifetime engine shader: never destroyed (transient
        // TcShader wrappers from material phases / Python bindings
        // can't bounce ref_count through zero and take it down).
        shadow_shader_handle_ = register_modular_shadow_shader();
    }
}

void ShadowPass::release_tgfx2_resources() {
    if (!device2_) return;
    // shadow_shader_handle_ intentionally NOT released here. The +1 ref
    // we took in ensure_tgfx2_resources is an intentional process-
    // lifetime hold: engine shaders need to survive ShadowPass teardown
    // on Play/Stop (frame-graph rebuild) so the render-device shader
    // cache can reuse compiled modules instead of forcing shaderc to
    // recompile on the next pass creation.
    device2_ = nullptr;
}


std::vector<ResourceSpec> ShadowPass::get_resource_specs() const {
    return {
        ResourceSpec{
            output_res,
            "shadow_map_array",
            std::nullopt,
            std::nullopt,
            std::nullopt
        }
    };
}


tgfx::TextureHandle ShadowPass::get_or_create_depth_tex2(
    tgfx::IRenderDevice& device,
    int resolution,
    int index
) {
    if (depth_pool_device_ && depth_pool_device_ != &device) {
        // Device changed — throw the whole pool away.
        for (auto& [_, slot] : depth_pool_) {
            if (slot.tex) depth_pool_device_->destroy(slot.tex);
        }
        depth_pool_.clear();
        depth_pool_device_ = nullptr;
    }
    depth_pool_device_ = &device;

    auto it = depth_pool_.find(index);
    if (it != depth_pool_.end() && it->second.resolution == resolution) {
        return it->second.tex;
    }

    // Resolution changed or slot missing — recreate.
    if (it != depth_pool_.end()) {
        if (it->second.tex) device.destroy(it->second.tex);
        // Reusing backend-native texture storage for a new size invalidates
        // cached render targets keyed on the old attachment identity.
        device.invalidate_render_target_cache();
        depth_pool_.erase(it);
    }

    tgfx::TextureDesc desc;
    desc.width = static_cast<uint32_t>(resolution);
    desc.height = static_cast<uint32_t>(resolution);
    // D32F is universally supported as a depth attachment across GL/Vulkan
    // drivers. D24_UNorm maps to VK_FORMAT_X8_D24_UNORM_PACK32 on Vulkan,
    // which is an *optional* format — unsupported on AMD and some Intel
    // parts, and produces a silently broken VkImage on affected hardware
    // (no validation error, just garbage depth values in the shadow map).
    desc.format = tgfx::PixelFormat::D32F;
    desc.sample_count = 1;
    desc.usage = tgfx::TextureUsage::Sampled |
                 tgfx::TextureUsage::DepthStencilAttachment |
                 tgfx::TextureUsage::CopySrc;   // needed for Frame Debugger blit

    tgfx::TextureHandle tex = device.create_texture(desc);
    if (!tex) {
        tc::Log::error("ShadowPass: failed to create depth texture (res=%d)",
                       resolution);
        return {};
    }

    depth_pool_[index] = ShadowDepthSlot{tex, resolution};
    return tex;
}


namespace {

struct CollectShadowShaderUsagesData {
    tc_shader_handle base_shader = tc_shader_handle_invalid();
    MaterialPipelinePassContract pass_contract;
    const std::function<void(TcShader)>* emit = nullptr;
};

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

bool collect_shadow_drawable_shader_usages(tc_component* tc, void* user_data) {
    auto* data = static_cast<CollectShadowShaderUsagesData*>(user_data);
    if (!tc || !data || !data->emit) {
        return true;
    }

    if (!tc_component_has_phase(tc, "shadow")) {
        return true;
    }

    RenderContext render_context;
    render_context.phase = "shadow";
    render_context.pass_contract = data->pass_contract;
    tc_render_item_collect_context item_context{};
    item_context.phase_mark = "shadow";
    item_context.layer_mask = UINT64_MAX;
    item_context.render_category_mask = UINT64_MAX;
    item_context.debug_pass_name = "ShadowPass/ShaderUsage";
    item_context.pass_contract = &data->pass_contract;

    RenderItemCollection items;
    if (!collect_drawable_render_items(tc, item_context, items)) {
        return true;
    }

    for (const tc_render_item& item : items.items) {
        tc_material_phase* phase = resolve_render_item_material_phase(item);
        if (!phase) {
            continue;
        }

        ShaderOverrideContext override_context;
        override_context.phase_mark = "shadow";
        override_context.geometry_id = item.geometry_id;
        override_context.original_shader = TcShader(data->base_shader);
        override_context.pass_contract = data->pass_contract;
        collect_drawable_shader_usages_with_context(tc, override_context, *data->emit);
    }

    return true;
}

} // anonymous namespace

void ShadowPass::collect_shadow_casters(
    tc_scene_handle scene,
    uint64_t layer_mask,
    uint64_t render_category_mask,
    RenderSceneItemCollector& collector
) {
    cached_draw_calls_.clear();

    if (!tc_scene_handle_valid(scene)) {
        return;
    }

    RenderContext render_context;
    render_context.phase = "shadow";
    render_context.pass_contract = shadow_material_pass_contract();
    render_context.layer_mask = layer_mask;
    render_context.render_category_mask = render_category_mask;
    render_context.scene = TcSceneRef(scene);

    MaterialPipelinePassContract pass_contract = shadow_material_pass_contract();
    RenderSceneItemCollectRequest request{};
    request.scene = scene;
    request.phase_mark = "shadow";
    request.layer_mask = layer_mask;
    request.render_category_mask = render_category_mask;
    request.debug_pass_name = "ShadowPass";
    request.pass_contract = &pass_contract;
    request.camera = render_context.camera;
    if (!collector.collect(request)) {
        tc::Log::error("[ShadowPass] collect_shadow_casters: item collection failed");
    }

    const auto& items = collector.items();
    cached_draw_calls_.reserve(items.size());
    for (size_t item_index = 0; item_index < items.size(); ++item_index) {
        const tc_render_item& item = items[item_index];
        tc_component* tc = item.component;
        if (!tc) {
            tc::Log::error(
                "[ShadowPass] collect_shadow_casters: collected item %zu has null component",
                item_index);
            continue;
        }

        Entity ent(tc->owner);
        if (!ent.valid()) {
            const char* component_name = tc_component_type_name(tc);
            tc::Log::error(
                "[ShadowPass] collect_shadow_casters: drawable component '%s' has invalid owner",
                component_name ? component_name : "<unknown>");
            continue;
        }

        tc_material_phase* phase = resolve_render_item_material_phase(item);
        if (!phase) {
            continue;
        }

        ShaderOverrideContext override_context;
        override_context.phase_mark = "shadow";
        override_context.geometry_id = item.geometry_id;
        override_context.original_shader = TcShader(shadow_shader_handle_);
        override_context.pass_contract = pass_contract;
        tc_shader_handle final_shader =
            override_drawable_shader(tc, override_context).handle;

        ShadowDrawCall dc;
        dc.entity = ent;
        dc.component = tc;
        dc.phase = phase;
        dc.final_shader = final_shader;
        dc.geometry_id = item.geometry_id;
        dc.item_index = item_index;
        dc.item = item;
        dc.material = item.material;
        dc.phase_index = item.material_phase_index;
        cached_draw_calls_.push_back(dc);
    }
}

void ShadowPass::collect_shader_usages(
    tc_scene_handle scene,
    const std::function<void(TcShader)>& emit
) const {
    if (!emit) {
        return;
    }
    if (!tc_scene_handle_valid(scene)) {
        tc::Log::error("[ShadowPass] cannot collect shader usages for invalid scene");
        return;
    }

    if (!tc_shader_is_valid(shadow_shader_handle_)) {
        shadow_shader_handle_ = register_modular_shadow_shader();
    }
    if (!tc_shader_is_valid(shadow_shader_handle_)) {
        tc::Log::error("[ShadowPass] cannot collect shader usages without a valid base shader");
        return;
    }

    CollectShadowShaderUsagesData data;
    data.base_shader = shadow_shader_handle_;
    data.pass_contract = shadow_material_pass_contract();
    data.emit = &emit;

    tc_scene_foreach_drawable(
        scene,
        collect_shadow_drawable_shader_usages,
        &data,
        TC_SCENE_FILTER_NONE,
        0);
}

void ShadowPass::sort_draw_calls_by_shader() {
    if (cached_draw_calls_.size() <= 1) return;

    std::sort(cached_draw_calls_.begin(), cached_draw_calls_.end(),
        [](const ShadowDrawCall& a, const ShadowDrawCall& b) {
            return a.final_shader.index < b.final_shader.index;
        });
}


ShadowCameraParams ShadowPass::build_shadow_params(
    const Light& light,
    const Mat44f& camera_view,
    const Mat44f& camera_projection
) {
    Vec3 light_dir = light.direction.normalized();

    // Use frustum fitting for better shadow quality
    return fit_shadow_frustum_to_camera(
        camera_view,
        camera_projection,
        light_dir,
        1.0f,  // padding
        light.shadows.map_resolution,
        true,  // stabilize (texel snapping)
        caster_offset
    );
}


// ----------------------------------------------------------------------------
// tgfx2 path — Stage 5.B.
// ----------------------------------------------------------------------------
//
// Draws shadow casters through RenderContext2. The pass owns tgfx2 depth
// textures, opens a depth-only render pass for each cascade, and draws
// mesh-backed drawables through the backend-neutral tc_mesh bridge.
// Drawables that cannot expose a tc_mesh* cast shadows through typed
// RenderItems and pass-specific encoders.
std::vector<ShadowMapResult> ShadowPass::execute_shadow_pass_tgfx2(
    ExecuteContext& ctx,
    const ShadowPassExecuteData& data
) {
    std::vector<ShadowMapResult> results;

    if (!ctx.ctx2) {
        tc::Log::error("ShadowPass/tgfx2: ctx2 is null");
        return results;
    }

    auto& device = ctx.ctx2->device();

    ensure_tgfx2_resources(device);

    if (!tc_shader_is_valid(shadow_shader_handle_)) {
        tc::Log::error("ShadowPass/tgfx2: shadow_shader_handle_ not registered");
        return results;
    }

    // Find directional lights that cast shadows.
    std::vector<std::pair<int, const Light*>> shadow_lights;
    for (size_t i = 0; i < data.lights.size(); ++i) {
        const Light& light = data.lights[i];
        if (light.type == LightType::Directional && light.shadows.enabled) {
            shadow_lights.push_back({static_cast<int>(i), &light});
        }
    }
    if (shadow_lights.empty()) {
        return results;
    }

    RenderSceneItemCollector scene_items;
    collect_shadow_casters(
        data.scene,
        data.layer_mask,
        ctx.render_category_mask,
        scene_items);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen;
    for (const auto& dc : cached_draw_calls_) {
        const char* name = dc.entity.name();
        if (name && seen.find(name) == seen.end()) {
            seen.insert(name);
            entity_names.push_back(name);
        }
    }

    float camera_near = data.camera_near;
    float camera_far = data.camera_far;
    if (camera_near < 0.001f) {
        camera_near = 0.1f;
    }
    if (camera_far <= camera_near + 0.001f) {
        camera_far = camera_near + 100.0f;
    }

    int fbo_index = 0;
    for (auto [light_index, light] : shadow_lights) {
        int resolution = light->shadows.map_resolution;
        int cascade_count = std::max(1, std::min(4, light->shadows.cascade_count));
        float max_distance = std::min(light->shadows.max_distance, camera_far);
        if (max_distance <= camera_near + 0.001f) {
            max_distance = camera_far;
        }
        float split_lambda = light->shadows.split_lambda;
        float depth_bias_slope = static_cast<float>(light->shadows.normal_bias);

        std::vector<float> splits = compute_cascade_splits(
            camera_near, max_distance, cascade_count, split_lambda);

        Vec3 light_dir = light->direction.normalized();

        for (int c = 0; c < cascade_count; ++c) {
            float cascade_near = splits[c];
            float cascade_far = splits[c + 1];

            tgfx::TextureHandle depth_tex2 =
                get_or_create_depth_tex2(ctx.ctx2->device(), resolution, fbo_index);
            fbo_index++;
            if (!depth_tex2) {
                tc::Log::error("ShadowPass/tgfx2: depth tex is null for cascade %d", c);
                continue;
            }

            ShadowCascadeFitRequest fit_request;
            fit_request.view_matrix = data.camera_view;
            fit_request.projection_matrix = data.camera_projection;
            fit_request.camera_near = camera_near;
            fit_request.camera_far = camera_far;
            fit_request.light_direction = light_dir;
            fit_request.cascade_near = cascade_near;
            fit_request.cascade_far = cascade_far;
            fit_request.shadow_map_resolution = resolution;
            fit_request.caster_offset = caster_offset;
            ShadowCameraParams params = fit_shadow_frustum_for_cascade(fit_request);
            Mat44f view_matrix = build_shadow_view_matrix(params);
            Mat44f proj_matrix = build_shadow_projection_matrix(params);
            Mat44f light_space_matrix = compute_light_space_matrix(params);

            ctx.ctx2->begin_pass(
                tgfx::TextureHandle{},  // depth-only
                depth_tex2,
                nullptr,                 // no color clear
                1.0f,                    // clear depth to 1.0
                true                     // clear_depth_enabled
            );
            ctx.ctx2->set_viewport(0, 0, resolution, resolution);
            ctx.ctx2->set_depth_test(true);
            ctx.ctx2->set_depth_write(true);
            ctx.ctx2->set_blend(false);
            // Render back faces into the shadow map. For closed meshes this
            // avoids front-face self-shadow acne without moving caster geometry
            // in light space; receiver bias remains a pure compare-depth offset
            // in the shader shadow helper.
            ctx.ctx2->set_cull(tgfx::CullMode::Front);
            ctx.ctx2->set_depth_bias(depth_bias_slope != 0.0f,
                                     0.0f,
                                     depth_bias_slope,
                                     0.0f);

            auto restore_shadow_raster_state = [&]() {
                ctx.ctx2->set_depth_test(true);
                ctx.ctx2->set_depth_write(true);
                ctx.ctx2->set_blend(false);
                ctx.ctx2->set_cull(tgfx::CullMode::Front);
                ctx.ctx2->set_depth_bias(depth_bias_slope != 0.0f,
                                         0.0f,
                                         depth_bias_slope,
                                         0.0f);
            };

            auto end_shadow_pass = [&]() {
                ctx.ctx2->end_pass();
                ctx.ctx2->set_depth_bias(false);
            };

            // Fetch cached VkShaderModule handles from the tc_shader slot.
            // First call on a fresh device compiles via shaderc; every
            // subsequent ShadowPass lifetime hits the slot cache.
            MaterialPipelineShaderBinding shadow_shader{};
            if (!ensure_material_pipeline_shader(
                    *ctx.ctx2,
                    device,
                    shadow_shader_handle_,
                    "ShadowPass",
                    shadow_shader)) {
                end_shadow_pass();
                continue;
            }

            // PerFrame UBO through the ring: a fresh offset per cascade,
            // so the per-cascade matrices survive into draw-execute time
            // without a slot-per-cascade pool (the shared ring buffer and
            // dynamic descriptor offsets do what per_frame_ubo_pool_ used
            // to do on the per-UBO path).
            ShadowPerFrameStd140 per_frame{};
            std::memcpy(per_frame.u_view, view_matrix.data, sizeof(float) * 16);
            std::memcpy(per_frame.u_projection, proj_matrix.data, sizeof(float) * 16);
            EnginePerFrameStd140 typed_per_frame = make_engine_per_frame_uniforms(
                view_matrix,
                proj_matrix,
                shadow_camera_position(params),
                static_cast<float>(resolution),
                static_cast<float>(resolution),
                cascade_near,
                cascade_far);
            std::array<MaterialPipelineUniformUpload, 1> per_frame_uniforms{{
                {
                    tc_shader_find_resource_binding(shadow_shader.shader, "per_frame"),
                    &per_frame,
                    static_cast<uint32_t>(sizeof(per_frame)),
                },
            }};
            MaterialPipelineResourceView shadow_resources{};
            shadow_resources.uniforms = per_frame_uniforms.data();
            shadow_resources.uniform_count = static_cast<uint32_t>(per_frame_uniforms.size());
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                shadow_shader.shader,
                nullptr,
                shadow_resources);

            if (cached_draw_calls_.empty()) {
                end_shadow_pass();
                results.emplace_back(depth_tex2, resolution, resolution,
                                     light_space_matrix, light_index,
                                     c, cascade_near, cascade_far);
                continue;
            }

            const std::string& debug_symbol = get_debug_internal_point();
            auto capture_debug_symbol = [&](const char* entity_name) {
                if (debug_symbol.empty() || !entity_name || debug_symbol != entity_name) {
                    return;
                }
                FrameGraphCapture* capture = debug_capture();
                if (!capture) {
                    return;
                }

                end_shadow_pass();
                capture->capture_direct_via_ctx2(
                    ctx.ctx2,
                    depth_tex2,
                    resolution,
                    resolution,
                    tgfx::PixelFormat::D32F);
                ctx.ctx2->begin_pass(
                    tgfx::TextureHandle{},
                    depth_tex2,
                    nullptr,
                    1.0f,
                    false);
                ctx.ctx2->set_viewport(0, 0, resolution, resolution);
                restore_shadow_raster_state();
                ctx.ctx2->bind_shader(shadow_shader.vertex, shadow_shader.fragment);
                ctx.ctx2->use_shader_resource_layout(shadow_shader.shader);
                prepare_material_pipeline_resources(
                    *ctx.ctx2,
                    device,
                    shadow_shader.shader,
                    nullptr,
                    shadow_resources);
            };
            MaterialPipelineResourceView draw_material_resources{};
            RenderTaskList render_tasks;
            render_tasks.reserve(cached_draw_calls_.size());

            for (const auto& dc : cached_draw_calls_) {
                tc_material_phase* phase = dc.resolve_phase();
                if (!phase) continue;

                const tc_render_item* item = scene_items.item(dc.item_index);
                if (!item) {
                    tc::Log::error(
                        "[ShadowPass/tgfx2] skip draw: invalid item index %zu",
                        dc.item_index);
                    continue;
                }
                phase = resolve_render_item_material_phase(*item);
                if (!phase) {
                    continue;
                }
                tc_shader_handle final_shader = dc.final_shader;

                ShadowTaskExtension& extension = render_tasks.emplace_extension<ShadowTaskExtension>();
                RenderTask& task = render_tasks.append();
                task.extension = &extension;
                task.item_index = dc.item_index;
                task.item = item;
                task.entity = dc.entity;
                task.component = dc.component;
                task.material_phase = phase;
                task.final_shader = final_shader;
                const char* entity_name = dc.entity.name();
                task.entity_name = entity_name ? entity_name : "";
                if (item->flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) {
                    std::memcpy(
                        extension.draw_data.u_model,
                        item->model_matrix,
                        sizeof(extension.draw_data.u_model));
                } else {
                    Mat44f identity = Mat44f::identity();
                    std::memcpy(
                        extension.draw_data.u_model,
                        identity.data,
                        sizeof(extension.draw_data.u_model));
                }

                task.draw_context.view = view_matrix;
                task.draw_context.projection = proj_matrix;
                std::memcpy(
                    task.draw_context.model.data,
                    extension.draw_data.u_model,
                    sizeof(extension.draw_data.u_model));
                task.draw_context.phase = "shadow";
                task.draw_context.pass_contract = shadow_material_pass_contract();
                task.draw_context.current_tc_shader = TcShader(final_shader);
                task.draw_context.layer_mask = data.layer_mask;
                task.draw_context.render_category_mask = ctx.render_category_mask;
                task.draw_context.camera_position = shadow_camera_position(params);
                task.draw_context.viewport_width = resolution;
                task.draw_context.viewport_height = resolution;
            }

            for (RenderTask& task : render_tasks) {
                auto& extension = *static_cast<ShadowTaskExtension*>(task.extension);
                // Both paths share the same draw-scope model matrix + PerFrame
                // UBO layout. Mesh encoder binds payload-specific resources
                // such as BoneBlock. Bias is applied receiver-side while
                // sampling so the caster's projected XY footprint stays stable.
                const std::array<RenderItemNamedUniformBinding, 3> uniforms{{
                    {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame)), "shadow_draw", nullptr},
                    {"shadow_draw", &extension.draw_data, static_cast<uint32_t>(sizeof(extension.draw_data)), "shadow_draw", nullptr},
                    {"per_frame", &typed_per_frame, static_cast<uint32_t>(sizeof(typed_per_frame)), nullptr, "shadow_draw"},
                }};
                task.set_resources(&draw_material_resources, uniforms);
            }

            for (const RenderTask& task : render_tasks) {
                RenderItemDrawSubmitRequest encode_request{};
                encode_request.shader = tc_shader_get(task.final_shader);
                encode_request.shader_handle = task.final_shader;
                encode_request.device = &device;
                encode_request.mesh_vertex_input = MaterialMeshVertexInput::Position;
                encode_request.draw_context = &task.draw_context;
                encode_request.material_phase = task.material_phase;
                encode_request.phase_mark = "shadow";
                encode_request.debug_pass_name = "ShadowPass";
                encode_request.debug_entity_name = task.entity_name.c_str();
                encode_request.resources = &task.resources;
                if (!submit_render_item_draw(
                    *ctx.ctx2,
                    *task.item,
                    encode_request)) {
                    continue;
                }
                capture_debug_symbol(task.entity_name.c_str());
                restore_shadow_raster_state();
                ctx.ctx2->bind_shader(shadow_shader.vertex, shadow_shader.fragment);
                ctx.ctx2->use_shader_resource_layout(shadow_shader.shader);
                prepare_material_pipeline_resources(
                    *ctx.ctx2,
                    device,
                    shadow_shader.shader,
                    nullptr,
                    shadow_resources);
            }

            end_shadow_pass();

            results.emplace_back(depth_tex2, resolution, resolution,
                                 light_space_matrix, light_index,
                                 c, cascade_near, cascade_far);
        }
    }

    return results;
}

void ShadowPass::execute(ExecuteContext& ctx) {
    bool profile = tc_profiler_enabled();
    if (profile) tc_profiler_begin_section("ShadowPass");

    auto it = ctx.shadow_arrays.find(output_res);
    if (it == ctx.shadow_arrays.end() || it->second == nullptr) {
        if (profile) tc_profiler_end_section();
        return;
    }
    ShadowMapArrayResource* shadow_array = it->second;

    // Clear previous frame's entries
    shadow_array->clear();

    if (ctx.lights.empty()) {
        if (profile) tc_profiler_end_section();
        return;
    }

    if (!ctx.camera) {
        tc::Log::error("ShadowPass: camera is null");
        return;
    }

    // Get camera matrices
    Mat44 view_d = ctx.camera->get_view_matrix();
    Mat44 proj_d = ctx.camera->get_projection_matrix();
    Mat44f camera_view = view_d.to_float();
    Mat44f camera_projection = proj_d.to_float();
    float camera_near = static_cast<float>(ctx.camera->near_clip);
    float camera_far = static_cast<float>(ctx.camera->far_clip);

    if (!ctx.ctx2) {
        tc::Log::error("[ShadowPass] ctx.ctx2 is null — ShadowPass is tgfx2-only");
        if (profile) tc_profiler_end_section();
        return;
    }

    ShadowPassExecuteData data;
    data.scene = ctx.scene.handle();
    data.lights = ctx.lights;
    data.camera_view = camera_view;
    data.camera_projection = camera_projection;
    data.camera_near = camera_near;
    data.camera_far = camera_far;
    data.layer_mask = ctx.layer_mask;
    std::vector<ShadowMapResult> results = execute_shadow_pass_tgfx2(ctx, data);

    // Add results to shadow array
    for (const auto& result : results) {
        ShadowMapArrayEntry entry;
        entry.depth_tex2 = result.depth_tex2;
        entry.width = result.width;
        entry.height = result.height;
        entry.light_space_matrix = result.light_space_matrix;
        entry.light_index = result.light_index;
        entry.cascade_index = result.cascade_index;
        entry.cascade_split_near = result.cascade_split_near;
        entry.cascade_split_far = result.cascade_split_far;
        shadow_array->add_entry(entry);
    }

    if (profile) tc_profiler_end_section();
}

// Register ShadowPass in tc_pass_registry for C#/standalone C++ usage
TC_DEFINE_FRAME_PASS_FACTORY(ShadowPass);

void ShadowPass::register_type() {
    register_frame_pass_ShadowPass();
    _register_inspect_output_res();
    _register_inspect_caster_offset();
    _register_inspect_metadata_graph();
}

} // namespace termin
