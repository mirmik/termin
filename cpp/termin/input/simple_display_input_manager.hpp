// simple_display_input_manager.hpp - Input handler for simple applications
#pragma once

#include "input_events.hpp"
#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
#include "render/tc_input_manager.h"
#include "render/tc_render_surface.h"
#include "core/tc_scene.h"
#include "core/tc_scene_pool.h"
#include "core/tc_component.h"

namespace termin {

// SimpleDisplayInputManager - routes input events to scene InputComponents
// Handles: mouse button, mouse move, scroll, key events
// ESC closes the window
class SimpleDisplayInputManager {
public:
    tc_input_manager tc_im;
    tc_display* display_ = nullptr;
    tc_viewport_handle active_viewport_ = TC_VIEWPORT_HANDLE_INVALID;
    double last_cursor_x_ = 0.0;
    double last_cursor_y_ = 0.0;
    bool has_cursor_ = false;

    static tc_input_manager_vtable vtable_;

    SimpleDisplayInputManager(tc_display* display)
        : display_(display)
    {
        tc_input_manager_init(&tc_im, &vtable_);
        tc_im.userdata = this;
    }

    ~SimpleDisplayInputManager() = default;

    // Get raw pointer to tc_input_manager
    tc_input_manager* tc_input_manager_ptr() { return &tc_im; }

    // Get display
    tc_display* display() const { return display_; }

    // Get cursor position from surface
    void get_cursor_pos(double* x, double* y) const {
        if (display_ && display_->surface) {
            tc_render_surface_get_cursor_pos(display_->surface, x, y);
        } else {
            *x = last_cursor_x_;
            *y = last_cursor_y_;
        }
    }

    // Find viewport at screen coordinates
    tc_viewport_handle viewport_at_screen(double x, double y) const {
        if (!display_) return TC_VIEWPORT_HANDLE_INVALID;
        return tc_display_viewport_at_screen(display_, (float)x, (float)y);
    }

    // Event handlers (called from vtable)
    void on_mouse_button(int button, int action, int mods) {
        double x, y;
        get_cursor_pos(&x, &y);

        tc_viewport_handle viewport = viewport_at_screen(x, y);

        // Track active viewport for drag operations
        if (action == TC_INPUT_PRESS) {
            active_viewport_ = viewport;
        }
        if (action == TC_INPUT_RELEASE) {
            has_cursor_ = false;
            if (!tc_viewport_handle_valid(viewport)) {
                viewport = active_viewport_;
            }
            active_viewport_ = TC_VIEWPORT_HANDLE_INVALID;
        }

        // Dispatch to scene
        if (tc_viewport_handle_valid(viewport)) {
            tc_scene_handle scene = tc_viewport_get_scene(viewport);
            if (tc_scene_handle_valid(scene)) {
                MouseButtonEvent event(viewport, x, y, button, action, mods);
                dispatch_mouse_button(scene, &event);
            }
        }
    }

    void on_mouse_move(double x, double y) {
        double dx = 0.0, dy = 0.0;
        if (has_cursor_) {
            dx = x - last_cursor_x_;
            dy = y - last_cursor_y_;
        }
        last_cursor_x_ = x;
        last_cursor_y_ = y;
        has_cursor_ = true;

        tc_viewport_handle viewport = active_viewport_;
        if (!tc_viewport_handle_valid(viewport)) {
            viewport = viewport_at_screen(x, y);
        }

        // Dispatch to scene
        if (tc_viewport_handle_valid(viewport)) {
            tc_scene_handle scene = tc_viewport_get_scene(viewport);
            if (tc_scene_handle_valid(scene)) {
                MouseMoveEvent event(viewport, x, y, dx, dy);
                dispatch_mouse_move(scene, &event);
            }
        }
    }

    void on_scroll(double xoffset, double yoffset, int mods) {
        double x = last_cursor_x_;
        double y = last_cursor_y_;

        tc_viewport_handle viewport = viewport_at_screen(x, y);
        if (!tc_viewport_handle_valid(viewport)) {
            viewport = active_viewport_;
        }

        // Dispatch to scene
        if (tc_viewport_handle_valid(viewport)) {
            tc_scene_handle scene = tc_viewport_get_scene(viewport);
            if (tc_scene_handle_valid(scene)) {
                ScrollEvent event(viewport, x, y, xoffset, yoffset, mods);
                dispatch_scroll(scene, &event);
            }
        }
    }

