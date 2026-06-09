// material_ubo_apply.cpp - Implementation of bind_material_ubo.
#include "termin/render/material_ubo_apply.hpp"
#include "termin/materials/shader_parser.hpp"
#include "termin/render/tgfx2_bridge.hpp"

#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"
#include "tcbase/tc_log.hpp"

#include <cstdint>
#include <cstring>
#include <vector>

extern "C" {
#include "tgfx/resources/tc_shader_registry.h"
}

namespace termin {

uint32_t material_ubo_binding_for_shader(
    const tc_shader* shader,
    uint32_t fallback_binding)
{
    const tc_shader_resource_binding* binding =
        tc_shader_find_resource_binding(shader, TC_SHADER_RESOURCE_MATERIAL);
    if (!binding) {
        return fallback_binding;
    }
    if (binding->kind != TC_SHADER_RESOURCE_CONSTANT_BUFFER) {
        tc::Log::error(
            "Shader resource '%s' has kind %u, expected constant buffer; using fallback binding %u",
            TC_SHADER_RESOURCE_MATERIAL,
            binding->kind,
            fallback_binding);
        return fallback_binding;
    }
    return binding->binding;
}

// Look up the descriptor set index for the material resource binding.
// Returns 0 for legacy GLSL shaders (shared layout); returns 1 for Slang
// shaders in the two-set scheme.
static uint32_t material_ubo_set_for_shader(const tc_shader* shader) {
    const tc_shader_resource_binding* binding =
        tc_shader_find_resource_binding(shader, TC_SHADER_RESOURCE_MATERIAL);
    if (!binding) return 0;  // legacy: no resource metadata → set=0
    return binding->set;
}

void bind_material_ubo(
    const MaterialUboLayout& layout,
    const std::vector<MaterialProperty>& values,
    const std::vector<MaterialTextureBinding>& textures,
    uint32_t ubo_slot,
    uint32_t set,
    tgfx::RenderContext2& ctx)
{
    if (!layout.empty()) {
        // Zero-initialised staging — unset properties become zero bytes,
        // which matches std140 padding expectations and gives deterministic
        // defaults when hot-reload drops a property between frames.
        std::vector<uint8_t> staging(layout.block_size, 0);
        std140_pack(layout, values, staging.data());

        // RenderContext2 owns the backend-specific transient path:
        // Vulkan uses the device ring UBO, while backends without a ring
        // allocate a deferred transient UBO. Material phases therefore do
        // not need to carry GPU buffer handles.
        ctx.bind_uniform_buffer_ring(ubo_slot, staging.data(),
                                     static_cast<uint32_t>(staging.size()),
                                     set);
    }

    for (const auto& tex : textures) {
        ctx.bind_sampled_texture(tex.slot, tex.texture, tex.sampler, set);
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

} // namespace

bool apply_material_phase_ubo(
    tc_material_phase* phase,
    const tc_shader* shader,
    uint32_t ubo_slot,
    uint32_t tex_slot_start,
    tgfx::IRenderDevice& device,
    tgfx::RenderContext2& ctx)
{
    if (!phase || !shader) return false;
    (void)tex_slot_start;

    // Translate phase uniforms (C) into MaterialProperty (C++) for
    // std140_pack. Linear, tiny (≤ 32 uniforms).
    std::vector<MaterialProperty> values;
    values.reserve(phase->uniform_count);
    for (size_t i = 0; i < phase->uniform_count; i++) {
        values.push_back(property_from_uniform(phase->uniforms[i]));
    }

    // Build the layout view on the tc_shader C-side entries.
    MaterialUboLayout layout = layout_from_tc_shader(shader);
    uint32_t resolved_ubo_slot =
        material_ubo_binding_for_shader(shader, ubo_slot);

    // Wrap each phase texture as a tgfx::TextureHandle. The active
    // IRenderDevice owns the bridge cache; callers must not defer-destroy
    // these handles. Sampler slots start at tex_slot_start and increment
    // in declaration order; shader_parser emits matching layout(binding=N)
    // qualifiers for .shader @property Texture entries.
    std::vector<MaterialTextureBinding> textures;
    textures.reserve(phase->texture_count);
    for (size_t i = 0; i < phase->texture_count; i++) {
        const tc_material_texture& mat_tex = phase->textures[i];
        if (tc_texture_handle_is_invalid(mat_tex.texture)) {
            continue;
        }
        tgfx::TextureHandle tex2 =
            wrap_tc_texture_as_tgfx2(device, mat_tex.texture);
        if (tex2) {
            MaterialTextureBinding b;
            b.slot = material_texture_binding_for_index(static_cast<uint32_t>(i));
            b.texture = tex2;
            textures.push_back(b);
        }
    }

    bind_material_ubo(layout, values, textures, resolved_ubo_slot,
                      material_ubo_set_for_shader(shader), ctx);
    return !layout.empty() || !textures.empty();
}

} // namespace termin
