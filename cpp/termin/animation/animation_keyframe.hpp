#pragma once

#include <optional>
#include "termin/geom/vec3.hpp"
#include "termin/geom/quat.hpp"

namespace termin {
namespace animation {

/**
 * Animation keyframe at a specific time.
 * Any of translation/rotation/scale can be nullopt if not animated.
 */
struct AnimationKeyframe {
    double time = 0.0;
    std::optional<Vec3> translation;
    std::optional<Quat> rotation;
    std::optional<double> scale;

    AnimationKeyframe() = default;
    AnimationKeyframe(double t) : time(t) {}
    AnimationKeyframe(double t, Vec3 tr) : time(t), translation(tr) {}
    AnimationKeyframe(double t, Quat rot) : time(t), rotation(rot) {}
    AnimationKeyframe(double t, double sc) : time(t), scale(sc) {}
};

} // namespace animation
} // namespace termin
