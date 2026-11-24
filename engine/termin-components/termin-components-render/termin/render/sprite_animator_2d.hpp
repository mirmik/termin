#pragma once

#include <functional>
#include <string>

#include <termin/entity/component.hpp>
#include <termin/render/sprite_animation_clip.hpp>

namespace termin {

    class SpriteRenderer2D;

    class ENTITY_API SpriteAnimator2D : public Component {
    public:
        using FrameEventCallback = std::function<void(const std::string&, size_t)>;

        SpriteAnimator2D();
        static void register_type();

        bool autoplay = true;
        bool loop = true;
        const std::string& clip_uuid() const {
            return clip_uuid_;
        }
        void set_clip_uuid(const std::string& uuid);
        double speed() const {
            return speed_;
        }
        void set_speed(double value);
        bool playing() const {
            return state_ == State::Playing;
        }
        size_t current_frame() const {
            return frame_;
        }
        double current_time() const {
            return time_;
        }
        void set_frame_event_callback(FrameEventCallback callback);

        void play();
        void pause();
        void stop();
        void start() override;
        void update(float dt) override;
        void on_removed_from_entity() override;
        tc_value serialize_data() const override;
        void deserialize_data(const tc_value* data, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) override;

    private:
        enum class State {
            Stopped,
            Playing,
            Paused,
            Finished
        };
        State state_ = State::Stopped;
        std::string clip_uuid_;
        TcSpriteAnimationClip clip_;
        uint32_t clip_version_ = 0;
        double speed_ = 1.0;
        double time_ = 0.0;
        size_t frame_ = 0;
        uint64_t playback_revision_ = 0;
        bool clip_has_events_ = false;
        bool initialized_ = false;
        bool pending_entry_ = false;
        bool reported_missing_clip_ = false;
        bool reported_missing_renderer_ = false;
        FrameEventCallback callback_;

        void rewind();
        bool synchronize(SpriteRenderer2D& renderer);
        bool notify_entry(const SpriteRenderer2D& renderer);
    };

} // namespace termin
