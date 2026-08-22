#include <cstring>
#include <cmath>
#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/animation/animation_player.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include <termin/render/skeleton_controller.hpp>

namespace termin {
    namespace {
        void apply_entity_transform(Entity entity,
                                    const Vec3* translation,
                                    const Quat* rotation,
                                    const Vec3* scale) {
            if (!entity.valid()) {
                return;
            }
            if (translation) {
                entity.set_local_position(&translation->x);
            }
            if (rotation) {
                entity.set_local_rotation(&rotation->x);
            }
            if (scale) {
                entity.set_local_scale(&scale->x);
            }
        }
    } // namespace

    AnimationPlayer::AnimationPlayer()
        : CxxComponent("AnimationPlayer") {
        _c.has_update = true;
    }

    void AnimationPlayer::register_type() {
        auto descriptor = ComponentTypeDescriptorBuilder::native<AnimationPlayer>(
            "AnimationPlayer", "termin-components-animation", "Component");
        descriptor.category("Animation");
        tc::stage_inspect_field(descriptor.inspect(),
                                &AnimationPlayer::clips,
                                "AnimationPlayer",
                                "clips",
                                "Animation Clips",
                                "list[tc_animation_clip]");
        tc::stage_inspect_field(descriptor.inspect(),
                                &AnimationPlayer::node_targets,
                                "AnimationPlayer",
                                "node_targets",
                                "Node Targets",
                                "list[entity]");
        tc::stage_inspect_field(descriptor.inspect(),
                                &AnimationPlayer::_current_clip_name,
                                "AnimationPlayer",
                                "_current_clip_name",
                                "Current Clip",
                                "clip_selector");
        tc::stage_inspect_field(
            descriptor.inspect(), &AnimationPlayer::playing, "AnimationPlayer", "playing", "Playing", "bool");
        (void)descriptor.commit();
    }

    void AnimationPlayer::start() {
        CxxComponent::start();

        _rebuild_clips_map();
        _acquire_skeleton();

        // Restore current clip from name
        if (!_current_clip_name.empty()) {
            auto it = _clips_map.find(_current_clip_name);
            if (it != _clips_map.end()) {
                _current_index = (int)it->second;
                _build_channel_mapping();
            }
        }
    }

    void AnimationPlayer::_rebuild_clips_map() {
        _clips_map.clear();
        for (size_t i = 0; i < clips.size(); i++) {
            const char* name = clips[i].name();
            if (name && name[0] != '\0') {
                _clips_map[name] = i;
            }
        }
    }

    void AnimationPlayer::_acquire_skeleton() {
        if (!entity().valid()) {
            tc::Log::warn("[AnimationPlayer::_acquire_skeleton] entity not valid");
            return;
        }

        SkeletonController* sc = entity().get_component<SkeletonController>();
        if (sc != nullptr) {
            _target_skeleton_controller.reset(sc);
        }
    }

    void AnimationPlayer::set_target_skeleton_controller(SkeletonController* controller) {
        _target_skeleton_controller.reset(controller);
        // Rebuild mapping if we have a clip
        if (_current_index >= 0) {
            _build_channel_mapping();
        }
    }

    SkeletonInstance* AnimationPlayer::target_skeleton() const {
        SkeletonController* ctrl = _target_skeleton_controller.get();
        if (!ctrl) {
            return nullptr;
        }
        return ctrl->skeleton_instance();
    }

    void AnimationPlayer::set_current(const std::string& name) {
        if (_clips_map.empty() && !clips.empty()) {
            _rebuild_clips_map();
        }
        _current_clip_name = name;
        auto it = _clips_map.find(name);
        if (it != _clips_map.end()) {
            _current_index = (int)it->second;
            _build_channel_mapping();
        } else {
            _current_index = -1;
            _channel_mappings.clear();
            _track_mappings.clear();
            _samples_buffer.clear();
            _mapped_clip_version = 0;
        }
    }

    void AnimationPlayer::play(const std::string& name, bool restart) {
        if (_clips_map.empty() && !clips.empty()) {
            _rebuild_clips_map();
        }
        auto it = _clips_map.find(name);
        if (it == _clips_map.end()) {
            tc::Log::warn("[AnimationPlayer::play] clip '%s' not found", name.c_str());
            return;
        }

        int new_index = (int)it->second;
        if (_current_index != new_index || restart) {
            time = 0.0;
        }

        _current_index = new_index;
        _current_clip_name = name;
        _build_channel_mapping();
        playing = true;
    }

