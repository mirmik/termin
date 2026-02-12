// editor_viewport_input_manager.cpp - Per-viewport input manager for editor mode

#include "termin/editor/editor_viewport_input_manager.hpp"
#include "termin/editor/editor_interaction_system.hpp"
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
#include "core/tc_entity_pool.h"
#include "tc_log.h"

namespace termin {

// Vtable callback wrappers
static void editor_on_mouse_button(tc_input_manager* m, int button, int action, int mods) {
    if (m && m->userdata) {
        static_cast<EditorViewportInputManager*>(m->userdata)->on_mouse_button(button, action, mods);
    }
}

static void editor_on_mouse_move(tc_input_manager* m, double x, double y) {
    if (m && m->userdata) {
        static_cast<EditorViewportInputManager*>(m->userdata)->on_mouse_move(x, y);
    }
}

static void editor_on_scroll(tc_input_manager* m, double x, double y, int mods) {
    if (m && m->userdata) {
        static_cast<EditorViewportInputManager*>(m->userdata)->on_scroll(x, y, mods);
    }
}

static void editor_on_key(tc_input_manager* m, int key, int scancode, int action, int mods) {
    if (m && m->userdata) {
        static_cast<EditorViewportInputManager*>(m->userdata)->on_key(key, scancode, action, mods);
    }
}

static void editor_on_char(tc_input_manager* m, uint32_t codepoint) {
    (void)m;
    (void)codepoint;
}

static void editor_destroy(tc_input_manager* m) {
    (void)m;
}

tc_input_manager_vtable EditorViewportInputManager::_vtable = {
    editor_on_mouse_button,
    editor_on_mouse_move,
    editor_on_scroll,
    editor_on_key,
    editor_on_char,
    editor_destroy
};

// ============================================================================
// Constructor
// ============================================================================

EditorViewportInputManager::EditorViewportInputManager(tc_viewport_handle viewport, tc_display* display)
    : _viewport(viewport)
    , _display(display)
{
    tc_input_manager_init(&_tc_im, &_vtable);
    _tc_im.userdata = this;

    // Auto-attach to viewport
    tc_viewport_set_input_manager(viewport, &_tc_im);
}

// ============================================================================
// Event Handlers
// ============================================================================

void EditorViewportInputManager::on_mouse_button(int button, int action, int mods) {
    if (!tc_viewport_alive(_viewport)) return;

    double x = _last_cursor_x;
    double y = _last_cursor_y;

    // Dispatch to camera, internal entities, and editor components
    MouseButtonEvent event(_viewport, x, y, button, action, mods);
    _dispatch_to_internal_entities(&event);
    _dispatch_to_editor_components(&event);
    _dispatch_to_camera(&event);

    // Delegate to EditorInteractionSystem for picking/gizmo
    auto* sys = EditorInteractionSystem::instance();
    if (sys) {
        sys->on_mouse_button(button, action, mods, (float)x, (float)y, _viewport, _display);
    }
}

void EditorViewportInputManager::on_mouse_move(double x, double y) {
    if (!tc_viewport_alive(_viewport)) return;

    double dx = 0.0, dy = 0.0;
    if (_has_cursor) {
        dx = x - _last_cursor_x;
        dy = y - _last_cursor_y;
    }
    _last_cursor_x = x;
    _last_cursor_y = y;
    _has_cursor = true;

    MouseMoveEvent event(_viewport, x, y, dx, dy);
    _dispatch_to_internal_entities(&event);
    _dispatch_to_editor_components(&event);
    _dispatch_to_camera(&event);

    // Delegate to EditorInteractionSystem for hover/gizmo
    auto* sys = EditorInteractionSystem::instance();
    if (sys) {
        sys->on_mouse_move((float)x, (float)y, (float)dx, (float)dy, _viewport, _display);
    }
}

void EditorViewportInputManager::on_scroll(double xoffset, double yoffset, int mods) {
    if (!tc_viewport_alive(_viewport)) return;

    double x = _last_cursor_x;
    double y = _last_cursor_y;

    // Use mods from parameter if provided, otherwise fall back to tracked mods
    int actual_mods = mods != 0 ? mods : _current_mods;

    ScrollEvent event(_viewport, x, y, xoffset, yoffset, actual_mods);
    _dispatch_to_internal_entities(&event);
    _dispatch_to_editor_components(&event);
    _dispatch_to_camera(&event);

    // Request render update (zoom changes camera, needs redraw)
    auto* sys = EditorInteractionSystem::instance();
    if (sys && sys->on_request_update) {
        sys->on_request_update();
    }
}

void EditorViewportInputManager::on_key(int key, int scancode, int action, int mods) {
    if (!tc_viewport_alive(_viewport)) return;

    _current_mods = mods;

    KeyEvent event(_viewport, key, scancode, action, mods);
    _dispatch_to_internal_entities(&event);
    _dispatch_to_editor_components(&event);
    _dispatch_to_camera(&event);

    // Delegate to EditorInteractionSystem for editor-level key handling
    auto* sys = EditorInteractionSystem::instance();
    if (sys && sys->on_key) {
        KeyEvent key_event(_viewport, key, scancode, action, mods);
        sys->on_key(key_event);
    } else {
        tc_log(TC_LOG_WARN, "EditorViewportInputManager::on_key: no sys=%p or no on_key callback", (void*)sys);
    }
}

// ============================================================================
// Dispatch helpers - Camera
// ============================================================================

static void _dispatch_camera_components(tc_viewport_handle vp, auto dispatch_fn) {
    tc_entity_handle cam_ent = tc_viewport_get_camera_entity(vp);
    if (!tc_entity_handle_valid(cam_ent)) return;

    tc_entity_foreach_input_handler_subtree(cam_ent,
        [](tc_component* c, void* user_data) -> bool {
            auto* fn = static_cast<decltype(&dispatch_fn)>(user_data);
            (*fn)(c);
            return true;
        },
        &dispatch_fn
    );
}

void EditorViewportInputManager::_dispatch_to_camera(tc_mouse_button_event* ev) {
    _dispatch_camera_components(_viewport, [ev](tc_component* c) {
        tc_component_on_mouse_button(c, ev);
    });
}

void EditorViewportInputManager::_dispatch_to_camera(tc_mouse_move_event* ev) {
    _dispatch_camera_components(_viewport, [ev](tc_component* c) {
        tc_component_on_mouse_move(c, ev);
    });
}

void EditorViewportInputManager::_dispatch_to_camera(tc_scroll_event* ev) {
    _dispatch_camera_components(_viewport, [ev](tc_component* c) {
        tc_component_on_scroll(c, ev);
    });
}

void EditorViewportInputManager::_dispatch_to_camera(tc_key_event* ev) {
    _dispatch_camera_components(_viewport, [ev](tc_component* c) {
        tc_component_on_key(c, ev);
    });
}

// ============================================================================
// Dispatch helpers - Editor components (active_in_editor=true)
// ============================================================================

void EditorViewportInputManager::_dispatch_to_editor_components(tc_mouse_button_event* ev) {
    tc_scene_handle scene = tc_viewport_get_scene(_viewport);
    if (!tc_scene_handle_valid(scene)) return;
    tc_scene_foreach_input_handler(scene,
        [](tc_component* c, void* ud) -> bool {
            tc_component_on_mouse_button(c, static_cast<tc_mouse_button_event*>(ud));
            return true;
        },
        ev,
        TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED | TC_DRAWABLE_FILTER_ACTIVE_IN_EDITOR);
}

void EditorViewportInputManager::_dispatch_to_editor_components(tc_mouse_move_event* ev) {
    tc_scene_handle scene = tc_viewport_get_scene(_viewport);
    if (!tc_scene_handle_valid(scene)) return;
    tc_scene_foreach_input_handler(scene,
        [](tc_component* c, void* ud) -> bool {
            tc_component_on_mouse_move(c, static_cast<tc_mouse_move_event*>(ud));
            return true;
        },
        ev,
        TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED | TC_DRAWABLE_FILTER_ACTIVE_IN_EDITOR);
}

void EditorViewportInputManager::_dispatch_to_editor_components(tc_scroll_event* ev) {
    tc_scene_handle scene = tc_viewport_get_scene(_viewport);
    if (!tc_scene_handle_valid(scene)) return;
    tc_scene_foreach_input_handler(scene,
        [](tc_component* c, void* ud) -> bool {
            tc_component_on_scroll(c, static_cast<tc_scroll_event*>(ud));
            return true;
        },
        ev,
        TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED | TC_DRAWABLE_FILTER_ACTIVE_IN_EDITOR);
}

void EditorViewportInputManager::_dispatch_to_editor_components(tc_key_event* ev) {
    tc_scene_handle scene = tc_viewport_get_scene(_viewport);
    if (!tc_scene_handle_valid(scene)) return;
    tc_scene_foreach_input_handler(scene,
        [](tc_component* c, void* ud) -> bool {
            tc_component_on_key(c, static_cast<tc_key_event*>(ud));
            return true;
        },
        ev,
        TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED | TC_DRAWABLE_FILTER_ACTIVE_IN_EDITOR);
}

// ============================================================================
// Dispatch helpers - Internal entities
// ============================================================================

void EditorViewportInputManager::_dispatch_to_internal_entities(tc_mouse_button_event* ev) {
    tc_entity_handle ent = tc_viewport_get_internal_entities(_viewport);
    if (!tc_entity_handle_valid(ent)) return;
    tc_entity_foreach_input_handler_subtree(ent,
        [](tc_component* c, void* ud) -> bool {
            tc_component_on_mouse_button(c, static_cast<tc_mouse_button_event*>(ud));
            return true;
        }, ev);
}

void EditorViewportInputManager::_dispatch_to_internal_entities(tc_mouse_move_event* ev) {
    tc_entity_handle ent = tc_viewport_get_internal_entities(_viewport);
    if (!tc_entity_handle_valid(ent)) return;
    tc_entity_foreach_input_handler_subtree(ent,
        [](tc_component* c, void* ud) -> bool {
            tc_component_on_mouse_move(c, static_cast<tc_mouse_move_event*>(ud));
            return true;
        }, ev);
}

void EditorViewportInputManager::_dispatch_to_internal_entities(tc_scroll_event* ev) {
    tc_entity_handle ent = tc_viewport_get_internal_entities(_viewport);
    if (!tc_entity_handle_valid(ent)) return;
    tc_entity_foreach_input_handler_subtree(ent,
        [](tc_component* c, void* ud) -> bool {
            tc_component_on_scroll(c, static_cast<tc_scroll_event*>(ud));
            return true;
        }, ev);
}

void EditorViewportInputManager::_dispatch_to_internal_entities(tc_key_event* ev) {
    tc_entity_handle ent = tc_viewport_get_internal_entities(_viewport);
    if (!tc_entity_handle_valid(ent)) return;
    tc_entity_foreach_input_handler_subtree(ent,
        [](tc_component* c, void* ud) -> bool {
            tc_component_on_key(c, static_cast<tc_key_event*>(ud));
            return true;
        }, ev);
}

} // namespace termin
