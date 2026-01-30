#pragma once

// TcViewport - RAII wrapper for tc_viewport with reference counting

extern "C" {
#include "termin_core.h"
}

#include <string>

namespace termin {

// TcViewport - Viewport wrapper with automatic reference counting
class TcViewport {
public:
    tc_viewport* ptr_ = nullptr;

    TcViewport() = default;

    explicit TcViewport(tc_viewport* vp) : ptr_(vp) {
        if (ptr_) {
            tc_viewport_add_ref(ptr_);
        }
    }

    TcViewport(const TcViewport& other) : ptr_(other.ptr_) {
        if (ptr_) {
            tc_viewport_add_ref(ptr_);
        }
    }

    TcViewport(TcViewport&& other) noexcept : ptr_(other.ptr_) {
        other.ptr_ = nullptr;
    }

    TcViewport& operator=(const TcViewport& other) {
        if (this != &other) {
            if (ptr_) {
                tc_viewport_release(ptr_);
            }
            ptr_ = other.ptr_;
            if (ptr_) {
                tc_viewport_add_ref(ptr_);
            }
        }
        return *this;
    }

    TcViewport& operator=(TcViewport&& other) noexcept {
        if (this != &other) {
            if (ptr_) {
                tc_viewport_release(ptr_);
            }
            ptr_ = other.ptr_;
            other.ptr_ = nullptr;
        }
        return *this;
    }

    ~TcViewport() {
        if (ptr_) {
            tc_viewport_release(ptr_);
        }
        ptr_ = nullptr;
    }

    // Get raw pointer
    tc_viewport* get() const { return ptr_; }

    // Check if valid
    bool is_valid() const { return ptr_ != nullptr; }

    // Query properties (safe - returns defaults if nullptr)
    const char* name() const {
        return ptr_ ? tc_viewport_get_name(ptr_) : "";
    }

    bool enabled() const {
        return ptr_ ? tc_viewport_get_enabled(ptr_) : false;
    }

    int depth() const {
        return ptr_ ? tc_viewport_get_depth(ptr_) : 0;
    }

    uint64_t layer_mask() const {
        return ptr_ ? tc_viewport_get_layer_mask(ptr_) : 0xFFFFFFFFFFFFFFFFULL;
    }

    tc_scene_handle scene() const {
        return ptr_ ? tc_viewport_get_scene(ptr_) : TC_SCENE_HANDLE_INVALID;
    }

    tc_component* camera() const {
        return ptr_ ? tc_viewport_get_camera(ptr_) : nullptr;
    }

    tc_pipeline* pipeline() const {
        return ptr_ ? tc_viewport_get_pipeline(ptr_) : nullptr;
    }

    // Modify properties
    void set_enabled(bool enabled) {
        if (ptr_) tc_viewport_set_enabled(ptr_, enabled);
    }

    void set_depth(int depth) {
        if (ptr_) tc_viewport_set_depth(ptr_, depth);
    }

    void set_layer_mask(uint64_t mask) {
        if (ptr_) tc_viewport_set_layer_mask(ptr_, mask);
    }

    void set_scene(tc_scene_handle scene) {
        if (ptr_) tc_viewport_set_scene(ptr_, scene);
    }

    void set_camera(tc_component* camera) {
        if (ptr_) tc_viewport_set_camera(ptr_, camera);
    }

    void set_pipeline(tc_pipeline* pipeline) {
        if (ptr_) tc_viewport_set_pipeline(ptr_, pipeline);
    }

    // Rect access
    void get_rect(float& x, float& y, float& w, float& h) const {
        if (ptr_) {
            tc_viewport_get_rect(ptr_, &x, &y, &w, &h);
        } else {
            x = y = 0.0f;
            w = h = 1.0f;
        }
    }

    void set_rect(float x, float y, float w, float h) {
        if (ptr_) tc_viewport_set_rect(ptr_, x, y, w, h);
    }

    void get_pixel_rect(int& px, int& py, int& pw, int& ph) const {
        if (ptr_) {
            tc_viewport_get_pixel_rect(ptr_, &px, &py, &pw, &ph);
        } else {
            px = py = 0;
            pw = ph = 1;
        }
    }

    void set_pixel_rect(int px, int py, int pw, int ph) {
        if (ptr_) tc_viewport_set_pixel_rect(ptr_, px, py, pw, ph);
    }

    void update_pixel_rect(int display_width, int display_height) {
        if (ptr_) tc_viewport_update_pixel_rect(ptr_, display_width, display_height);
    }

    // Reference count access (for debugging)
    uint32_t ref_count() const {
        return ptr_ ? tc_viewport_get_ref_count(ptr_) : 0;
    }

    // Create new viewport (takes ownership, ref_count starts at 1)
    static TcViewport create(const std::string& name, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID, tc_component* camera = nullptr) {
        tc_viewport* vp = tc_viewport_new(name.c_str(), scene, camera);
        if (!vp) {
            return TcViewport();
        }
        // tc_viewport_new already sets ref_count=1, so we don't add_ref here
        TcViewport result;
        result.ptr_ = vp;
        return result;
    }

    // Wrap existing pointer (adds ref)
    static TcViewport from_ptr(tc_viewport* vp) {
        return TcViewport(vp);
    }
};

} // namespace termin
