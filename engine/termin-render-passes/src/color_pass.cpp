#include "termin/render/color_pass.hpp"
#include "termin/render/camera_capability.hpp"
#include "termin/render/frame_uniforms.hpp"
#include "termin/render/material_pipeline.hpp"
#include "termin/render/material_ubo_apply.hpp"
#include "termin/render/render_item_submission.hpp"
#include "termin/render/render_task.hpp"
#include "termin/render/scene_render_services.hpp"
#include "termin/render/shader_abi.hpp"
#include "termin/render/tgfx2_bridge.hpp"

#include "termin/lighting/lighting_upload.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/tc_shader_bridge.hpp"
#include <tcbase/tc_log.hpp>
#include <termin/render/frame_graph_capture.hpp>
#include <tgfx/tgfx_shader_handle.hpp>
extern "C" {
#include "core/tc_component.h"
#include "core/tc_drawable_protocol.h"
#include "core/tc_scene_drawable.h"
#include "core/tc_scene_render_state.h"
#include "tc_profiler.h"
#include <tgfx/resources/tc_material.h>
#include <tgfx/resources/tc_shader.h>
#include <tgfx/resources/tc_shader_registry.h>
}

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstring>
#include <numeric>
#include <span>
#include <string>

namespace termin {

    namespace {

        tc_value string_map_to_tc_value(const std::unordered_map<std::string, std::string>& values) {
            tc_value result = tc_value_dict_new();
            for (const auto& [key, value] : values) {
                tc_value_dict_set(&result, key.c_str(), tc_value_string(value.c_str()));
            }
            return result;
        }

        void tc_value_to_string_map(const tc_value* value, std::unordered_map<std::string, std::string>& out) {
            out.clear();
            if (!value || value->type != TC_VALUE_DICT) {
                return;
            }
            for (size_t index = 0; index < tc_value_dict_size(value); ++index) {
                const char* key = nullptr;
                tc_value* item = tc_value_dict_get_at(const_cast<tc_value*>(value), index, &key);
                if (!key || !item || item->type != TC_VALUE_STRING || !item->data.s) {
                    continue;
                }
                out[key] = item->data.s;
            }
        }

