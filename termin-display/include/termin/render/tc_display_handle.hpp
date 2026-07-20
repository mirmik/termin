#pragma once

#include <string>
#include <utility>

extern "C" {
#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "render/tc_render_surface.h"
}

namespace termin {

// Copyable, non-owning facade over process-owned tc_display storage.
// Native lifetime is controlled only through explicit tc_display_free/destroy().
class TcDisplay {
public:
    tc_display_handle handle_ = TC_DISPLAY_HANDLE_INVALID;

    TcDisplay() = default;
    explicit TcDisplay(tc_display_handle handle) : handle_(handle) {}

    explicit TcDisplay(tc_render_surface* surface, const std::string& name = "Display")
        : handle_(tc_display_new(name.c_str(), surface)) {}

    bool is_valid() const { return tc_display_alive(handle_); }
    tc_display_handle handle() const { return handle_; }

    bool destroy() {
        if (!tc_display_handle_valid(handle_)) return false;
        bool destroyed = tc_display_free(handle_);
        if (destroyed) handle_ = TC_DISPLAY_HANDLE_INVALID;
        return destroyed;
    }

    std::string name() const {
        const char* value = tc_display_get_name(handle_);
        return value ? value : "";
    }
    void set_name(const std::string& value) { tc_display_set_name(handle_, value.c_str()); }

    std::string uuid() const {
        const char* value = tc_display_get_uuid(handle_);
        return value ? value : "";
    }
    void set_uuid(const std::string& value) { tc_display_set_uuid(handle_, value.c_str()); }

    bool editor_only() const { return tc_display_get_editor_only(handle_); }
    void set_editor_only(bool value) { tc_display_set_editor_only(handle_, value); }

    bool enabled() const { return tc_display_get_enabled(handle_); }
    void set_enabled(bool value) { tc_display_set_enabled(handle_, value); }

    bool auto_remove_when_empty() const {
        return tc_display_get_auto_remove_when_empty(handle_);
    }
    void set_auto_remove_when_empty(bool value) {
        tc_display_set_auto_remove_when_empty(handle_, value);
    }

    tc_render_surface* surface() const { return tc_display_get_surface(handle_); }
    bool set_surface(tc_render_surface* surface) {
        return tc_display_set_surface(handle_, surface);
    }

    tc_input_manager* input_manager() const {
        return tc_display_get_input_manager(handle_);
    }
    bool dispatch_pointer_move(double x, double y) {
        return tc_display_dispatch_pointer_move(handle_, x, y);
    }
    bool dispatch_pointer_button(double x, double y, int button, int action,
                                 int mods, uint32_t click_count) {
        return tc_display_dispatch_pointer_button(
            handle_, x, y, button, action, mods, click_count);
    }
    bool dispatch_wheel(double x, double y, double wheel_x, double wheel_y, int mods) {
        return tc_display_dispatch_wheel(handle_, x, y, wheel_x, wheel_y, mods);
    }
    bool dispatch_key(int key, int scancode, int action, int mods) {
        return tc_display_dispatch_key(handle_, key, scancode, action, mods);
    }
    bool dispatch_text(uint32_t codepoint) {
        return tc_display_dispatch_text(handle_, codepoint);
    }

    std::pair<int, int> get_size() const {
        int width = 0;
        int height = 0;
        tc_display_get_size(handle_, &width, &height);
        return {width, height};
    }

    size_t viewport_count() const { return tc_display_get_viewport_count(handle_); }
    tc_viewport_handle first_viewport() const {
        return tc_display_get_first_viewport(handle_);
    }
    tc_viewport_handle viewport_at_index(size_t index) const {
        return tc_display_get_viewport_at_index(handle_, index);
    }
    void add_viewport(tc_viewport_handle viewport) {
        tc_display_add_viewport(handle_, viewport);
    }
    void remove_viewport(tc_viewport_handle viewport) {
        tc_display_remove_viewport(handle_, viewport);
    }
    tc_viewport_handle viewport_at(float x, float y) const {
        return tc_display_viewport_at(handle_, x, y);
    }
    tc_viewport_handle viewport_at_screen(float x, float y) const {
        return tc_display_viewport_at_screen(handle_, x, y);
    }
    void update_all_pixel_rects() { tc_display_update_all_pixel_rects(handle_); }

    static TcDisplay create(tc_render_surface* surface,
                            const std::string& name = "Display") {
        return TcDisplay(surface, name);
    }
    static TcDisplay from_handle(tc_display_handle handle) { return TcDisplay(handle); }
};

} // namespace termin
