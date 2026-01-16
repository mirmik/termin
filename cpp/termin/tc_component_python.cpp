// tc_component_python.cpp - External component implementation
// Provides component functionality for external scripting languages (e.g. Python)
#include "tc_component_python.h"
#include <stdlib.h>
#include <string.h>

// Global Python callbacks (set once at initialization)
static tc_python_callbacks g_py_callbacks = {0};
static tc_python_drawable_callbacks g_py_drawable_callbacks = {0};

// ============================================================================
// Python vtable callbacks - these dispatch to global Python callbacks
// ============================================================================

static void py_vtable_start(tc_component* c) {
    if (g_py_callbacks.start && c->wrapper) {
        g_py_callbacks.start(c->wrapper);
    }
}

static void py_vtable_update(tc_component* c, float dt) {
    if (g_py_callbacks.update && c->wrapper) {
        g_py_callbacks.update(c->wrapper, dt);
    }
}

static void py_vtable_fixed_update(tc_component* c, float dt) {
    if (g_py_callbacks.fixed_update && c->wrapper) {
        g_py_callbacks.fixed_update(c->wrapper, dt);
    }
}

static void py_vtable_before_render(tc_component* c) {
    if (g_py_callbacks.before_render && c->wrapper) {
        g_py_callbacks.before_render(c->wrapper);
    }
}

static void py_vtable_on_destroy(tc_component* c) {
    if (g_py_callbacks.on_destroy && c->wrapper) {
        g_py_callbacks.on_destroy(c->wrapper);
    }
}

static void py_vtable_on_added_to_entity(tc_component* c) {
    if (g_py_callbacks.on_added_to_entity && c->wrapper) {
        g_py_callbacks.on_added_to_entity(c->wrapper);
    }
}

static void py_vtable_on_removed_from_entity(tc_component* c) {
    if (g_py_callbacks.on_removed_from_entity && c->wrapper) {
        g_py_callbacks.on_removed_from_entity(c->wrapper);
    }
}

static void py_vtable_on_added(tc_component* c, void* scene) {
    if (g_py_callbacks.on_added && c->wrapper) {
        g_py_callbacks.on_added(c->wrapper, scene);
    }
}

static void py_vtable_on_removed(tc_component* c) {
    if (g_py_callbacks.on_removed && c->wrapper) {
        g_py_callbacks.on_removed(c->wrapper);
    }
}

static void py_vtable_on_scene_inactive(tc_component* c) {
    if (g_py_callbacks.on_scene_inactive && c->wrapper) {
        g_py_callbacks.on_scene_inactive(c->wrapper);
    }
}

static void py_vtable_on_scene_active(tc_component* c) {
    if (g_py_callbacks.on_scene_active && c->wrapper) {
        g_py_callbacks.on_scene_active(c->wrapper);
    }
}

static void py_vtable_on_editor_start(tc_component* c) {
    if (g_py_callbacks.on_editor_start && c->wrapper) {
        g_py_callbacks.on_editor_start(c->wrapper);
    }
}

static void py_vtable_retain(tc_component* c) {
    if (g_py_callbacks.incref && c->wrapper) {
        g_py_callbacks.incref(c->wrapper);
    }
}

static void py_vtable_release(tc_component* c) {
    if (g_py_callbacks.decref && c->wrapper) {
        g_py_callbacks.decref(c->wrapper);
    }
}

// ============================================================================
// External component vtable (static, shared by all external components)
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
    .setup_editor_defaults = NULL,  // External code handles this differently
    .drop = NULL,  // External code manages its own memory
    .retain = py_vtable_retain,
    .release = py_vtable_release,
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
    c->wrapper = py_self;
    c->externally_managed = true;

    // Set instance type name (overrides vtable->type_name)
    c->type_name = type_name;

    // Python components
    c->kind = TC_EXTERNAL_COMPONENT;

    return c;
}

void tc_component_free_python(tc_component* c) {
    if (c) {
        // Don't free c->wrapper - Python manages its own objects
        free(c);
    }
}

// ============================================================================
// Python drawable vtable callbacks
// ============================================================================

static bool py_drawable_has_phase(tc_component* c, const char* phase_mark) {
    if (g_py_drawable_callbacks.has_phase && c->wrapper) {
        return g_py_drawable_callbacks.has_phase(c->wrapper, phase_mark);
    }
    return false;
}

static void py_drawable_draw_geometry(tc_component* c, void* render_context, int geometry_id) {
    if (g_py_drawable_callbacks.draw_geometry && c->wrapper) {
        g_py_drawable_callbacks.draw_geometry(c->wrapper, render_context, geometry_id);
    }
}

static void* py_drawable_get_geometry_draws(tc_component* c, const char* phase_mark) {
    if (g_py_drawable_callbacks.get_geometry_draws && c->wrapper) {
        return g_py_drawable_callbacks.get_geometry_draws(c->wrapper, phase_mark);
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
