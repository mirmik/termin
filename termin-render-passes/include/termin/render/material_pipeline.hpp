#pragma once

#include <cstddef>
#include <cstdint>
#include <span>

#include "termin/render/frame_uniforms.hpp"
#include "tgfx2/handles.hpp"

extern "C" {
#include "tgfx/resources/tc_material.h"
#include "tgfx/resources/tc_shader.h"
}

namespace tgfx {
class IRenderDevice;
class RenderContext2;
}

namespace termin {

struct MaterialPipelineResourceContext {
    const EnginePerFrameStd140* per_frame = nullptr;
    const void* shadow_block = nullptr;
    uint32_t shadow_block_size = 0;
    tgfx::BufferHandle lighting_ubo;
    std::span<const tgfx::TextureHandle> shadow_maps;
    tgfx::SamplerHandle shadow_sampler;
};

struct MaterialPipelineFallbackBindings {
    uint32_t shadow_block = 0;
    uint32_t material_ubo = 0;
    uint32_t material_texture_base = 0;
    uint32_t lighting_ubo = 0;
    uint32_t shadow_map_base = 0;
    size_t max_shadow_maps = 0;
};

bool prepare_material_pipeline_resources(
    tgfx::RenderContext2& ctx,
    tgfx::IRenderDevice& device,
    const tc_shader* shader,
    tc_material_phase* phase,
    const MaterialPipelineResourceContext& resources,
    const MaterialPipelineFallbackBindings& fallback);

} // namespace termin
