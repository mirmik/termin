// tc_simple_input_manager.c - Simple input manager implementation

#include "render/tc_simple_input_manager.h"
#include "render/tc_render_surface.h"
#include "render/tc_viewport.h"
#include "tc_scene.h"
#include "tc_component.h"
#include "tc_entity_pool.h"
#include "tc_input_event.h"
#include "tc_log.h"

#include <stdlib.h>
#include <string.h>

// ============================================================================
// Dispatch Callbacks
// ============================================================================

static bool dispatch_mouse_button_cb(tc_component* c, void* user_data) {
    tc_mouse_button_event* ev = (tc_mouse_button_event*)user_data;
    tc_component_on_mouse_button(c, ev);
    return true;
}

static bool dispatch_mouse_move_cb(tc_component* c, void* user_data) {
    tc_mouse_move_event* ev = (tc_mouse_move_event*)user_data;
    tc_component_on_mouse_move(c, ev);
    return true;
}

static bool dispatch_scroll_cb(tc_component* c, void* user_data) {
    tc_scroll_event* ev = (tc_scroll_event*)user_data;
    tc_component_on_scroll(c, ev);
    return true;
}

static bool dispatch_key_cb(tc_component* c, void* user_data) {
    tc_key_event* ev = (tc_key_event*)user_data;
    tc_component_on_key(c, ev);
    return true;
}

// ============================================================================
// Internal Entities Dispatch Helper
// ============================================================================

// Dispatch to input handlers in viewport's internal_entities subtree
static void dispatch_to_internal_entities(
    tc_viewport* viewport,
    tc_component_iter_fn callback,
    void* user_data
) {
    if (!viewport) return;
    if (!tc_viewport_has_internal_entities(viewport)) return;

    tc_entity_pool* pool = tc_viewport_get_internal_entities_pool(viewport);
    tc_entity_id root_id = tc_viewport_get_internal_entities_id(viewport);

    if (pool && tc_entity_id_valid(root_id)) {
        tc_entity_pool_foreach_input_handler_subtree(pool, root_id, callback, user_data);
    }
}

// ============================================================================
// Event Handlers
// ============================================================================

static void simple_on_mouse_button(tc_input_manager* m, int button, int action, int mods) {
    tc_simple_input_manager* sim = (tc_simple_input_manager*)m;
    if (!sim || !sim->display) return;

    // Get cursor position
    double x = sim->last_cursor_x;
    double y = sim->last_cursor_y;
    if (sim->display->surface) {
        tc_render_surface_get_cursor_pos(sim->display->surface, &x, &y);
    }

    // Find viewport under cursor
    tc_viewport* viewport = tc_display_viewport_at_screen(sim->display, (float)x, (float)y);

    // Track active viewport for drag operations
    if (action == TC_INPUT_PRESS) {
        sim->active_viewport = viewport;
    }
    if (action == TC_INPUT_RELEASE) {
        sim->has_cursor = false;
        if (viewport == NULL) {
            viewport = sim->active_viewport;
        }
        sim->active_viewport = NULL;
    }

    // Dispatch to scene and internal_entities
    if (viewport != NULL) {
        tc_mouse_button_event event;
        event.viewport = viewport;
        event.x = x;
        event.y = y;
        event.button = button;
        event.action = action;
        event.mods = mods;

        // Dispatch to internal_entities first (camera controllers, etc.)
        dispatch_to_internal_entities(viewport, dispatch_mouse_button_cb, &event);

        // Then dispatch to scene
        tc_scene* scene = tc_viewport_get_scene(viewport);
        if (scene != NULL) {
            tc_scene_foreach_input_handler(
                scene,
                dispatch_mouse_button_cb,
                &event,
                TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED
            );
        }
    }
}

static void simple_on_mouse_move(tc_input_manager* m, double x, double y) {
    tc_simple_input_manager* sim = (tc_simple_input_manager*)m;
    if (!sim) return;

    // Calculate delta
    double dx = 0.0, dy = 0.0;
    if (sim->has_cursor) {
        dx = x - sim->last_cursor_x;
        dy = y - sim->last_cursor_y;
    }
    sim->last_cursor_x = x;
    sim->last_cursor_y = y;
    sim->has_cursor = true;

    // Find viewport (prefer active for drag)
    tc_viewport* viewport = sim->active_viewport;
    if (viewport == NULL && sim->display) {
        viewport = tc_display_viewport_at_screen(sim->display, (float)x, (float)y);
    }

    // Dispatch to scene and internal_entities
    if (viewport != NULL) {
        tc_mouse_move_event event;
        event.viewport = viewport;
        event.x = x;
        event.y = y;
        event.dx = dx;
        event.dy = dy;

        // Dispatch to internal_entities first
        dispatch_to_internal_entities(viewport, dispatch_mouse_move_cb, &event);

        // Then dispatch to scene
        tc_scene* scene = tc_viewport_get_scene(viewport);
        if (scene != NULL) {
            tc_scene_foreach_input_handler(
                scene,
                dispatch_mouse_move_cb,
                &event,
                TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED
            );
        }
    }
}

