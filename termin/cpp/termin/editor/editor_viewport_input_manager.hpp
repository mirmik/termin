// editor_viewport_input_manager.hpp - Per-viewport input manager for editor mode
// Dispatches events to camera/scene components and delegates
// picking/gizmo/selection to EditorInteractionSystem singleton.
#pragma once

#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "render/tc_input_manager.h"
#include "core/tc_scene.h"
#include "core/tc_component.h"
#include "termin/input/input_events.hpp"

namespace termin {

class EditorViewportInputManager {
public:
    tc_input_manager _tc_im;
    tc_viewport_handle _viewport = TC_VIEWPORT_HANDLE_INVALID;
    tc_display* _display = nullptr;

private:
    double _last_cursor_x = 0.0;
    double _last_cursor_y = 0.0;
    bool _has_cursor = false;
    int _current_mods = 0;

    static tc_input_manager_vtable _vtable;

public:
    EditorViewportInputManager(tc_viewport_handle viewport, tc_display* display);
    ~EditorViewportInputManager() = default;

    tc_input_manager* tc_input_manager_ptr() { return &_tc_im; }
    tc_viewport_handle viewport() const { return _viewport; }
    tc_display* display() const { return _display; }

    // vtable event handlers
    void on_mouse_button(int button, int action, int mods);
    void on_mouse_move(double x, double y);
    void on_scroll(double xoffset, double yoffset, int mods);
    void on_key(int key, int scancode, int action, int mods);

private:
    // Dispatch to camera entity's input handler components
    void _dispatch_to_camera(tc_mouse_button_event* ev);
    void _dispatch_to_camera(tc_mouse_move_event* ev);
    void _dispatch_to_camera(tc_scroll_event* ev);
    void _dispatch_to_camera(tc_key_event* ev);

    // Dispatch to scene's editor components (active_in_editor=true)
    void _dispatch_to_editor_components(tc_mouse_button_event* ev);
    void _dispatch_to_editor_components(tc_mouse_move_event* ev);
    void _dispatch_to_editor_components(tc_scroll_event* ev);
    void _dispatch_to_editor_components(tc_key_event* ev);

    // Dispatch to viewport's internal entities
    void _dispatch_to_internal_entities(tc_mouse_button_event* ev);
    void _dispatch_to_internal_entities(tc_mouse_move_event* ev);
    void _dispatch_to_internal_entities(tc_scroll_event* ev);
    void _dispatch_to_internal_entities(tc_key_event* ev);
};

} // namespace termin
