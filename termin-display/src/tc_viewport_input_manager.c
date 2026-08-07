// tc_viewport_input_manager.c - Per-viewport input manager implementation
#include "render/tc_viewport_input_manager.h"
#include "core/tc_component.h"
#include "core/tc_entity_pool.h"
#include "core/tc_input_component.h"
#include "core/tc_input_entity_pool.h"
#include "core/tc_input_scene.h"
#include "core/tc_scene.h"
#include "render/tc_viewport.h"
#include "tc_input_event.h"
#include <tcbase/tc_log.h>

#include <stdlib.h>

// ============================================================================
// Dispatch Callbacks
// ============================================================================

static bool dispatch_pointer_cb(tc_component* c, void* user_data) {
    tc_pointer_event* event = (tc_pointer_event*)user_data;
    if (tc_component_accepts_input_source(c, event->source)) {
        tc_component_on_pointer(c, event);
    }
    return !event->handled;
}

static bool dispatch_mouse_button_cb(tc_component* c, void* user_data) {
    tc_mouse_button_event* event = (tc_mouse_button_event*)user_data;
    if (tc_component_accepts_input_source(c, event->source)) {
        tc_component_on_mouse_button(c, event);
    }
    return !event->handled;
}

static bool dispatch_mouse_move_cb(tc_component* c, void* user_data) {
    tc_mouse_move_event* event = (tc_mouse_move_event*)user_data;
    if (tc_component_accepts_input_source(c, event->source)) {
        tc_component_on_mouse_move(c, event);
    }
    return !event->handled;
}

static bool dispatch_scroll_cb(tc_component* c, void* user_data) {
    tc_scroll_event* event = (tc_scroll_event*)user_data;
    if (tc_component_accepts_input_source(c, event->source)) {
        tc_component_on_scroll(c, event);
    }
    return !event->handled;
}

static bool dispatch_key_cb(tc_component* c, void* user_data) {
    tc_key_event* event = (tc_key_event*)user_data;
    if (tc_component_accepts_input_source(c, event->source)) {
        tc_component_on_key(c, event);
    }
    return !event->handled;
}

static bool dispatch_text_cb(tc_component* c, void* user_data) {
    tc_text_event* event = (tc_text_event*)user_data;
    if (tc_component_accepts_input_source(c, event->source)) {
        tc_component_on_text(c, event);
    }
    return !event->handled;
}

static bool dispatch_focus_lost_cb(tc_component* c, void* user_data) {
    tc_input_focus_event* event = (tc_input_focus_event*)user_data;
    if (tc_component_accepts_input_source(c, event->source)) {
        tc_component_on_focus_lost(c, event);
    }
    return true;
}

// ============================================================================
// Internal Entities Dispatch
// ============================================================================

static void dispatch_to_internal_entities(tc_viewport_handle viewport, tc_component_iter_fn callback, void* user_data) {
    if (!tc_viewport_has_internal_entities(viewport))
        return;

    tc_entity_handle ent = tc_viewport_get_internal_entities(viewport);
    tc_entity_pool* pool = tc_entity_pool_registry_get(ent.pool);

    if (pool && tc_entity_id_valid(ent.id)) {
        tc_entity_pool_foreach_input_handler_subtree(pool, ent.id, callback, user_data);
    }
}

// ============================================================================
// Scene Dispatch
// ============================================================================

static void dispatch_to_scene(tc_viewport_handle viewport, tc_component_iter_fn callback, void* user_data) {
    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    if (!tc_scene_handle_valid(scene))
        return;

    tc_scene_foreach_input_handler(
        scene, callback, user_data, TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);
}

// ============================================================================
// Helpers
// ============================================================================

static inline tc_viewport_input_manager* vim_from(tc_input_manager* self) {
    return self ? (tc_viewport_input_manager*)self->userdata : NULL;
}

static const tc_input_platform_services* vim_platform_services(tc_viewport_input_manager* m) {
    return &m->base.platform_services;
}

typedef struct tc_viewport_pointer_state {
    uint64_t pointer_id;
    int device;
    double x;
    double y;
    struct tc_viewport_pointer_state* next;
} tc_viewport_pointer_state;

static tc_viewport_pointer_state*
vim_find_pointer(tc_viewport_input_manager* m, uint64_t pointer_id, int device, tc_viewport_pointer_state** previous) {
    tc_viewport_pointer_state* prev = NULL;
    tc_viewport_pointer_state* current = (tc_viewport_pointer_state*)m->pointer_states;
    while (current) {
        if (current->pointer_id == pointer_id && current->device == device) {
            if (previous)
                *previous = prev;
            return current;
        }
        prev = current;
        current = current->next;
    }
    if (previous)
        *previous = NULL;
    return NULL;
}

static tc_viewport_pointer_state* vim_ensure_pointer(tc_viewport_input_manager* m, uint64_t pointer_id, int device) {
    tc_viewport_pointer_state* state = vim_find_pointer(m, pointer_id, device, NULL);
    if (state)
        return state;
    state = (tc_viewport_pointer_state*)calloc(1, sizeof(tc_viewport_pointer_state));
    if (!state) {
        tc_log(TC_LOG_ERROR, "[tc_viewport_input_manager] pointer state allocation failed");
        return NULL;
    }
    state->pointer_id = pointer_id;
    state->device = device;
    state->next = (tc_viewport_pointer_state*)m->pointer_states;
    m->pointer_states = state;
    return state;
}

