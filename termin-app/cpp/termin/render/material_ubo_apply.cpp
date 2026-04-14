// material_ubo_apply.cpp - Implementation of bind_material_ubo.
#include "termin/render/material_ubo_apply.hpp"
#include "termin/render/shader_parser.hpp"

#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/opengl/opengl_render_device.hpp"

#include <glad/glad.h>

#include <tcbase/tc_log.hpp>

#include <atomic>
#include <cstdint>
#include <cstring>
#include <span>
#include <vector>

extern "C" {
#include "tgfx/resources/tc_shader_registry.h"
}

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

// ============================================================================
// Per-phase UBO lifecycle
// ============================================================================

namespace {

// Runtime→C++ converter: build a `MaterialProperty` carrying the current
// value out of a `tc_uniform_value`. The parser's `default_value` variant
// is reused as a generic "current value" container — that's a mild naming
// abuse but avoids duplicating std140_pack logic for runtime values.
MaterialProperty property_from_uniform(const tc_uniform_value& u) {
    MaterialProperty p;
    p.name = u.name;
    switch (static_cast<tc_uniform_type>(u.type)) {
        case TC_UNIFORM_BOOL:
            p.property_type = "Bool";
            p.default_value = static_cast<bool>(u.data.i != 0);
            break;
        case TC_UNIFORM_INT:
            p.property_type = "Int";
            p.default_value = static_cast<int>(u.data.i);
            break;
        case TC_UNIFORM_FLOAT:
            p.property_type = "Float";
            p.default_value = static_cast<double>(u.data.f);
            break;
        case TC_UNIFORM_VEC2:
            p.property_type = "Vec2";
            p.default_value = std::vector<double>{u.data.v2[0], u.data.v2[1]};
            break;
        case TC_UNIFORM_VEC3:
            p.property_type = "Vec3";
            p.default_value = std::vector<double>{
                u.data.v3[0], u.data.v3[1], u.data.v3[2]
            };
            break;
        case TC_UNIFORM_VEC4:
            p.property_type = "Vec4";
            p.default_value = std::vector<double>{
                u.data.v4[0], u.data.v4[1], u.data.v4[2], u.data.v4[3]
            };
            break;
        case TC_UNIFORM_MAT4: {
            p.property_type = "Mat4";
            std::vector<double> v;
            v.reserve(16);
            for (int i = 0; i < 16; i++) v.push_back(u.data.m4[i]);
            p.default_value = std::move(v);
            break;
        }
        default:
            // TC_UNIFORM_NONE / TC_UNIFORM_FLOAT_ARRAY — not handled by
            // std140_pack at this stage. Leave empty; the packer will skip.
            p.property_type = "";
            break;
    }
    return p;
}

// Build a throwaway MaterialUboLayout copy from a tc_shader's C-side
// entries so we can hand it to std140_pack. We cannot just cast the C
// array — std140_pack consumes a C++ MaterialUboLayout with std::string
// names inside MaterialUboEntry.
MaterialUboLayout layout_from_tc_shader(const tc_shader* shader) {
    MaterialUboLayout layout;
    if (!shader) return layout;
    layout.block_size = shader->material_ubo_block_size;
    layout.entries.reserve(shader->material_ubo_entry_count);
    for (uint32_t i = 0; i < shader->material_ubo_entry_count; i++) {
        const tc_material_ubo_entry& src = shader->material_ubo_entries[i];
        MaterialUboEntry e;
        e.name = src.name;
        e.property_type = src.property_type;
        e.offset = src.offset;
        e.size = src.size;
        layout.entries.push_back(std::move(e));
    }
    return layout;
}

// --- Release callback (C ABI, registered with tc_material) ---
//
// The phase owns a tgfx2::BufferHandle (stored as uint32_t) plus a back
// pointer to the IRenderDevice that minted it. On phase destroy, the C
// layer calls us to invoke IRenderDevice::destroy on the handle. This
// mirrors the tgfx2_shader_device back-pointer on tc_gpu_slot from
// Stage 5.A.
extern "C" void material_phase_release_ubo_cb(tc_material_phase* phase) {
    if (!phase || phase->ubo_id == 0 || !phase->ubo_device) return;
    auto* device = static_cast<tgfx2::IRenderDevice*>(phase->ubo_device);
    tgfx2::BufferHandle handle{};
    handle.id = phase->ubo_id;
    device->destroy(handle);
    // Field reset happens in tc_material_phase_release_ubo in the C
    // registry — we just do the GPU destroy here.
}

// C ABI wrapper so legacy GL passes that live outside termin-app (e.g.
// MaterialPass in termin-components-render) can call the dispatcher via
// tc_material_phase_apply_ubo_gl without linking termin-app.
extern "C" bool material_phase_apply_ubo_gl_cb(
    tc_material_phase* phase,
    const tc_shader* shader,
    uint32_t binding_slot,
    void* tgfx2_device
) {
    if (!tgfx2_device) return false;
    auto* device = static_cast<tgfx2::IRenderDevice*>(tgfx2_device);
    return termin::apply_material_phase_ubo_gl(phase, shader, binding_slot, *device);
}

std::atomic<bool> g_callbacks_installed{false};

void ensure_release_cb_installed() {
    bool expected = false;
    if (g_callbacks_installed.compare_exchange_strong(expected, true)) {
        tc_material_phase_set_release_ubo_callback(material_phase_release_ubo_cb);
        tc_material_phase_set_apply_ubo_gl_callback(material_phase_apply_ubo_gl_cb);
    }
}

} // namespace

