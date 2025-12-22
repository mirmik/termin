#pragma once

#include <string>
#include <unordered_map>
#include <cmath>

#include "animation_channel.hpp"

namespace termin {
namespace animation {

/**
 * Animation clip containing multiple channels.
 * Stores time in ticks, provides sample() in seconds.
 */
class AnimationClip {
public:
    std::string name;
    std::unordered_map<std::string, AnimationChannel> channels;
    double tps = 30.0;  // ticks per second
    double duration = 0.0;  // in seconds
    bool loop = true;

    AnimationClip() = default;

    AnimationClip(std::string name_,
                  std::unordered_map<std::string, AnimationChannel> channels_,
                  double tps_,
                  bool loop_ = true)
        : name(std::move(name_))
        , channels(std::move(channels_))
        , tps(tps_)
        , loop(loop_)
    {
        // Compute duration in seconds
        double max_ticks = 0.0;
        for (const auto& [_, ch] : channels) {
            max_ticks = std::max(max_ticks, ch.duration);
        }
        duration = (tps > 0.0) ? max_ticks / tps : 0.0;
    }

    /**
     * Sample all channels at time t_seconds.
     * Returns map: channel_name -> AnimationChannelSample
     */
    std::unordered_map<std::string, AnimationChannelSample> sample(double t_seconds) const {
        if (loop && duration > 0.0) {
            t_seconds = std::fmod(t_seconds, duration);
            if (t_seconds < 0.0) t_seconds += duration;
        }

        double t_ticks = t_seconds * tps;

        std::unordered_map<std::string, AnimationChannelSample> result;
        result.reserve(channels.size());

        for (const auto& [name, channel] : channels) {
            result[name] = channel.sample(t_ticks);
        }

        return result;
    }
};

} // namespace animation
} // namespace termin