static void vim_remove_pointer(tc_viewport_input_manager* m, uint64_t pointer_id, int device) {
    tc_viewport_pointer_state* previous = NULL;
    tc_viewport_pointer_state* state = vim_find_pointer(m, pointer_id, device, &previous);
    if (!state)
        return;
    if (previous) {
        previous->next = state->next;
    } else {
        m->pointer_states = state->next;
    }
    free(state);
}

// ============================================================================
// VTable Callbacks
// ============================================================================

static void
vim_on_pointer(tc_input_manager* self, uint64_t pointer_id, int device, int phase, double x, double y, float pressure) {
    tc_viewport_input_manager* m = vim_from(self);
    if (!m || !tc_viewport_alive(m->viewport))
        return;

    tc_viewport_pointer_state* state = vim_find_pointer(m, pointer_id, device, NULL);
    double dx = 0.0;
    double dy = 0.0;
    if (state && phase != TC_POINTER_DOWN) {
        dx = x - state->x;
        dy = y - state->y;
    }
    if (!state && phase != TC_POINTER_UP && phase != TC_POINTER_CANCEL) {
        state = vim_ensure_pointer(m, pointer_id, device);
    }
    if (state) {
        state->x = x;
        state->y = y;
    }

    tc_pointer_event event;
    tc_pointer_event_init_source(
        &event, m->viewport, pointer_id, device, phase, x, y, dx, dy, pressure, TC_INPUT_SOURCE_RUNTIME);
    event.platform_services = vim_platform_services(m);

    dispatch_to_internal_entities(m->viewport, dispatch_pointer_cb, &event);
    if (!event.handled) {
        dispatch_to_scene(m->viewport, dispatch_pointer_cb, &event);
    }

    if (phase == TC_POINTER_UP || phase == TC_POINTER_CANCEL) {
        vim_remove_pointer(m, pointer_id, device);
    }
}

static void vim_on_mouse_button(tc_input_manager* self, int button, int action, int mods, uint32_t click_count) {
    tc_viewport_input_manager* m = vim_from(self);
    if (!m || !tc_viewport_alive(m->viewport))
        return;

    tc_mouse_button_event event;
    const tc_mouse_button_event_init_info info = {
        m->viewport, m->last_cursor_x, m->last_cursor_y, button, action, mods, click_count, TC_INPUT_SOURCE_RUNTIME};
    tc_mouse_button_event_init_source(&event, &info);
    event.platform_services = vim_platform_services(m);

    dispatch_to_internal_entities(m->viewport, dispatch_mouse_button_cb, &event);
    if (event.handled)
        return;
    dispatch_to_scene(m->viewport, dispatch_mouse_button_cb, &event);
}

static void vim_on_mouse_move(tc_input_manager* self, double x, double y) {
    tc_viewport_input_manager* m = vim_from(self);
    if (!m || !tc_viewport_alive(m->viewport))
        return;

    double dx = 0.0, dy = 0.0;
    if (m->has_cursor) {
        dx = x - m->last_cursor_x;
        dy = y - m->last_cursor_y;
    }
    m->last_cursor_x = x;
    m->last_cursor_y = y;
    m->has_cursor = true;

    tc_mouse_move_event event;
    tc_mouse_move_event_init_source(&event, m->viewport, x, y, dx, dy, TC_INPUT_SOURCE_RUNTIME);
    event.platform_services = vim_platform_services(m);

    dispatch_to_internal_entities(m->viewport, dispatch_mouse_move_cb, &event);
    if (event.handled)
        return;
    dispatch_to_scene(m->viewport, dispatch_mouse_move_cb, &event);
}

static void vim_on_scroll(tc_input_manager* self, double xoffset, double yoffset, int mods) {
    tc_viewport_input_manager* m = vim_from(self);
    if (!m || !tc_viewport_alive(m->viewport))
        return;

    tc_scroll_event event;
    const tc_scroll_event_init_info info = {
        m->viewport, m->last_cursor_x, m->last_cursor_y, xoffset, yoffset, mods, TC_INPUT_SOURCE_RUNTIME};
    tc_scroll_event_init_source(&event, &info);
    event.platform_services = vim_platform_services(m);

    dispatch_to_internal_entities(m->viewport, dispatch_scroll_cb, &event);
    if (event.handled)
        return;
    dispatch_to_scene(m->viewport, dispatch_scroll_cb, &event);
}

static void vim_on_key(tc_input_manager* self, int key, int scancode, int action, int mods) {
    tc_viewport_input_manager* m = vim_from(self);
    if (!m || !tc_viewport_alive(m->viewport))
        return;

    tc_key_event event;
    tc_key_event_init_source(&event, m->viewport, key, scancode, action, mods, TC_INPUT_SOURCE_RUNTIME);
    event.platform_services = vim_platform_services(m);

    dispatch_to_internal_entities(m->viewport, dispatch_key_cb, &event);
    if (event.handled)
        return;
    dispatch_to_scene(m->viewport, dispatch_key_cb, &event);
}