tgfx2::BufferHandle ensure_material_phase_ubo(
    tc_material_phase* phase,
    const tc_shader* shader,
    tgfx2::IRenderDevice& device)
{
    if (!phase || !shader) return {};
    uint32_t block_size = shader->material_ubo_block_size;
    if (block_size == 0) {
        // Shader has no material UBO layout (e.g. raw shader without
        // @property). If a stale UBO is still attached to the phase
        // from a previous shader version that had one, release it.
        if (phase->ubo_id != 0) {
            tc_material_phase_release_ubo(phase);
        }
        return {};
    }

    ensure_release_cb_installed();

    // Detect staleness: different size, or the device back pointer points
    // elsewhere (different tgfx2 device — shouldn't happen in production
    // but is defensive), or the shader version differs from what the UBO
    // was allocated against.
    int32_t shader_version = static_cast<int32_t>(shader->version);
    bool stale =
        phase->ubo_id == 0 ||
        phase->ubo_size != block_size ||
        phase->ubo_device != &device ||
        phase->ubo_version != shader_version;

    if (stale) {
        // If the phase already had a UBO (same device), destroy it before
        // allocating a new one. If the device pointer is different we
        // leak — that's the "device changed under us" case which we log
        // and accept in favour of not double-freeing.
        if (phase->ubo_id != 0 && phase->ubo_device == &device) {
            tgfx2::BufferHandle old{};
            old.id = phase->ubo_id;
            device.destroy(old);
        } else if (phase->ubo_id != 0) {
            tc::Log::error("ensure_material_phase_ubo: phase UBO leak — device changed");
        }

        tgfx2::BufferDesc desc;
        desc.size = block_size;
        desc.usage = tgfx2::BufferUsage::Uniform | tgfx2::BufferUsage::CopyDst;
        tgfx2::BufferHandle fresh = device.create_buffer(desc);

        phase->ubo_id = fresh.id;
        phase->ubo_size = block_size;
        phase->ubo_version = shader_version;
        phase->ubo_device = &device;

        // Diagnostic marker: a tc_material_phase grew a new UBO. Fires
        // once on first draw per material phase and after hot-reload /
        // resize events. Useful for confirming the pilot path ran.
        tc::Log::error("[Stage 5.H] allocated material UBO: phase=%s shader_pool_idx=%u "
                       "block_size=%u buffer_id=%u shader_version=%d",
                       phase->phase_mark, shader->pool_index, block_size,
                       fresh.id, shader_version);
        return fresh;
    }

    tgfx2::BufferHandle h{};
    h.id = phase->ubo_id;
    return h;
}

