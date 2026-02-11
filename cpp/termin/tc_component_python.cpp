// tc_component_python.cpp - External component implementation
// Provides component functionality for external scripting languages (e.g. Python)
#include "tc_component_python.h"
#include <stdlib.h>
#include <string.h>

// Global Python callbacks (set once at initialization)
static tc_python_callbacks g_py_callbacks = {0};
static tc_python_drawable_callbacks g_py_drawable_callbacks = {0};
static tc_python_input_callbacks g_py_input_callbacks = {0};

// ============================================================================
// Python vtable callbacks - these dispatch to global Python callbacks
// ============================================================================

static void py_vtable_start(tc_component* c) {
    if (g_py_callbacks.start && c->body) {
        g_py_callbacks.start(c->body);
    }
}

static void py_vtable_update(tc_component* c, float dt) {
    if (g_py_callbacks.update && c->body) {
        g_py_callbacks.update(c->body, dt);
    }
}

static void py_vtable_fixed_update(tc_component* c, float dt) {
    if (g_py_callbacks.fixed_update && c->body) {
        g_py_callbacks.fixed_update(c->body, dt);
    }
}

static void py_vtable_before_render(tc_component* c) {
    if (g_py_callbacks.before_render && c->body) {
        g_py_callbacks.before_render(c->body);
    }
}

static void py_vtable_on_destroy(tc_component* c) {
    if (g_py_callbacks.on_destroy && c->body) {
        g_py_callbacks.on_destroy(c->body);
    }
}

static void py_vtable_on_added_to_entity(tc_component* c) {
    if (g_py_callbacks.on_added_to_entity && c->body) {
        g_py_callbacks.on_added_to_entity(c->body);
    }
}

static void py_vtable_on_removed_from_entity(tc_component* c) {
    if (g_py_callbacks.on_removed_from_entity && c->body) {
        g_py_callbacks.on_removed_from_entity(c->body);
    }
}

static void py_vtable_on_added(tc_component* c) {
    if (g_py_callbacks.on_added && c->body) {
        g_py_callbacks.on_added(c->body);
    }
}

static void py_vtable_on_removed(tc_component* c) {
    if (g_py_callbacks.on_removed && c->body) {
        g_py_callbacks.on_removed(c->body);
    }
}

static void py_vtable_on_scene_inactive(tc_component* c) {
    if (g_py_callbacks.on_scene_inactive && c->body) {
        g_py_callbacks.on_scene_inactive(c->body);
    }
}

static void py_vtable_on_scene_active(tc_component* c) {
    if (g_py_callbacks.on_scene_active && c->body) {
        g_py_callbacks.on_scene_active(c->body);
    }
}

static void py_vtable_on_editor_start(tc_component* c) {
    if (g_py_callbacks.on_editor_start && c->body) {
        g_py_callbacks.on_editor_start(c->body);
    }
}

// ============================================================================
// Python ref_vtable for Python components (TC_PYTHON_COMPONENT)
// ============================================================================

static void py_ext_ref_retain(tc_component* c) {
    if (g_py_callbacks.incref && c->body) {
        g_py_callbacks.incref(c->body);
    }
}

static void py_ext_ref_release(tc_component* c) {
    if (g_py_callbacks.decref && c->body) {
        g_py_callbacks.decref(c->body);
    }
}

static const tc_component_ref_vtable g_py_ext_component_ref_vtable = {
    py_ext_ref_retain,
    py_ext_ref_release,
    NULL,  // drop: Python GC owns the object
};

// ============================================================================
// External component vtable (static, shared by all external components)
// ============================================================================

static const tc_component_vtable g_python_vtable = {
    .start = py_vtable_start,
    .update = py_vtable_update,
    .fixed_update = py_vtable_fixed_update,
    .before_render = py_vtable_before_render,
    .on_destroy = py_vtable_on_destroy,
    .on_added_to_entity = py_vtable_on_added_to_entity,
    .on_removed_from_entity = py_vtable_on_removed_from_entity,
    .on_added = py_vtable_on_added,
    .on_removed = py_vtable_on_removed,
    .on_scene_inactive = py_vtable_on_scene_inactive,
    .on_scene_active = py_vtable_on_scene_active,
    .on_editor_start = py_vtable_on_editor_start,
    .setup_editor_defaults = NULL,  // External code handles this differently
    .serialize = NULL,
    .deserialize = NULL,
};

// ============================================================================
// Public API
// ============================================================================

