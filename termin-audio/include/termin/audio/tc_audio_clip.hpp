#pragma once

extern "C" {
#include <termin/audio/tc_audio_clip.h>
#include <termin/audio/tc_audio_clip_registry.h>
}

#include <string>

namespace termin::audio {

class TcAudioClip {
public:
    tc_audio_clip_handle handle = tc_audio_clip_handle_invalid();

    TcAudioClip() = default;

    explicit TcAudioClip(tc_audio_clip_handle value) : handle(value) {
        retain();
    }

    TcAudioClip(const TcAudioClip& other) : handle(other.handle) {
        retain();
    }

    TcAudioClip(TcAudioClip&& other) noexcept : handle(other.handle) {
        other.handle = tc_audio_clip_handle_invalid();
    }

    TcAudioClip& operator=(const TcAudioClip& other) {
        if (this != &other) {
            release();
            handle = other.handle;
            retain();
        }
        return *this;
    }

    TcAudioClip& operator=(TcAudioClip&& other) noexcept {
        if (this != &other) {
            release();
            handle = other.handle;
            other.handle = tc_audio_clip_handle_invalid();
        }
        return *this;
    }

    ~TcAudioClip() {
        release();
    }

    bool is_valid() const { return tc_audio_clip_is_valid(handle); }

    bool is_loaded() const {
        const tc_audio_clip* clip = get();
        return clip && clip->header.is_loaded != 0;
    }

    const tc_audio_clip* get() const { return tc_audio_clip_get(handle); }
    tc_audio_clip* get() { return tc_audio_clip_get(handle); }

    std::string uuid() const {
        const tc_audio_clip* clip = get();
        return clip ? clip->header.uuid : "";
    }

    std::string name() const {
        const tc_audio_clip* clip = get();
        return clip && clip->header.name ? clip->header.name : "";
    }

    std::string source_path() const {
        const tc_audio_clip* clip = get();
        return clip && clip->source_path ? clip->source_path : "";
    }

    uint32_t version() const {
        const tc_audio_clip* clip = get();
        return clip ? clip->header.version : 0;
    }

    uint64_t frame_count() const {
        const tc_audio_clip* clip = get();
        return clip ? clip->frame_count : 0;
    }

    uint32_t sample_rate() const {
        const tc_audio_clip* clip = get();
        return clip ? clip->sample_rate : 0;
    }

    uint16_t channels() const {
        const tc_audio_clip* clip = get();
        return clip ? clip->channels : 0;
    }

    double duration() const { return tc_audio_clip_duration_seconds(handle); }
    uint64_t duration_ms() const { return tc_audio_clip_duration_ms(handle); }

    bool load_file(const std::string& path = "") {
        const std::string selected = path.empty() ? source_path() : path;
        return !selected.empty() && tc_audio_clip_load_file(handle, selected.c_str());
    }

    bool ensure_loaded() { return tc_audio_clip_ensure_loaded(handle); }
    bool unload() { return tc_audio_clip_unload(handle); }

    bool set_name(const std::string& value) {
        return tc_audio_clip_set_name(handle, value.c_str());
    }

    bool set_source_path(const std::string& value) {
        return tc_audio_clip_set_source_path(handle, value.c_str());
    }

    static TcAudioClip from_uuid(const std::string& uuid) {
        return TcAudioClip(tc_audio_clip_find(uuid.c_str()));
    }

    static TcAudioClip declare(
        const std::string& uuid,
        const std::string& name = "",
        const std::string& source_path = ""
    ) {
        return TcAudioClip(tc_audio_clip_declare(uuid.c_str(), name.c_str(), source_path.c_str()));
    }

private:
    void retain() {
        if (tc_audio_clip* clip = tc_audio_clip_get(handle)) {
            tc_audio_clip_add_ref(clip);
        }
    }

    void release() {
        if (tc_audio_clip* clip = tc_audio_clip_get(handle)) {
            tc_audio_clip_release(clip);
        }
        handle = tc_audio_clip_handle_invalid();
    }
};

} // namespace termin::audio

