#include "termin/render/color_pass.hpp"
#include "termin/render/camera_capability.hpp"
#include "termin/render/frame_uniforms.hpp"
#include "termin/render/material_pipeline.hpp"
#include "termin/render/material_ubo_apply.hpp"
#include "termin/render/render_item_submission.hpp"
#include "termin/render/render_task.hpp"
#include "termin/render/tgfx2_bridge.hpp"

#include <tgfx/tgfx_shader_handle.hpp>
#include <tcbase/tc_log.hpp>
#include "termin/lighting/lighting_upload.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/tc_shader_bridge.hpp"
#include <termin/render/frame_graph_capture.hpp>
extern "C" {
#include <tgfx/resources/tc_shader.h>
#include <tgfx/resources/tc_shader_registry.h>
#include "tc_profiler.h"
#include "core/tc_component.h"
#include "core/tc_drawable_protocol.h"
#include "core/tc_scene_drawable.h"
#include <tgfx/resources/tc_material.h>
#include "core/tc_scene_render_state.h"
}

#include <cmath>
#include <array>
#include <cstring>
#include <span>
#include <string>
#include <algorithm>
#include <numeric>
#include <chrono>

namespace termin {

namespace {

// Convert tc_render_state to C++ RenderState
inline RenderState convert_render_state(const tc_render_state& s) {
    RenderState rs;
    rs.polygon_mode = (s.polygon_mode == TC_POLYGON_LINE) ? PolygonMode::Line : PolygonMode::Fill;
    rs.cull = s.cull != 0;
    rs.depth_test = s.depth_test != 0;
    rs.depth_write = s.depth_write != 0;
    rs.blend = s.blend != 0;

    // Convert blend factors
    switch (s.blend_src) {
        case TC_BLEND_ZERO: rs.blend_src = BlendFactor::Zero; break;
        case TC_BLEND_ONE: rs.blend_src = BlendFactor::One; break;
        case TC_BLEND_ONE_MINUS_SRC_ALPHA: rs.blend_src = BlendFactor::OneMinusSrcAlpha; break;
        default: rs.blend_src = BlendFactor::SrcAlpha; break;
    }
    switch (s.blend_dst) {
        case TC_BLEND_ZERO: rs.blend_dst = BlendFactor::Zero; break;
        case TC_BLEND_ONE: rs.blend_dst = BlendFactor::One; break;
        case TC_BLEND_SRC_ALPHA: rs.blend_dst = BlendFactor::SrcAlpha; break;
        default: rs.blend_dst = BlendFactor::OneMinusSrcAlpha; break;
    }
    return rs;
}

inline tgfx::BlendFactor convert_blend_factor_tgfx2(BlendFactor factor) {
    switch (factor) {
        case BlendFactor::Zero: return tgfx::BlendFactor::Zero;
        case BlendFactor::One: return tgfx::BlendFactor::One;
        case BlendFactor::OneMinusSrcAlpha: return tgfx::BlendFactor::OneMinusSrcAlpha;
        case BlendFactor::SrcAlpha:
        default:
            return tgfx::BlendFactor::SrcAlpha;
    }
}

// Get global position from Entity.
inline Vec3 get_global_position(const Entity& entity) {
    return entity.transform().global_pose().lin;
}

MaterialPipelinePassContract color_material_pass_contract()
{
    MaterialPipelinePassContract contract;
    contract.debug_name = "color";
    contract.required_material_fragment_input =
        material_pipeline_standard_material_fragment_interface();
    contract.uses_material_fragment = true;
    contract.vertex_output_adapter =
        material_pipeline_standard_material_vertex_output_adapter();
    contract.static_vertex_transform =
        material_pipeline_make_static_mesh_vertex_transform_provider(
            "static",
            MeshVertexTransformProfile::Material,
            "draw_data.u_model");
    contract.skinned_vertex_transform =
        material_pipeline_make_skinned_mesh_vertex_transform_provider(
            "skinned",
            MeshVertexTransformProfile::Material,
            "draw_data.u_model");
    contract.static_vertex_transform->resources.push_back(
        material_pipeline_draw_resource_decl(
            "draw_data", TC_SHADER_STAGE_VERTEX, 64u));
    contract.skinned_vertex_transform->resources.push_back(
        material_pipeline_draw_resource_decl(
            "draw_data", TC_SHADER_STAGE_VERTEX, 64u));
    contract.foliage_vertex_transform =
        material_pipeline_make_foliage_material_vertex_transform_provider(
            "foliage");
    return contract;
}

// Convert float distance to uint32 for radix-friendly sorting.
// Preserves order: smaller distance -> smaller uint value.
inline uint32_t float_to_sortable_uint(float f) {
    uint32_t bits;
    std::memcpy(&bits, &f, sizeof(bits));
    // If negative, flip all bits; if positive, flip sign bit only
    uint32_t mask = -int32_t(bits >> 31) | 0x80000000;
    return bits ^ mask;
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

struct ColorDrawData {
    float u_model[16];
};

struct ColorTaskExtension final : RenderTaskExtension {
    ColorDrawData draw_data{};
};

RenderItemTaskPlanningContract color_task_planning_contract(
    tc_phase_mask phase,
    const MaterialPipelinePassContract& shader_contract,
    const char* debug_pass_name)
{
    RenderItemTaskPlanningContract contract{};
    contract.phase = phase;
    contract.material_phase_policy = RenderItemMaterialPhasePolicy::Required;
    contract.provided_input_mask =
        render_item_task_input_bit(RenderItemTaskInput::DrawContext);
    contract.required_input_mask =
        render_item_task_input_bit(RenderItemTaskInput::DrawContext);
    contract.accepted_vertex_transform_kind_mask =
        render_item_vertex_transform_kind_bit(VertexTransformKind::StaticMesh)
        | render_item_vertex_transform_kind_bit(VertexTransformKind::SkinnedMesh)
        | render_item_vertex_transform_kind_bit(VertexTransformKind::Foliage);
    contract.shader_contract = &shader_contract;
    contract.debug_pass_name = debug_pass_name;
    return contract;
}

bool plan_color_item_shader(
    const tc_render_item& item,
    tc_material_phase* phase,
    const MaterialPipelinePassContract& shader_contract,
    const char* debug_pass_name,
    RenderTaskList& tasks)
{
    RenderItemTaskPlanningContract contract =
        color_task_planning_contract(phase ? phase->phase : TC_PHASE_NONE,
                                     shader_contract, debug_pass_name);
    RenderItemTaskPlanningRequest request{};
    request.item = &item;
    request.material_phase = phase;
    request.candidate_shader = phase
        ? phase->shader
        : tc_shader_handle_invalid();
    request.contract = &contract;
    return plan_render_item_task(request, tasks).accepted();
}

} // anonymous namespace

ColorPass::ColorPass(const ColorPassConfig& config)
    : input_res(config.input_res),
      output_res(config.output_res),
      shadow_res(config.shadow_res),
      phase_mark(config.phase_mark),
      sort_mode(config.sort_mode),
      camera_name(config.camera_name),
      clear_depth(config.clear_depth)
{
    set_pass_name(config.pass_name);
}

std::set<const char*> ColorPass::compute_reads() const {
    std::set<const char*> result;
    result.insert(input_res.c_str());
    if (!shadow_res.empty()) {
        result.insert(shadow_res.c_str());
    }
    // Add extra texture resources
    for (const auto& [uniform_name, resource_name] : extra_textures) {
        result.insert(resource_name.c_str());
    }
    return result;
}

std::set<const char*> ColorPass::compute_writes() const {
    return {output_res.c_str()};
}

std::vector<std::pair<std::string, std::string>> ColorPass::get_inplace_aliases() const {
    return {{input_res, output_res}};
}

void ColorPass::add_extra_texture(const std::string& uniform_name, const std::string& resource_name) {
    if (resource_name.empty() || resource_name.find("empty_") == 0) {
        return;
    }
    // Ensure u_ prefix for uniform name
    std::string name = uniform_name;
    if (name.find("u_") != 0) {
        name = "u_" + name;
    }
    extra_textures[name] = resource_name;
}

std::vector<ResourceSpec> ColorPass::get_resource_specs() const {
    return {
        ResourceSpec{
            input_res,
            "fbo",                                          // resource_type
            std::nullopt,                                   // size
            std::array<double, 4>{0.2, 0.2, 0.2, 1.0},      // clear_color
            1.0f                                            // clear_depth
        }
    };
}

namespace {

struct CollectShaderUsagesData {
    const char* phase_mark = nullptr;
    tc_phase_mask phase = TC_PHASE_NONE;
    MaterialPipelinePassContract pass_contract;
    const std::function<void(TcShader)>* emit = nullptr;
};

const char* safe_component_type(const tc_component* component) {
    const char* type_name = component ? tc_component_type_name(component) : nullptr;
    return type_name ? type_name : "<unknown>";
}

bool collect_color_drawable_shader_usages(tc_component* tc, void* user_data) {
    auto* data = static_cast<CollectShaderUsagesData*>(user_data);
    if (!tc || !data || !data->phase_mark || !data->emit) {
        tc::Log::error("[ColorPass] collect_color_drawable_shader_usages: invalid callback data");
        return true;
    }

    if (!tc_phase_mask_contains(tc_component_phase_mask(tc), data->phase)) {
        return true;
    }

    RenderContext render_context;
    render_context.phase = data->phase;
    render_context.pass_contract = data->pass_contract;
    tc_render_item_collect_context item_context{};
    item_context.phase = data->phase;
    item_context.layer_mask = UINT64_MAX;
    item_context.render_category_mask = UINT64_MAX;
    item_context.debug_pass_name = "ColorPass/ShaderUsage";
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

        RenderTaskList tasks;
        if (!plan_color_item_shader(
                item,
                phase,
                data->pass_contract,
                "ColorPass/ShaderUsage",
                tasks)) {
            continue;
        }
        const RenderTask& task = tasks.at(0);
        for (uint32_t i = 0; i < task.shader_usage_count; ++i) {
            (*data->emit)(TcShader(task.shader_usages[i]));
        }
    }

