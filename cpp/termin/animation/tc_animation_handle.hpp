#pragma once

// TcAnimationClip - RAII wrapper with handle-based access to tc_animation
// Uses tc_animation_handle with generation checking for safety

extern "C" {
#include "termin_core.h"
}

#include <string>
#include <vector>
#include <nanobind/nanobind.h>
#include "../../trent/trent.h"
#include "../../core_c/include/tc_scene.h"

namespace nb = nanobind;

namespace termin {
namespace animation {

// TcAnimationClip - animation clip wrapper with registry integration
// Stores handle (index + generation) instead of raw pointer
class TcAnimationClip {
public:
    tc_animation_handle handle = tc_animation_handle_invalid();

    TcAnimationClip() = default;

    explicit TcAnimationClip(tc_animation_handle h) : handle(h) {
        if (tc_animation* a = tc_animation_get(handle)) {
            tc_animation_add_ref(a);
        }
    }

    TcAnimationClip(const TcAnimationClip& other) : handle(other.handle) {
        if (tc_animation* a = tc_animation_get(handle)) {
            tc_animation_add_ref(a);
        }
    }

    TcAnimationClip(TcAnimationClip&& other) noexcept : handle(other.handle) {
        other.handle = tc_animation_handle_invalid();
    }

    TcAnimationClip& operator=(const TcAnimationClip& other) {
        if (this != &other) {
            if (tc_animation* a = tc_animation_get(handle)) {
                tc_animation_release(a);
            }
            handle = other.handle;
            if (tc_animation* a = tc_animation_get(handle)) {
                tc_animation_add_ref(a);
            }
        }
        return *this;
    }

    TcAnimationClip& operator=(TcAnimationClip&& other) noexcept {
        if (this != &other) {
            if (tc_animation* a = tc_animation_get(handle)) {
                tc_animation_release(a);
            }
            handle = other.handle;
            other.handle = tc_animation_handle_invalid();
        }
        return *this;
    }

    ~TcAnimationClip() {
        if (tc_animation* a = tc_animation_get(handle)) {
            tc_animation_release(a);
        }
        handle = tc_animation_handle_invalid();
    }

    // Get raw C struct pointer
    tc_animation* get() const { return tc_animation_get(handle); }

    // Query
    bool is_valid() const { return tc_animation_is_valid(handle); }

    const char* uuid() const {
        tc_animation* a = get();
        return a ? a->header.uuid : "";
    }

    const char* name() const {
        tc_animation* a = get();
        return (a && a->header.name) ? a->header.name : "";
    }

    uint32_t version() const {
        tc_animation* a = get();
        return a ? a->header.version : 0;
    }

    double duration() const {
        tc_animation* a = get();
        return a ? a->duration : 0.0;
    }

    double tps() const {
        tc_animation* a = get();
        return a ? a->tps : 30.0;
    }

    size_t channel_count() const {
        tc_animation* a = get();
        return a ? a->channel_count : 0;
    }

    bool loop() const {
        tc_animation* a = get();
        return a && a->loop;
    }

    // Channel access
    tc_animation_channel* channels() const {
        tc_animation* a = get();
        return a ? a->channels : nullptr;
    }

    tc_animation_channel* get_channel(size_t index) const {
        tc_animation* a = get();
        return a ? tc_animation_get_channel(a, index) : nullptr;
    }

    int find_channel(const char* target_name) const {
        tc_animation* a = get();
        return a ? tc_animation_find_channel(a, target_name) : -1;
    }

    void bump_version() {
        if (tc_animation* a = get()) {
            a->header.version++;
        }
    }

    // Trigger lazy load
    bool ensure_loaded() {
        return tc_animation_ensure_loaded(handle);
    }

    // Allocate channels
    tc_animation_channel* alloc_channels(size_t count) {
        tc_animation* a = get();
        return a ? tc_animation_alloc_channels(a, count) : nullptr;
    }

