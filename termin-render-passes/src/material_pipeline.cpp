#include "termin/render/material_pipeline.hpp"

#include "termin/render/material_ubo_apply.hpp"
#include "termin/render/shader_resource_apply.hpp"

extern "C" {
#include "tgfx/resources/tc_shader_registry.h"
}

namespace termin {

bool prepare_material_pipeline_resources(
    tgfx::RenderContext2& ctx,
    tgfx::IRenderDevice& device,
    const tc_shader* shader,
    tc_material_phase* phase,
    const MaterialPipelineResourceContext& resources,
    const MaterialPipelineFallbackBindings& fallback)
{
    if (!shader) {
        return false;
    }

    bool bound_any = false;

    if (resources.per_frame) {
        bind_engine_per_frame_uniforms(ctx, *resources.per_frame, shader);
        bound_any = true;
    }

    if (resources.shadow_block && resources.shadow_block_size > 0) {
        bound_any |= bind_shadow_block_for_shader(
            ctx,
            shader,
            resources.shadow_block,
            resources.shadow_block_size,
            fallback.shadow_block);
    }

    if (resources.lighting_ubo &&
        tc_shader_has_feature(shader, TC_SHADER_FEATURE_LIGHTING_UBO)) {
        bound_any |= bind_lighting_ubo_for_shader(
            ctx,
            shader,
            resources.lighting_ubo,
            fallback.lighting_ubo);
    }

    if (phase) {
        bound_any |= apply_material_phase_ubo(
            phase,
            shader,
            fallback.material_ubo,
            fallback.material_texture_base,
            device,
            ctx);
    }

    if (!resources.shadow_maps.empty() && resources.shadow_sampler) {
        bound_any |= bind_shadow_maps_for_shader(
            ctx,
            shader,
            resources.shadow_maps,
            resources.shadow_sampler,
            fallback.shadow_map_base,
            fallback.max_shadow_maps);
    }

    return bound_any;
}

} // namespace termin
