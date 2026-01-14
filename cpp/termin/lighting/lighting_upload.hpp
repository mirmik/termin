#pragma once

#include <vector>
#include <string>

#include "termin/lighting/shadow.hpp"
#include "termin/render/shader_program.hpp"

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

} // namespace termin