    // Set properties
    void set_tps(double value) {
        if (tc_animation* a = get()) {
            a->tps = value;
        }
    }

    void set_loop(bool value) {
        if (tc_animation* a = get()) {
            a->loop = value ? 1 : 0;
        }
    }

    // Recompute duration from channels
    void recompute_duration() {
        if (tc_animation* a = get()) {
            tc_animation_recompute_duration(a);
        }
    }

    // Sample animation at time t_seconds
    // Returns vector of samples, one per channel
    std::vector<tc_channel_sample> sample(double t_seconds) const {
        tc_animation* a = get();
        if (!a || a->channel_count == 0) {
            return {};
        }

        std::vector<tc_channel_sample> samples(a->channel_count);
        tc_animation_sample(a, t_seconds, samples.data());
        return samples;
    }

    // Sample animation into preallocated buffer
    // Returns number of channels sampled
    size_t sample_into(double t_seconds, tc_channel_sample* out_samples, size_t max_count) const {
        tc_animation* a = get();
        if (!a || !out_samples || a->channel_count == 0) {
            return 0;
        }

        size_t count = a->channel_count < max_count ? a->channel_count : max_count;
        tc_animation_sample(a, t_seconds, out_samples);
        return count;
    }

    // Serialize for scene saving (returns nanobind dict)
    nb::dict serialize() const {
        nb::dict d;
        if (!is_valid()) {
            d["type"] = "none";
            return d;
        }
        d["uuid"] = uuid();
        d["name"] = name();
        d["type"] = "uuid";
        return d;
    }

    // Deserialize from trent data
    void deserialize_from(const nos::trent& data, tc_scene* = nullptr) {
        // Release current handle
        if (tc_animation* a = tc_animation_get(handle)) {
            tc_animation_release(a);
        }
        handle = tc_animation_handle_invalid();

        if (!data.is_dict()) {
            return;
        }

        // Try UUID first
        if (data.contains("uuid")) {
            std::string uuid_str = data["uuid"].as_string();
            tc_animation_handle h = tc_animation_find(uuid_str.c_str());
            if (!tc_animation_handle_is_invalid(h)) {
                handle = h;
                if (tc_animation* a = tc_animation_get(handle)) {
                    tc_animation_add_ref(a);
                }
                return;
            }
        }

        // Try name lookup
        if (data.contains("name")) {
            std::string name_str = data["name"].as_string();
            tc_animation_handle h = tc_animation_find_by_name(name_str.c_str());
            if (!tc_animation_handle_is_invalid(h)) {
                handle = h;
                if (tc_animation* a = tc_animation_get(handle)) {
                    tc_animation_add_ref(a);
                }
            }
        }
    }

    // Get by UUID from registry
    static TcAnimationClip from_uuid(const std::string& uuid) {
        tc_animation_handle h = tc_animation_find(uuid.c_str());
        if (tc_animation_handle_is_invalid(h)) {
            return TcAnimationClip();
        }
        return TcAnimationClip(h);
    }

    // Get or create by UUID
    static TcAnimationClip get_or_create(const std::string& uuid) {
        tc_animation_handle h = tc_animation_get_or_create(uuid.c_str());
        if (tc_animation_handle_is_invalid(h)) {
            return TcAnimationClip();
        }
        return TcAnimationClip(h);
    }

    // Create new animation
    static TcAnimationClip create(const std::string& name = "", const std::string& uuid_hint = "") {
        const char* uuid = uuid_hint.empty() ? nullptr : uuid_hint.c_str();
        tc_animation_handle h = tc_animation_create(uuid);
        if (tc_animation_handle_is_invalid(h)) {
            return TcAnimationClip();
        }

        tc_animation* a = tc_animation_get(h);
        if (a && !name.empty()) {
            a->header.name = tc_intern_string(name.c_str());
        }

        return TcAnimationClip(h);
    }
};

} // namespace animation
} // namespace termin
