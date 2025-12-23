#pragma once

#include <vector>
#include <algorithm>
#include <cmath>

#include "termin/geom/vec3.hpp"
#include "termin/geom/quat.hpp"
#include "animation_keyframe.hpp"
#include "animation_channel_sample.hpp"

namespace termin {
namespace animation {

/**
 * Animation channel for a single node/bone.
 * Stores keyframes for translation, rotation, and scale.
 * Time is in TICKS (not seconds).
 */
class AnimationChannel {
public:
    std::vector<AnimationKeyframe> translation_keys;
    std::vector<AnimationKeyframe> rotation_keys;
    std::vector<AnimationKeyframe> scale_keys;
    double duration = 0.0;

    AnimationChannel() = default;

    AnimationChannel(std::vector<AnimationKeyframe> tr_keys,
                     std::vector<AnimationKeyframe> rot_keys,
                     std::vector<AnimationKeyframe> sc_keys)
        : translation_keys(std::move(tr_keys))
        , rotation_keys(std::move(rot_keys))
        , scale_keys(std::move(sc_keys))
    {
        // Sort by time
        auto by_time = [](const AnimationKeyframe& a, const AnimationKeyframe& b) {
            return a.time < b.time;
        };
        std::sort(translation_keys.begin(), translation_keys.end(), by_time);
        std::sort(rotation_keys.begin(), rotation_keys.end(), by_time);
        std::sort(scale_keys.begin(), scale_keys.end(), by_time);

        // Compute duration
        duration = 0.0;
        if (!translation_keys.empty()) {
            duration = std::max(duration, translation_keys.back().time);
        }
        if (!rotation_keys.empty()) {
            duration = std::max(duration, rotation_keys.back().time);
        }
        if (!scale_keys.empty()) {
            duration = std::max(duration, scale_keys.back().time);
        }
    }

    /**
     * Sample the channel at time t_ticks.
     * Returns (translation, rotation, scale) - any can be nullopt.
     */
    AnimationChannelSample sample(double t_ticks) const {
        AnimationChannelSample result;

        if (!translation_keys.empty()) {
            result.translation = sample_translation(t_ticks);
        }
        if (!rotation_keys.empty()) {
            result.rotation = sample_rotation(t_ticks);
        }
        if (!scale_keys.empty()) {
            result.scale = sample_scale(t_ticks);
        }

        return result;
    }

private:
    Vec3 sample_translation(double t) const {
        return sample_keys_linear<Vec3>(
            translation_keys, t,
            [](const AnimationKeyframe& k) { return *k.translation; },
            [](const Vec3& a, const Vec3& b, double alpha) {
                return Vec3{
                    a.x * (1.0 - alpha) + b.x * alpha,
                    a.y * (1.0 - alpha) + b.y * alpha,
                    a.z * (1.0 - alpha) + b.z * alpha
                };
            }
        );
    }

    Quat sample_rotation(double t) const {
        return sample_keys_linear<Quat>(
            rotation_keys, t,
            [](const AnimationKeyframe& k) { return *k.rotation; },
            [](const Quat& a, const Quat& b, double alpha) {
                return quat_slerp(a, b, alpha);
            }
        );
    }

    double sample_scale(double t) const {
        return sample_keys_linear<double>(
            scale_keys, t,
            [](const AnimationKeyframe& k) { return *k.scale; },
            [](double a, double b, double alpha) {
                return a * (1.0 - alpha) + b * alpha;
            }
        );
    }

    template<typename T, typename GetValue, typename Interpolate>
    T sample_keys_linear(const std::vector<AnimationKeyframe>& keys,
                         double t,
                         GetValue get_value,
                         Interpolate interpolate) const
    {
        if (keys.empty()) {
            return T{};
        }

        const AnimationKeyframe& first = keys.front();
        const AnimationKeyframe& last = keys.back();

        if (t <= first.time) {
            return get_value(first);
        }
        if (t >= last.time) {
            return get_value(last);
        }

        // Binary search for the right interval
        size_t lo = 0;
        size_t hi = keys.size() - 1;
        while (lo + 1 < hi) {
            size_t mid = (lo + hi) / 2;
            if (keys[mid].time <= t) {
                lo = mid;
            } else {
                hi = mid;
            }
        }

        const AnimationKeyframe& k1 = keys[lo];
        const AnimationKeyframe& k2 = keys[hi];

        double dt = k2.time - k1.time;
        double alpha = (dt > 0.0) ? (t - k1.time) / dt : 0.0;

        return interpolate(get_value(k1), get_value(k2), alpha);
    }

    static Quat quat_slerp(const Quat& a, const Quat& b, double t) {
        // Compute dot product
        double dot = a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w;

        // If dot is negative, negate one quaternion to take shorter path
        Quat b_adj = b;
        if (dot < 0.0) {
            b_adj = Quat{-b.x, -b.y, -b.z, -b.w};
            dot = -dot;
        }

        // If quaternions are very close, use linear interpolation
        constexpr double DOT_THRESHOLD = 0.9995;
        if (dot > DOT_THRESHOLD) {
            Quat result{
                a.x + t * (b_adj.x - a.x),
                a.y + t * (b_adj.y - a.y),
                a.z + t * (b_adj.z - a.z),
                a.w + t * (b_adj.w - a.w)
            };
            // Normalize
            double len = std::sqrt(result.x * result.x + result.y * result.y +
                                   result.z * result.z + result.w * result.w);
            if (len > 0.0) {
                result.x /= len;
                result.y /= len;
                result.z /= len;
                result.w /= len;
            }
            return result;
        }

        // Spherical interpolation
        double theta_0 = std::acos(dot);
        double theta = theta_0 * t;
        double sin_theta = std::sin(theta);
        double sin_theta_0 = std::sin(theta_0);

        double s0 = std::cos(theta) - dot * sin_theta / sin_theta_0;
        double s1 = sin_theta / sin_theta_0;

        return Quat{
            s0 * a.x + s1 * b_adj.x,
            s0 * a.y + s1 * b_adj.y,
            s0 * a.z + s1 * b_adj.z,
            s0 * a.w + s1 * b_adj.w
        };
    }
};

} // namespace animation
} // namespace termin
