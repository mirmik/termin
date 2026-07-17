#include <termin/animation/animation_player.hpp>
#include <termin/entity/entity.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/render/skeleton_controller.hpp>
#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <cstring>

namespace termin {

AnimationPlayer::AnimationPlayer()
    : CxxComponent("AnimationPlayer")
{
    _c.has_update = true;
}

void AnimationPlayer::register_type() {
    register_component_type<AnimationPlayer>("AnimationPlayer", "Component");
    ComponentRegistry::instance().set_category("AnimationPlayer", "Animation");
    tc::register_inspect_field(
        &AnimationPlayer::clips,
        "AnimationPlayer",
        "clips",
        "Animation Clips",
        "list[tc_animation_clip]"
    );
    tc::register_inspect_field(
        &AnimationPlayer::node_targets,
        "AnimationPlayer",
        "node_targets",
        "Node Targets",
        "list[entity]"
    );
    tc::register_inspect_field(
        &AnimationPlayer::_current_clip_name,
        "AnimationPlayer",
        "_current_clip_name",
        "Current Clip",
        "clip_selector"
    );
    tc::register_inspect_field(
        &AnimationPlayer::playing,
        "AnimationPlayer",
        "playing",
        "Playing",
        "bool"
    );
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

    if (_current_index < 0 || _current_index >= (int)clips.size()) {
        return;
    }

    const animation::TcAnimationClip& clip = clips[_current_index];
    tc_animation* anim = clip.get();
    if (!anim) {
        return;
    }

    tc_skeleton* skel = nullptr;
    if (SkeletonInstance* skel_inst = target_skeleton()) {
        skel = skel_inst->_skeleton;
    }

    // Build mapping from channel index to either bone index or imported node entity.
    _channel_mappings.resize(anim->channel_count);
    for (size_t i = 0; i < anim->channel_count; i++) {
        const char* target_name = anim->channels[i].target_name;
        const bool has_target_name = target_name && target_name[0] != '\0';
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

    const animation::TcAnimationClip& clip = clips[_current_index];
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

    SkeletonInstance* skel_inst = target_skeleton();
    for (size_t i = 0; i < count && i < _channel_mappings.size(); ++i) {
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

        const ChannelMapping& mapping = _channel_mappings[i];
        if (mapping.bone_index >= 0) {
            if (skel_inst) {
                skel_inst->set_bone_transform(mapping.bone_index, tr_ptr, rot_ptr, sc_ptr);
            }
            continue;
        }

        Entity node = mapping.node_entity;
        if (!node.valid()) {
            continue;
        }
        if (tr_ptr) {
            node.set_local_position(tr_ptr);
        }
        if (rot_ptr) {
            node.set_local_rotation(rot_ptr);
        }
        if (sc_ptr) {
            node.set_local_scale(sc_ptr);
        }
    }
}

} // namespace termin
