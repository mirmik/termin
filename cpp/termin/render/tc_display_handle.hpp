// tc_display_handle.hpp - C++ wrapper for tc_display
#pragma once

#include <string>
#include <vector>
#include <functional>

extern "C" {
#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
#include "render/tc_render_surface.h"
}

namespace termin {

class TcViewport;

// TcDisplay - RAII wrapper for tc_display
// Owns the tc_display pointer and frees it on destruction.
class TcDisplay {
public:
    tc_display* ptr_ = nullptr;
    bool owned_ = true;

public:
    TcDisplay() = default;

    // Create new display with surface
    explicit TcDisplay(tc_render_surface* surface, const std::string& name = "Display")
        : ptr_(tc_display_new(name.c_str(), surface)), owned_(true) {}

    // Wrap existing pointer (non-owning by default)
    explicit TcDisplay(tc_display* ptr, bool owned = false)
        : ptr_(ptr), owned_(owned) {}

    ~TcDisplay() {
        if (ptr_ && owned_) {
            tc_display_free(ptr_);
        }
        ptr_ = nullptr;
    }

    // Move semantics
    TcDisplay(TcDisplay&& other) noexcept
        : ptr_(other.ptr_), owned_(other.owned_) {
        other.ptr_ = nullptr;
        other.owned_ = false;
    }

    TcDisplay& operator=(TcDisplay&& other) noexcept {
        if (this != &other) {
            if (ptr_ && owned_) {
                tc_display_free(ptr_);
            }
            ptr_ = other.ptr_;
            owned_ = other.owned_;
            other.ptr_ = nullptr;
            other.owned_ = false;
        }
        return *this;
    }

    // No copy
    TcDisplay(const TcDisplay&) = delete;
    TcDisplay& operator=(const TcDisplay&) = delete;

    bool is_valid() const { return ptr_ != nullptr; }
    tc_display* ptr() const { return ptr_; }

    // Properties
    std::string name() const {
        if (!ptr_) return "";
        const char* n = tc_display_get_name(ptr_);
        return n ? n : "";
    }

    void set_name(const std::string& name) {
        if (ptr_) tc_display_set_name(ptr_, name.c_str());
    }

    std::string uuid() const {
        if (!ptr_) return "";
        const char* u = tc_display_get_uuid(ptr_);
        return u ? u : "";
    }

    void set_uuid(const std::string& uuid) {
        if (ptr_) tc_display_set_uuid(ptr_, uuid.c_str());
    }

    bool editor_only() const {
        return ptr_ ? tc_display_get_editor_only(ptr_) : false;
    }

    void set_editor_only(bool value) {
        if (ptr_) tc_display_set_editor_only(ptr_, value);
    }

    bool enabled() const {
        return ptr_ ? tc_display_get_enabled(ptr_) : true;
    }

    void set_enabled(bool value) {
        if (ptr_) tc_display_set_enabled(ptr_, value);
    }

    tc_render_surface* surface() const {
        return ptr_ ? tc_display_get_surface(ptr_) : nullptr;
    }

    void set_surface(tc_render_surface* surface) {
        if (ptr_) tc_display_set_surface(ptr_, surface);
    }

    // Size
    std::pair<int, int> get_size() const {
        int w = 0, h = 0;
        if (ptr_) tc_display_get_size(ptr_, &w, &h);
        return {w, h};
    }

    // Window size (logical pixels, may differ from framebuffer on HiDPI)
    std::pair<int, int> get_window_size() const {
        int w = 0, h = 0;
        if (ptr_) tc_display_get_window_size(ptr_, &w, &h);
        return {w, h};
    }

    // Cursor position in window pixels
    std::pair<double, double> get_cursor_pos() const {
        double x = 0.0, y = 0.0;
        if (ptr_) tc_display_get_cursor_pos(ptr_, &x, &y);
        return {x, y};
    }

    // Should close
    bool should_close() const {
        return ptr_ ? tc_display_should_close(ptr_) : false;
    }

    void set_should_close(bool value) {
        if (ptr_) tc_display_set_should_close(ptr_, value);
    }

    // Viewport management
    size_t viewport_count() const {
        return ptr_ ? tc_display_get_viewport_count(ptr_) : 0;
    }

    tc_viewport_handle first_viewport() const {
        return ptr_ ? tc_display_get_first_viewport(ptr_) : TC_VIEWPORT_HANDLE_INVALID;
    }

    tc_viewport_handle viewport_at_index(size_t index) const {
        return ptr_ ? tc_display_get_viewport_at_index(ptr_, index) : TC_VIEWPORT_HANDLE_INVALID;
    }

    void add_viewport(tc_viewport_handle vh) {
        if (ptr_) tc_display_add_viewport(ptr_, vh);
    }

    void remove_viewport(tc_viewport_handle vh) {
        if (ptr_) tc_display_remove_viewport(ptr_, vh);
    }

    // Viewport lookup
    tc_viewport_handle viewport_at(float x, float y) const {
        return ptr_ ? tc_display_viewport_at(ptr_, x, y) : TC_VIEWPORT_HANDLE_INVALID;
    }

    tc_viewport_handle viewport_at_screen(float px, float py) const {
        return ptr_ ? tc_display_viewport_at_screen(ptr_, px, py) : TC_VIEWPORT_HANDLE_INVALID;
    }

    // Update pixel rects
    void update_all_pixel_rects() {
        if (ptr_) tc_display_update_all_pixel_rects(ptr_);
    }

    // Context operations
    void make_current() {
        if (ptr_) tc_display_make_current(ptr_);
    }

    void swap_buffers() {
        if (ptr_) tc_display_swap_buffers(ptr_);
    }

    // Static factory
    static TcDisplay create(tc_render_surface* surface, const std::string& name = "Display") {
        return TcDisplay(surface, name);
    }

    static TcDisplay from_ptr(tc_display* ptr, bool owned = false) {
        return TcDisplay(ptr, owned);
    }
};

} // namespace termin
