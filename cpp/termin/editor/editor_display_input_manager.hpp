// editor_display_input_manager.hpp - Per-display input manager for editor mode
// Created in Display when editor mode is active.
// Dispatches events to camera/scene components and delegates
// picking/gizmo/selection to EditorInteractionSystem singleton.
#pragma once

#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "render/tc_input_manager.h"
#include "render/tc_render_surface.h"
#include "core/tc_scene.h"
#include "core/tc_component.h"
#include "termin/input/input_events.hpp"

namespace termin {

class EditorDisplayInputManager {
public:
    tc_input_manager _tc_im;

    tc_display* _display = nullptr;
    tc_viewport_handle _active_viewport = TC_VIEWPORT_HANDLE_INVALID;
    double _last_cursor_x = 0.0;
    double _last_cursor_y = 0.0;
    bool _has_cursor = false;
    int _current_mods = 0;

private:
    static tc_input_manager_vtable _vtable;

public:
    EditorDisplayInputManager(tc_display* display);
    ~EditorDisplayInputManager() = default;

    tc_input_manager* tc_input_manager_ptr() { return &_tc_im; }
    tc_display* display() const { return _display; }
    tc_viewport_handle active_viewport() const { return _active_viewport; }

    void get_cursor_pos(double* x, double* y) const;
    tc_viewport_handle viewport_under_cursor(double x, double y) const;

    // vtable event handlers
    void on_mouse_button(int button, int action, int mods);
    void on_mouse_move(double x, double y);
    void on_scroll(double xoffset, double yoffset, int mods);
    void on_key(int key, int scancode, int action, int mods);

private:
    // Dispatch to camera entity's input handler components
    void _dispatch_to_camera(tc_viewport_handle vp, tc_mouse_button_event* ev);
    void _dispatch_to_camera(tc_viewport_handle vp, tc_mouse_move_event* ev);
    void _dispatch_to_camera(tc_viewport_handle vp, tc_scroll_event* ev);
    void _dispatch_to_camera(tc_viewport_handle vp, tc_key_event* ev);

    // Dispatch to scene's editor components (active_in_editor=true)
    void _dispatch_to_editor_components(tc_viewport_handle vp, tc_mouse_button_event* ev);
    void _dispatch_to_editor_components(tc_viewport_handle vp, tc_mouse_move_event* ev);
    void _dispatch_to_editor_components(tc_viewport_handle vp, tc_scroll_event* ev);
    void _dispatch_to_editor_components(tc_viewport_handle vp, tc_key_event* ev);

    // Dispatch to viewport's internal entities
    void _dispatch_to_internal_entities(tc_viewport_handle vp, tc_mouse_button_event* ev);
    void _dispatch_to_internal_entities(tc_viewport_handle vp, tc_mouse_move_event* ev);
    void _dispatch_to_internal_entities(tc_viewport_handle vp, tc_scroll_event* ev);
    void _dispatch_to_internal_entities(tc_viewport_handle vp, tc_key_event* ev);
};

} // namespace termin