    void AnimationPlayer::_build_channel_mapping() {
        _channel_mappings.clear();
        _track_mappings.clear();
        _samples_buffer.clear();
        _mapped_clip_version = 0;

        if (_current_index < 0 || _current_index >= (int)clips.size()) {
            return;
        }

        const animation::TcAnimationClip& clip = clips[_current_index];
        tc_animation* anim = clip.get();
        if (!anim) {
            return;
        }

        TcSkeleton skeleton_owner;
        if (SkeletonInstance* skel_inst = target_skeleton()) {
            skeleton_owner = skel_inst->skeleton();
        }

        if (anim->track_count > 0) {
            SkeletonController* skeleton_controller = _target_skeleton_controller.get();
            _track_mappings.resize(anim->track_count);
            for (size_t i = 0; i < anim->track_count; ++i) {
                const tc_animation_track& track = anim->tracks[i];
                ChannelMapping& mapping = _track_mappings[i];
                if (track.target_node_index >= 0 &&
                    static_cast<size_t>(track.target_node_index) < node_targets.size()) {
                    mapping.node_entity = node_targets[static_cast<size_t>(track.target_node_index)];
                }
                if (skeleton_controller && mapping.node_entity.valid()) {
                    const std::vector<Entity>& bones = skeleton_controller->bone_entities;
                    for (size_t bone_index = 0; bone_index < bones.size(); ++bone_index) {
                        if (bones[bone_index] == mapping.node_entity) {
                            mapping.bone_index = static_cast<int>(bone_index);
                            break;
                        }
                    }
                }
                if (track.interpolation == TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE ||
                    track.path == TC_ANIMATION_PATH_WEIGHTS) {
                    tc::Log::warn(
                        "[AnimationPlayer::_build_channel_mapping] track %zu target node %d "
                        "is preserved but playback for path=%u interpolation=%u is unsupported",
                        i,
                        track.target_node_index,
                        static_cast<unsigned>(track.path),
                        static_cast<unsigned>(track.interpolation));
                } else if (!mapping.node_entity.valid()) {
                    tc::Log::warn(
                        "[AnimationPlayer::_build_channel_mapping] no entity for track %zu target node %d",
                        i,
                        track.target_node_index);
                }
            }
            _mapped_clip_version = anim->header.version;
            return;
        }

        // Build mapping from channel index to either bone index or imported node entity.
        _channel_mappings.resize(anim->channel_count);
        for (size_t i = 0; i < anim->channel_count; i++) {
            const char* target_name = anim->channels[i].target_name;
            const bool has_target_name = target_name && target_name[0] != '\0';
            const tc_skeleton* skel = skeleton_owner.get();
            int bone_idx = (skel && has_target_name) ? tc_skeleton_find_bone(skel, target_name) : -1;
            _channel_mappings[i].bone_index = bone_idx;
            if (bone_idx < 0) {
                _channel_mappings[i].node_entity = _find_node_target(target_name);
                if (!_channel_mappings[i].node_entity.valid()) {
                    tc::Log::warn("[AnimationPlayer::_build_channel_mapping] no target for channel '%s'",
                                  target_name ? target_name : "<null>");
                }
            }
        }

        // Resize samples buffer
        _samples_buffer.resize(anim->channel_count);
        _mapped_clip_version = anim->header.version;
    }

    void AnimationPlayer::update(float dt) {
        if (!playing || _current_index < 0) {
            return;
        }

        time += dt;

        if (_current_index >= static_cast<int>(clips.size())) {
            return;
        }
        const animation::TcAnimationClip& clip = clips[_current_index];
        tc_animation* anim = clip.get();
        if (!anim) {
            return;
        }
        if (_mapped_clip_version != anim->header.version) {
            _build_channel_mapping();
        }
        if (anim->track_count > 0) {
            _apply_tracks_at_time(anim, time);
            return;
        }
        size_t count = clip.sample_into(time, _samples_buffer.data(), _samples_buffer.size());
        _apply_sample(_samples_buffer.data(), count);
    }

    void AnimationPlayer::update_bones_at_time(double t) {
        if (_current_index < 0 || _current_index >= (int)clips.size()) {
            tc::Log::warn("[AnimationPlayer::update_bones_at_time] no current clip: index=%d clips=%zu",
                          _current_index,
                          clips.size());
            return;
        }

        // Lazy skeleton acquisition (in case start() was called before SkeletonController existed)
        if (!_target_skeleton_controller.valid()) {
            _acquire_skeleton();
        }

        const animation::TcAnimationClip& clip = clips[_current_index];
        tc_animation* anim = clip.get();
        if (!anim) {
            return;
        }
        if (_mapped_clip_version != anim->header.version) {
            _build_channel_mapping();
        }
        if (anim->track_count > 0) {
            _apply_tracks_at_time(anim, t);
            return;
        }
        size_t count = clip.sample_into(t, _samples_buffer.data(), _samples_buffer.size());
        _apply_sample(_samples_buffer.data(), count);
    }

