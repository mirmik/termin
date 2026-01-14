#include "animation_player.hpp"
#include "termin/entity/entity.hpp"
#include "termin/render/skeleton_controller.hpp"
#include "tc_log.hpp"

namespace termin {

AnimationPlayer::AnimationPlayer()
    : CxxComponent()
{
    set_type_name("AnimationPlayer");
    _c.has_update = true;
}

void AnimationPlayer::start() {
    CxxComponent::start();

    tc::Log::info("[AnimationPlayer::start] clips.size()=%zu", clips.size());

    _rebuild_clips_map();
    _acquire_skeleton();

    tc::Log::info("[AnimationPlayer::start] _clips_map.size()=%zu, _current_clip_name='%s'",
        _clips_map.size(), _current_clip_name.c_str());

    // Restore current clip from name
    if (!_current_clip_name.empty()) {
        auto it = _clips_map.find(_current_clip_name);
        if (it != _clips_map.end()) {
            _current = it->second;
            _build_channel_mapping();
            tc::Log::info("[AnimationPlayer::start] Restored clip '%s'", _current_clip_name.c_str());
        }
    }
}

void AnimationPlayer::_rebuild_clips_map() {
    _clips_map.clear();
    for (auto& handle : clips) {
        animation::AnimationClip* clip = handle.get();
        if (clip != nullptr) {
            _clips_map[clip->name] = clip;
        }
    }
}

void AnimationPlayer::_acquire_skeleton() {
    if (!entity.valid()) {
        return;
    }

    SkeletonController* sc = entity.get_component<SkeletonController>();
    if (sc != nullptr) {
        _target_skeleton = sc->skeleton_instance();
    }
}

void AnimationPlayer::set_target_skeleton(SkeletonInstance* skeleton) {
    _target_skeleton = skeleton;
    // Rebuild mapping if we have a clip
    if (_current != nullptr) {
        _build_channel_mapping();
    }
}

void AnimationPlayer::set_current(const std::string& name) {
    _current_clip_name = name;
    auto it = _clips_map.find(name);
    if (it != _clips_map.end()) {
        _current = it->second;
        _build_channel_mapping();
    } else {
        _current = nullptr;
        _channel_to_bone.clear();
        _channel_names.clear();
    }
}

void AnimationPlayer::play(const std::string& name, bool restart) {
    auto it = _clips_map.find(name);
    if (it == _clips_map.end()) {
        tc::Log::warn("[AnimationPlayer::play] clip '%s' not found", name.c_str());
        return;
    }

    if (_current != it->second || restart) {
        time = 0.0;
    }

    _current = it->second;
    _current_clip_name = name;
    _build_channel_mapping();
    playing = true;
}

void AnimationPlayer::_build_channel_mapping() {
    _channel_to_bone.clear();
    _channel_names.clear();

    if (_current == nullptr || _target_skeleton == nullptr) {
        return;
    }

    SkeletonData* skel_data = _target_skeleton->skeleton_data();
    if (skel_data == nullptr) {
        return;
    }

    // Build mapping from channel index to bone index
    for (const auto& [name, channel] : _current->channels) {
        int bone_idx = skel_data->get_bone_index(name);
        _channel_names.push_back(name);
        _channel_to_bone.push_back(bone_idx);
    }
}

void AnimationPlayer::update(float dt) {
    if (!playing || _current == nullptr) {
        return;
    }

    time += dt;

    auto sample = _current->sample(time);
    _apply_sample(sample);
}

void AnimationPlayer::update_bones_at_time(double t) {
    if (_current == nullptr) {
        return;
    }

    auto sample = _current->sample(t);
    _apply_sample(sample);
}

void AnimationPlayer::_apply_sample(
    const std::unordered_map<std::string, animation::AnimationChannelSample>& sample
) {
    if (_target_skeleton == nullptr) {
        return;
    }

    // Use cached channel-to-bone mapping for fast lookup
    for (size_t i = 0; i < _channel_names.size(); ++i) {
        int bone_idx = _channel_to_bone[i];
        if (bone_idx < 0) {
            continue;
        }

        const std::string& name = _channel_names[i];
        auto it = sample.find(name);
        if (it == sample.end()) {
            continue;
        }

        const animation::AnimationChannelSample& ch = it->second;

        // Prepare data for set_bone_transform
        double tr[3] = {0, 0, 0};
        double rot[4] = {0, 0, 0, 1};
        double sc[3] = {1, 1, 1};

        const double* tr_ptr = nullptr;
        const double* rot_ptr = nullptr;
        const double* sc_ptr = nullptr;

        if (ch.translation.has_value()) {
            tr[0] = ch.translation->x;
            tr[1] = ch.translation->y;
            tr[2] = ch.translation->z;
            tr_ptr = tr;
        }

        if (ch.rotation.has_value()) {
            rot[0] = ch.rotation->x;
            rot[1] = ch.rotation->y;
            rot[2] = ch.rotation->z;
            rot[3] = ch.rotation->w;
            rot_ptr = rot;
        }

        if (ch.scale.has_value()) {
            double s = *ch.scale;
            sc[0] = s;
            sc[1] = s;
            sc[2] = s;
            sc_ptr = sc;
        }

        _target_skeleton->set_bone_transform(bone_idx, tr_ptr, rot_ptr, sc_ptr);
    }
}

} // namespace termin