static void vim_on_char(tc_input_manager* self, uint32_t codepoint) {
    char text[5] = {0};
    if (codepoint <= 0x7f) {
        text[0] = (char)codepoint;
    } else if (codepoint <= 0x7ff) {
        text[0] = (char)(0xc0 | (codepoint >> 6));
        text[1] = (char)(0x80 | (codepoint & 0x3f));
    } else if (codepoint <= 0xffff) {
        if (codepoint >= 0xd800 && codepoint <= 0xdfff) {
            tc_log(TC_LOG_WARN, "[tc_viewport_input_manager] ignored UTF-16 surrogate codepoint");
            return;
        }
        text[0] = (char)(0xe0 | (codepoint >> 12));
        text[1] = (char)(0x80 | ((codepoint >> 6) & 0x3f));
        text[2] = (char)(0x80 | (codepoint & 0x3f));
    } else if (codepoint <= 0x10ffff) {
        text[0] = (char)(0xf0 | (codepoint >> 18));
        text[1] = (char)(0x80 | ((codepoint >> 12) & 0x3f));
        text[2] = (char)(0x80 | ((codepoint >> 6) & 0x3f));
        text[3] = (char)(0x80 | (codepoint & 0x3f));
    } else {
        tc_log(TC_LOG_WARN, "[tc_viewport_input_manager] ignored invalid Unicode codepoint");
        return;
    }
    tc_input_manager_on_text(self, text);
}

static void vim_on_text(tc_input_manager* self, const char* text_utf8) {
    tc_viewport_input_manager* m = vim_from(self);
    if (!m || !tc_viewport_alive(m->viewport) || !text_utf8 || !text_utf8[0])
        return;

    tc_text_event event;
    tc_text_event_init_source(&event, m->viewport, text_utf8, TC_INPUT_SOURCE_RUNTIME);
    event.platform_services = vim_platform_services(m);
    dispatch_to_internal_entities(m->viewport, dispatch_text_cb, &event);
    if (!event.handled) {
        dispatch_to_scene(m->viewport, dispatch_text_cb, &event);
    }
}

static void vim_on_focus_lost(tc_input_manager* self) {
    tc_viewport_input_manager* m = vim_from(self);
    if (!m || !tc_viewport_alive(m->viewport))
        return;

    tc_viewport_pointer_state* state = (tc_viewport_pointer_state*)m->pointer_states;
    while (state) {
        tc_viewport_pointer_state* next = state->next;
        vim_on_pointer(self, state->pointer_id, state->device, TC_POINTER_CANCEL, state->x, state->y, 0.0f);
        state = next;
    }

    tc_input_focus_event event;
    tc_input_focus_event_init_source(&event, m->viewport, TC_INPUT_SOURCE_RUNTIME);
    event.platform_services = vim_platform_services(m);
    dispatch_to_internal_entities(m->viewport, dispatch_focus_lost_cb, &event);
    dispatch_to_scene(m->viewport, dispatch_focus_lost_cb, &event);
    m->has_cursor = false;
}

static void vim_destroy(tc_input_manager* self) {
    (void)self;
}

// ============================================================================
// VTable
// ============================================================================

static const tc_input_manager_vtable g_vim_vtable = {
    .on_pointer = vim_on_pointer,
    .on_mouse_button = vim_on_mouse_button,
    .on_mouse_move = vim_on_mouse_move,
    .on_scroll = vim_on_scroll,
    .on_key = vim_on_key,
    .on_char = vim_on_char,
    .destroy = vim_destroy,
    .on_text = vim_on_text,
    .on_focus_lost = vim_on_focus_lost,
};

// ============================================================================
// Lifecycle
// ============================================================================

tc_viewport_input_manager* tc_viewport_input_manager_new(tc_viewport_handle viewport) {
    tc_viewport_input_manager* m = (tc_viewport_input_manager*)calloc(1, sizeof(tc_viewport_input_manager));
    if (!m)
        return NULL;

    tc_input_manager_init(&m->base, &g_vim_vtable);
    m->base.userdata = m;
    m->viewport = viewport;
    m->last_cursor_x = 0.0;
    m->last_cursor_y = 0.0;
    m->has_cursor = false;
    m->pointer_states = NULL;

    // Auto-attach to viewport
    tc_viewport_set_input_manager(viewport, &m->base);

    return m;
}

void tc_viewport_input_manager_free(tc_viewport_input_manager* m) {
    if (!m)
        return;

    vim_on_focus_lost(&m->base);

    // Detach from viewport
    if (tc_viewport_alive(m->viewport)) {
        if (tc_viewport_get_input_manager(m->viewport) == &m->base) {
            tc_viewport_set_input_manager(m->viewport, NULL);
        }
    }

    tc_viewport_pointer_state* state = (tc_viewport_pointer_state*)m->pointer_states;
    while (state) {
        tc_viewport_pointer_state* next = state->next;
        free(state);
        state = next;
    }
    free(m);
}