    Entity AnimationPlayer::_find_node_target(const char* target_name) const {
        if (!target_name || target_name[0] == '\0') {
            return Entity();
        }

        for (const Entity& target : node_targets) {
            if (!target.valid()) {
                continue;
            }
            const char* name = target.name();
            if (name && std::strcmp(name, target_name) == 0) {
                return target;
            }
        }
        return Entity();
    }

    void AnimationPlayer::_apply_tracks_at_time(const tc_animation* animation, double t_seconds) {
        if (!animation || animation->track_count == 0) {
            return;
        }
        if (_track_mappings.size() != animation->track_count) {
            _build_channel_mapping();
        }

        if (animation->loop && animation->duration > 0.0) {
            t_seconds = std::fmod(t_seconds, animation->duration);
            if (t_seconds < 0.0) {
                t_seconds += animation->duration;
            }
        }
        const double t_ticks = t_seconds * animation->tps;
        SkeletonController* skeleton_controller = _target_skeleton_controller.get();
        for (size_t i = 0; i < animation->track_count && i < _track_mappings.size(); ++i) {
            const tc_animation_track& track = animation->tracks[i];
            if (track.interpolation == TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE ||
                track.path == TC_ANIMATION_PATH_WEIGHTS) {
                continue;
            }

            double value[4] = {};
            if (!tc_animation_track_sample(&track, t_ticks, value, 4)) {
                tc::Log::error("[AnimationPlayer::_apply_tracks_at_time] failed to sample track %zu", i);
                continue;
            }

            const ChannelMapping& mapping = _track_mappings[i];
            if (mapping.bone_index >= 0 && !skeleton_controller) {
                continue;
            }
            const Entity target = mapping.bone_index >= 0
                                      ? skeleton_controller->bone_entity(mapping.bone_index)
                                      : mapping.node_entity;
            switch ((tc_animation_path)track.path) {
            case TC_ANIMATION_PATH_TRANSLATION: {
                const Vec3 translation{value[0], value[1], value[2]};
                apply_entity_transform(target, &translation, nullptr, nullptr);
                break;
            }
            case TC_ANIMATION_PATH_ROTATION: {
                const Quat rotation{value[0], value[1], value[2], value[3]};
                apply_entity_transform(target, nullptr, &rotation, nullptr);
                break;
            }
            case TC_ANIMATION_PATH_SCALE: {
                const Vec3 scale{value[0], value[1], value[2]};
                apply_entity_transform(target, nullptr, nullptr, &scale);
                break;
            }
            case TC_ANIMATION_PATH_WEIGHTS:
                break;
            }
        }
    }

    void AnimationPlayer::_apply_sample(const tc_channel_sample* samples, size_t count) {
        if (!samples) {
            tc::Log::warn("[AnimationPlayer::_apply_sample] samples=null");
            return;
        }

        if (count == 0) {
            tc::Log::warn("[AnimationPlayer::_apply_sample] count=0");
            return;
        }

        if (_channel_mappings.empty()) {
            tc::Log::warn("[AnimationPlayer::_apply_sample] _channel_mappings is empty! count=%zu", count);
            return;
        }

        SkeletonController* skeleton_controller = _target_skeleton_controller.get();
        for (size_t i = 0; i < count && i < _channel_mappings.size(); ++i) {
            const tc_channel_sample& ch = samples[i];
            const Vec3* tr_ptr = ch.has_translation ? &ch.translation : nullptr;
            const Quat* rot_ptr = ch.has_rotation ? &ch.rotation : nullptr;

            Vec3 sc{1.0, 1.0, 1.0};
            const Vec3* sc_ptr = nullptr;
            if (ch.has_scale) {
                sc = {ch.scale, ch.scale, ch.scale};
                sc_ptr = &sc;
            }

            const ChannelMapping& mapping = _channel_mappings[i];
            if (mapping.bone_index >= 0) {
                if (skeleton_controller) {
                    apply_entity_transform(
                        skeleton_controller->bone_entity(mapping.bone_index), tr_ptr, rot_ptr, sc_ptr);
                }
                continue;
            }
            apply_entity_transform(mapping.node_entity, tr_ptr, rot_ptr, sc_ptr);
        }
    }

} // namespace termin
