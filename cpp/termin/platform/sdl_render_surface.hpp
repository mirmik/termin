#pragma once

#include "sdl_window.hpp"
#include "render/tc_render_surface.h"
#include "render/tc_input_manager.h"

namespace termin {

class SDLWindowBackend;

// SDLWindowRenderSurface - владеет SDLWindow и tc_render_surface
class SDLWindowRenderSurface {
private:
    SDLWindow* window_;
    tc_render_surface surface_;
    tc_input_manager* input_manager_;
    SDLWindowBackend* backend_;
    bool needs_render_;
    int last_width_;
    int last_height_;

public:
    SDLWindowRenderSurface(
        int width,
        int height,
        const std::string& title,
        SDLWindowBackend* backend,
        SDLWindowRenderSurface* share = nullptr
    );

    ~SDLWindowRenderSurface();

    // Non-copyable
    SDLWindowRenderSurface(const SDLWindowRenderSurface&) = delete;
    SDLWindowRenderSurface& operator=(const SDLWindowRenderSurface&) = delete;

    // tc_render_surface pointer (для передачи в C код)
    tc_render_surface* tc_surface() { return &surface_; }
    const tc_render_surface* tc_surface() const { return &surface_; }

    // Input manager
    void set_input_manager(tc_input_manager* manager);
    tc_input_manager* input_manager() const { return input_manager_; }

    // Window access
    SDLWindow* window() { return window_; }
    const SDLWindow* window() const { return window_; }
    uint32_t window_id() const { return window_ ? window_->get_window_id() : 0; }

    // Native handle for Qt embedding (HWND on Windows, NSWindow on macOS, X11 Window on Linux)
    uintptr_t get_native_handle() const;

    // Surface methods (convenience)
    void make_current() { if (window_) window_->make_current(); }
    void swap_buffers() { if (window_) window_->swap_buffers(); }
    std::pair<int, int> get_size() const { return window_ ? window_->framebuffer_size() : std::make_pair(0, 0); }
    std::pair<int, int> window_size() const { return window_ ? window_->window_size() : std::make_pair(0, 0); }
    bool should_close() const { return window_ ? window_->should_close() : true; }
    void set_should_close(bool value) { if (window_) window_->set_should_close(value); }
    std::pair<double, double> get_cursor_pos() const { return window_ ? window_->get_cursor_pos() : std::make_pair(0.0, 0.0); }

    // Graphics backend (for framebuffer creation)
    void set_graphics(OpenGLGraphicsBackend* graphics) { if (window_) window_->set_graphics(graphics); }
    FramebufferHandle* get_window_framebuffer() { return window_ ? window_->get_window_framebuffer() : nullptr; }

    // Render flag for pull-mode rendering
    void request_update() { needs_render_ = true; }
    bool needs_render() const { return needs_render_; }
    void clear_render_flag() { needs_render_ = false; }

    // Check if window was resized and update state
    bool check_resize();

private:
    // VTable implementation
    static uint32_t vtable_get_framebuffer(tc_render_surface* self);
    static void vtable_get_size(tc_render_surface* self, int* width, int* height);
    static void vtable_make_current(tc_render_surface* self);
    static void vtable_swap_buffers(tc_render_surface* self);
    static uintptr_t vtable_context_key(tc_render_surface* self);
    static void vtable_poll_events(tc_render_surface* self);
    static void vtable_get_window_size(tc_render_surface* self, int* width, int* height);
    static bool vtable_should_close(tc_render_surface* self);
    static void vtable_set_should_close(tc_render_surface* self, bool value);
    static void vtable_get_cursor_pos(tc_render_surface* self, double* x, double* y);
    static void vtable_destroy(tc_render_surface* self);

    static const tc_render_surface_vtable s_vtable;

    // Get SDLWindowRenderSurface* from tc_render_surface*
    static SDLWindowRenderSurface* from_tc_surface(tc_render_surface* s) {
        // surface_ is first member after vtable, so we can recover this pointer
        return reinterpret_cast<SDLWindowRenderSurface*>(
            reinterpret_cast<char*>(s) - offsetof(SDLWindowRenderSurface, surface_)
        );
    }
};

} // namespace termin
