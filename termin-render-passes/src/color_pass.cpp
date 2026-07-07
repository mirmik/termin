#include "termin/render/color_pass.hpp"
#include "termin/camera/render_camera_utils.hpp"
#include "termin/render/frame_uniforms.hpp"
#include "termin/render/material_pipeline.hpp"
#include "termin/render/material_ubo_apply.hpp"
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

} // anonymous namespace

ColorPass::ColorPass(
    const std::string& input_res,
    const std::string& output_res,
    const std::string& shadow_res,
    const std::string& phase_mark,
    const std::string& pass_name,
    const std::string& sort_mode,
    bool clear_depth,
    const std::string& camera_name
) : input_res(input_res),
    output_res(output_res),
    shadow_res(shadow_res),
    phase_mark(phase_mark),
    sort_mode(sort_mode),
    camera_name(camera_name),
    clear_depth(clear_depth)
{
    set_pass_name(pass_name);
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

// User data for drawable iteration callback
struct CollectDrawCallsData {
    std::vector<PhaseDrawCall>* draw_calls;
    const char* phase_mark;
    MaterialPipelinePassContract pass_contract;
    const RenderContext* render_context;
};

struct CollectShaderUsagesData {
    const char* phase_mark = nullptr;
    MaterialPipelinePassContract pass_contract;
    const std::function<void(TcShader)>* emit = nullptr;
};

const char* safe_component_type(const tc_component* component) {
    const char* type_name = component ? tc_component_type_name(component) : nullptr;
    return type_name ? type_name : "<unknown>";
}

// Callback for tc_scene_foreach_drawable
bool collect_drawable_draw_calls(tc_component* tc, void* user_data) {
    auto* data = static_cast<CollectDrawCallsData*>(user_data);
    if (!tc || !data || !data->draw_calls || !data->phase_mark) {
        tc::Log::error("[ColorPass] collect_drawable_draw_calls: invalid callback data");
        return true;
    }

    // Filter by phase_mark
    if (data->phase_mark[0] != '\0' && !tc_component_has_phase(tc, data->phase_mark)) {
        return true;
    }

    void* draws_ptr = tc_component_get_geometry_draws(
        tc,
        const_cast<RenderContext*>(data->render_context),
        data->phase_mark);
    if (!draws_ptr) {
        return true;
    }
    auto* geometry_draws = static_cast<std::vector<GeometryDrawCall>*>(draws_ptr);

    // Build Entity from component's owner
    Entity ent(tc->owner);
    if (!ent.valid()) {
        tc::Log::error(
            "[ColorPass] collect_drawable_draw_calls: drawable component '%s' has invalid owner",
            safe_component_type(tc));
        return true;
    }

    for (const auto& gd : *geometry_draws) {
        tc_material_phase* phase = gd.resolve_phase();
        if (phase) {
            // Get final shader with overrides (skinning, etc.) applied
            tc_shader_handle base_shader = phase->shader;
            ShaderOverrideContext override_context;
            override_context.phase_mark = data->phase_mark;
            override_context.geometry_id = gd.geometry_id;
            override_context.original_shader = TcShader(base_shader);
            override_context.pass_contract = data->pass_contract;
            tc_shader_handle final_shader =
                override_drawable_shader(tc, override_context).handle;

            PhaseDrawCall dc;
            dc.entity = ent;
            dc.component = tc;
            dc.phase = phase;
            dc.final_shader = final_shader;
            dc.priority = phase->priority;
            dc.geometry_id = gd.geometry_id;
            dc.material = gd.material;
            dc.phase_index = gd.phase_index;
            data->draw_calls->push_back(dc);
        }
    }

    return true;
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
    void* draws_ptr = tc_component_get_geometry_draws(
        tc,
        &render_context,
        data->phase_mark);
    if (!draws_ptr) {
        return true;
    }

    auto* geometry_draws = static_cast<std::vector<GeometryDrawCall>*>(draws_ptr);
    for (const auto& gd : *geometry_draws) {
        tc_material_phase* phase = gd.resolve_phase();
        if (!phase) {
            continue;
        }

        ShaderOverrideContext override_context;
        override_context.phase_mark = data->phase_mark;
        override_context.geometry_id = gd.geometry_id;
        override_context.original_shader = TcShader(phase->shader);
        override_context.pass_contract = data->pass_contract;
        collect_drawable_shader_usages_with_context(tc, override_context, *data->emit);
    }

    return true;
}

bool same_shader_handle(tc_shader_handle a, tc_shader_handle b) {
    return a.index == b.index && a.generation == b.generation;
}

struct ResolvedDrawPhase {
    tc_material_phase* phase = nullptr;
    tc_shader_handle final_shader = tc_shader_handle_invalid();
};

ResolvedDrawPhase resolve_draw_phase(
    tc_component* component,
    const RenderContext& render_context,
    const std::string& phase_mark,
    int geometry_id,
    tc_material_handle expected_material,
    size_t expected_phase_index,
    const MaterialPipelinePassContract& pass_contract
) {
    ResolvedDrawPhase resolved;
    if (!component) {
        return resolved;
    }

    void* draws_ptr = tc_component_get_geometry_draws(
        component,
        const_cast<RenderContext*>(&render_context),
        phase_mark.c_str());
    if (!draws_ptr) {
        return resolved;
    }
    auto* geometry_draws = static_cast<std::vector<GeometryDrawCall>*>(draws_ptr);
    for (const GeometryDrawCall& gd : *geometry_draws) {
        tc_material_phase* phase = gd.resolve_phase();
        if (!phase || gd.geometry_id != geometry_id) {
            continue;
        }
        if (!tc_material_handle_is_invalid(expected_material) &&
            (!tc_material_handle_eq(gd.material, expected_material) ||
             gd.phase_index != expected_phase_index)) {
            continue;
        }

        ShaderOverrideContext override_context;
        override_context.phase_mark = phase_mark;
        override_context.geometry_id = geometry_id;
        override_context.original_shader = TcShader(phase->shader);
        override_context.pass_contract = pass_contract;
        tc_shader_handle final_shader =
            override_drawable_shader(component, override_context).handle;

        resolved.phase = phase;
        resolved.final_shader = final_shader;
        return resolved;
    }

    return resolved;
}

} // anonymous namespace