        constexpr const char* STANDARD_PBR_FORWARD_CONSUMER = R"slang(
import termin_lighting;
import termin_shadows;
import termin_ibl;

static const float TERMIN_STANDARD_PBR_PI = 3.14159265359;
static const float TERMIN_STANDARD_PBR_IBL_MAX_LOD = 6.0;

struct FragmentOutput {
    float4 color : SV_Target0;
};

float termin_standard_pbr_distribution_ggx(
    float normal_dot_half,
    float roughness)
{
    float alpha = roughness * roughness;
    float alpha_squared = alpha * alpha;
    float denominator =
        normal_dot_half * normal_dot_half * (alpha_squared - 1.0) + 1.0;
    return alpha_squared /
        (TERMIN_STANDARD_PBR_PI * denominator * denominator);
}

float termin_standard_pbr_geometry_smith(
    float normal_dot_view,
    float normal_dot_light,
    float roughness)
{
    float remapped_roughness = roughness + 1.0;
    float k = (remapped_roughness * remapped_roughness) / 8.0;
    float view_term =
        normal_dot_view /
        (normal_dot_view * (1.0 - k) + k);
    float light_term =
        normal_dot_light /
        (normal_dot_light * (1.0 - k) + k);
    return view_term * light_term;
}

float3 termin_standard_pbr_fresnel_schlick(
    float cosine,
    float3 reflectance_zero)
{
    return reflectance_zero +
        (1.0 - reflectance_zero) *
        pow(clamp(1.0 - cosine, 0.0, 1.0), 5.0);
}

float3 termin_standard_pbr_fresnel_schlick_roughness(
    float cosine,
    float3 reflectance_zero,
    float roughness)
{
    return reflectance_zero +
        (max(float3(1.0 - roughness), reflectance_zero) -
         reflectance_zero) *
        pow(clamp(1.0 - cosine, 0.0, 1.0), 5.0);
}

[shader("fragment")]
FragmentOutput termin_standard_pbr_forward(FragmentInput input) {
    TerminStandardSurfaceV1 surface = evaluate_standard_surface(input);
    float3 normal = normalize(surface.normal_world);
    float3 view_direction =
        normalize(get_camera_position() - input.world_pos);
    float metallic = saturate(surface.metallic);
    float roughness =
        max(saturate(surface.perceptual_roughness), 0.04);
    float occlusion = saturate(surface.occlusion);
    float3 reflectance_zero =
        lerp(float3(0.04, 0.04, 0.04), surface.base_color, metallic);

    float normal_dot_view =
        max(dot(normal, view_direction), 0.001);
    float3 ibl_fresnel =
        termin_standard_pbr_fresnel_schlick_roughness(
            normal_dot_view,
            reflectance_zero,
            roughness);
    float3 ibl_diffuse_weight =
        (1.0 - ibl_fresnel) * (1.0 - metallic);
    float3 ambient;
    if (has_environment_lighting()) {
        float3 irradiance = sample_ibl_diffuse_irradiance(normal);
        float3 diffuse_ibl =
            irradiance * surface.base_color / TERMIN_STANDARD_PBR_PI;

        float3 reflection_direction = reflect(-view_direction, normal);
        float3 prefiltered_radiance = sample_ibl_prefiltered_specular(
            reflection_direction,
            roughness * TERMIN_STANDARD_PBR_IBL_MAX_LOD);
        float2 environment_brdf = sample_ibl_brdf(normal_dot_view, roughness);
        float3 specular_ibl = prefiltered_radiance *
            (reflectance_zero * environment_brdf.x + environment_brdf.y);
        ambient =
            (ibl_diffuse_weight * diffuse_ibl + specular_ibl) * occlusion;
    } else {
        ambient =
            get_ambient_color() * get_ambient_intensity() *
            surface.base_color * occlusion;
    }
    float3 direct = float3(0.0, 0.0, 0.0);

    for (int light_index = 0;
         light_index < get_light_count();
         ++light_index) {
        float3 light_direction;
        float attenuation = 1.0;

        if (get_light_type(light_index) == LIGHT_TYPE_DIRECTIONAL) {
            light_direction = normalize(-get_light_direction(light_index));
        } else {
            float3 to_light =
                get_light_position(light_index) - input.world_pos;
            float distance_to_light = length(to_light);
            light_direction =
                to_light / max(distance_to_light, 0.0001);
            attenuation = compute_distance_attenuation(
                get_light_attenuation(light_index),
                get_light_range(light_index),
                distance_to_light);

            if (get_light_type(light_index) == LIGHT_TYPE_SPOT) {
                attenuation *= compute_spot_weight(
                    get_light_direction(light_index),
                    light_direction,
                    get_light_inner_angle(light_index),
                    get_light_outer_angle(light_index));
            }
        }

        float3 half_direction =
            normalize(view_direction + light_direction);
        float normal_dot_light =
            max(dot(normal, light_direction), 0.0);
        float normal_dot_view =
            max(dot(normal, view_direction), 0.001);
        float normal_dot_half =
            max(dot(normal, half_direction), 0.0);
        float half_dot_view =
            max(dot(half_direction, view_direction), 0.0);

        float distribution = termin_standard_pbr_distribution_ggx(
            normal_dot_half,
            roughness);
        float geometry = termin_standard_pbr_geometry_smith(
            normal_dot_view,
            normal_dot_light,
            roughness);
        float3 fresnel = termin_standard_pbr_fresnel_schlick(
            half_dot_view,
            reflectance_zero);
        float3 specular =
            distribution * geometry * fresnel /
            (4.0 * normal_dot_view * normal_dot_light + 0.0001);
        float3 diffuse_weight =
            (1.0 - fresnel) * (1.0 - metallic);
        float3 diffuse =
            diffuse_weight * surface.base_color /
            TERMIN_STANDARD_PBR_PI;

        float shadow = 1.0;
        if (get_light_type(light_index) == LIGHT_TYPE_DIRECTIONAL) {
            shadow = compute_shadow_auto(
                light_index,
                input.world_pos);
        }

        float3 radiance =
            get_light_color(light_index) *
            get_light_intensity(light_index) *
            attenuation;
        direct +=
            (diffuse + specular) *
            radiance *
            normal_dot_light *
            shadow;
    }

    FragmentOutput output;
    output.color = float4(
        ambient + direct + surface.emission,
        saturate(surface.opacity));
    return output;
}
)slang";

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
            case TC_BLEND_ZERO:
                rs.blend_src = BlendFactor::Zero;
                break;
            case TC_BLEND_ONE:
                rs.blend_src = BlendFactor::One;
                break;
            case TC_BLEND_ONE_MINUS_SRC_ALPHA:
                rs.blend_src = BlendFactor::OneMinusSrcAlpha;
                break;
            default:
                rs.blend_src = BlendFactor::SrcAlpha;
                break;
            }
            switch (s.blend_dst) {
            case TC_BLEND_ZERO:
                rs.blend_dst = BlendFactor::Zero;
                break;
            case TC_BLEND_ONE:
                rs.blend_dst = BlendFactor::One;
                break;
            case TC_BLEND_SRC_ALPHA:
                rs.blend_dst = BlendFactor::SrcAlpha;
                break;
            default:
                rs.blend_dst = BlendFactor::OneMinusSrcAlpha;
                break;
            }
            return rs;
        }

        inline tgfx::BlendFactor convert_blend_factor_tgfx2(BlendFactor factor) {
            switch (factor) {
            case BlendFactor::Zero:
                return tgfx::BlendFactor::Zero;
            case BlendFactor::One:
                return tgfx::BlendFactor::One;
            case BlendFactor::OneMinusSrcAlpha:
                return tgfx::BlendFactor::OneMinusSrcAlpha;
            case BlendFactor::SrcAlpha:
            default:
                return tgfx::BlendFactor::SrcAlpha;
            }
        }

        // Get global position from Entity.
        inline Vec3 get_global_position(const Entity& entity) {
            return entity.transform().global_position();
        }

        MaterialPipelinePassContract build_color_material_pass_contract() {
            MaterialPipelinePassContract contract;
            contract.debug_name = "color";
            contract.allows_authored_vertex_stage = true;
            contract.fragment_composition = MaterialFragmentComposition::SurfaceConsumerOrFinalColor;
            contract.required_material_fragment_input = material_pipeline_standard_material_fragment_interface();
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
            consumer.consumer_source = STANDARD_PBR_FORWARD_CONSUMER;
            consumer.fragment_entry = "termin_standard_pbr_forward";
            consumer.source_identity = "termin.surface.standard-pbr@1:forward-consumer:v1";
            consumer.required_fragment_input.semantics.push_back({"world_pos", MaterialPipelineValueType::Float3});
            consumer.resources = {
                material_pipeline_abi_resource_decl(ShaderAbiResourceId::Lighting,
                                                    TC_SHADER_STAGE_FRAGMENT,
                                                    MaterialPipelineResourceOwner::Pass,
                                                    static_cast<uint32_t>(sizeof(LightingUBOData))),
                material_pipeline_abi_resource_decl(ShaderAbiResourceId::ShadowBlock,
                                                    TC_SHADER_STAGE_FRAGMENT,
                                                    MaterialPipelineResourceOwner::Pass,
                                                    SHADOW_BLOCK_STD140_SIZE),
                material_pipeline_abi_resource_decl(
                    ShaderAbiResourceId::ShadowMaps, TC_SHADER_STAGE_FRAGMENT, MaterialPipelineResourceOwner::Pass),
                material_pipeline_abi_resource_decl(ShaderAbiResourceId::IblDiffuseIrradiance,
                                                    TC_SHADER_STAGE_FRAGMENT,
                                                    MaterialPipelineResourceOwner::Pass),
                material_pipeline_abi_resource_decl(ShaderAbiResourceId::IblPrefilteredSpecular,
                                                    TC_SHADER_STAGE_FRAGMENT,
                                                    MaterialPipelineResourceOwner::Pass),
                material_pipeline_abi_resource_decl(
                    ShaderAbiResourceId::IblBrdfLut, TC_SHADER_STAGE_FRAGMENT, MaterialPipelineResourceOwner::Pass),
            };
            contract.surface_consumer = std::move(consumer);
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
            if (!tc_material_handle_is_invalid(item.material) && item.material_phase_index != SIZE_MAX) {
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

        RenderItemTaskPlanningContract color_task_planning_contract(tc_phase_mask phase,
                                                                    const MaterialPipelinePassContract& shader_contract,
                                                                    const char* debug_pass_name) {
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
            contract.debug_pass_name = debug_pass_name;
            return contract;
        }

        bool plan_color_item_shader(const tc_render_item& item,
                                    tc_material_phase* phase,
                                    const MaterialPipelinePassContract& shader_contract,
                                    const char* debug_pass_name,
                                    RenderTaskList& tasks) {
            RenderItemTaskPlanningContract contract =
                color_task_planning_contract(phase ? phase->phase : TC_PHASE_NONE, shader_contract, debug_pass_name);
            RenderItemTaskPlanningRequest request{};
            request.item = &item;
            request.material_phase = phase;
            request.candidate_shader = phase ? phase->shader : tc_shader_handle_invalid();
            request.contract = &contract;
            return plan_render_item_task(request, tasks).accepted();
        }

    } // anonymous namespace

    MaterialPipelinePassContract color_material_pass_contract() {
        return build_color_material_pass_contract();
    }

    MaterialPipelinePassContract multiview_color_material_pass_contract() {
        MaterialPipelinePassContract contract = build_color_material_pass_contract();
        contract.debug_name = "multiview_color";
        contract.allows_authored_vertex_stage = false;
        contract.vertex_output_adapter = material_pipeline_multiview_material_vertex_output_adapter();
        return contract;
    }

    ColorPass::ColorPass(const ColorPassConfig& config)
        : input_res(config.input_res),
          output_res(config.output_res),
          shadow_res(config.shadow_res),
          environment_res(config.environment_res),
          phase_mark(config.phase_mark),
          sort_mode(config.sort_mode),
          camera_name(config.camera_name),
          clear_depth(config.clear_depth),
          attachment_barrier_between_draws(config.attachment_barrier_between_draws) {
        set_pass_name(config.pass_name);
    }

    tc_value ColorPass::serialize_extra_textures() const {
        return string_map_to_tc_value(extra_textures);
    }

    void ColorPass::deserialize_extra_textures(const tc_value* value) {
        tc_value_to_string_map(value, extra_textures);
    }

    std::set<const char*> ColorPass::compute_reads() const {
        std::set<const char*> result;
        result.insert(input_res.c_str());
        if (!shadow_res.empty()) {
            result.insert(shadow_res.c_str());
        }
        if (!environment_res.empty()) {
            result.insert(environment_res.c_str());
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

    bool ColorPass::set_graph_resource_input(const std::string& socket_name, const std::string& resource_name) {
        if (socket_name.empty() || resource_name.empty()) {
            return false;
        }
        if (socket_name == "input_res" || socket_name == "output_res" || socket_name == "shadow_res" ||
            socket_name == "environment_res") {
            return false;
        }
        add_extra_texture(socket_name, resource_name);
        return true;
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
        return {ResourceSpec{
            input_res,
            "fbo",                                       // resource_type
            std::nullopt,                                // size
            termin::LinearColor{0.0f, 0.0f, 0.0f, 1.0f}, // clear_color
            1.0f                                         // clear_depth
        }};
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
                if (!plan_color_item_shader(item, phase, data->pass_contract, "ColorPass/ShaderUsage", tasks)) {
                    continue;
                }
                // Runtime packages need every executable shader which the pass can
                // bind. A task's broader usage list may contain both several draw
                // variants (for example, line body and cap) and evaluator-only planner
                // inputs. Exporting the latter as pipeline requirements would
                // incorrectly treat authoring dependencies as GPU entry points.
                for (const RenderTask& task : tasks) {
                    for (uint32_t i = 0; i < task.shader_usage_count; ++i) {
                        tc_shader* shader = tc_shader_get(task.shader_usages[i]);
                        if (tc_shader_is_executable(shader)) {
                            (*data->emit)(TcShader(task.shader_usages[i]));
                        }
                    }
                }
            }

            return true;
        }

    } // anonymous namespace

    void ColorPass::collect_draw_calls(tc_scene_handle scene,
                                       const std::string& phase_mark,
                                       const RenderContext& render_context,
                                       uint64_t layer_mask,
                                       const RenderItemSnapshot& snapshot) {
        (void)render_context;
        (void)layer_mask;
        // Clear but keep capacity
        cached_draw_calls_.clear();

        if (!tc_scene_handle_valid(scene)) {
            tc::Log::warn("[ColorPass] collect_draw_calls: scene is invalid!");
            return;
        }

        const auto& items = snapshot.items();
        const std::span<const size_t> routed_items = snapshot.phase_item_indices(tc_phase_find(phase_mark.c_str()));
        cached_draw_calls_.reserve(routed_items.size());
        for (size_t item_index : routed_items) {
            const tc_render_item& item = items[item_index];
            tc_component* tc = render_scene_item_component(item);
            if (!tc) {
                tc::Log::error("[ColorPass] collect_draw_calls: collected item %zu has null component", item_index);
                continue;
            }

            Entity ent(tc->owner);
            if (!ent.valid()) {
                tc::Log::error("[ColorPass] collect_draw_calls: drawable component '%s' has invalid owner",
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

    void ColorPass::collect_scene_shader_usages(tc_scene_handle scene,
                                                const std::function<void(TcShader)>& emit) const {
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
                "[ColorPass] pass '%s' requests unregistered phase '%s'", get_pass_name().c_str(), phase_mark.c_str());
            return;
        }
        data.pass_contract =
            multiview_mode_ ? multiview_color_material_pass_contract() : color_material_pass_contract();
        data.emit = &emit;

        tc_scene_foreach_drawable(scene, collect_color_drawable_shader_usages, &data, TC_SCENE_FILTER_NONE, 0);
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
            float dist2 = static_cast<float>(dx * dx + dy * dy + dz * dz);

            uint32_t dist_bits = float_to_sortable_uint(dist2);
            if (invert_distance) {
                dist_bits = ~dist_bits; // Invert for far-to-near
            }

            sort_keys_[i] = (priority_bits << 48) | (shader_bits << 32) | dist_bits;
        }
    }

    void ColorPass::sort_draw_calls() {
        const size_t n = cached_draw_calls_.size();
        if (n <= 1)
            return;

        // Resize index array (reuses capacity)
        sort_indices_.resize(n);
        std::iota(sort_indices_.begin(), sort_indices_.end(), size_t(0));

        // Sort indices by sort_keys
        std::sort(sort_indices_.begin(), sort_indices_.end(), [this](size_t a, size_t b) {
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

    void ColorPass::execute_with_data(ExecuteContext& ctx, const ColorPassExecuteData& data) {
        execute_with_data_impl(ctx, data, false);
    }

    void ColorPass::execute_with_data_impl(ExecuteContext& ctx,
                                           const ColorPassExecuteData& data,
                                           bool raster_scope_already_open) {
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
            tc::Log::warn("[ColorPass/tgfx2] tgfx2 color texture for '%s' not available", output_res.c_str());
            return;
        }
        tgfx::TextureHandle color_tex2 = color_it->second;

        auto depth_it = ctx.tex2_depth_writes.find(output_res);
        tgfx::TextureHandle depth_tex2 =
            (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};

        const RenderItemSnapshot* scene_items = require_render_item_snapshot(ctx, "ColorPass");
        if (!scene_items) {
            return;
        }

        EnginePerFrameStd140 pf =
            make_engine_per_frame_uniforms(data.view,
                                           data.projection,
                                           data.camera_position,
                                           static_cast<float>(data.rect.width),
                                           static_cast<float>(data.rect.height),
                                           ctx.view.primary ? static_cast<float>(ctx.view.primary->near_clip) : 0.1f,
                                           ctx.view.primary ? static_cast<float>(ctx.view.primary->far_clip) : 100.0f);
        StereoPerFrameStd140 stereo_pf{};
        if (multiview_mode_) {
            if (!ctx.view.stereo) {
                tc::Log::error("[MultiviewColorPass] StereoRenderViews are missing");
                return;
            }
            stereo_pf = make_stereo_per_frame_uniforms(
                *ctx.view.stereo, static_cast<float>(data.rect.width), static_cast<float>(data.rect.height));
        }

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
        const size_t active_shadow_budget = std::min<size_t>(SHADOW_UBO_MAX, device.capabilities().max_shadow_maps);
        struct ShadowBlockStd140 {
            int u_shadow_map_count; // 4
            int _pad0[3];           // 12
            // mat4[16] = 64 * 16 = 1024
            float u_light_space_matrix[SHADOW_UBO_MAX][4][4];
            // int[16] with std140 vec4 alignment (4 bytes + 12 pad per element)
            int u_shadow_light_index[SHADOW_UBO_MAX][4];
            int u_shadow_cascade_index[SHADOW_UBO_MAX][4];
            float u_shadow_split_near[SHADOW_UBO_MAX][4];
            float u_shadow_split_far[SHADOW_UBO_MAX][4];
            float u_camera_view_depth[4];
            float u_shadow_texel_size[SHADOW_UBO_MAX][4];
        };
        static_assert(sizeof(ShadowBlockStd140) == SHADOW_BLOCK_STD140_SIZE,
                      "ShadowBlockStd140 must match the shared shadow ABI size");

        ShadowBlockStd140 sb{};
        {
            int sm_count = static_cast<int>(std::min(data.shadow_maps.size(), active_shadow_budget));
            sb.u_shadow_map_count = sm_count;
            for (int i = 0; i < sm_count; ++i) {
                const ShadowMapArrayEntry& e = data.shadow_maps[i];
                // Mat44f is column-major; the shader consumes four explicit rows.
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        sb.u_light_space_matrix[i][row][col] = e.light_space_matrix(col, row);
                    }
                }
                sb.u_shadow_light_index[i][0] = e.light_index;
                sb.u_shadow_cascade_index[i][0] = e.cascade_index;
                sb.u_shadow_split_near[i][0] = e.cascade_split_near;
                sb.u_shadow_split_far[i][0] = e.cascade_split_far;
                sb.u_shadow_texel_size[i][0] = e.width > 0 ? 1.0f / static_cast<float>(e.width) : 0.0f;
                sb.u_shadow_texel_size[i][1] = e.height > 0 ? 1.0f / static_cast<float>(e.height) : 0.0f;
            }
            for (int col = 0; col < 4; ++col) {
                sb.u_camera_view_depth[col] = data.view(col, 1);
            }
        }

        auto begin_output_pass = [&](bool clear_depth_now) -> bool {
            if (!multiview_mode_) {
                ctx2->begin_pass(color_tex2, depth_tex2, nullptr, 1.0f, clear_depth_now);
                return true;
            }
            tgfx::MultiviewRenderPassDesc pass;
            tgfx::ColorAttachmentDesc color;
            color.texture = color_tex2;
            color.load = tgfx::LoadOp::Load;
            pass.colors.push_back(color);
            if (depth_tex2) {
                pass.has_depth = true;
                pass.depth.texture = depth_tex2;
                pass.depth.load = clear_depth_now ? tgfx::LoadOp::Clear : tgfx::LoadOp::Load;
            }
            pass.view_count = 2;
            return ctx2->begin_multiview_pass(pass);
        };
        if (!raster_scope_already_open) {
            if (!begin_output_pass(clear_depth)) {
                return;
            }
        }
        ctx2->set_viewport(0, 0, data.rect.width, data.rect.height);
        ctx2->set_depth_bias(false);

        // Collect + sort draw calls. Gathering logic is backend-agnostic.
        RenderContext collect_context;
        collect_context.view = data.view;
        collect_context.projection = data.projection;
        collect_context.phase = tc_phase_find(phase_mark.c_str());
        collect_context.pass_contract =
            multiview_mode_ ? multiview_color_material_pass_contract() : color_material_pass_contract();
        collect_context.layer_mask = data.layer_mask;
        collect_context.render_category_mask = data.render_category_mask;
        collect_context.camera_position = data.camera_position;
        collect_context.viewport_width = data.rect.width;
        collect_context.viewport_height = data.rect.height;

        collect_draw_calls(data.scene, phase_mark, collect_context, data.layer_mask, *scene_items);

        const std::string debug_pass_name = get_pass_name();
        const char* debug_pass_name_c = debug_pass_name.c_str();
        const MaterialPipelinePassContract task_shader_contract =
            multiview_mode_ ? multiview_color_material_pass_contract() : color_material_pass_contract();
        RenderItemTaskPlanningContract task_planning_contract =
            color_task_planning_contract(tc_phase_find(phase_mark.c_str()), task_shader_contract, debug_pass_name_c);
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
                    tc::Log::error("[ColorPass/tgfx2] skip planning: pass='%s' phase='%s' has invalid item index %zu",
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
            RenderItemTaskPlanningResult planning_result = plan_render_item_task(planning_request, render_tasks);
            ++source_draw_index;
            if (!planning_result.accepted()) {
                continue;
            }

            ColorTaskExtension& extension = render_tasks.emplace_extension<ColorTaskExtension>();
            RenderTask& task = render_tasks.at(planning_result.task_index);
            task.extension = &extension;
            const char* entity_name = dc.entity.name();
            task.debug_name = entity_name ? entity_name : "";
            if (item->flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) {
                std::memcpy(extension.draw_data.u_model, item->model_matrix, sizeof(extension.draw_data.u_model));
            } else {
                Mat44f identity = Mat44f::identity();
                std::memcpy(extension.draw_data.u_model, identity.data, sizeof(extension.draw_data.u_model));
            }

            std::memcpy(task.draw_context.model.data, extension.draw_data.u_model, sizeof(extension.draw_data.u_model));
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

            dc.final_shader = TcShader(task.final_shader);
            tasks_by_item_index[dc.item_index] = &task;
            sorted_draw_calls_.push_back(std::move(dc));
        }
        std::swap(cached_draw_calls_, sorted_draw_calls_);

        if (sort_mode != "none" && !cached_draw_calls_.empty()) {
            compute_sort_keys(data.camera_position);
            sort_draw_calls();
        } else if (!cached_draw_calls_.empty()) {
            std::sort(cached_draw_calls_.begin(),
                      cached_draw_calls_.end(),
                      [](const PhaseDrawCall& a, const PhaseDrawCall& b) { return a.priority < b.priority; });
        }

        std::vector<RenderTask*> sorted_render_tasks;
        sorted_render_tasks.reserve(cached_draw_calls_.size());
        for (const PhaseDrawCall& dc : cached_draw_calls_) {
            RenderTask* task = tasks_by_item_index[dc.item_index];
            if (!task) {
                tc::Log::error("[ColorPass/tgfx2] accepted draw has no planned task: pass='%s' item=%zu",
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
        const bool environment_lighting_ready = data.environment_lighting && data.environment_lighting->ready();
        if (!cached_draw_calls_.empty()) {
            lighting_ubo_.create(device);
            lighting_ubo_.update_from_lights(data.lights,
                                             data.ambient_color,
                                             data.ambient_intensity,
                                             data.camera_position,
                                             data.shadow_settings,
                                             environment_lighting_ready);
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
        const std::string debug_symbol = requested_debug_symbol ? *requested_debug_symbol : std::string{};
        if (debug_symbol.empty()) {
            selected_symbol_timing = {};
        }
        auto capture_debug_symbol = [&](const char* entity_name) {
            if (!ctx.should_capture_internal(entity_name)) {
                return;
            }

            if (raster_scope_already_open) {
                tc::Log::error("[ColorPass] internal capture requires standalone raster execution");
                return;
            }

            ctx2->end_pass();
            ctx.capture_internal(entity_name, color_tex2, data.rect.width, data.rect.height);
            selected_symbol_timing = {};
            selected_symbol_timing.name = debug_symbol;

            if (!begin_output_pass(false)) {
                tc::Log::error("[ColorPass] failed to resume render pass after capture");
                return;
            }
            ctx2->set_viewport(0, 0, data.rect.width, data.rect.height);
            ctx2->set_depth_bias(false);
        };

        MaterialPipelineResourceView material_resources{};
        material_resources.per_frame =
            multiview_mode_ ? static_cast<const void*>(&stereo_pf) : static_cast<const void*>(&pf);
        material_resources.per_frame_size =
            multiview_mode_ ? static_cast<uint32_t>(sizeof(stereo_pf)) : static_cast<uint32_t>(sizeof(pf));
        material_resources.shadow_block = &sb;
        material_resources.shadow_block_size = static_cast<uint32_t>(sizeof(sb));
        material_resources.lighting_ubo = lighting_ubo_tgfx2;
        material_resources.shadow_maps = shadow_tex2s.data();
        material_resources.shadow_map_count =
            static_cast<uint32_t>(std::min(shadow_tex2s.size(), active_shadow_budget));
        material_resources.material_texture_sources = ctx.material_texture_sources;

        std::vector<RenderItemNamedTextureBinding> extra_texture_bindings;
        extra_texture_bindings.reserve(extra_textures.size() + 3u);
        if (environment_lighting_ready) {
            extra_texture_bindings.push_back(
                RenderItemNamedTextureBinding{"ibl_diffuse_irradiance",
                                              data.environment_lighting->diffuse_irradiance,
                                              data.environment_lighting->sampler,
                                              true});
            extra_texture_bindings.push_back(
                RenderItemNamedTextureBinding{"ibl_prefiltered_specular",
                                              data.environment_lighting->prefiltered_specular,
                                              data.environment_lighting->sampler,
                                              true});
            extra_texture_bindings.push_back(RenderItemNamedTextureBinding{
                "ibl_brdf_lut", data.environment_lighting->brdf_lut, data.environment_lighting->sampler, true});
        }
        for (const auto& [uniform_name, resource_name] : extra_textures) {
            auto it = ctx.tex2_reads.find(resource_name);
            if (it == ctx.tex2_reads.end() || !it->second) {
                tc::Log::warn("[ColorPass:%s] tgfx2 texture not found for resource: %s",
                              get_pass_name().c_str(),
                              resource_name.c_str());
                continue;
            }
            extra_texture_bindings.push_back(
                RenderItemNamedTextureBinding{uniform_name.c_str(), it->second, tgfx::SamplerHandle{}, true});
        }

        for (const RenderTask* task : sorted_render_tasks) {
            entity_names.push_back(task->debug_name);
        }

        if (!render_tasks.empty() && !shadow_sampler_) {
            tgfx::SamplerDesc sd;
            sd.min_filter = tgfx::FilterMode::Linear;
            sd.mag_filter = tgfx::FilterMode::Linear;
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
                {"draw_data",
                 &extension.draw_data,
                 static_cast<uint32_t>(sizeof(extension.draw_data)),
                 "draw_data",
                 nullptr},
            }};
            task.set_resources(&material_resources, uniforms, extra_texture_bindings);
        }

        for (size_t sorted_task_index = 0; sorted_task_index < sorted_render_tasks.size(); ++sorted_task_index) {
            const RenderTask* task_ptr = sorted_render_tasks[sorted_task_index];
            const RenderTask& task = *task_ptr;
            // Every material draw owns its descriptor set. Material textures are
            // optional at runtime; if one is missing, the Vulkan backend fills
            // that slot with its default texture. Without this reset, a missing
            // slot kept the previous draw/pass texture bound and produced
            // striped materials after resize/post-processing passes.
            ctx2->clear_resource_bindings();

            // Render state from the material phase.
            RenderState state = convert_render_state(task.material_phase->state);
            if (wireframe)
                state.polygon_mode = PolygonMode::Line;

            ctx2->set_depth_test(state.depth_test);
            ctx2->set_depth_write(state.depth_write);
            ctx2->set_blend(state.blend);
            ctx2->set_blend_func(convert_blend_factor_tgfx2(state.blend_src),
                                 convert_blend_factor_tgfx2(state.blend_dst));
            ctx2->set_cull(state.cull ? tgfx::CullMode::Back : tgfx::CullMode::None);
            ctx2->set_polygon_mode(state.polygon_mode == PolygonMode::Line ? tgfx::PolygonMode::Line
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
            encode_request.debug_entity_name = task.debug_name.c_str();
            encode_request.resources = &task.resources;
            if (!submit_render_item_draw(*ctx2, *task.item, encode_request)) {
                continue;
            }
            capture_debug_symbol(task.debug_name.c_str());
            if (attachment_barrier_between_draws && sorted_task_index + 1 < sorted_render_tasks.size()) {
                ctx2->framebuffer_local_barrier();
            }
        }

        if (!raster_scope_already_open) {
            ctx2->end_pass();
        }
    }

    void ColorPass::execute(ExecuteContext& ctx) {
        execute_impl(ctx, false);
    }

    bool ColorPass::get_raster_contract(ExecuteContext& ctx, tc_raster_pass_contract& out_contract) const {
        out_contract = {};
        out_contract.struct_size = sizeof(out_contract);
        out_contract.target_resource = output_res.c_str();
        out_contract.view_count = multiview_mode_ ? 2u : 1u;
        out_contract.color_load = TC_RASTER_LOAD;
        out_contract.depth_load = clear_depth ? TC_RASTER_CLEAR : TC_RASTER_LOAD;
        const auto color = ctx.tex2_writes.find(output_res);
        out_contract.has_color = color != ctx.tex2_writes.end() && static_cast<bool>(color->second);
        const auto depth = ctx.tex2_depth_writes.find(output_res);
        out_contract.has_depth = depth != ctx.tex2_depth_writes.end() && static_cast<bool>(depth->second);
        out_contract.attachment_barrier_after = attachment_barrier_between_draws;
        out_contract.fusion_eligible = ctx.debug_internal_capture_requests.empty();
        return !output_res.empty() && out_contract.has_color;
    }

    bool ColorPass::record_raster(ExecuteContext& ctx) {
        if (!ctx.debug_internal_capture_requests.empty()) {
            tc::Log::error("[ColorPass] record_raster called while an internal capture requires standalone execution");
            return false;
        }
        if (!ctx.ctx2) {
            tc::Log::error("[ColorPass] record_raster called without a render context");
            return false;
        }
        const auto color = ctx.tex2_writes.find(output_res);
        if (color == ctx.tex2_writes.end() || !color->second) {
            tc::Log::error("[ColorPass] record_raster has no color output '%s'", output_res.c_str());
            return false;
        }
        execute_impl(ctx, true);
        return true;
    }

    void ColorPass::execute_impl(ExecuteContext& ctx, bool raster_scope_already_open) {
        bool profile = tc_profiler_enabled();
        if (profile)
            tc_profiler_begin_section(("ColorPass:" + get_pass_name()).c_str());

        const SceneRenderServices* services = require_scene_render_services(ctx, "ColorPass");
        if (!services) {
            if (profile)
                tc_profiler_end_section();
            return;
        }

        // Use the scene-neutral primary view, or find a scene camera by name.
        const RenderCamera* camera = ctx.view.primary_view();
        RenderCamera stereo_sort_camera;
        if (multiview_mode_) {
            if (!ctx.view.stereo) {
                tc::Log::error("[MultiviewColorPass] StereoRenderViews are missing");
                if (profile)
                    tc_profiler_end_section();
                return;
            }
            if (!camera_name.empty()) {
                tc::Log::error(
                    "[MultiviewColorPass] camera_name override is incompatible with frame-local StereoRenderViews");
                if (profile)
                    tc_profiler_end_section();
                return;
            }
            stereo_sort_camera = ctx.view.stereo->left;
            stereo_sort_camera.position = (ctx.view.stereo->left.position + ctx.view.stereo->right.position) * 0.5;
            camera = &stereo_sort_camera;
        }
        tc_scene_handle scene = services->scene.handle();
        RenderCameraSnapshot named_camera_snapshot;
        uint64_t camera_layer_mask = services->layer_mask;
        uint64_t camera_render_category_mask = services->render_category_mask;
        if (!camera_name.empty()) {
            if (!resolve_named_render_camera_for_pass(
                    scene, camera_name.c_str(), 0.0, "ColorPass", named_camera_snapshot)) {
                if (profile)
                    tc_profiler_end_section();
                return;
            }
            camera = &named_camera_snapshot.camera;
            camera_layer_mask = named_camera_snapshot.layer_mask;
            camera_render_category_mask = named_camera_snapshot.render_category_mask;
        }

        if (!camera) {
            if (profile)
                tc_profiler_end_section();
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
                        if (!resolve_named_render_camera_for_pass(scene,
                                                                  camera_name.c_str(),
                                                                  static_cast<double>(w) / std::max(1, h),
                                                                  "ColorPass",
                                                                  named_camera_snapshot)) {
                            if (profile)
                                tc_profiler_end_section();
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
                ambient_color = Vec3{lighting->ambient_color.r, lighting->ambient_color.g, lighting->ambient_color.b};
                ambient_intensity = lighting->ambient_intensity;
                shadow_settings.method = lighting->shadow_method;
                shadow_settings.softness = lighting->shadow_softness;
                shadow_settings.bias = lighting->shadow_bias;
            }
        }

        std::vector<ShadowMapArrayEntry> shadow_maps;
        if (!shadow_res.empty()) {
            ShadowMapArrayResource* shadow_array = ctx.get_frame_graph_resource_as<ShadowMapArrayResource>(shadow_res);
            if (shadow_array) {
                shadow_maps = shadow_array->entries;
            }
        }

        const EnvironmentLightingResource* environment_lighting = nullptr;
        if (!environment_res.empty()) {
            FrameGraphResource* environment_resource = ctx.get_frame_graph_resource(environment_res);
            environment_lighting = dynamic_cast<EnvironmentLightingResource*>(environment_resource);
            if (environment_resource && !environment_lighting) {
                tc::Log::error("[ColorPass:%s] resource '%s' is not an environment_lighting resource",
                               get_pass_name().c_str(),
                               environment_res.c_str());
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
        data.lights = services->lights;
        data.ambient_color = ambient_color;
        data.ambient_intensity = ambient_intensity;
        data.shadow_maps = shadow_maps;
        data.environment_lighting = environment_lighting;
        data.shadow_settings = shadow_settings;
        data.layer_mask = camera_layer_mask;
        data.render_category_mask = camera_render_category_mask;
        execute_with_data_impl(ctx, data, raster_scope_already_open);

        if (profile)
            tc_profiler_end_section();
    }

    // Register ColorPass in tc_pass_registry for C#/standalone C++ usage
    void ColorPass::register_type() {
        auto descriptor = FramePassTypeDescriptorBuilder::native<ColorPass>("ColorPass", "termin-render-passes");
        auto& inspect = descriptor.inspect();
        _register_inspect_input_res(inspect);
        _register_inspect_output_res(inspect);
        _register_inspect_shadow_res(inspect);
        _register_inspect_environment_res(inspect);
        _register_inspect_phase_mark(inspect);
        _register_inspect_sort_mode(inspect);
        _register_inspect_clear_depth(inspect);
        _register_inspect_attachment_barrier_between_draws(inspect);
        _register_inspect_camera_name(inspect);
        _register_inspect_metadata_graph(inspect);
        register_serialize_ColorPass_extra_textures(inspect);
        (void)descriptor.commit();
    }

    MultiviewColorPass::MultiviewColorPass(const ColorPassConfig& config)
        : ColorPass(config) {
        multiview_mode_ = true;
        shadow_res.clear();
        if (get_pass_name() == "Color") {
            pass_name_set("MultiviewColor");
        }
        link_to_type_registry("MultiviewColorPass");
    }

    void MultiviewColorPass::register_type() {
        auto descriptor = FramePassTypeDescriptorBuilder::native<MultiviewColorPass>(
            "MultiviewColorPass", "termin-render-passes", "ColorPass");
        auto& inspect = descriptor.inspect();
        MultiviewColorPass::_register_inspect_metadata_graph(inspect);
        (void)descriptor.commit();
    }

} // namespace termin
