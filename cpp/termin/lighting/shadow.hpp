#pragma once

#include <vector>
#include "termin/geom/mat44.hpp"
#include "termin/lighting/shadow_settings.hpp"

namespace termin {

/**
 * Shadow map entry for one light source.
 *
 * Contains the light-space matrix for transforming world coordinates
 * to the light's clip space, and the index of the light in the lights array.
 */
struct ShadowMapEntry {
    Mat44f light_space_matrix;
    int light_index = 0;

    ShadowMapEntry() = default;

    ShadowMapEntry(const Mat44f& matrix, int idx)
        : light_space_matrix(matrix), light_index(idx) {}
};

// ShadowSettings is defined in shadow_settings.hpp

} // namespace termin
