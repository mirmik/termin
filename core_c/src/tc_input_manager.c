// tc_input_manager.c - Input manager implementation
#include "render/tc_input_manager.h"
#include "tc_log.h"
#include <stdlib.h>
#include <string.h>

// ============================================================================
// External Callbacks
// ============================================================================

static tc_external_input_manager_callbacks g_external_callbacks = {0};

void tc_input_manager_set_external_callbacks(
    const tc_external_input_manager_callbacks* callbacks
) {
    if (callbacks) {
        g_external_callbacks = *callbacks;
    } else {
        memset(&g_external_callbacks, 0, sizeof(g_external_callbacks));
    }
}

// ============================================================================
// External Input Manager VTable Implementation
// ============================================================================

static void external_on_mouse_button(tc_input_manager* m, int button, int action, int mods) {
    if (m->body && g_external_callbacks.on_mouse_button) {
        g_external_callbacks.on_mouse_button(m->body, button, action, mods);
    }
}

static void external_on_mouse_move(tc_input_manager* m, double x, double y) {
    if (m->body && g_external_callbacks.on_mouse_move) {
        g_external_callbacks.on_mouse_move(m->body, x, y);
    }
}

static void external_on_scroll(tc_input_manager* m, double x, double y, int mods) {
    if (m->body && g_external_callbacks.on_scroll) {
        g_external_callbacks.on_scroll(m->body, x, y, mods);
    }
}

static void external_on_key(tc_input_manager* m, int key, int scancode, int action, int mods) {
    if (m->body && g_external_callbacks.on_key) {
        g_external_callbacks.on_key(m->body, key, scancode, action, mods);
    }
}

static void external_on_char(tc_input_manager* m, uint32_t codepoint) {
    if (m->body && g_external_callbacks.on_char) {
        g_external_callbacks.on_char(m->body, codepoint);
    }
}

static void external_destroy(tc_input_manager* m) {
    if (m->body && g_external_callbacks.destroy) {
        g_external_callbacks.destroy(m->body);
    }
}

static const tc_input_manager_vtable g_external_vtable = {
    .on_mouse_button = external_on_mouse_button,
    .on_mouse_move = external_on_mouse_move,
    .on_scroll = external_on_scroll,
    .on_key = external_on_key,
    .on_char = external_on_char,
    .destroy = external_destroy,
};

// ============================================================================
// External Input Manager Lifecycle
// ============================================================================

tc_input_manager* tc_input_manager_new_external(void* body) {
    if (!body) {
        tc_log(TC_LOG_ERROR, "[tc_input_manager_new_external] body is NULL");
        return NULL;
    }

    tc_input_manager* m = (tc_input_manager*)calloc(1, sizeof(tc_input_manager));
    if (!m) {
        tc_log(TC_LOG_ERROR, "[tc_input_manager_new_external] allocation failed");
        return NULL;
    }

    tc_input_manager_init(m, &g_external_vtable);
    m->body = body;

    if (g_external_callbacks.incref) {
        g_external_callbacks.incref(body);
    }

    return m;
}

void tc_input_manager_free_external(tc_input_manager* m) {
    if (!m) return;

    if (m->body && g_external_callbacks.decref) {
        g_external_callbacks.decref(m->body);
    }

    free(m);
}
