// tc_viewport_input_manager.c - Per-viewport input manager implementation
#include "render/tc_viewport_input_manager.h"
#include "render/tc_viewport.h"
#include "core/tc_scene.h"
#include "core/tc_component.h"
#include "core/tc_entity_pool.h"
#include "tc_input_event.h"
#include "tc_log.h"

#include <stdlib.h>

// ============================================================================
// Dispatch Callbacks
// ============================================================================

static bool dispatch_mouse_button_cb(tc_component* c, void* user_data) {
    tc_component_on_mouse_button(c, (tc_mouse_button_event*)user_data);
    return true;
}

static bool dispatch_mouse_move_cb(tc_component* c, void* user_data) {
    tc_component_on_mouse_move(c, (tc_mouse_move_event*)user_data);
    return true;
}

static bool dispatch_scroll_cb(tc_component* c, void* user_data) {
    tc_component_on_scroll(c, (tc_scroll_event*)user_data);
    return true;
}

static bool dispatch_key_cb(tc_component* c, void* user_data) {
    tc_component_on_key(c, (tc_key_event*)user_data);
    return true;
}

// ============================================================================
// Internal Entities Dispatch
// ============================================================================

static void dispatch_to_internal_entities(
    tc_viewport_handle viewport,
    tc_component_iter_fn callback,
    void* user_data
) {
    if (!tc_viewport_has_internal_entities(viewport)) return;

    tc_entity_handle ent = tc_viewport_get_internal_entities(viewport);
    tc_entity_pool* pool = tc_entity_pool_registry_get(ent.pool);

    if (pool && tc_entity_id_valid(ent.id)) {
        tc_entity_pool_foreach_input_handler_subtree(pool, ent.id, callback, user_data);
    }
}

// ============================================================================
// Scene Dispatch
// ============================================================================

static void dispatch_to_scene(
    tc_viewport_handle viewport,
    tc_component_iter_fn callback,
    void* user_data
) {
    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    if (!tc_scene_handle_valid(scene)) return;

    tc_scene_foreach_input_handler(
        scene,
        callback,
        user_data,
        TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED
    );
}

// ============================================================================
// Helpers
// ============================================================================

static inline tc_viewport_input_manager* vim_from(tc_input_manager* self) {
    return self ? (tc_viewport_input_manager*)self->userdata : NULL;
}

// ============================================================================
// VTable Callbacks
// ============================================================================

static void vim_on_mouse_button(tc_input_manager* self, int button, int action, int mods) {
    tc_viewport_input_manager* m = vim_from(self);
    if (!m || !tc_viewport_alive(m->viewport)) return;

    tc_mouse_button_event event;
    tc_mouse_button_event_init(&event, m->viewport,
        m->last_cursor_x, m->last_cursor_y, button, action, mods);

    dispatch_to_internal_entities(m->viewport, dispatch_mouse_button_cb, &event);
    dispatch_to_scene(m->viewport, dispatch_mouse_button_cb, &event);
}

static void vim_on_mouse_move(tc_input_manager* self, double x, double y) {
    tc_viewport_input_manager* m = vim_from(self);
    if (!m || !tc_viewport_alive(m->viewport)) return;

    double dx = 0.0, dy = 0.0;
    if (m->has_cursor) {
        dx = x - m->last_cursor_x;
        dy = y - m->last_cursor_y;
    }
    m->last_cursor_x = x;
    m->last_cursor_y = y;
    m->has_cursor = true;

    tc_mouse_move_event event;
    tc_mouse_move_event_init(&event, m->viewport, x, y, dx, dy);

    dispatch_to_internal_entities(m->viewport, dispatch_mouse_move_cb, &event);
    dispatch_to_scene(m->viewport, dispatch_mouse_move_cb, &event);
}

static void vim_on_scroll(tc_input_manager* self, double xoffset, double yoffset, int mods) {
    tc_viewport_input_manager* m = vim_from(self);
    if (!m || !tc_viewport_alive(m->viewport)) return;

    tc_scroll_event event;
    tc_scroll_event_init(&event, m->viewport,
        m->last_cursor_x, m->last_cursor_y, xoffset, yoffset, mods);

    dispatch_to_internal_entities(m->viewport, dispatch_scroll_cb, &event);
    dispatch_to_scene(m->viewport, dispatch_scroll_cb, &event);
}

static void vim_on_key(tc_input_manager* self, int key, int scancode, int action, int mods) {
    tc_viewport_input_manager* m = vim_from(self);
    if (!m || !tc_viewport_alive(m->viewport)) return;

    tc_key_event event;
    tc_key_event_init(&event, m->viewport, key, scancode, action, mods);

    dispatch_to_internal_entities(m->viewport, dispatch_key_cb, &event);
    dispatch_to_scene(m->viewport, dispatch_key_cb, &event);
}

static void vim_on_char(tc_input_manager* self, uint32_t codepoint) {
    (void)self;
    (void)codepoint;
}

static void vim_destroy(tc_input_manager* self) {
    (void)self;
}

// ============================================================================
// VTable
// ============================================================================

static const tc_input_manager_vtable g_vim_vtable = {
    vim_on_mouse_button,
    vim_on_mouse_move,
    vim_on_scroll,
    vim_on_key,
    vim_on_char,
    vim_destroy
};

// ============================================================================
// Lifecycle
// ============================================================================

tc_viewport_input_manager* tc_viewport_input_manager_new(tc_viewport_handle viewport) {
    tc_viewport_input_manager* m = (tc_viewport_input_manager*)calloc(1, sizeof(tc_viewport_input_manager));
    if (!m) return NULL;

    tc_input_manager_init(&m->base, &g_vim_vtable);
    m->base.userdata = m;
    m->viewport = viewport;
    m->last_cursor_x = 0.0;
    m->last_cursor_y = 0.0;
    m->has_cursor = false;

    // Auto-attach to viewport
    tc_viewport_set_input_manager(viewport, &m->base);

    return m;
}

void tc_viewport_input_manager_free(tc_viewport_input_manager* m) {
    if (!m) return;

    // Detach from viewport
    if (tc_viewport_alive(m->viewport)) {
        if (tc_viewport_get_input_manager(m->viewport) == &m->base) {
            tc_viewport_set_input_manager(m->viewport, NULL);
        }
    }

    free(m);
}