    return true;
}

} // anonymous namespace

void ColorPass::collect_draw_calls(
    tc_scene_handle scene,
    const std::string& phase_mark,
    const RenderContext& render_context,
    uint64_t layer_mask,
    const RenderSceneItemSnapshot& snapshot
) {
    (void)render_context;
    (void)layer_mask;
    // Clear but keep capacity
    cached_draw_calls_.clear();

    if (!tc_scene_handle_valid(scene)) {
        tc::Log::warn("[ColorPass] collect_draw_calls: scene is invalid!");
        return;
    }

    const auto& items = snapshot.items();
    const std::span<const size_t> routed_items =
        snapshot.phase_item_indices(tc_phase_find(phase_mark.c_str()));
    cached_draw_calls_.reserve(routed_items.size());
    for (size_t item_index : routed_items) {
        const tc_render_item& item = items[item_index];
        tc_component* tc = item.component;
        if (!tc) {
            tc::Log::error(
                "[ColorPass] collect_draw_calls: collected item %zu has null component",
                item_index);
            continue;
        }

        Entity ent(tc->owner);
        if (!ent.valid()) {
            tc::Log::error(
                "[ColorPass] collect_draw_calls: drawable component '%s' has invalid owner",
                safe_component_type(tc));
            continue;
        }

        tc_material_phase* phase = resolve_render_item_material_phase(item);
        if (!phase) {
            continue;
        }

        PhaseDrawCall dc;
        dc.entity = ent;
        dc.component = tc;
        dc.phase = phase;
        dc.priority = phase->priority;
        dc.geometry_id = item.geometry_id;
        dc.item_index = item_index;
        dc.item = item;
        dc.material = item.material;
        dc.phase_index = item.material_phase_index;
        cached_draw_calls_.push_back(dc);
    }
}

void ColorPass::collect_shader_usages(
    tc_scene_handle scene,
    const std::function<void(TcShader)>& emit
) const {
    if (!emit) {
        return;
    }
    if (!tc_scene_handle_valid(scene)) {
        tc::Log::error("[ColorPass] cannot collect shader usages for invalid scene");
        return;
    }
    if (phase_mark.empty()) {
        tc::Log::error(
            "[ColorPass] pass '%s' has empty phase mark; shader usage collection requires an explicit phase",
            get_pass_name().c_str());
        return;
    }

    CollectShaderUsagesData data;
    data.phase_mark = phase_mark.c_str();
    data.phase = tc_phase_find(phase_mark.c_str());
    if (data.phase == TC_PHASE_NONE) {
        tc::Log::error(
            "[ColorPass] pass '%s' requests unregistered phase '%s'",
            get_pass_name().c_str(), phase_mark.c_str());
        return;
    }
    data.pass_contract = color_material_pass_contract();
    data.emit = &emit;

    tc_scene_foreach_drawable(
        scene,
        collect_color_drawable_shader_usages,
        &data,
        TC_SCENE_FILTER_NONE,
        0);
}

void ColorPass::compute_sort_keys(const Vec3& camera_position) {
    const size_t n = cached_draw_calls_.size();
    sort_keys_.resize(n);

    // Determine sort direction from sort_mode
    // sort_key format: [priority:16][shader_id:16][distance:32]
    // This groups objects by shader to minimize state changes,
    // while preserving priority ordering and distance-based sorting within groups.
    // For near_to_far: lower distance = lower key
    // For far_to_near: lower distance = higher key (invert distance bits)
    bool invert_distance = (sort_mode == "far_to_near");

    for (size_t i = 0; i < n; ++i) {
        const PhaseDrawCall& dc = cached_draw_calls_[i];

        // Priority in upper 16 bits (offset to handle negative)
        uint64_t priority_bits = static_cast<uint16_t>((dc.priority + 0x8000) & 0xFFFF);

        // Shader ID in next 16 bits (from final shader after overrides)
        uint64_t shader_bits = 0;
        if (dc.final_shader.is_valid()) {
            shader_bits = dc.final_shader.handle.index & 0xFFFF;
        }

        // Distance in lower 32 bits
        Vec3 pos = get_global_position(dc.entity);
        double dx = pos.x - camera_position.x;
        double dy = pos.y - camera_position.y;
        double dz = pos.z - camera_position.z;
        float dist2 = static_cast<float>(dx*dx + dy*dy + dz*dz);

        uint32_t dist_bits = float_to_sortable_uint(dist2);
        if (invert_distance) {
            dist_bits = ~dist_bits;  // Invert for far-to-near
        }

        sort_keys_[i] = (priority_bits << 48) | (shader_bits << 32) | dist_bits;
    }
}

void ColorPass::sort_draw_calls() {
    const size_t n = cached_draw_calls_.size();
    if (n <= 1) return;

    // Resize index array (reuses capacity)
    sort_indices_.resize(n);
    std::iota(sort_indices_.begin(), sort_indices_.end(), size_t(0));

    // Sort indices by sort_keys
    std::sort(sort_indices_.begin(), sort_indices_.end(),
        [this](size_t a, size_t b) {
            return sort_keys_[a] < sort_keys_[b];
        });

    // Reorder using temp buffer (reuses capacity)
    sorted_draw_calls_.clear();
    sorted_draw_calls_.reserve(n);
    for (size_t i : sort_indices_) {
        sorted_draw_calls_.push_back(std::move(cached_draw_calls_[i]));
    }
    std::swap(cached_draw_calls_, sorted_draw_calls_);
}

// ----------------------------------------------------------------------------
// ColorPass draw loop — tgfx2 native.
// ----------------------------------------------------------------------------
//
// Uses ctx2 end-to-end for pass boundary, shader binding, resource set
// (material UBO + textures), mesh draws, and state. Engine uniforms from
// legacy-looking shader source are rewritten by shader_parser into PerFrame
// UBOs, push constants, and explicit sampler bindings before tgfx2 sees them.
//
// Non-mesh drawables participate through typed RenderItems and registered
// encoders. This pass owns material state, lighting UBO, shadow samplers,
// and phase ordering.
//
// Intentionally skipped for now:
//   - shader variants where material pipeline preparation fails
//   - maybe_blit_to_debugger for the selected debug symbol
//   - GPU timing queries
// These each get a log line when they are skipped.

void ColorPass::execute_with_data(
    ExecuteContext& ctx,
    const ColorPassExecuteData& data)
{
    auto* ctx2 = ctx.ctx2;
    if (!ctx2) {
        tc::Log::error("[ColorPass/tgfx2] ctx2 is null");
        return;
    }

    auto& device = ctx2->device();

    // Resolve output textures from ctx.tex2_* — persistent FBOPool
    // wrappers, no per-frame wrap/destroy churn.
    auto color_it = ctx.tex2_writes.find(output_res);
    if (color_it == ctx.tex2_writes.end() || !color_it->second) {
        tc::Log::warn("[ColorPass/tgfx2] tgfx2 color texture for '%s' not available",
                      output_res.c_str());
        return;
    }
    tgfx::TextureHandle color_tex2 = color_it->second;

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};

