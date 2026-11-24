#include <termin/render/sprite_animator_2d.hpp>

#include <algorithm>
#include <cmath>
#include <utility>

#include <tcbase/tc_log.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/render/sprite_renderer_2d.hpp>

#include "sprite_reference_kind.hpp"

namespace termin {

    SpriteAnimator2D::SpriteAnimator2D()
        : Component("SpriteAnimator2D") {
        set_has_update(true);
        set_active_in_editor(true);
    }

    void SpriteAnimator2D::register_type() {
        register_sprite_reference_kind("sprite_animation_clip");
        constexpr const char* type = "SpriteAnimator2D";
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<SpriteAnimator2D>(type, "termin-components-render", "Component");
        descriptor.category("Rendering/2D").require("SpriteRenderer2D");
        auto& inspect = descriptor.inspect();
        inspect.add_with_callbacks<SpriteAnimator2D, std::string>(
            type,
            "clip",
            "Clip",
            "sprite_animation_clip",
            [](SpriteAnimator2D* self) -> std::string& { return self->clip_uuid_; },
            [](SpriteAnimator2D* self, const std::string& value) { self->set_clip_uuid(value); });
        inspect.add<SpriteAnimator2D, bool>(type, &SpriteAnimator2D::autoplay, "autoplay", "Autoplay", "bool");
        inspect.add<SpriteAnimator2D, bool>(type, &SpriteAnimator2D::loop, "loop", "Loop", "bool");
        inspect.add_with_callbacks<SpriteAnimator2D, double>(
            type,
            "speed",
            "Speed",
            "double",
            [](SpriteAnimator2D* self) -> double& { return self->speed_; },
            [](SpriteAnimator2D* self, const double& value) { self->set_speed(value); });
        (void)descriptor.commit();
    }

    tc_value SpriteAnimator2D::serialize_data() const {
        tc_value data = Component::serialize_data();
        if (data.type == TC_VALUE_DICT && !clip_uuid_.empty()) {
            tc_value clip = tc_value_dict_new();
            tc_value_dict_set(&clip, "type", tc_value_string("uuid"));
            tc_value_dict_set(&clip, "kind", tc_value_string("sprite_animation_clip"));
            tc_value_dict_set(&clip, "role", tc_value_string("clip"));
            tc_value_dict_set(&clip, "uuid", tc_value_string(clip_uuid_.c_str()));
            tc_value_dict_set(&data, "clip", clip);
        }
        return data;
    }

    void SpriteAnimator2D::deserialize_data(const tc_value* data, tc_scene_handle scene) {
        if (!data || data->type != TC_VALUE_DICT) {
            Component::deserialize_data(data, scene);
            return;
        }
        tc_value fields = tc_value_copy(data);
        tc_value* clip = tc_value_dict_get(&fields, "clip");
        if (clip && clip->type == TC_VALUE_DICT) {
            const tc_value* uuid = tc_value_dict_get(clip, "uuid");
            if (uuid && uuid->type == TC_VALUE_STRING && uuid->data.s) {
                tc_value_dict_set(&fields, "clip", tc_value_string(uuid->data.s));
            } else {
                tc::Log::error("[SpriteAnimator2D] serialized clip reference has no UUID");
                tc_value_dict_set(&fields, "clip", tc_value_string(""));
            }
        }
        Component::deserialize_data(&fields, scene);
        tc_value_free(&fields);
    }

    void SpriteAnimator2D::set_clip_uuid(const std::string& uuid) {
        if (uuid == clip_uuid_)
            return;
        clip_uuid_ = uuid;
        clip_ = {};
        clip_version_ = 0;
        reported_missing_clip_ = false;
        rewind();
        if (initialized_)
            update(0);
    }

    void SpriteAnimator2D::set_speed(double value) {
        if (!std::isfinite(value) || value < 0) {
            tc::Log::error("[SpriteAnimator2D] playback speed must be finite and nonnegative");
            return;
        }
        if (speed_ != value)
            ++playback_revision_;
        speed_ = value;
    }

    void SpriteAnimator2D::set_frame_event_callback(FrameEventCallback callback) {
        callback_ = std::move(callback);
    }

    void SpriteAnimator2D::rewind() {
        ++playback_revision_;
        time_ = 0;
        frame_ = 0;
        pending_entry_ = playing();
    }

    void SpriteAnimator2D::start() {
        if (initialized_)
            return;
        initialized_ = true;
        if (autoplay)
            play();
        else
            update(0);
    }

    void SpriteAnimator2D::play() {
        if (playing())
            return;
        initialized_ = true;
        bool resume = state_ == State::Paused;
        state_ = State::Playing;
        if (!resume)
            rewind();
        update(0);
    }

    void SpriteAnimator2D::pause() {
        if (playing()) {
            ++playback_revision_;
            state_ = State::Paused;
        }
    }

    void SpriteAnimator2D::stop() {
        initialized_ = true;
        state_ = State::Stopped;
        rewind();
        update(0);
    }

