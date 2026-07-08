#include "termin/render/color_pass.hpp"
#include "termin/camera/render_camera_utils.hpp"
#include "termin/render/frame_uniforms.hpp"
#include "termin/render/material_pipeline.hpp"
#include "termin/render/material_ubo_apply.hpp"
#include "termin/render/render_item_submission.hpp"
#include "termin/render/shader_abi.hpp"
#include "termin/render/shader_resource_apply.hpp"
#include "termin/render/tgfx2_bridge.hpp"

#include <optional>
#include <tgfx/tgfx_shader_handle.hpp>
#include <tcbase/tc_log.hpp>
#include "termin/lighting/lighting_upload.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/tc_shader_bridge.hpp"
#include <termin/render/frame_graph_debugger_core.hpp>
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

    MaterialFragmentInterface fragment_input =
        material_pipeline_standard_material_fragment_interface();
    contract.static_vertex_transform =
        material_pipeline_make_static_vertex_transform_contract(
            "static",
            material_pipeline_full_material_mesh_input(),
            fragment_input,
            material_pipeline_common_vertex_resources("draw_data"));
    contract.skinned_vertex_transform =
        material_pipeline_make_skinned_vertex_transform_contract(
            *contract.static_vertex_transform,
            "skinned",
            "termin-engine-skinned-material",
            material_pipeline_skinned_material_mesh_input());
    contract.foliage_vertex_transform =
        material_pipeline_make_foliage_vertex_transform_contract(
            VertexTransformKind::Foliage,
            "foliage",
            "termin-engine-foliage-instanced",
            material_pipeline_foliage_material_mesh_input(),
            fragment_input,
            material_pipeline_foliage_vertex_resources());
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

template <typename T>
void bind_draw_data_for_shader(
    tgfx::RenderContext2& ctx,
    const tc_shader* shader,
    const T& payload)
{
    const tc_shader_resource_binding* rb =
        find_shader_abi_resource_binding(shader, ShaderAbiResourceId::DrawData);
    if (rb) {
        ctx.bind_uniform_data(rb, &payload, sizeof(payload));
        return;
    }
    if (shader && tc_shader_has_resource_layout(shader)) {
        return;
    }
    tc::Log::error(
        "[ColorPass/tgfx2] shader '%s' is missing draw_data resource layout entry",
        shader && shader->name ? shader->name : "<unnamed>");
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

void ColorPass::bind_extra_textures(
    const Tex2Map& tex2_reads,
    tgfx::RenderContext2* ctx2,
    const tc_shader* shader
) {
    extra_texture_uniforms.clear();
    if (!ctx2) return;
    if (!shader) {
        tc::Log::error(
            "[ColorPass:%s] cannot bind extra textures without active shader layout",
            get_pass_name().c_str());
        return;
    }

    for (const auto& [uniform_name, resource_name] : extra_textures) {
        auto it = tex2_reads.find(resource_name);
        if (it == tex2_reads.end() || !it->second) {
            tc::Log::warn("[ColorPass:%s] tgfx2 texture not found for resource: %s",
                         get_pass_name().c_str(), resource_name.c_str());
            continue;
        }

        const tc_shader_resource_binding* rb =
            tc_shader_find_resource_binding(shader, uniform_name.c_str());
        if (!rb || rb->kind != TC_SHADER_RESOURCE_TEXTURE) {
            tc::Log::error(
                "[ColorPass:%s] extra texture '%s' cannot be bound to '%s': "
                "shader does not declare a Texture2D resource with that name",
                get_pass_name().c_str(),
                resource_name.c_str(),
                uniform_name.c_str());
            continue;
        }

        ctx2->bind_texture(uniform_name, it->second);
    }
}

CameraComponent* ColorPass::find_camera_by_name(tc_scene_handle scene, const std::string& name) {
    if (name.empty() || !tc_scene_handle_valid(scene)) {
        return nullptr;
    }

    // Search in scene entities
    // TODO: This requires iterating scene entities and finding CameraComponent
    // For now, return nullptr - camera lookup by name needs scene iteration support
    return nullptr;
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

    if (data->phase_mark[0] != '\0' && !tc_component_has_phase(tc, data->phase_mark)) {
        return true;
    }

    RenderContext render_context;
    render_context.phase = data->phase_mark;
    render_context.pass_contract = data->pass_contract;
    tc_render_item_collect_context item_context{};
    item_context.phase_mark = data->phase_mark;
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

        ShaderOverrideContext override_context;
        override_context.phase_mark = data->phase_mark;
        override_context.geometry_id = item.geometry_id;
        override_context.original_shader = TcShader(phase->shader);
        override_context.pass_contract = data->pass_contract;
        collect_drawable_shader_usages_with_context(tc, override_context, *data->emit);
    }

    return true;
}

} // anonymous namespace