    RenderSceneItemSnapshot* scene_items =
        ensure_render_item_snapshot(ctx, "ColorPass");
    if (!scene_items) {
        return;
    }

    EnginePerFrameStd140 pf = make_engine_per_frame_uniforms(
        data.view,
        data.projection,
        data.camera_position,
        static_cast<float>(data.rect.width),
        static_cast<float>(data.rect.height),
        ctx.camera ? static_cast<float>(ctx.camera->near_clip) : 0.1f,
        ctx.camera ? static_cast<float>(ctx.camera->far_clip) : 100.0f);

    // --- Shadow metadata UBO (binding 3) ------------------------------
    // Packs shadow metadata (u_shadow_map_count, u_light_space_matrix[N], ...)
    // into a std140 block so Vulkan's "no non-opaque uniforms outside a block"
    // rule is satisfied. The same layout also works on GL and is mirrored by
    // the Slang termin_shadows module.
    //
    // std140 pads each scalar-in-array to 16 bytes and each mat4 to 64.
    // MAX_SHADOW_MAPS = 16 (from lighting_upload.hpp) — hardcoded here
    // so the struct layout can be static_asserted at compile time.
    constexpr size_t SHADOW_UBO_MAX = MAX_SHADOW_MAPS;
    struct ShadowBlockStd140 {
        int   u_shadow_map_count;       // 4
        int   _pad0[3];                 // 12
        // mat4[16] = 64 * 16 = 1024
        float u_light_space_matrix[SHADOW_UBO_MAX][16];
        // int[16] with std140 vec4 alignment (4 bytes + 12 pad per element)
        int   u_shadow_light_index[SHADOW_UBO_MAX][4];
        int   u_shadow_cascade_index[SHADOW_UBO_MAX][4];
        float u_shadow_split_near[SHADOW_UBO_MAX][4];
        float u_shadow_split_far[SHADOW_UBO_MAX][4];
    };
    static_assert(sizeof(ShadowBlockStd140) ==
                  16 + 1024 + 256 + 256 + 256 + 256,
                  "ShadowBlockStd140 must match std140 layout (2064 B)");