static void simple_on_scroll(tc_input_manager* m, double xoffset, double yoffset, int mods) {
    tc_simple_input_manager* sim = (tc_simple_input_manager*)m;
    if (!sim) return;

    double x = sim->last_cursor_x;
    double y = sim->last_cursor_y;

    // Find viewport under cursor
    tc_viewport* viewport = NULL;
    if (sim->display) {
        viewport = tc_display_viewport_at_screen(sim->display, (float)x, (float)y);
    }
    if (viewport == NULL) {
        viewport = sim->active_viewport;
    }

    // Dispatch to scene and internal_entities
    if (viewport != NULL) {
        tc_scroll_event event;
        event.viewport = viewport;
        event.x = x;
        event.y = y;
        event.xoffset = xoffset;
        event.yoffset = yoffset;
        event.mods = mods;

        // Dispatch to internal_entities first
        dispatch_to_internal_entities(viewport, dispatch_scroll_cb, &event);

        // Then dispatch to scene
        tc_scene* scene = tc_viewport_get_scene(viewport);
        if (scene != NULL) {
            tc_scene_foreach_input_handler(
                scene,
                dispatch_scroll_cb,
                &event,
                TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED
            );
        }
    }
}

// ESC key code (GLFW_KEY_ESCAPE)
#define TC_KEY_ESCAPE 256

static void simple_on_key(tc_input_manager* m, int key, int scancode, int action, int mods) {
    tc_simple_input_manager* sim = (tc_simple_input_manager*)m;
    if (!sim) return;

    // ESC closes window
    if (key == TC_KEY_ESCAPE && action == TC_INPUT_PRESS) {
        if (sim->display && sim->display->surface) {
            tc_render_surface_set_should_close(sim->display->surface, true);
        }
    }

    // Find viewport
    tc_viewport* viewport = sim->active_viewport;
    if (viewport == NULL && sim->display) {
        viewport = tc_display_get_first_viewport(sim->display);
    }

    // Dispatch to scene and internal_entities
    if (viewport != NULL) {
        tc_key_event event;
        event.viewport = viewport;
        event.key = key;
        event.scancode = scancode;
        event.action = action;
        event.mods = mods;

        // Dispatch to internal_entities first
        dispatch_to_internal_entities(viewport, dispatch_key_cb, &event);

        // Then dispatch to scene
        tc_scene* scene = tc_viewport_get_scene(viewport);
        if (scene != NULL) {
            tc_scene_foreach_input_handler(
                scene,
                dispatch_key_cb,
                &event,
                TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED
            );
        }
    }
}

static void simple_on_char(tc_input_manager* m, uint32_t codepoint) {
    // Not used in simple manager
    (void)m;
    (void)codepoint;
}

static void simple_destroy(tc_input_manager* m) {
    // Called when input manager is destroyed
    // We don't free here - tc_simple_input_manager_free handles it
    (void)m;
}

// ============================================================================
// Static VTable
// ============================================================================

static const tc_input_manager_vtable simple_vtable = {
    simple_on_mouse_button,
    simple_on_mouse_move,
    simple_on_scroll,
    simple_on_key,
    simple_on_char,
    simple_destroy
};

// ============================================================================
// Lifecycle
// ============================================================================

tc_simple_input_manager* tc_simple_input_manager_new(tc_display* display) {
    tc_simple_input_manager* m = (tc_simple_input_manager*)calloc(1, sizeof(tc_simple_input_manager));
    if (!m) return NULL;

    // Initialize base input manager
    tc_input_manager_init(&m->base, &simple_vtable);
    m->base.userdata = m;

    // Store display
    m->display = display;
    m->active_viewport = NULL;
    m->last_cursor_x = 0.0;
    m->last_cursor_y = 0.0;
    m->has_cursor = false;

    // Auto-attach to display's surface
    if (display && display->surface) {
        tc_render_surface_set_input_manager(display->surface, &m->base);
    }

    return m;
}

void tc_simple_input_manager_free(tc_simple_input_manager* m) {
    if (!m) return;

    // Detach from surface
    if (m->display && m->display->surface) {
        if (m->display->surface->input_manager == &m->base) {
            m->display->surface->input_manager = NULL;
        }
    }

    free(m);
}

tc_input_manager* tc_simple_input_manager_base(tc_simple_input_manager* m) {
    return m ? &m->base : NULL;
}
