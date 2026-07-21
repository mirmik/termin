#pragma once

extern "C" {
#include <termin/audio/tc_audio_engine.h>
}

#include <termin/audio/tc_audio_clip.hpp>

namespace termin::audio {

class TcAudioVoice {
public:
    tc_audio_voice_handle handle = tc_audio_voice_handle_invalid();

    TcAudioVoice() = default;
    explicit TcAudioVoice(tc_audio_voice_handle value) : handle(value) {}
    TcAudioVoice(const TcAudioVoice&) = delete;
    TcAudioVoice& operator=(const TcAudioVoice&) = delete;

    TcAudioVoice(TcAudioVoice&& other) noexcept : handle(other.handle) {
        other.handle = tc_audio_voice_handle_invalid();
    }

    TcAudioVoice& operator=(TcAudioVoice&& other) noexcept {
        if (this != &other) {
            destroy();
            handle = other.handle;
            other.handle = tc_audio_voice_handle_invalid();
        }
        return *this;
    }

    ~TcAudioVoice() { destroy(); }

    bool is_valid() const { return tc_audio_voice_is_valid(handle); }
    bool start() { return tc_audio_voice_start(handle); }
    bool stop(uint32_t fade_out_ms = 0) { return tc_audio_voice_stop(handle, fade_out_ms); }
    bool pause() { return tc_audio_voice_pause(handle); }
    bool resume() { return tc_audio_voice_resume(handle); }
    bool is_playing() const { return tc_audio_voice_is_playing(handle); }
    bool is_paused() const { return tc_audio_voice_is_paused(handle); }

    void destroy() {
        if (tc_audio_voice_is_valid(handle)) tc_audio_voice_destroy(handle);
        handle = tc_audio_voice_handle_invalid();
    }

    static TcAudioVoice create(const TcAudioClip& clip) {
        return TcAudioVoice(tc_audio_voice_create(clip.handle));
    }
};

} // namespace termin::audio