    ShadowBlockStd140 sb{};
    {
        int sm_count = static_cast<int>(
            std::min(data.shadow_maps.size(), static_cast<size_t>(SHADOW_UBO_MAX)));
        sb.u_shadow_map_count = sm_count;
        for (int i = 0; i < sm_count; ++i) {
            const ShadowMapArrayEntry& e = data.shadow_maps[i];
            std::memcpy(sb.u_light_space_matrix[i],
                        e.light_space_matrix.data,
                        sizeof(sb.u_light_space_matrix[i]));
            sb.u_shadow_light_index[i][0]   = e.light_index;
            sb.u_shadow_cascade_index[i][0] = e.cascade_index;
            sb.u_shadow_split_near[i][0]    = e.cascade_split_near;
            sb.u_shadow_split_far[i][0]     = e.cascade_split_far;
        }
    }

    ctx2->begin_pass(color_tex2, depth_tex2,
                     /*clear_color=*/nullptr,
                     /*clear_depth=*/1.0f,
                     /*clear_depth_enabled=*/clear_depth);
    ctx2->set_viewport(0, 0, data.rect.width, data.rect.height);
    ctx2->set_depth_bias(false);

    // Collect + sort draw calls. Gathering logic is backend-agnostic.
    RenderContext collect_context;
    collect_context.view = data.view;
    collect_context.projection = data.projection;
    collect_context.phase = tc_phase_find(phase_mark.c_str());
    collect_context.pass_contract = color_material_pass_contract();
    collect_context.layer_mask = data.layer_mask;
    collect_context.render_category_mask = data.render_category_mask;
    collect_context.camera_position = data.camera_position;
    collect_context.viewport_width = data.rect.width;
    collect_context.viewport_height = data.rect.height;
    collect_context.scene = TcSceneRef(data.scene);
    collect_context.camera = const_cast<RenderCamera*>(ctx.camera);

