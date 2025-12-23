#pragma once

#include <optional>
#include "termin/geom/vec3.hpp"
#include "termin/geom/quat.hpp"

namespace termin {
namespace animation {

/**
 * Result of sampling an animation channel.
 * Any of translation/rotation/scale can be nullopt if not animated.
 */
struct AnimationChannelSample {
    std::optional<Vec3> translation;
    std::optional<Quat> rotation;
    std::optional<double> scale;
};

} // namespace animation
} // namespace termin