void ColorPass::collect_draw_calls(
    tc_scene_handle scene,
    const std::string& phase_mark,
    const RenderContext& render_context,
    uint64_t layer_mask,
    RenderSceneItemCollector& collector
) {
    // Clear but keep capacity
    cached_draw_calls_.clear();

    if (!tc_scene_handle_valid(scene)) {
        tc::Log::warn("[ColorPass] collect_draw_calls: scene is invalid!");
        return;
    }

    MaterialPipelinePassContract pass_contract = color_material_pass_contract();
    RenderSceneItemCollectRequest request{};
    request.scene = scene;
    request.phase_mark = phase_mark.c_str();
    request.layer_mask = layer_mask;
    request.render_category_mask = render_context.render_category_mask;
    request.debug_pass_name = "ColorPass";
    request.pass_contract = &pass_contract;
    request.camera = render_context.camera;
    if (!collector.collect(request)) {
        tc::Log::error(
            "[ColorPass] collect_draw_calls: item collection failed for phase '%s'",
            phase_mark.c_str());
    }

    const auto& items = collector.items();
    cached_draw_calls_.reserve(items.size());
    for (size_t item_index = 0; item_index < items.size(); ++item_index) {
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

        ShaderOverrideContext override_context;
        override_context.phase_mark = phase_mark;
        override_context.geometry_id = item.geometry_id;
        override_context.original_shader = TcShader(phase->shader);
        override_context.pass_contract = pass_contract;
        tc_shader_handle final_shader =
            override_drawable_shader(tc, override_context).handle;

        PhaseDrawCall dc;
        dc.entity = ent;
        dc.component = tc;
        dc.phase = phase;
        dc.final_shader = final_shader;
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
        if (!tc_shader_handle_is_invalid(dc.final_shader)) {
            shader_bits = dc.final_shader.index & 0xFFFF;
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
    collect_context.phase = phase_mark;
    collect_context.pass_contract = color_material_pass_contract();
    collect_context.layer_mask = data.layer_mask;
    collect_context.render_category_mask = ctx.render_category_mask;
    collect_context.camera_position = data.camera_position;
    collect_context.viewport_width = data.rect.width;
    collect_context.viewport_height = data.rect.height;
    collect_context.scene = TcSceneRef(data.scene);
    collect_context.camera = const_cast<RenderCamera*>(ctx.camera);

    RenderSceneItemCollector scene_items;
    collect_draw_calls(
        data.scene,
        phase_mark,
        collect_context,
        data.layer_mask,
        scene_items);

    if (sort_mode != "none" && !cached_draw_calls_.empty()) {
        compute_sort_keys(data.camera_position);
        sort_draw_calls();
    } else if (!cached_draw_calls_.empty()) {
        std::sort(cached_draw_calls_.begin(), cached_draw_calls_.end(),
            [](const PhaseDrawCall& a, const PhaseDrawCall& b) {
                return a.priority < b.priority;
            });
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
    const std::string& debug_symbol = get_debug_internal_point();
    if (debug_symbol.empty()) {
        selected_symbol_timing = {};
    }
    auto capture_debug_symbol = [&](const char* entity_name) {
        if (debug_symbol.empty() || !entity_name || debug_symbol != entity_name) {
            return;
        }
        FrameGraphCapture* capture = debug_capture();
        if (!capture) {
            return;
        }

        ctx2->end_pass();
        capture->capture_direct_via_ctx2(ctx2, color_tex2, data.rect.width, data.rect.height);
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

    size_t draw_index = 0;
    const std::string debug_pass_name = get_pass_name();
    const char* debug_pass_name_c = debug_pass_name.c_str();

    for (const auto& dc : cached_draw_calls_) {
        if (!dc.component) {
            tc::Log::error(
                "[ColorPass/tgfx2] skip draw: pass='%s' phase='%s' index=%zu has null component",
                get_pass_name().c_str(),
                phase_mark.c_str(),
                draw_index);
            ++draw_index;
            continue;
        }
        if (!dc.entity.valid()) {
            tc::Log::error(
                "[ColorPass/tgfx2] skip draw: pass='%s' phase='%s' index=%zu component='%s' has invalid entity",
                get_pass_name().c_str(),
                phase_mark.c_str(),
                draw_index,
                safe_component_type(dc.component));
            ++draw_index;
            continue;
        }
        tc_material_phase* phase = dc.resolve_phase();
        if (!phase) {
            tc::Log::error(
                "[ColorPass/tgfx2] skip draw: pass='%s' phase='%s' index=%zu entity='%s' component='%s' has null material phase",
                get_pass_name().c_str(),
                phase_mark.c_str(),
                draw_index,
                dc.entity.name() ? dc.entity.name() : "<unnamed>",
                safe_component_type(dc.component));
            ++draw_index;
            continue;
        }

        const char* ename = dc.entity.name();
        entity_names.push_back(ename ? ename : "");

        tc_shader_handle final_shader = dc.final_shader;
        const tc_render_item* item = scene_items.item(dc.item_index);
        if (!item) {
            tc::Log::error(
                "[ColorPass/tgfx2] skip draw: pass='%s' phase='%s' index=%zu has invalid item index %zu",
                get_pass_name().c_str(),
                phase_mark.c_str(),
                draw_index,
                dc.item_index);
            ++draw_index;
            continue;
        }
        phase = resolve_render_item_material_phase(*item);
        if (!phase) {
            ++draw_index;
            continue;
        }

        // Every material draw owns its descriptor set. Material textures are
        // optional at runtime; if one is missing, the Vulkan backend fills
        // that slot with its default texture. Without this reset, a missing
        // slot kept the previous draw/pass texture bound and produced
        // striped materials after resize/post-processing passes.
        ctx2->clear_resource_bindings();

        // Render state from the material phase.
        RenderState state = convert_render_state(phase->state);
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

        if (!shadow_sampler_) {
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

        struct ColorPushData {
            float u_model[16];
        };
        ColorPushData push{};
        if (item->flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) {
            std::memcpy(push.u_model, item->model_matrix, sizeof(push.u_model));
        } else {
            Mat44f identity = Mat44f::identity();
            std::memcpy(push.u_model, identity.data, sizeof(push.u_model));
        }

        RenderContext draw_context;
        draw_context.view = data.view;
        draw_context.projection = data.projection;
        std::memcpy(draw_context.model.data, push.u_model, sizeof(push.u_model));
        draw_context.phase = phase_mark;
        draw_context.pass_contract = color_material_pass_contract();
        draw_context.current_tc_shader = TcShader(final_shader);
        draw_context.layer_mask = data.layer_mask;
        draw_context.render_category_mask = ctx.render_category_mask;
        draw_context.camera_position = data.camera_position;
        draw_context.viewport_width = data.rect.width;
        draw_context.viewport_height = data.rect.height;
        draw_context.camera = const_cast<RenderCamera*>(ctx.camera);

        RenderItemDrawSubmitRequest encode_request{};
        encode_request.shader = tc_shader_get(final_shader);
        encode_request.shader_handle = final_shader;
        encode_request.device = &device;
        encode_request.mesh_vertex_input = MaterialMeshVertexInput::FullMaterial;
        encode_request.draw_context = &draw_context;
        encode_request.material_phase = phase;
        encode_request.phase_mark = phase_mark.c_str();
        encode_request.debug_pass_name = debug_pass_name_c;
        encode_request.debug_entity_name = ename;
        encode_request.prepare_material_resources =
            [this,
             &device,
             &material_resources,
             &ctx,
             &push](
                tgfx::RenderContext2& draw_ctx,
                const tc_shader* shader,
                tc_material_phase* live_phase) {
                if (!shader || !live_phase) {
                    tc::Log::error(
                        "[ColorPass/tgfx2] RenderItem resource callback called without shader or phase");
                    return;
                }

                MaterialPipelineResourceView draw_resources = material_resources;
                draw_resources.shadow_sampler = shadow_sampler_;
                prepare_material_pipeline_resources(
                    draw_ctx,
                    device,
                    shader,
                    live_phase,
                    draw_resources);

                if (!extra_textures.empty()) {
                    bind_extra_textures(ctx.tex2_reads, &draw_ctx, shader);
                }

                bind_draw_data_for_shader(draw_ctx, shader, push);
            };
        if (!submit_render_item_draw(
            *ctx2,
            *item,
            encode_request)) {
            ++draw_index;
            continue;
        }
        capture_debug_symbol(ename);
        ++draw_index;
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
    std::optional<RenderCamera> named_camera_snapshot;
    if (!camera_name.empty()) {
        CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
        if (named_camera) {
            named_camera_snapshot = make_render_camera(*named_camera);
            camera = &*named_camera_snapshot;
        } else {
            // Camera not found, skip pass
            if (profile) tc_profiler_end_section();
            return;
        }
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
    data.layer_mask = ctx.layer_mask;
    execute_with_data(ctx, data);

    if (profile) tc_profiler_end_section();
}

// Register ColorPass in tc_pass_registry for C#/standalone C++ usage
TC_REGISTER_FRAME_PASS(ColorPass);

} // namespace termin
