import termin_prelude;
import termin_lighting;
__exported import termin_shadow_data;

#ifndef TERMIN_MAX_SHADOW_SAMPLERS
#define TERMIN_MAX_SHADOW_SAMPLERS 16
#endif

[[TerminScope("pass")]]
public Sampler2DShadow shadow_maps[TERMIN_MAX_SHADOW_SAMPLERS];

public float sample_shadow_map(int sm, float2 uv, float depth) {
    // Shadow maps have one mip level. An explicit LOD keeps comparison
    // sampling valid inside runtime light and filter loops on D3D11.
    switch (sm) {
        case 0: return shadow_maps[0].SampleCmpLevelZero(uv, depth);
        case 1: return shadow_maps[1].SampleCmpLevelZero(uv, depth);
        case 2: return shadow_maps[2].SampleCmpLevelZero(uv, depth);
        case 3: return shadow_maps[3].SampleCmpLevelZero(uv, depth);
        case 4: return shadow_maps[4].SampleCmpLevelZero(uv, depth);
        case 5: return shadow_maps[5].SampleCmpLevelZero(uv, depth);
        case 6: return shadow_maps[6].SampleCmpLevelZero(uv, depth);
        case 7: return shadow_maps[7].SampleCmpLevelZero(uv, depth);
#if TERMIN_MAX_SHADOW_SAMPLERS > 8
        case 8: return shadow_maps[8].SampleCmpLevelZero(uv, depth);
        case 9: return shadow_maps[9].SampleCmpLevelZero(uv, depth);
        case 10: return shadow_maps[10].SampleCmpLevelZero(uv, depth);
        case 11: return shadow_maps[11].SampleCmpLevelZero(uv, depth);
        case 12: return shadow_maps[12].SampleCmpLevelZero(uv, depth);
        case 13: return shadow_maps[13].SampleCmpLevelZero(uv, depth);
        case 14: return shadow_maps[14].SampleCmpLevelZero(uv, depth);
        case 15: return shadow_maps[15].SampleCmpLevelZero(uv, depth);
#endif
        default: return 1.0;
    }
}

#include "termin_shadow_filter.slang"

public int find_shadow_map_for_cascade(int light_index, int cascade_index) {
    for (int sm = 0; sm < shadow_block.u_shadow_map_count; ++sm) {
        if (shadow_block.u_shadow_light_index[sm] == light_index &&
            shadow_block.u_shadow_cascade_index[sm] == cascade_index) {
            return sm;
        }
    }
    return -1;
}

public int find_shadow_map_for_depth(int light_index, float view_depth) {
    for (int sm = 0; sm < shadow_block.u_shadow_map_count; ++sm) {
        if (shadow_block.u_shadow_light_index[sm] != light_index) continue;
        float split_near = shadow_block.u_shadow_split_near[sm];
        float split_far = shadow_block.u_shadow_split_far[sm];
        if (view_depth >= split_near && view_depth <= split_far) {
            return sm;
        }
    }
    return -1;
}

public float compute_single_shadow(int light_index, float3 world_pos) {
    float result = 1.0;
    int sm = find_shadow_map_for_cascade(light_index, 0);
    if (sm >= 0) {
        float visibility = compute_shadow_candidate(sm, light_index, world_pos);
        if (visibility >= 0.0) result = visibility;
    }
    return result;
}

public float compute_cascaded_shadow(int light_index, int cascade_count, float3 world_pos) {
    float4 world = float4(world_pos, 1.0);
    float view_depth = dot(shadow_block.u_camera_view_depth, world);
    int cascade_sm = find_shadow_map_for_depth(light_index, view_depth);
    if (cascade_sm < 0) return 1.0;
    float primary = 1.0;
    float primary_candidate = compute_shadow_candidate(cascade_sm, light_index, world_pos);
    if (primary_candidate >= 0.0) primary = primary_candidate;

    if (!get_light_cascade_blend(light_index)) return primary;
    int cascade_index = shadow_block.u_shadow_cascade_index[cascade_sm];
    if (cascade_index + 1 >= cascade_count) return primary;

    float split_far = shadow_block.u_shadow_split_far[cascade_sm];
    float split_near = shadow_block.u_shadow_split_near[cascade_sm];
    float blend_distance = min(
        max(get_light_blend_distance(light_index), 0.0),
        max(split_far - split_near, 0.0));
    if (blend_distance <= 0.0 || view_depth < split_far - blend_distance) {
        return primary;
    }

    int next_sm = find_shadow_map_for_cascade(light_index, cascade_index + 1);
    if (next_sm < 0) return primary;
    float secondary = compute_shadow_candidate(next_sm, light_index, world_pos);
    if (secondary < 0.0) return primary;
    float blend = saturate((view_depth - (split_far - blend_distance)) / blend_distance);
    return lerp(primary, secondary, blend);
}

public float compute_shadow_auto(int light_index, float3 world_pos) {
    int cascade_count = max(get_light_cascade_count(light_index), 1);
    float result = 1.0;
    if (cascade_count == 1) {
        result = compute_single_shadow(light_index, world_pos);
    } else {
        result = compute_cascaded_shadow(light_index, cascade_count, world_pos);
    }
    return result;
}
