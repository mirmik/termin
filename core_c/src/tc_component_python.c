// tc_component_python.c - Python-specific component implementation
#include "../include/tc_component_python.h"
#include <stdlib.h>
#include <string.h>

// Global Python callbacks (set once at initialization)
static tc_python_callbacks g_py_callbacks = {0};
static tc_python_drawable_callbacks g_py_drawable_callbacks = {0};

// ============================================================================
// Python vtable callbacks - these dispatch to global Python callbacks
// ============================================================================

static void py_vtable_start(tc_component* c) {
    if (g_py_callbacks.start && c->py_wrap) {
        g_py_callbacks.start(c->py_wrap);
    }
}

static void py_vtable_update(tc_component* c, float dt) {
    if (g_py_callbacks.update && c->py_wrap) {
        g_py_callbacks.update(c->py_wrap, dt);
    }
}

static void py_vtable_fixed_update(tc_component* c, float dt) {
    if (g_py_callbacks.fixed_update && c->py_wrap) {
        g_py_callbacks.fixed_update(c->py_wrap, dt);
    }
}

static void py_vtable_before_render(tc_component* c) {
    if (g_py_callbacks.before_render && c->py_wrap) {
        g_py_callbacks.before_render(c->py_wrap);
    }
}

static void py_vtable_on_destroy(tc_component* c) {
    if (g_py_callbacks.on_destroy && c->py_wrap) {
        g_py_callbacks.on_destroy(c->py_wrap);
    }
}

static void py_vtable_on_added_to_entity(tc_component* c) {
    if (g_py_callbacks.on_added_to_entity && c->py_wrap) {
        g_py_callbacks.on_added_to_entity(c->py_wrap);
    }
}

static void py_vtable_on_removed_from_entity(tc_component* c) {
    if (g_py_callbacks.on_removed_from_entity && c->py_wrap) {
        g_py_callbacks.on_removed_from_entity(c->py_wrap);
    }
}

static void py_vtable_on_added(tc_component* c, void* scene) {
    if (g_py_callbacks.on_added && c->py_wrap) {
        g_py_callbacks.on_added(c->py_wrap, scene);
    }
}

static void py_vtable_on_removed(tc_component* c) {
    if (g_py_callbacks.on_removed && c->py_wrap) {
        g_py_callbacks.on_removed(c->py_wrap);
    }
}

static void py_vtable_on_scene_inactive(tc_component* c) {
    if (g_py_callbacks.on_scene_inactive && c->py_wrap) {
        g_py_callbacks.on_scene_inactive(c->py_wrap);
    }
}

static void py_vtable_on_scene_active(tc_component* c) {
    if (g_py_callbacks.on_scene_active && c->py_wrap) {
        g_py_callbacks.on_scene_active(c->py_wrap);
    }
}

static void py_vtable_on_editor_start(tc_component* c) {
    if (g_py_callbacks.on_editor_start && c->py_wrap) {
        g_py_callbacks.on_editor_start(c->py_wrap);
    }
}

// ============================================================================
// Python vtable (static, shared by all Python components)
// ============================================================================

static const tc_component_vtable g_python_vtable = {
    .type_name = "PythonComponent",  // Instance type_name will override this
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
    .setup_editor_defaults = NULL,  // Python handles this differently
    .drop = NULL,  // Python manages its own memory
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

    // Store Python object pointer
    c->py_wrap = py_self;
    c->python_allocated = true;

    // Set instance type name (overrides vtable->type_name)
    c->type_name = type_name;

    // Python components
    c->kind = TC_PYTHON_COMPONENT;

    return c;
}

void tc_component_free_python(tc_component* c) {
    if (c) {
        // Don't free c->py_wrap - Python manages its own objects
        free(c);
    }
}

// ============================================================================
// Python drawable vtable callbacks
// ============================================================================

static bool py_drawable_has_phase(tc_component* c, const char* phase_mark) {
    if (g_py_drawable_callbacks.has_phase && c->py_wrap) {
        return g_py_drawable_callbacks.has_phase(c->py_wrap, phase_mark);
    }
    return false;
}

static void py_drawable_draw_geometry(tc_component* c, void* render_context, int geometry_id) {
    if (g_py_drawable_callbacks.draw_geometry && c->py_wrap) {
        g_py_drawable_callbacks.draw_geometry(c->py_wrap, render_context, geometry_id);
    }
}

static void* py_drawable_get_geometry_draws(tc_component* c, const char* phase_mark) {
    if (g_py_drawable_callbacks.get_geometry_draws && c->py_wrap) {
        return g_py_drawable_callbacks.get_geometry_draws(c->py_wrap, phase_mark);
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
