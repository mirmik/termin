#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

#include "termin/animation/tc_animation_handle.hpp"
#include "termin/animation/termin_components_animation_api.hpp"
#include "termin/entity/cmp_ref.hpp"
#include "termin/skeleton/skeleton_instance.hpp"
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>

namespace termin {

    class SkeletonController;

    // AnimationPlayer - plays animation clips on skeleton.
    //
    // Stores clips, current clip, time. Updates skeleton bones each frame.
    // Can be controlled externally (playing=false) via update_bones_at_time().
    class TERMIN_COMPONENTS_ANIMATION_API AnimationPlayer : public CxxComponent {
    public:
        // Clip handles for serialization
        std::vector<animation::TcAnimationClip> clips;

        // Non-bone entity targets imported from animation node hierarchies.
        std::vector<Entity> node_targets;

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

        // Target skeleton controller (CmpRef validates entity liveness)
        CmpRef<SkeletonController> _target_skeleton_controller;

        struct ChannelMapping {
            int bone_index = -1;
            Entity node_entity;
        };

        // Cached target mapping: channel index -> skeleton bone or node entity
        // Rebuilt when clip changes
        std::vector<ChannelMapping> _channel_mappings;

        // Bulk glTF tracks are mapped by their stable source node index.  The
        // mapping is kept separate from legacy name-grouped channels so the
        // two representations cannot be mixed accidentally.
        std::vector<ChannelMapping> _track_mappings;

        // Cached samples buffer for reuse
        std::vector<tc_channel_sample> _samples_buffer;

        // Payload replacement is versioned by the animation registry. Mapping
        // and sample storage must follow both target changes and representation
        // switches between legacy channels and bulk tracks.
        uint32_t _mapped_clip_version = 0;

    public:
        AnimationPlayer();
        ~AnimationPlayer() override = default;

        static void register_type();

        // Accessors
        animation::TcAnimationClip* current() {
            if (_current_index < 0 || _current_index >= (int)clips.size())
                return nullptr;
            return &clips[_current_index];
        }
        const animation::TcAnimationClip* current() const {
            if (_current_index < 0 || _current_index >= (int)clips.size())
                return nullptr;
            return &clips[_current_index];
        }
        const std::unordered_map<std::string, size_t>& clips_map() const {
            return _clips_map;
        }

        // Set current clip by name
        void set_current(const std::string& name);

        // Play clip by name
        void play(const std::string& name, bool restart = true);

        // Stop playback
        void stop() {
            playing = false;
        }

        // Update bones at specific time (for external control)
        void update_bones_at_time(double t);

        // Get/set target skeleton controller
        SkeletonController* target_skeleton_controller() const {
            return _target_skeleton_controller.get();
        }
        void set_target_skeleton_controller(SkeletonController* controller);

        // Get target skeleton instance (from controller, nullptr if controller is dead)
        SkeletonInstance* target_skeleton() const;

        // Component lifecycle
        void start() override;
        void update(float dt) override;

    private:
        // Rebuild clips map from handles
        void _rebuild_clips_map();

        // Find SkeletonController on entity
        void _acquire_skeleton();

        // Build channel target mapping for current clip
        void _build_channel_mapping();

        // Sample and apply exact bulk tracks (vec3 scale and STEP included).
        void _apply_tracks_at_time(const tc_animation* animation, double t_seconds);

        // Resolve non-bone target entity by channel target name
        Entity _find_node_target(const char* target_name) const;

        // Apply animation sample to skeleton
        void _apply_sample(const tc_channel_sample* samples, size_t count);
    };

} // namespace termin
