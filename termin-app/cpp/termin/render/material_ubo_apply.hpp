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

extern "C" {
#include "tgfx/resources/tc_material.h"
#include "tgfx/resources/tc_shader.h"
}

namespace tgfx2 {
class IRenderDevice;
class RenderContext2;
}

namespace termin {

// Reserved GL UBO binding slot for the per-material std140 block.
// Convention:
//   slot 0  — per-frame / lighting (LIGHTING_UBO_BINDING in ColorPass;
//             PerFrame view/proj in ShadowPass/DepthPass/NormalPass/IdPass)
//   slot 1  — per-material (this)
//   slot 14 — per-object push constants (TGFX2_PUSH_CONSTANTS_BINDING)
constexpr uint32_t MATERIAL_UBO_BINDING = 1;

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

// Ensure `phase` has a tgfx2 UBO that matches the current shader's
// material_ubo_block_size. Allocates on first call, reallocates on
// shader version bump or block resize. Installs the phase-release
// callback the first time it is invoked so tc_material_release can
// tear down the UBO later without knowing about tgfx2.
//
// Returns a BufferHandle wrapping `phase->ubo_id`. If the shader has no
// material UBO layout (block_size == 0), returns an invalid handle and
// leaves the phase fields cleared.
tgfx2::BufferHandle ensure_material_phase_ubo(
    tc_material_phase* phase,
    const tc_shader* shader,
    tgfx2::IRenderDevice& device);

// Dispatch entry point: if `shader` declares a material UBO layout,
// packs + uploads the phase's uniforms + binds the UBO at `ubo_slot`
// (creating it lazily). Textures from phase->textures[] are bound
// starting at `tex_slot_start` (one slot per entry, in declared order).
// Returns true when the UBO path ran; false when the shader has no
// layout and the caller should fall back to legacy per-uniform
// dispatch.
bool apply_material_phase_ubo(
    tc_material_phase* phase,
    const tc_shader* shader,
    uint32_t ubo_slot,
    uint32_t tex_slot_start,
    tgfx2::IRenderDevice& device,
    tgfx2::RenderContext2& ctx);

// Raw-GL variant: same as apply_material_phase_ubo but bypasses
// RenderContext2 entirely and binds the UBO via direct
// glBindBufferRange at slot `binding_slot`. Intended for use from
// legacy GL-state-machine passes (ColorPass / MaterialPass before
// their tgfx2 migration lands) that cannot open a tgfx2 render pass.
// Caller still owns glUseProgram of the legacy TcShader and is
// responsible for calling shader.set_block_binding("MaterialParams",
// binding_slot) so the compiled program reads from the right slot.
//
// Allocation lifetime goes through the same ensure_material_phase_ubo
// path, so the UBO is reused across frames and cleaned up by
// tc_material_release.
//
// Returns true when the UBO path ran, false when the shader has no
// material layout (caller should fall back to legacy per-uniform).
bool apply_material_phase_ubo_gl(
    tc_material_phase* phase,
    const tc_shader* shader,
    uint32_t binding_slot,
    tgfx2::IRenderDevice& device);

} // namespace termin