    collect_draw_calls(
        data.scene,
        phase_mark,
        collect_context,
        data.layer_mask,
        *scene_items);

    const std::string debug_pass_name = get_pass_name();
    const char* debug_pass_name_c = debug_pass_name.c_str();
    const MaterialPipelinePassContract task_shader_contract =
        color_material_pass_contract();
    RenderItemTaskPlanningContract task_planning_contract =
        color_task_planning_contract(tc_phase_find(phase_mark.c_str()),
                                     task_shader_contract, debug_pass_name_c);
    RenderTaskList render_tasks;
    render_tasks.reserve(cached_draw_calls_.size());
    std::vector<RenderTask*> tasks_by_item_index(scene_items->item_count(), nullptr);

    // Retain only accepted draw calls in the pass scratch buffer. Each
    // accepted call points back to one owned task by its stable collected item
    // index, so sorting draw calls never moves task RAII state.
    sorted_draw_calls_.clear();
    sorted_draw_calls_.reserve(cached_draw_calls_.size());
    size_t source_draw_index = 0;
    for (PhaseDrawCall& dc : cached_draw_calls_) {
        tc_material_phase* phase = dc.resolve_phase();
        const tc_render_item* item = scene_items->item(dc.item_index);
        if (!phase || !item) {
            if (!item) {
                tc::Log::error(
                    "[ColorPass/tgfx2] skip planning: pass='%s' phase='%s' has invalid item index %zu",
                    debug_pass_name_c,
                    phase_mark.c_str(),
                    dc.item_index);
            }
            ++source_draw_index;
            continue;
        }
        phase = resolve_render_item_material_phase(*item);
        if (!phase) {
            ++source_draw_index;
            continue;
        }

        RenderItemTaskPlanningRequest planning_request{};
        planning_request.item = item;
        planning_request.item_index = dc.item_index;
        planning_request.source_draw_index = source_draw_index;
        planning_request.material_phase = phase;
        planning_request.candidate_shader = phase->shader;
        planning_request.contract = &task_planning_contract;
        RenderItemTaskPlanningResult planning_result =
            plan_render_item_task(planning_request, render_tasks);
        ++source_draw_index;
        if (!planning_result.accepted()) {
            continue;
        }

        ColorTaskExtension& extension =
            render_tasks.emplace_extension<ColorTaskExtension>();
        RenderTask& task = render_tasks.at(planning_result.task_index);
        task.extension = &extension;
        task.entity = dc.entity;
        task.component = dc.component;
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

        std::memcpy(
            task.draw_context.model.data,
            extension.draw_data.u_model,
            sizeof(extension.draw_data.u_model));
        task.draw_context.view = data.view;
        task.draw_context.projection = data.projection;
        task.draw_context.phase = tc_phase_find(phase_mark.c_str());
        task.draw_context.pass_contract = task_shader_contract;
        task.draw_context.current_tc_shader = TcShader(task.final_shader);
        task.draw_context.layer_mask = data.layer_mask;
        task.draw_context.render_category_mask = data.render_category_mask;
        task.draw_context.camera_position = data.camera_position;
        task.draw_context.viewport_width = data.rect.width;
        task.draw_context.viewport_height = data.rect.height;
        task.draw_context.camera = const_cast<RenderCamera*>(ctx.camera);

        dc.final_shader = TcShader(task.final_shader);
        tasks_by_item_index[dc.item_index] = &task;
        sorted_draw_calls_.push_back(std::move(dc));
    }
    std::swap(cached_draw_calls_, sorted_draw_calls_);

