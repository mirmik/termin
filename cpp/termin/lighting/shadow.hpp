#pragma once

#include <vector>
#include "termin/geom/mat44.hpp"
#include "termin/lighting/shadow_settings.hpp"

namespace termin {

/**
 * Shadow map entry for one light source (or cascade).
 *
 * Contains the light-space matrix for transforming world coordinates
 * to the light's clip space, and the index of the light in the lights array.
 * For CSM, each cascade has a separate entry with its own matrix and split distances.
 */
struct ShadowMapEntry {
    Mat44f light_space_matrix;
    int light_index = 0;

    // Cascade parameters
    int cascade_index = 0;           // Cascade index (0-3)
    float cascade_split_near = 0.0f; // Near split distance (view-space Z)
    float cascade_split_far = 0.0f;  // Far split distance (view-space Z)

    ShadowMapEntry() = default;

    ShadowMapEntry(const Mat44f& matrix, int idx)
        : light_space_matrix(matrix), light_index(idx) {}

    ShadowMapEntry(const Mat44f& matrix, int light_idx, int cascade_idx,
                   float split_near, float split_far)
        : light_space_matrix(matrix), light_index(light_idx),
          cascade_index(cascade_idx), cascade_split_near(split_near),
          cascade_split_far(split_far) {}
};

// ShadowSettings is defined in shadow_settings.hpp

} // namespace termin