void tc_component_set_python_callbacks(const tc_python_callbacks* callbacks) {
    if (callbacks) {
        g_py_callbacks = *callbacks;
    }
}

tc_component* tc_component_new_python(void* py_self, const char* type_name) {
    tc_component* c = (tc_component*)calloc(1, sizeof(tc_component));
    if (!c) return NULL;

    // Initialize with Python vtable
    tc_component_init(c, &g_python_vtable);
    c->ref_vtable = &g_py_ext_component_ref_vtable;

    // Store Python object pointer as body (this is a Python-native component)
    c->body = py_self;
    c->native_language = TC_LANGUAGE_PYTHON;

    // Python components
    c->kind = TC_PYTHON_COMPONENT;

    // Link to type registry for type name and instance tracking
    if (type_name) {
        tc_type_entry* entry = tc_component_registry_get_entry(type_name);
        if (entry) {
            c->type_entry = entry;
            c->type_version = entry->version;
            // Note: linking to instance list is done via tc_type_entry_link_instance
            // but we need the offsets which are defined in tc_component.c
            // For external components, we skip instance linking for now
            // since they're tracked differently via Python GC
        }
    }

    return c;
}

void tc_component_free_python(tc_component* c) {
    if (c) {
        // Unlink from type registry if linked
        tc_component_unlink_from_registry(c);
        free(c);
    }
}

// ============================================================================
// Python drawable vtable callbacks
// ============================================================================

static bool py_drawable_has_phase(tc_component* c, const char* phase_mark) {
    if (g_py_drawable_callbacks.has_phase && c->body) {
        return g_py_drawable_callbacks.has_phase(c->body, phase_mark);
    }
    return false;
}

static void py_drawable_draw_geometry(tc_component* c, void* render_context, int geometry_id) {
    if (g_py_drawable_callbacks.draw_geometry && c->body) {
        g_py_drawable_callbacks.draw_geometry(c->body, render_context, geometry_id);
    }
}

static void* py_drawable_get_geometry_draws(tc_component* c, const char* phase_mark) {
    if (g_py_drawable_callbacks.get_geometry_draws && c->body) {
        return g_py_drawable_callbacks.get_geometry_draws(c->body, phase_mark);
    }
    return NULL;
}

// Python drawable vtable (shared by all Python drawable components)
static const tc_drawable_vtable g_python_drawable_vtable = {
    .has_phase = py_drawable_has_phase,
    .draw_geometry = py_drawable_draw_geometry,
    .get_geometry_draws = py_drawable_get_geometry_draws,
};

void tc_component_set_python_drawable_callbacks(const tc_python_drawable_callbacks* callbacks) {
    if (callbacks) {
        g_py_drawable_callbacks = *callbacks;
    }
}

void tc_component_install_python_drawable_vtable(tc_component* c) {
    if (c) {
        c->drawable_vtable = &g_python_drawable_vtable;
    }
}

// ============================================================================
// Python input vtable callbacks
// ============================================================================

static void py_input_on_mouse_button(tc_component* c, tc_mouse_button_event* event) {
    if (g_py_input_callbacks.on_mouse_button && c->body) {
        g_py_input_callbacks.on_mouse_button(c->body, event);
    }
}

static void py_input_on_mouse_move(tc_component* c, tc_mouse_move_event* event) {
    if (g_py_input_callbacks.on_mouse_move && c->body) {
        g_py_input_callbacks.on_mouse_move(c->body, event);
    }
}

static void py_input_on_scroll(tc_component* c, tc_scroll_event* event) {
    if (g_py_input_callbacks.on_scroll && c->body) {
        g_py_input_callbacks.on_scroll(c->body, event);
    }
}

static void py_input_on_key(tc_component* c, tc_key_event* event) {
    if (g_py_input_callbacks.on_key && c->body) {
        g_py_input_callbacks.on_key(c->body, event);
    }
}

// Python input vtable (shared by all Python input handler components)
static const tc_input_vtable g_python_input_vtable = {
    .on_mouse_button = py_input_on_mouse_button,
    .on_mouse_move = py_input_on_mouse_move,
    .on_scroll = py_input_on_scroll,
    .on_key = py_input_on_key,
};

void tc_component_set_python_input_callbacks(const tc_python_input_callbacks* callbacks) {
    if (callbacks) {
        g_py_input_callbacks = *callbacks;
    }
}

void tc_component_install_python_input_vtable(tc_component* c) {
    if (c) {
        c->input_vtable = &g_python_input_vtable;
    }
}
