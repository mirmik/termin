import termin_prelude;
import termin_lighting;
import termin_shadow_data;

// Scalar binding for materials authored for a single shadow-casting light.
// Both receivers use the same pass UBO, projection and filtering.
[[TerminScope("pass")]]
public Sampler2DShadow single_shadow_map;

public float sample_shadow_map(int sm, float2 uv, float depth) {
    return single_shadow_map.SampleCmpLevelZero(uv, depth);
}

#include "termin_shadow_filter.slang"

public float compute_single_shadow(int light_index, float3 world_pos) {
    float visibility = compute_shadow_candidate(0, light_index, world_pos);
    return visibility < 0.0 ? 1.0 : visibility;
}