    void SpriteAnimator2D::on_removed_from_entity() {
        if (auto* renderer = entity().get_component<SpriteRenderer2D>()) {
            renderer->set_animation_sprite_uuid({});
        }
        state_ = State::Stopped;
        rewind();
        initialized_ = false;
    }

    bool SpriteAnimator2D::synchronize(SpriteRenderer2D& renderer) {
        if (!clip_.is_valid() && !clip_uuid_.empty())
            clip_ = TcSpriteAnimationClip::from_uuid(clip_uuid_);
        if (!clip_.is_loaded()) {
            renderer.set_animation_sprite_uuid({});
            if (!clip_uuid_.empty() && !reported_missing_clip_) {
                tc::Log::error("[SpriteAnimator2D] clip is missing or unloaded: '%s'", clip_uuid_.c_str());
                reported_missing_clip_ = true;
            }
            return false;
        }

        reported_missing_clip_ = false;
        if (clip_version_ != clip_.version()) {
            clip_version_ = clip_.version();
            const auto& frames = clip_.get()->frames;
            clip_has_events_ =
                std::any_of(frames.begin(), frames.end(), [](const auto& frame) { return !frame.event.empty(); });
            rewind();
        }
        renderer.set_animation_sprite_uuid(clip_.get()->frames[frame_].sprite_uuid);
        return true;
    }

    bool SpriteAnimator2D::notify_entry(const SpriteRenderer2D& renderer) {
        const auto& name = clip_.get()->frames[frame_].event;
        if (!callback_ || name.empty())
            return true;

        // A handler can replace the clip/callback, remove the component, or pause playback.
        auto owner = entity();
        const tc_component* component = c_component();
        const tc_component* target = renderer.c_component();
        const auto revision = playback_revision_;
        const auto version = clip_version_;
        auto callback = callback_;
        try {
            callback(std::string(name), frame_);
        } catch (const std::exception& e) {
            tc::Log::error("[SpriteAnimator2D] frame event callback failed: %s", e.what());
            if (owner.valid() && owner.component_index(component) != SIZE_MAX)
                pause();
            return false;
        }
        return owner.valid() && owner.component_index(component) != SIZE_MAX &&
               owner.component_index(target) != SIZE_MAX && playing() && revision == playback_revision_ &&
               clip_.version() == version;
    }

    void SpriteAnimator2D::update(float dt) {
        if (!entity().valid())
            return;
        auto* renderer = entity().get_component<SpriteRenderer2D>();
        if (!renderer) {
            if (!reported_missing_renderer_) {
                tc::Log::error("[SpriteAnimator2D] entity '%s' has no SpriteRenderer2D", entity().name());
                reported_missing_renderer_ = true;
            }
            return;
        }
        reported_missing_renderer_ = false;
        if (!synchronize(*renderer) || !playing())
            return;
        if (pending_entry_) {
            pending_entry_ = false;
            if (!notify_entry(*renderer))
                return;
        }
        double remaining = static_cast<double>(dt) * speed_;
        if (remaining == 0)
            return;
        if (!std::isfinite(remaining) || remaining < 0) {
            tc::Log::error("[SpriteAnimator2D] invalid elapsed playback time");
            return;
        }

        const auto& clip = *clip_.get();
        const double end = clip.frame_ends.back();
        // With a subscriber, visit every crossed frame boundary, including loops.
        while (callback_ && clip_has_events_) {
            const double boundary = clip.frame_ends[frame_];
            const double step = boundary - time_;
            if (remaining < step) {
                time_ = std::min(time_ + remaining, std::nextafter(boundary, time_));
                return;
            }
            if (remaining - step == remaining) {
                tc::Log::error("[SpriteAnimator2D] elapsed time exceeds precision for individual frame events");
                pause();
                return;
            }
            remaining -= step;
            if (frame_ + 1 == clip.frames.size()) {
                if (!loop) {
                    time_ = end;
                    state_ = State::Finished;
                    return;
                }
                time_ = 0;
                frame_ = 0;
            } else {
                time_ = boundary;
                ++frame_;
            }
            renderer->set_animation_sprite_uuid(clip.frames[frame_].sprite_uuid);
            if (!notify_entry(*renderer))
                return;
        }
        // Without events, a long tick or high speed may skip whole loops in one operation.
        if (loop) {
            const double offset = std::fmod(remaining, end);
            time_ = offset >= end - time_ ? offset - (end - time_) : time_ + offset;
            if (time_ == end)
                time_ = 0;
        } else if (remaining >= end - time_) {
            time_ = end;
            state_ = State::Finished;
        } else {
            time_ += remaining;
        }
        frame_ = std::min(static_cast<size_t>(std::upper_bound(clip.frame_ends.begin(), clip.frame_ends.end(), time_) -
                                              clip.frame_ends.begin()),
                          clip.frames.size() - 1);
        renderer->set_animation_sprite_uuid(clip.frames[frame_].sprite_uuid);
    }

} // namespace termin
