#pragma once

#include <vector>
#include <string>
#include <unordered_map>

#include "termin/entity/component.hpp"
#include "termin/entity/component_registry.hpp"
#include "termin/animation/tc_animation_handle.hpp"
#include "termin/skeleton/skeleton_instance.hpp"

namespace termin {

class SkeletonController;

// AnimationPlayer - plays animation clips on skeleton.
//
// Stores clips, current clip, time. Updates skeleton bones each frame.
// Can be controlled externally (playing=false) via update_bones_at_time().
class AnimationPlayer : public CxxComponent {
public:
    // Clip handles for serialization
    std::vector<animation::TcAnimationClip> clips;

    // Current clip name (for serialization, underscore prefix for compatibility)
    std::string _current_clip_name;

    // Playback state
    double time = 0.0;
    bool playing = false;

private:
    // Cached clips map: name -> index in clips vector
    std::unordered_map<std::string, size_t> _clips_map;

    // Current clip index (-1 if none)
    int _current_index = -1;

    // Target skeleton (from SkeletonController on same entity)
    SkeletonInstance* _target_skeleton = nullptr;

    // Cached bone index mapping: channel index -> bone index
    // Rebuilt when clip changes
    std::vector<int> _channel_to_bone;

    // Cached samples buffer for reuse
    std::vector<tc_channel_sample> _samples_buffer;

public:
    INSPECT_FIELD(AnimationPlayer, clips, "Animation Clips", "list[tc_animation_clip]")
    INSPECT_FIELD(AnimationPlayer, _current_clip_name, "Current Clip", "clip_selector")
    INSPECT_FIELD(AnimationPlayer, playing, "Playing", "bool")

public:
    AnimationPlayer();
    ~AnimationPlayer() override = default;

    // Accessors
    animation::TcAnimationClip* current() {
        if (_current_index < 0 || _current_index >= (int)clips.size()) return nullptr;
        return &clips[_current_index];
    }
    const animation::TcAnimationClip* current() const {
        if (_current_index < 0 || _current_index >= (int)clips.size()) return nullptr;
        return &clips[_current_index];
    }
    const std::unordered_map<std::string, size_t>& clips_map() const { return _clips_map; }

    // Set current clip by name
    void set_current(const std::string& name);

    // Play clip by name
    void play(const std::string& name, bool restart = true);

    // Stop playback
    void stop() { playing = false; }

    // Update bones at specific time (for external control)
    void update_bones_at_time(double t);

    // Get/set target skeleton
    SkeletonInstance* target_skeleton() const { return _target_skeleton; }
    void set_target_skeleton(SkeletonInstance* skeleton);

    // Component lifecycle
    void start() override;
    void update(float dt) override;

private:
    // Rebuild clips map from handles
    void _rebuild_clips_map();

    // Find SkeletonController on entity
    void _acquire_skeleton();

    // Build channel-to-bone mapping for current clip
    void _build_channel_mapping();

    // Apply animation sample to skeleton
    void _apply_sample(const tc_channel_sample* samples, size_t count);
};

REGISTER_COMPONENT(AnimationPlayer, Component);

} // namespace termin
