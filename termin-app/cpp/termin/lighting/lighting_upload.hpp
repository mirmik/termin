#pragma once

// Shadow-map uniform-name tables + constants shared by C++ passes
// (ColorPass uses them on the ctx2 path via ctx2->set_uniform_int).
// Legacy TcShader helpers (upload_shadow_maps_to_shader,
// init_shadow_map_samplers, bind_shadow_textures) were removed in
// Stage 8.1 — nothing calls them any more, and the ctx2 path binds
// shadow textures directly via bind_sampled_texture.

#include <vector>
#include <string>

#include "termin/lighting/shadow.hpp"

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

} // namespace termin
