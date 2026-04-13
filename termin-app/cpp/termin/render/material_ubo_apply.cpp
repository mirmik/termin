// material_ubo_apply.cpp - Implementation of bind_material_ubo.
#include "termin/render/material_ubo_apply.hpp"
#include "termin/render/shader_parser.hpp"

#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"

#include <cstdint>
#include <span>
#include <vector>

namespace termin {

void bind_material_ubo(
    const MaterialUboLayout& layout,
    const std::vector<MaterialProperty>& values,
    const std::vector<MaterialTextureBinding>& textures,
    tgfx2::BufferHandle ubo,
    uint32_t ubo_slot,
    tgfx2::IRenderDevice& device,
    tgfx2::RenderContext2& ctx)
{
    if (!layout.empty() && ubo) {
        // Zero-initialised staging — unset properties become zero bytes,
        // which matches std140 padding expectations and gives deterministic
        // defaults when hot-reload drops a property between frames.
        std::vector<uint8_t> staging(layout.block_size, 0);
        std140_pack(layout, values, staging.data());

        device.upload_buffer(
            ubo,
            std::span<const uint8_t>(staging.data(), staging.size()));

        ctx.bind_uniform_buffer(ubo_slot, ubo);
    }

    for (const auto& tex : textures) {
        ctx.bind_sampled_texture(tex.slot, tex.texture, tex.sampler);
    }
}

} // namespace termin