    if (sort_mode != "none" && !cached_draw_calls_.empty()) {
        compute_sort_keys(data.camera_position);
        sort_draw_calls();
    } else if (!cached_draw_calls_.empty()) {
        std::sort(cached_draw_calls_.begin(), cached_draw_calls_.end(),
            [](const PhaseDrawCall& a, const PhaseDrawCall& b) {
                return a.priority < b.priority;
            });
    }

    std::vector<RenderTask*> sorted_render_tasks;
    sorted_render_tasks.reserve(cached_draw_calls_.size());
    for (const PhaseDrawCall& dc : cached_draw_calls_) {
        RenderTask* task = tasks_by_item_index[dc.item_index];
        if (!task) {
            tc::Log::error(
                "[ColorPass/tgfx2] accepted draw has no planned task: pass='%s' item=%zu",
                debug_pass_name_c,
                dc.item_index);
            continue;
        }
        sorted_render_tasks.push_back(task);
    }

    // Allocate lighting UBO directly on the tgfx2 device and upload this
    // frame's data for the color batch. Whether a shader consumes it is now
    // decided by reflected resources during binding, not by legacy feature
    // flags that material-pipeline variants may not own at collection time.
    tgfx::BufferHandle lighting_ubo_tgfx2{};
    if (!cached_draw_calls_.empty()) {
        lighting_ubo_.create(device);
        lighting_ubo_.update_from_lights(
            data.lights,
            data.ambient_color,
            data.ambient_intensity,
            data.camera_position,
            data.shadow_settings);
        lighting_ubo_.upload();
        lighting_ubo_tgfx2 = lighting_ubo_.buffer;
    }

    // Shadow maps are now native tgfx2 depth textures owned by
    // ShadowPass; no per-frame wrap needed.
    std::vector<tgfx::TextureHandle> shadow_tex2s;
    shadow_tex2s.reserve(data.shadow_maps.size());
    for (const auto& smap : data.shadow_maps) {
        shadow_tex2s.push_back(smap.depth_tex2);
    }

    entity_names.clear();
    entity_names.reserve(cached_draw_calls_.size());
    const std::string* requested_debug_symbol = ctx.requested_internal_symbol();
    const std::string debug_symbol = requested_debug_symbol
        ? *requested_debug_symbol : std::string{};
    if (debug_symbol.empty()) {
        selected_symbol_timing = {};
    }
    auto capture_debug_symbol = [&](const char* entity_name) {
        if (!ctx.should_capture_internal(entity_name)) {
            return;
        }

        ctx2->end_pass();
        ctx.capture_internal(
            entity_name, color_tex2, data.rect.width, data.rect.height);
        selected_symbol_timing = {};
        selected_symbol_timing.name = debug_symbol;

        ctx2->begin_pass(color_tex2, depth_tex2,
                         /*clear_color=*/nullptr,
                         /*clear_depth=*/1.0f,
                         /*clear_depth_enabled=*/false);
        ctx2->set_viewport(0, 0, data.rect.width, data.rect.height);
        ctx2->set_depth_bias(false);
    };

    MaterialPipelineResourceView material_resources{};
    material_resources.per_frame = &pf;
    material_resources.shadow_block = &sb;
    material_resources.shadow_block_size = static_cast<uint32_t>(sizeof(sb));
    material_resources.lighting_ubo = lighting_ubo_tgfx2;
    material_resources.shadow_maps = shadow_tex2s.data();
    material_resources.shadow_map_count = static_cast<uint32_t>(
        std::min<size_t>(shadow_tex2s.size(), MAX_SHADOW_MAPS));

