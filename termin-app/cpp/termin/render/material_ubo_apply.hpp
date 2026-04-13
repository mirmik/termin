// material_ubo_apply.hpp - Upload + bind a std140 material UBO for a draw.
//
// Stage 3 of the tgfx2 migration. Consumes a MaterialUboLayout (produced by
// shader_parser at shader load time) and a list of property values to:
//   1. Pack values into a std140-laid out staging buffer.
//   2. Upload that buffer into the caller-owned UBO via IRenderDevice.
//   3. Bind the UBO at the requested slot via RenderContext2.
//   4. Bind any accompanying sampled textures at their slots via RenderContext2.
//
// The caller owns the UBO handle lifecycle. This function does NOT create or
// destroy buffers — materials (or whoever drives draw loops) are expected to
// keep a persistent UBO per phase and reuse it across frames.
#pragma once

#include <cstdint>
#include <vector>

#include "tgfx2/handles.hpp"

namespace tgfx2 {
class IRenderDevice;
class RenderContext2;
}

namespace termin {

struct MaterialProperty;
struct MaterialUboLayout;

// A sampled texture that accompanies the material UBO at draw time.
struct MaterialTextureBinding {
    uint32_t slot = 0;
    tgfx2::TextureHandle texture;
    tgfx2::SamplerHandle sampler;  // may be {} for default sampling
};

// Pack, upload, and bind one material UBO + its textures.
//
// Requirements:
//   - `ubo` must be a valid tgfx2 buffer with size >= layout.block_size and
//     usage that includes Uniform (plus CopyDst for upload).
//   - `ctx` must be inside begin_pass (so command-list state is live).
//   - `device` must be the same device that created `ubo` and that `ctx`
//     draws through.
//
// Values not present in `values` keep their previous bytes in the upload
// path — since we re-upload the whole block each call, "not present" means
// "written as zero" after the staging buffer is zero-initialised here.
void bind_material_ubo(
    const MaterialUboLayout& layout,
    const std::vector<MaterialProperty>& values,
    const std::vector<MaterialTextureBinding>& textures,
    tgfx2::BufferHandle ubo,
    uint32_t ubo_slot,
    tgfx2::IRenderDevice& device,
    tgfx2::RenderContext2& ctx);

} // namespace termin
