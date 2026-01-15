#pragma once

#include <vector>
#include <string>

#include "termin/lighting/shadow.hpp"
#include "termin/render/shader_program.hpp"
#include "termin/render/tc_shader_handle.hpp"

namespace termin {

constexpr int MAX_SHADOW_MAPS = 16;  // 4 lights * 4 cascades
constexpr int MAX_CASCADES = 4;
constexpr int SHADOW_MAP_TEXTURE_UNIT_START = 8;

/**
 * Upload shadow maps uniforms.
 *
 * Uniforms:
 *   u_shadow_map_count: int
 *   u_shadow_map[i]: int (texture unit)
 *   u_light_space_matrix[i]: mat4
 *   u_shadow_light_index[i]: int
 *   u_shadow_cascade_index[i]: int
 *   u_shadow_split_near[i]: float
 *   u_shadow_split_far[i]: float
 *
 * Note: Shadow map textures must be bound by the caller before rendering.
 * This function only sets the uniform values.
 */
inline void upload_shadow_maps_to_shader(ShaderProgram* shader, const std::vector<ShadowMapEntry>& shadow_maps) {
    int count = static_cast<int>(std::min(shadow_maps.size(), static_cast<size_t>(MAX_SHADOW_MAPS)));
    shader->set_uniform_int("u_shadow_map_count", count);

    for (int i = 0; i < count; ++i) {
        const ShadowMapEntry& entry = shadow_maps[i];
        std::string idx = "[" + std::to_string(i) + "]";

        // Texture unit for sampler2DShadow
        shader->set_uniform_int(("u_shadow_map" + idx).c_str(), SHADOW_MAP_TEXTURE_UNIT_START + i);

        // Light-space matrix: P_light * V_light (no transpose - Mat44f is already column-major)
        shader->set_uniform_matrix4(("u_light_space_matrix" + idx).c_str(), entry.light_space_matrix, false);

        // Light index (for matching with u_light_* arrays)
        shader->set_uniform_int(("u_shadow_light_index" + idx).c_str(), entry.light_index);

        // Cascade parameters
        shader->set_uniform_int(("u_shadow_cascade_index" + idx).c_str(), entry.cascade_index);
        shader->set_uniform_float(("u_shadow_split_near" + idx).c_str(), entry.cascade_split_near);
        shader->set_uniform_float(("u_shadow_split_far" + idx).c_str(), entry.cascade_split_far);
    }

    // Set remaining samplers to their units (for AMD drivers)
    for (int i = count; i < MAX_SHADOW_MAPS; ++i) {
        std::string idx = "[" + std::to_string(i) + "]";
        shader->set_uniform_int(("u_shadow_map" + idx).c_str(), SHADOW_MAP_TEXTURE_UNIT_START + i);
    }
}

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
inline void upload_shadow_maps_to_shader(TcShader& shader, const std::vector<ShadowMapEntry>& shadow_maps) {
    int count = static_cast<int>(std::min(shadow_maps.size(), static_cast<size_t>(MAX_SHADOW_MAPS)));
    shader.set_uniform_int("u_shadow_map_count", count);

    for (int i = 0; i < count; ++i) {
        const ShadowMapEntry& entry = shadow_maps[i];

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

} // namespace termin