    std::vector<RenderItemNamedTextureBinding> extra_texture_bindings;
    extra_texture_bindings.reserve(extra_textures.size());
    for (const auto& [uniform_name, resource_name] : extra_textures) {
        auto it = ctx.tex2_reads.find(resource_name);
        if (it == ctx.tex2_reads.end() || !it->second) {
            tc::Log::warn(
                "[ColorPass:%s] tgfx2 texture not found for resource: %s",
                get_pass_name().c_str(),
                resource_name.c_str());
            continue;
        }
        extra_texture_bindings.push_back(RenderItemNamedTextureBinding{
            uniform_name.c_str(),
            it->second,
            tgfx::SamplerHandle{}});
    }

    for (const RenderTask* task : sorted_render_tasks) {
        entity_names.push_back(task->entity_name);
    }

    if (!render_tasks.empty() && !shadow_sampler_) {
        tgfx::SamplerDesc sd;
        sd.min_filter = tgfx::FilterMode::Nearest;
        sd.mag_filter = tgfx::FilterMode::Nearest;
        sd.mip_filter = tgfx::FilterMode::Nearest;
        // ClampToEdge + clear-depth 1.0 gives the same "outside
        // frustum = not in shadow" behaviour as GL's ClampToBorder
        // + white border: sampling beyond the shadow map returns a
        // texel cleared to the far plane, and LessOrEqual below
        // passes the compare.
        sd.address_u = tgfx::AddressMode::ClampToEdge;
        sd.address_v = tgfx::AddressMode::ClampToEdge;
        sd.address_w = tgfx::AddressMode::ClampToEdge;
        sd.compare_enable = true;
        sd.compare_op = tgfx::CompareOp::LessEqual;
        shadow_sampler_ = device.create_sampler(sd);
    }
    material_resources.shadow_sampler = shadow_sampler_;

    for (RenderTask& task : render_tasks) {
        auto& extension = *static_cast<ColorTaskExtension*>(task.extension);
        const std::array<RenderItemNamedUniformBinding, 1> uniforms{{
            {"draw_data", &extension.draw_data, static_cast<uint32_t>(sizeof(extension.draw_data)), "draw_data", nullptr},
        }};
        task.set_resources(&material_resources, uniforms, extra_texture_bindings);
    }

    for (const RenderTask* task_ptr : sorted_render_tasks) {
        const RenderTask& task = *task_ptr;
        // Every material draw owns its descriptor set. Material textures are
        // optional at runtime; if one is missing, the Vulkan backend fills
        // that slot with its default texture. Without this reset, a missing
        // slot kept the previous draw/pass texture bound and produced
        // striped materials after resize/post-processing passes.
        ctx2->clear_resource_bindings();

        // Render state from the material phase.
        RenderState state = convert_render_state(task.material_phase->state);
        if (wireframe) state.polygon_mode = PolygonMode::Line;

        ctx2->set_depth_test(state.depth_test);
        ctx2->set_depth_write(state.depth_write);
        ctx2->set_blend(state.blend);
        ctx2->set_blend_func(convert_blend_factor_tgfx2(state.blend_src),
                             convert_blend_factor_tgfx2(state.blend_dst));
        ctx2->set_cull(state.cull ? tgfx::CullMode::Back : tgfx::CullMode::None);
        ctx2->set_polygon_mode(state.polygon_mode == PolygonMode::Line
                               ? tgfx::PolygonMode::Line
                               : tgfx::PolygonMode::Fill);

        RenderItemDrawSubmitRequest encode_request{};
        encode_request.shader = tc_shader_get(task.final_shader);
        encode_request.shader_handle = task.final_shader;
        encode_request.device = &device;
        encode_request.mesh_vertex_input = MaterialMeshVertexInput::FullMaterial;
        encode_request.draw_context = &task.draw_context;
        encode_request.material_phase = task.material_phase;
        encode_request.phase = tc_phase_find(phase_mark.c_str());
        encode_request.debug_pass_name = debug_pass_name_c;
        encode_request.debug_entity_name = task.entity_name.c_str();
        encode_request.resources = &task.resources;
        if (!submit_render_item_draw(
            *ctx2,
            *task.item,
            encode_request)) {
            continue;
        }
        capture_debug_symbol(task.entity_name.c_str());
    }

    ctx2->end_pass();
}

