#pragma once

#include <vector>
#include <string>

#include "termin/lighting/shadow.hpp"
#include "termin/texture/tc_texture_handle.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include <tcbase/tc_log.hpp>

namespace termin {

constexpr int MAX_SHADOW_MAPS = 16;  // 4 lights * 4 cascades
constexpr int MAX_CASCADES = 4;
constexpr int SHADOW_MAP_TEXTURE_UNIT_START = 8;

// Static uniform names to avoid allocations
namespace detail {
    constexpr const char* shadow_map_names[] = {
        "u_shadow_map[0]", "u_shadow_map[1]", "u_shadow_map[2]", "u_shadow_map[3]",
        "u_shadow_map[4]", "u_shadow_map[5]", "u_shadow_map[6]", "u_shadow_map[7]",
        "u_shadow_map[8]", "u_shadow_map[9]", "u_shadow_map[10]", "u_shadow_map[11]",
        "u_shadow_map[12]", "u_shadow_map[13]", "u_shadow_map[14]", "u_shadow_map[15]"
    };
    constexpr const char* light_space_matrix_names[] = {
        "u_light_space_matrix[0]", "u_light_space_matrix[1]", "u_light_space_matrix[2]", "u_light_space_matrix[3]",
        "u_light_space_matrix[4]", "u_light_space_matrix[5]", "u_light_space_matrix[6]", "u_light_space_matrix[7]",
        "u_light_space_matrix[8]", "u_light_space_matrix[9]", "u_light_space_matrix[10]", "u_light_space_matrix[11]",
        "u_light_space_matrix[12]", "u_light_space_matrix[13]", "u_light_space_matrix[14]", "u_light_space_matrix[15]"
    };
    constexpr const char* shadow_light_index_names[] = {
        "u_shadow_light_index[0]", "u_shadow_light_index[1]", "u_shadow_light_index[2]", "u_shadow_light_index[3]",
        "u_shadow_light_index[4]", "u_shadow_light_index[5]", "u_shadow_light_index[6]", "u_shadow_light_index[7]",
        "u_shadow_light_index[8]", "u_shadow_light_index[9]", "u_shadow_light_index[10]", "u_shadow_light_index[11]",
        "u_shadow_light_index[12]", "u_shadow_light_index[13]", "u_shadow_light_index[14]", "u_shadow_light_index[15]"
    };
    constexpr const char* shadow_cascade_index_names[] = {
        "u_shadow_cascade_index[0]", "u_shadow_cascade_index[1]", "u_shadow_cascade_index[2]", "u_shadow_cascade_index[3]",
        "u_shadow_cascade_index[4]", "u_shadow_cascade_index[5]", "u_shadow_cascade_index[6]", "u_shadow_cascade_index[7]",
        "u_shadow_cascade_index[8]", "u_shadow_cascade_index[9]", "u_shadow_cascade_index[10]", "u_shadow_cascade_index[11]",
        "u_shadow_cascade_index[12]", "u_shadow_cascade_index[13]", "u_shadow_cascade_index[14]", "u_shadow_cascade_index[15]"
    };
    constexpr const char* shadow_split_near_names[] = {
        "u_shadow_split_near[0]", "u_shadow_split_near[1]", "u_shadow_split_near[2]", "u_shadow_split_near[3]",
        "u_shadow_split_near[4]", "u_shadow_split_near[5]", "u_shadow_split_near[6]", "u_shadow_split_near[7]",
        "u_shadow_split_near[8]", "u_shadow_split_near[9]", "u_shadow_split_near[10]", "u_shadow_split_near[11]",
        "u_shadow_split_near[12]", "u_shadow_split_near[13]", "u_shadow_split_near[14]", "u_shadow_split_near[15]"
    };
    constexpr const char* shadow_split_far_names[] = {
        "u_shadow_split_far[0]", "u_shadow_split_far[1]", "u_shadow_split_far[2]", "u_shadow_split_far[3]",
        "u_shadow_split_far[4]", "u_shadow_split_far[5]", "u_shadow_split_far[6]", "u_shadow_split_far[7]",
        "u_shadow_split_far[8]", "u_shadow_split_far[9]", "u_shadow_split_far[10]", "u_shadow_split_far[11]",
        "u_shadow_split_far[12]", "u_shadow_split_far[13]", "u_shadow_split_far[14]", "u_shadow_split_far[15]"
    };
}

// TcShader version (no allocations)
inline void upload_shadow_maps_to_shader(TcShader& shader, const std::vector<ShadowMapArrayEntry>& shadow_maps) {
    int count = static_cast<int>(std::min(shadow_maps.size(), static_cast<size_t>(MAX_SHADOW_MAPS)));
    shader.set_uniform_int("u_shadow_map_count", count);

    for (int i = 0; i < count; ++i) {
        const ShadowMapArrayEntry& entry = shadow_maps[i];

        shader.set_uniform_int(detail::shadow_map_names[i], SHADOW_MAP_TEXTURE_UNIT_START + i);
        shader.set_uniform_mat4(detail::light_space_matrix_names[i], entry.light_space_matrix.data, false);
        shader.set_uniform_int(detail::shadow_light_index_names[i], entry.light_index);
        shader.set_uniform_int(detail::shadow_cascade_index_names[i], entry.cascade_index);
        shader.set_uniform_float(detail::shadow_split_near_names[i], entry.cascade_split_near);
        shader.set_uniform_float(detail::shadow_split_far_names[i], entry.cascade_split_far);
    }

    // CRITICAL: Set remaining samplers to their dedicated units (for AMD drivers)
    // sampler2DShadow uniforms default to unit 0, which conflicts with material textures (sampler2D)
    // AMD strictly enforces that different sampler types cannot share the same texture unit
    for (int i = count; i < MAX_SHADOW_MAPS; ++i) {
        shader.set_uniform_int(detail::shadow_map_names[i], SHADOW_MAP_TEXTURE_UNIT_START + i);
    }
}

/**
 * Initialize shadow map sampler uniforms to their dedicated texture units.
 * MUST be called when switching shaders, even if no shadow maps are used.
 *
 * On AMD drivers, sampler2DShadow uniforms default to texture unit 0.
 * This conflicts with material textures (sampler2D) which also use unit 0,
 * causing "Different sampler types for same sample texture unit" errors.
 */
inline void init_shadow_map_samplers(TcShader& shader) {
    shader.set_uniform_int("u_shadow_map_count", 0);
    for (int i = 0; i < MAX_SHADOW_MAPS; ++i) {
        shader.set_uniform_int(detail::shadow_map_names[i], SHADOW_MAP_TEXTURE_UNIT_START + i);
    }
}

/**
 * Bind shadow map textures to their texture units.
 * Call this ONCE per frame, before rendering any draw calls.
 *
 * Binds actual shadow textures from entries, and fills remaining slots
 * with dummy shadow texture (required by AMD drivers).
 */
inline void bind_shadow_textures(const std::vector<ShadowMapArrayEntry>& shadow_maps) {
    int bound_count = 0;

    // Bind actual shadow textures
    for (size_t i = 0; i < shadow_maps.size() && i < static_cast<size_t>(MAX_SHADOW_MAPS); ++i) {
        GPUTextureHandle* tex = shadow_maps[i].texture();
        if (tex) {
            tex->bind(SHADOW_MAP_TEXTURE_UNIT_START + static_cast<int>(i));
            ++bound_count;
        }
    }

    // Bind dummy texture to remaining slots (AMD compatibility)
    TcTexture dummy = TcTexture::dummy_shadow_1x1();
    for (int i = bound_count; i < MAX_SHADOW_MAPS; ++i) {
        dummy.bind_gpu(SHADOW_MAP_TEXTURE_UNIT_START + i);
    }
}

} // namespace termin