bool apply_material_phase_ubo(
    tc_material_phase* phase,
    const tc_shader* shader,
    uint32_t ubo_slot,
    uint32_t tex_slot_start,
    tgfx2::IRenderDevice& device,
    tgfx2::RenderContext2& ctx)
{
    if (!phase || !shader) return false;
    if (shader->material_ubo_block_size == 0) return false;

    tgfx2::BufferHandle ubo = ensure_material_phase_ubo(phase, shader, device);
    if (!ubo) return false;

    // Translate phase uniforms (C) into MaterialProperty (C++) for
    // std140_pack. Linear, tiny (≤ 32 uniforms).
    std::vector<MaterialProperty> values;
    values.reserve(phase->uniform_count);
    for (size_t i = 0; i < phase->uniform_count; i++) {
        values.push_back(property_from_uniform(phase->uniforms[i]));
    }

    // Build the layout view on the tc_shader C-side entries.
    MaterialUboLayout layout = layout_from_tc_shader(shader);

    // Textures: bind each phase texture at successive slots. The shader
    // must declare samplers with matching `layout(binding = N)` qualifiers
    // or rely on tc_shader set_block_binding for block-based textures.
    // For per-texture samplers we bind by index order starting at
    // `tex_slot_start` — the shader author is responsible for keeping the
    // declaration order in the .shader file in sync with the sampler
    // binding slots in the fragment stage.
    std::vector<MaterialTextureBinding> textures;
    textures.reserve(phase->texture_count);
    for (size_t i = 0; i < phase->texture_count; i++) {
        (void)phase->textures[i];
        // tc_texture_handle → tgfx2::TextureHandle conversion needs the
        // texture registry bridge (tc_texture_get_gl_id → register_external
        // _texture via an existing helper). Not implemented at this stage;
        // the first pilot shader will be texture-free to keep Stage 5.H
        // focused. Textures land in Stage 5.H.1.
    }

    bind_material_ubo(layout, values, textures, ubo, ubo_slot, device, ctx);
    return true;
}

bool apply_material_phase_ubo_gl(
    tc_material_phase* phase,
    const tc_shader* shader,
    uint32_t binding_slot,
    tgfx2::IRenderDevice& device)
{
    if (!phase || !shader) return false;
    if (shader->material_ubo_block_size == 0) return false;

    // Allocate (or reuse) the phase's tgfx2 buffer. Ownership stays
    // with the phase; we get its gl id and drive GL directly.
    tgfx2::BufferHandle ubo = ensure_material_phase_ubo(phase, shader, device);
    if (!ubo) return false;

    auto* gl_dev = dynamic_cast<tgfx2::OpenGLRenderDevice*>(&device);
    if (!gl_dev) {
        tc::Log::error("apply_material_phase_ubo_gl: device is not OpenGLRenderDevice");
        return false;
    }
    auto* gl_buf = gl_dev->get_buffer(ubo);
    if (!gl_buf || gl_buf->gl_id == 0) {
        tc::Log::error("apply_material_phase_ubo_gl: tgfx2 buffer has no GL id");
        return false;
    }

    // Pack the phase's current uniform values into a std140 staging buffer.
    // Zero-initialised so unset slots render as zero (deterministic default).
    MaterialUboLayout layout = layout_from_tc_shader(shader);
    std::vector<uint8_t> staging(layout.block_size, 0);

    std::vector<MaterialProperty> values;
    values.reserve(phase->uniform_count);
    for (size_t i = 0; i < phase->uniform_count; i++) {
        values.push_back(property_from_uniform(phase->uniforms[i]));
    }
    std140_pack(layout, values, staging.data());

    // Upload + bind directly. The legacy ColorPass draw loop's
    // glUseProgram + glDraw that follows this will pick up the binding
    // via glGetUniformBlockIndex / glUniformBlockBinding performed by
    // TcShader::set_block_binding (the caller must invoke that).
    glBindBuffer(GL_UNIFORM_BUFFER, gl_buf->gl_id);
    glBufferSubData(GL_UNIFORM_BUFFER, 0,
                    static_cast<GLsizeiptr>(layout.block_size),
                    staging.data());
    glBindBufferRange(GL_UNIFORM_BUFFER, binding_slot, gl_buf->gl_id,
                      0, static_cast<GLsizeiptr>(layout.block_size));
    glBindBuffer(GL_UNIFORM_BUFFER, 0);

    return true;
}

} // namespace termin
