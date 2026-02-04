#include "animation_player.hpp"
#include "termin/entity/entity.hpp"
#include "termin/render/skeleton_controller.hpp"
#include "tc_log.hpp"

namespace termin {

AnimationPlayer::AnimationPlayer()
    : CxxComponent()
{
    // type_entry is set by registry when component is created via factory
    _c.has_update = true;
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
    _current_clip_name = name;
    auto it = _clips_map.find(name);
    if (it != _clips_map.end()) {
        _current_index = (int)it->second;
        _build_channel_mapping();
    } else {
        _current_index = -1;
        _channel_to_bone.clear();
    }
}

void AnimationPlayer::play(const std::string& name, bool restart) {
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
    _channel_to_bone.clear();

    if (_current_index < 0 || _current_index >= (int)clips.size()) {
        return;
    }

    const animation::TcAnimationClip& clip = clips[_current_index];
    tc_animation* anim = clip.get();
    SkeletonInstance* skel_inst = target_skeleton();
    if (!anim || !skel_inst) {
        return;
    }

    tc_skeleton* skel = skel_inst->_skeleton;
    if (!skel) {
        return;
    }

    // Build mapping from channel index to bone index
    _channel_to_bone.resize(anim->channel_count);
    for (size_t i = 0; i < anim->channel_count; i++) {
        const char* target_name = anim->channels[i].target_name;
        int bone_idx = tc_skeleton_find_bone(skel, target_name);
        _channel_to_bone[i] = bone_idx;
    }

    // Resize samples buffer
    _samples_buffer.resize(anim->channel_count);
}

void AnimationPlayer::update(float dt) {
    if (!playing || _current_index < 0) {
        return;
    }

    time += dt;

    const animation::TcAnimationClip& clip = clips[_current_index];
    size_t count = clip.sample_into(time, _samples_buffer.data(), _samples_buffer.size());
    _apply_sample(_samples_buffer.data(), count);
}

void AnimationPlayer::update_bones_at_time(double t) {
    if (_current_index < 0 || _current_index >= (int)clips.size()) {
        tc::Log::warn("[AnimationPlayer::update_bones_at_time] no current clip: index=%d clips=%zu",
            _current_index, clips.size());
        return;
    }

    // Lazy skeleton acquisition (in case start() was called before SkeletonController existed)
    if (!_target_skeleton_controller.valid()) {
        _acquire_skeleton();
    }

    SkeletonInstance* skel_inst = target_skeleton();
    if (!skel_inst) {
        tc::Log::warn("[AnimationPlayer::update_bones_at_time] no target skeleton");
        return;
    }

    const animation::TcAnimationClip& clip = clips[_current_index];
    size_t count = clip.sample_into(t, _samples_buffer.data(), _samples_buffer.size());
    _apply_sample(_samples_buffer.data(), count);
}

void AnimationPlayer::_apply_sample(const tc_channel_sample* samples, size_t count) {
    SkeletonInstance* skel_inst = target_skeleton();
    if (!skel_inst || !samples) {
        tc::Log::warn("[AnimationPlayer::_apply_sample] skeleton=%p samples=%p",
            (void*)skel_inst, (void*)samples);
        return;
    }

    if (count == 0) {
        tc::Log::warn("[AnimationPlayer::_apply_sample] count=0");
        return;
    }

    if (_channel_to_bone.empty()) {
        tc::Log::warn("[AnimationPlayer::_apply_sample] _channel_to_bone is empty! count=%zu", count);
        return;
    }

    // Use cached channel-to-bone mapping for fast lookup
    for (size_t i = 0; i < count && i < _channel_to_bone.size(); ++i) {
        int bone_idx = _channel_to_bone[i];
        if (bone_idx < 0) {
            continue;
        }

        const tc_channel_sample& ch = samples[i];

        const double* tr_ptr = ch.has_translation ? ch.translation : nullptr;
        const double* rot_ptr = ch.has_rotation ? ch.rotation : nullptr;

        double sc[3] = {1, 1, 1};
        const double* sc_ptr = nullptr;
        if (ch.has_scale) {
            sc[0] = ch.scale;
            sc[1] = ch.scale;
            sc[2] = ch.scale;
            sc_ptr = sc;
        }

        skel_inst->set_bone_transform(bone_idx, tr_ptr, rot_ptr, sc_ptr);
    }
}

} // namespace termin