void ColorPass::collect_draw_calls(
    tc_scene_handle scene,
    const std::string& phase_mark,
    const RenderContext& render_context,
    uint64_t layer_mask
) {
    // Clear but keep capacity
    cached_draw_calls_.clear();

    if (!tc_scene_handle_valid(scene)) {
        tc::Log::warn("[ColorPass] collect_draw_calls: scene is invalid!");
        return;
    }

    // Collect draw calls via drawable iteration
    CollectDrawCallsData data;
    data.draw_calls = &cached_draw_calls_;
    data.phase_mark = phase_mark.c_str();
    data.pass_contract = color_material_pass_contract();
    data.render_context = &render_context;

    // Use tc_scene_foreach_drawable with filtering
    int filter_flags = TC_SCENE_FILTER_ENABLED
                     | TC_SCENE_FILTER_VISIBLE
                     | TC_SCENE_FILTER_ENTITY_ENABLED;
    tc_scene_foreach_drawable(scene, collect_drawable_draw_calls, &data, filter_flags, layer_mask);
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
// Direct non-mesh drawables may still participate by implementing
// Drawable::draw_tgfx2(). They bind their own geometry shaders, while this
// pass owns material state, lighting UBO, shadow samplers, and phase ordering.
//
// Intentionally skipped for now:
//   - shader variants where material pipeline preparation fails
//   - maybe_blit_to_debugger for the selected debug symbol
//   - GPU timing queries
// These each get a log line when they are skipped.

void ColorPass::execute_with_data(
    ExecuteContext& ctx,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    const Vec3& camera_position,
    const std::vector<Light>& lights,
    const Vec3& ambient_color,
    float ambient_intensity,
    const std::vector<ShadowMapArrayEntry>& shadow_maps,
    const ShadowSettings& shadow_settings,
    uint64_t layer_mask)
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
        view,
        projection,
        camera_position,
        static_cast<float>(rect.width),
        static_cast<float>(rect.height),
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
            std::min(shadow_maps.size(), static_cast<size_t>(SHADOW_UBO_MAX)));
        sb.u_shadow_map_count = sm_count;
        for (int i = 0; i < sm_count; ++i) {
            const ShadowMapArrayEntry& e = shadow_maps[i];
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
    ctx2->set_viewport(0, 0, rect.width, rect.height);
    ctx2->set_depth_bias(false);

    // Collect + sort draw calls. Gathering logic is backend-agnostic.
    RenderContext collect_context;
    collect_context.view = view;
    collect_context.projection = projection;
    collect_context.phase = phase_mark;
    collect_context.pass_contract = color_material_pass_contract();
    collect_context.layer_mask = layer_mask;
    collect_context.render_category_mask = ctx.render_category_mask;
    collect_context.camera_position = camera_position;
    collect_context.viewport_width = rect.width;
    collect_context.viewport_height = rect.height;
    collect_context.scene = TcSceneRef(scene);
    collect_context.camera = const_cast<RenderCamera*>(ctx.camera);

    collect_draw_calls(scene, phase_mark, collect_context, layer_mask);

    if (sort_mode != "none" && !cached_draw_calls_.empty()) {
        compute_sort_keys(camera_position);
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
        lighting_ubo_.update_from_lights(lights, ambient_color, ambient_intensity,
                                         camera_position, shadow_settings);
        lighting_ubo_.upload();
        lighting_ubo_tgfx2 = lighting_ubo_.buffer;
    }

    // Shadow maps are now native tgfx2 depth textures owned by
    // ShadowPass; no per-frame wrap needed.
    std::vector<tgfx::TextureHandle> shadow_tex2s;
    shadow_tex2s.reserve(shadow_maps.size());
    for (const auto& smap : shadow_maps) {
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
        capture->capture_direct_via_ctx2(ctx2, color_tex2, rect.width, rect.height);
        selected_symbol_timing = {};
        selected_symbol_timing.name = debug_symbol;

        ctx2->begin_pass(color_tex2, depth_tex2,
                         /*clear_color=*/nullptr,
                         /*clear_depth=*/1.0f,
                         /*clear_depth_enabled=*/false);
        ctx2->set_viewport(0, 0, rect.width, rect.height);
        ctx2->set_depth_bias(false);
    };

    MaterialPipelineResourceContext material_resources{};
    material_resources.per_frame = &pf;
    material_resources.shadow_block = &sb;
    material_resources.shadow_block_size = static_cast<uint32_t>(sizeof(sb));
    material_resources.lighting_ubo = lighting_ubo_tgfx2;
    material_resources.shadow_maps =
        std::span<const tgfx::TextureHandle>(shadow_tex2s.data(), shadow_tex2s.size());
    material_resources.max_shadow_maps = MAX_SHADOW_MAPS;

    size_t draw_index = 0;
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

        // Only cast the drawable userdata to Drawable* when the component
        // actually installed the C++ drawable vtable. Python drawables use
        // the same capability slot with a PyObject* userdata and a
        // different C vtable — casting that to Drawable* and calling
        // virtual methods on it is undefined behaviour.
        Drawable* drawable = nullptr;
        if (tc_component_get_drawable_vtable(dc.component) == &Drawable::cxx_drawable_vtable()) {
            drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        }
        if (!drawable) {
            ++draw_index;
            continue;
        }

        auto refresh_phase = [&]() -> bool {
            ResolvedDrawPhase resolved = resolve_draw_phase(
                dc.component,
                collect_context,
                phase_mark,
                dc.geometry_id,
                dc.material,
                dc.phase_index,
                color_material_pass_contract());
            if (!resolved.phase) {
                tc::Log::error(
                    "[ColorPass/tgfx2] skip draw: pass='%s' phase='%s' index=%zu entity='%s' component='%s' geometry=%d could not resolve live material phase",
                    get_pass_name().c_str(),
                    phase_mark.c_str(),
                    draw_index,
                    ename ? ename : "<unnamed>",
                    safe_component_type(dc.component),
                    dc.geometry_id);
                return false;
            }
            phase = resolved.phase;
            final_shader = resolved.final_shader;
            return true;
        };

        if (!refresh_phase()) {
            ++draw_index;
            continue;
        }

        MeshDrawGeometry mesh_geometry{};
        if (!drawable->resolve_mesh_geometry(phase_mark, dc.geometry_id, mesh_geometry)) {
            if (!drawable->supports_direct_tgfx2_draw(
                    phase_mark, dc.geometry_id, DirectTgfx2DrawKind::MaterialPhase)) {
                ++draw_index;
                continue;
            }

            RenderState state = convert_render_state(phase->state);
            if (wireframe) state.polygon_mode = PolygonMode::Line;

            ctx2->clear_resource_bindings();


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
                sd.address_u = tgfx::AddressMode::ClampToEdge;
                sd.address_v = tgfx::AddressMode::ClampToEdge;
                sd.address_w = tgfx::AddressMode::ClampToEdge;
                sd.compare_enable = true;
                sd.compare_op = tgfx::CompareOp::LessEqual;
                shadow_sampler_ = device.create_sampler(sd);
            }

            RenderContext direct_context;
            direct_context.view = view;
            direct_context.projection = projection;
            direct_context.model = drawable->get_model_matrix(dc.entity);
            direct_context.phase = phase_mark;
            direct_context.pass_contract = color_material_pass_contract();
            direct_context.current_tc_shader = TcShader(final_shader);
            direct_context.layer_mask = layer_mask;
            direct_context.render_category_mask = ctx.render_category_mask;
            direct_context.camera_position = camera_position;
            direct_context.viewport_width = rect.width;
            direct_context.viewport_height = rect.height;
            direct_context.camera = const_cast<RenderCamera*>(ctx.camera);
            direct_context.prepare_tgfx2_material_resources =
                [this,
                 &device,
                 &material_resources,
                 &ctx](
                    tgfx::RenderContext2& draw_ctx,
                    const tc_shader* shader,
                    tc_material_phase* live_phase) {
                    if (!shader || !live_phase) {
                        tc::Log::error(
                            "[ColorPass/tgfx2] direct drawable resource callback called without shader or phase");
                        return;
                    }

                    MaterialPipelineResourceContext direct_resources = material_resources;
                    direct_resources.shadow_sampler = shadow_sampler_;
                    prepare_material_pipeline_resources(
                        draw_ctx,
                        device,
                        shader,
                        live_phase,
                        direct_resources);

                    if (!extra_textures.empty()) {
                        bind_extra_textures(ctx.tex2_reads, &draw_ctx, shader);
                    }
                };

            if (drawable->draw_tgfx2(*ctx2, direct_context, phase_mark, phase, dc.geometry_id)) {
                capture_debug_symbol(ename);
                ++draw_index;
                continue;
            }

            // Other non-mesh drawables (immediate gizmos, NavMesh debug,
            // solid primitive helpers) belong in their own dedicated
            // passes (UnifiedGizmoPass, ColliderGizmoPass, ...), not
            // in ColorPass. Stage 8.1 removed the path that ran them
            // through shader.use() + draw_geometry.
            ++draw_index;
            continue;
        }

        Mat44f model = drawable->get_model_matrix(dc.entity);

        // Prepare the shader through the shared material pipeline helper.
        // The helper owns artifact creation, shader binding, and active
        // resource-layout selection for the draw.
        tc_shader* raw_shader = tc_shader_get(final_shader);
        if (!raw_shader) {
            ++draw_index;
            continue;
        }
        MaterialPipelineShaderBinding shader_binding;
        if (!ensure_material_pipeline_shader(
                *ctx2,
                device,
                final_shader,
                "ColorPass",
                shader_binding)) {
            ++draw_index;
            continue;
        }
        tgfx::ShaderHandle vs2 = shader_binding.vertex;
        tgfx::ShaderHandle fs2 = shader_binding.fragment;
        raw_shader = shader_binding.shader;
        tc_shader_handle ensured_shader = final_shader;

        // Every material draw owns its descriptor set. Material textures are
        // optional at runtime; if one is missing, the Vulkan backend fills
        // that slot with its default texture. Without this reset, a missing
        // slot kept the previous draw/pass texture bound and produced
        // striped materials after resize/post-processing passes.
        ctx2->clear_resource_bindings();
        ctx2->use_shader_resource_layout(raw_shader);

        // Material storage is handle-addressable but not pointer-stable:
        // tc_material_create() may grow the pool and move existing materials.
        // Resolve the phase as late as possible so a draw never dereferences
        // a stale phase pointer captured during collection/sorting.
        if (!refresh_phase()) {
            ++draw_index;
            continue;
        }
        if (!same_shader_handle(final_shader, ensured_shader)) {
            raw_shader = tc_shader_get(final_shader);
            if (!raw_shader) {
                ++draw_index;
                continue;
            }
            if (!ensure_material_pipeline_shader(
                    *ctx2,
                    device,
                    final_shader,
                    "ColorPass/refreshed",
                    shader_binding)) {
                ++draw_index;
                continue;
            }
            raw_shader = shader_binding.shader;
            vs2 = shader_binding.vertex;
            fs2 = shader_binding.fragment;
            ensured_shader = final_shader;
        }

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

        ctx2->bind_shader(vs2, fs2);
        ctx2->use_shader_resource_layout(raw_shader);

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

        MaterialPipelineResourceContext draw_resources = material_resources;
        draw_resources.shadow_sampler = shadow_sampler_;
        prepare_material_pipeline_resources(
            *ctx2,
            device,
            raw_shader,
            phase,
            draw_resources);

        // Extra textures (nodegraph inputs) bind into the currently active
        // pipeline after material textures are in place.
        if (!extra_textures.empty()) {
            bind_extra_textures(ctx.tex2_reads, ctx2, raw_shader);
        }

        // --- Per-draw data ---
        //
        // Layout-only shaders receive the model matrix through their draw
        // scope resource.
        struct ColorPushData {
            float u_model[16];
        };
        ColorPushData push{};
        std::memcpy(push.u_model, model.data, sizeof(push.u_model));
        bind_draw_data_for_shader(*ctx2, raw_shader, push);

        // Per-draw uniforms that can't live in push-constants or the
        // material UBO yet — skinning bone matrices are the main case.
        // Default implementation is a no-op for non-skinned drawables.
        drawable->upload_per_draw_uniforms_tgfx2(*ctx2, dc.geometry_id);

        // Issue the draw through the shared backend-neutral TcMesh path.
        // It sets vertex layout/topology, wraps/uploads mesh buffers for the
        // current backend, submits ctx2->draw(), then releases transient
        // bindings.
        draw_material_pipeline_submesh(
            *ctx2,
            mesh_geometry.mesh,
            mesh_geometry.submesh_index,
            material_mesh_vertex_input_for_shader(
                raw_shader,
                MaterialMeshVertexInput::FullMaterial));
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
    Rect4i rect = ctx.render_rect;
    if (ctx.ctx2) {
        auto it = ctx.tex2_writes.find(output_res);
        if (it != ctx.tex2_writes.end() && it->second) {
            auto desc = ctx.ctx2->device().texture_desc(it->second);
            int w = static_cast<int>(desc.width);
            int h = static_cast<int>(desc.height);
            if (w > 0 && h > 0) {
                rect = Rect4i{0, 0, w, h};
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

    execute_with_data(
        ctx,
        rect,
        scene,
        view,
        projection,
        camera_position,
        ctx.lights,
        ambient_color,
        ambient_intensity,
        shadow_maps,
        shadow_settings,
        ctx.layer_mask
    );

    if (profile) tc_profiler_end_section();
}

// Register ColorPass in tc_pass_registry for C#/standalone C++ usage
TC_REGISTER_FRAME_PASS(ColorPass);

} // namespace termin