void ColorPass::execute(ExecuteContext& ctx) {
    bool profile = tc_profiler_enabled();
    if (profile) tc_profiler_begin_section(("ColorPass:" + get_pass_name()).c_str());

    // Use camera from context, or find by name if camera_name is set
    const RenderCamera* camera = ctx.camera;
    tc_scene_handle scene = ctx.scene.handle();
    if (!tc_scene_handle_valid(scene)) {
        tc::Log::error("[ColorPass] scene is invalid");
        if (profile) tc_profiler_end_section();
        return;
    }
    RenderCameraSnapshot named_camera_snapshot;
    uint64_t camera_layer_mask = ctx.layer_mask;
    uint64_t camera_render_category_mask = ctx.render_category_mask;
    if (!camera_name.empty()) {
        if (!resolve_named_render_camera_for_pass(
                scene,
                camera_name.c_str(),
                0.0,
                "ColorPass",
                named_camera_snapshot)) {
            if (profile) tc_profiler_end_section();
            return;
        }
        camera = &named_camera_snapshot.camera;
        camera_layer_mask = named_camera_snapshot.layer_mask;
        camera_render_category_mask = named_camera_snapshot.render_category_mask;
    }

    if (!camera) {
        if (profile) tc_profiler_end_section();
        return;
    }

    // extra_textures are resolved inside execute_with_data after a ctx2
    // shader is bound so the active pass owns the texture bindings.

    // Get output size from the tgfx2 color texture and update rect.
    Rect2i rect = ctx.render_rect;
    if (ctx.ctx2) {
        auto it = ctx.tex2_writes.find(output_res);
        if (it != ctx.tex2_writes.end() && it->second) {
            auto desc = ctx.ctx2->device().texture_desc(it->second);
            int w = static_cast<int>(desc.width);
            int h = static_cast<int>(desc.height);
            if (w > 0 && h > 0) {
                rect = Rect2i{0, 0, w, h};
                if (!camera_name.empty()) {
                    if (!resolve_named_render_camera_for_pass(
                            scene,
                            camera_name.c_str(),
                            static_cast<double>(w) / std::max(1, h),
                            "ColorPass",
                            named_camera_snapshot)) {
                        if (profile) tc_profiler_end_section();
                        return;
                    }
                    camera = &named_camera_snapshot.camera;
                    camera_layer_mask = named_camera_snapshot.layer_mask;
                    camera_render_category_mask = named_camera_snapshot.render_category_mask;
                }
            }
        }
    }

    // Get camera matrices
    Mat44 view64 = camera->get_view_matrix();
    Mat44 proj64 = camera->get_projection_matrix();
    Mat44f view = view64.to_float();
    Mat44f projection = proj64.to_float();

    // Get camera position
    Vec3 camera_position = camera->get_position();

    // Get scene lighting properties
    Vec3 ambient_color{1.0, 1.0, 1.0};
    float ambient_intensity = 0.1f;
    ShadowSettings shadow_settings;

    if (tc_scene_handle_valid(scene)) {
        tc_scene_render_state* render_state = tc_scene_render_state_get(scene);
        tc_scene_lighting* lighting = render_state ? &render_state->lighting : nullptr;
        if (lighting) {
            ambient_color = Vec3{
                lighting->ambient_color[0],
                lighting->ambient_color[1],
                lighting->ambient_color[2]
            };
            ambient_intensity = lighting->ambient_intensity;
            shadow_settings.method = lighting->shadow_method;
            shadow_settings.softness = lighting->shadow_softness;
            shadow_settings.bias = lighting->shadow_bias;
        }
    }

    std::vector<ShadowMapArrayEntry> shadow_maps;
    if (!shadow_res.empty()) {
        auto shadow_it = ctx.shadow_arrays.find(shadow_res);
        if (shadow_it != ctx.shadow_arrays.end() && shadow_it->second != nullptr) {
            shadow_maps = shadow_it->second->entries;
        }
    }

    if (!ctx.ctx2) {
        tc::Log::error("[ColorPass] ctx.ctx2 is null — ColorPass is tgfx2-only");
        return;
    }

    ColorPassExecuteData data;
    data.rect = rect;
    data.scene = scene;
    data.view = view;
    data.projection = projection;
    data.camera_position = camera_position;
    data.lights = ctx.lights;
    data.ambient_color = ambient_color;
    data.ambient_intensity = ambient_intensity;
    data.shadow_maps = shadow_maps;
    data.shadow_settings = shadow_settings;
    data.layer_mask = camera_layer_mask;
    data.render_category_mask = camera_render_category_mask;
    execute_with_data(ctx, data);

    if (profile) tc_profiler_end_section();
}

// Register ColorPass in tc_pass_registry for C#/standalone C++ usage
void ColorPass::register_type() {
    auto descriptor = FramePassTypeDescriptorBuilder::native<ColorPass>(
        "ColorPass", "termin-render-passes");
    auto& inspect = descriptor.inspect();
    _register_inspect_input_res(inspect);
    _register_inspect_output_res(inspect);
    _register_inspect_shadow_res(inspect);
    _register_inspect_phase_mark(inspect);
    _register_inspect_sort_mode(inspect);
    _register_inspect_clear_depth(inspect);
    _register_inspect_camera_name(inspect);
    _register_inspect_metadata_graph(inspect);
    (void)descriptor.commit();
}

} // namespace termin