    void on_key(int key, int scancode, int action, int mods) {
        // ESC closes window (key code 256 = GLFW_KEY_ESCAPE)
        if (key == 256 && action == TC_INPUT_PRESS) {
            if (display_ && display_->surface) {
                tc_render_surface_set_should_close(display_->surface, true);
            }
        }

        tc_viewport_handle viewport = active_viewport_;
        if (!tc_viewport_handle_valid(viewport) && display_) {
            viewport = tc_display_get_first_viewport(display_);
        }

        // Dispatch to scene
        if (tc_viewport_handle_valid(viewport)) {
            tc_scene_handle scene = tc_viewport_get_scene(viewport);
            if (tc_scene_handle_valid(scene)) {
                KeyEvent event(viewport, key, scancode, action, mods);
                dispatch_key(scene, &event);
            }
        }
    }

    void on_char(uint32_t codepoint) {
        // Not used in simple manager
        (void)codepoint;
    }

private:
    // Dispatch functions with explicit types
    void dispatch_mouse_button(tc_scene_handle scene, tc_mouse_button_event* event) {
        tc_scene_foreach_input_handler(scene,
            [](tc_component* c, void* user_data) -> bool {
                tc_mouse_button_event* ev = static_cast<tc_mouse_button_event*>(user_data);
                tc_component_on_mouse_button(c, ev);
                return true;
            },
            event,
            TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED);
    }

    void dispatch_mouse_move(tc_scene_handle scene, tc_mouse_move_event* event) {
        tc_scene_foreach_input_handler(scene,
            [](tc_component* c, void* user_data) -> bool {
                tc_mouse_move_event* ev = static_cast<tc_mouse_move_event*>(user_data);
                tc_component_on_mouse_move(c, ev);
                return true;
            },
            event,
            TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED);
    }

    void dispatch_scroll(tc_scene_handle scene, tc_scroll_event* event) {
        tc_scene_foreach_input_handler(scene,
            [](tc_component* c, void* user_data) -> bool {
                tc_scroll_event* ev = static_cast<tc_scroll_event*>(user_data);
                tc_component_on_scroll(c, ev);
                return true;
            },
            event,
            TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED);
    }

    void dispatch_key(tc_scene_handle scene, tc_key_event* event) {
        tc_scene_foreach_input_handler(scene,
            [](tc_component* c, void* user_data) -> bool {
                tc_key_event* ev = static_cast<tc_key_event*>(user_data);
                tc_component_on_key(c, ev);
                return true;
            },
            event,
            TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED);
    }
};

// Static vtable callbacks
inline void simple_on_mouse_button(tc_input_manager* m, int button, int action, int mods) {
    if (m && m->userdata) {
        static_cast<SimpleDisplayInputManager*>(m->userdata)->on_mouse_button(button, action, mods);
    }
}

inline void simple_on_mouse_move(tc_input_manager* m, double x, double y) {
    if (m && m->userdata) {
        static_cast<SimpleDisplayInputManager*>(m->userdata)->on_mouse_move(x, y);
    }
}

inline void simple_on_scroll(tc_input_manager* m, double x, double y, int mods) {
    if (m && m->userdata) {
        static_cast<SimpleDisplayInputManager*>(m->userdata)->on_scroll(x, y, mods);
    }
}

inline void simple_on_key(tc_input_manager* m, int key, int scancode, int action, int mods) {
    if (m && m->userdata) {
        static_cast<SimpleDisplayInputManager*>(m->userdata)->on_key(key, scancode, action, mods);
    }
}

inline void simple_on_char(tc_input_manager* m, uint32_t codepoint) {
    if (m && m->userdata) {
        static_cast<SimpleDisplayInputManager*>(m->userdata)->on_char(codepoint);
    }
}

inline void simple_destroy(tc_input_manager* m) {
    // body is managed by Python, nothing to do here
    (void)m;
}

// Static vtable definition
inline tc_input_manager_vtable SimpleDisplayInputManager::vtable_ = {
    simple_on_mouse_button,
    simple_on_mouse_move,
    simple_on_scroll,
    simple_on_key,
    simple_on_char,
    simple_destroy
};

} // namespace termin
