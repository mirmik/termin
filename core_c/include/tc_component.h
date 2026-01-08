// tc_component.h - Component base and vtable
#ifndef TC_COMPONENT_H
#define TC_COMPONENT_H

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Component Kind - distinguishes C++ vs Python components
// ============================================================================

typedef enum tc_component_kind {
    TC_CXX_COMPONENT = 0,     // C++ component (data points to CxxComponent*)
    TC_PYTHON_COMPONENT = 1   // Python component (data points to PythonComponent PyObject*)
} tc_component_kind;

// ============================================================================
// Drawable VTable - for components that can render geometry
// ============================================================================

struct tc_drawable_vtable {
    // Check if this drawable participates in a rendering phase
    bool (*has_phase)(tc_component* self, const char* phase_mark);

    // Draw geometry (shader already bound by pass)
    // render_context is opaque (RenderContext* in C++)
    void (*draw_geometry)(tc_component* self, void* render_context, const char* geometry_id);

    // Get geometry draw calls for a phase
    // Returns opaque pointer to be interpreted by caller (std::vector<GeometryDrawCall>* in C++)
    // Caller must NOT free the returned pointer
    void* (*get_geometry_draws)(tc_component* self, const char* phase_mark);

    // Override shader for a draw call (for skinning injection, etc.)
    // Pass calls this before applying uniforms to let drawable modify the shader.
    // Returns original_shader if no override needed, or a different shader.
    // original_shader is opaque (ShaderProgram* in C++)
    void* (*override_shader)(tc_component* self, const char* phase_mark, const char* geometry_id, void* original_shader);
};

// ============================================================================
// Component VTable - virtual method table for components
// ============================================================================

struct tc_component_vtable {
    // Type identification
    const char* type_name;

    // Lifecycle methods (all optional - can be NULL)
    void (*start)(tc_component* self);
    void (*update)(tc_component* self, float dt);
    void (*fixed_update)(tc_component* self, float dt);
    void (*before_render)(tc_component* self);
    void (*on_destroy)(tc_component* self);

    // Entity relationship
    void (*on_added_to_entity)(tc_component* self);
    void (*on_removed_from_entity)(tc_component* self);

    // Scene relationship (scene is opaque void*)
    void (*on_added)(tc_component* self, void* scene);
    void (*on_removed)(tc_component* self);

    // Editor hooks
    void (*on_editor_start)(tc_component* self);
    void (*setup_editor_defaults)(tc_component* self);

    // Memory management - called to free component data
    // If NULL, component data is not freed (external ownership)
    void (*drop)(tc_component* self);

    // Serialization (optional)
    // serialize returns opaque data pointer, deserialize consumes it
    void* (*serialize)(const tc_component* self);
    void (*deserialize)(tc_component* self, const void* data);
};

// ============================================================================
// Component structure
// ============================================================================

struct tc_component {
    // Virtual method table
    const tc_component_vtable* vtable;

    // Drawable vtable (NULL if component is not drawable)
    const tc_drawable_vtable* drawable_vtable;

    // Owner entity (set by entity_add_component)
    tc_entity* entity;

    // Instance-specific type name (takes precedence over vtable->type_name)
    const char* type_name;

    // Component kind (C++ or Python)
    tc_component_kind kind;

    // If true, this tc_component was allocated from Python
    bool python_allocated;

    // Python wrapper object (PyObject*)
    // - For python_allocated components: holds the owning reference
    // - For C++ components accessed from Python: cached wrapper (may be NULL)
    void* py_wrap;

    // Flags
    bool enabled;
    bool active_in_editor;
    bool _started;
    bool has_update;
    bool has_fixed_update;
    bool has_before_render;

    // Intrusive list for scene's type-based component lists
    // Linked when registered with scene, unlinked on unregister
    tc_component* type_prev;
    tc_component* type_next;
};

// ============================================================================
// Component initialization helper
// ============================================================================

static inline void tc_component_init(tc_component* c, const tc_component_vtable* vtable) {
    c->vtable = vtable;
    c->drawable_vtable = NULL;
    c->entity = NULL;
    c->type_name = NULL;
    c->kind = TC_CXX_COMPONENT;
    c->python_allocated = false;
    c->py_wrap = NULL;
    c->enabled = true;
    c->active_in_editor = false;
    c->_started = false;
    c->has_update = (vtable && vtable->update != NULL);
    c->has_fixed_update = (vtable && vtable->fixed_update != NULL);
    c->has_before_render = (vtable && vtable->before_render != NULL);
    c->type_prev = NULL;
    c->type_next = NULL;
}

// ============================================================================
// Component lifecycle calls (null-safe vtable dispatch)
// ============================================================================

static inline void tc_component_start(tc_component* c) {
    if (c && c->vtable && c->vtable->start) {
        c->vtable->start(c);
    }
    if (c) c->_started = true;
}

static inline void tc_component_update(tc_component* c, float dt) {
    if (c && c->enabled && c->vtable && c->vtable->update) {
        c->vtable->update(c, dt);
    }
}

static inline void tc_component_fixed_update(tc_component* c, float dt) {
    if (c && c->enabled && c->vtable && c->vtable->fixed_update) {
        c->vtable->fixed_update(c, dt);
    }
}

static inline void tc_component_before_render(tc_component* c) {
    if (c && c->enabled && c->vtable && c->vtable->before_render) {
        c->vtable->before_render(c);
    }
}

static inline void tc_component_on_destroy(tc_component* c) {
    if (c && c->vtable && c->vtable->on_destroy) {
        c->vtable->on_destroy(c);
    }
}

static inline void tc_component_on_added_to_entity(tc_component* c) {
    if (c && c->vtable && c->vtable->on_added_to_entity) {
        c->vtable->on_added_to_entity(c);
    }
}

static inline void tc_component_on_removed_from_entity(tc_component* c) {
    if (c && c->vtable && c->vtable->on_removed_from_entity) {
        c->vtable->on_removed_from_entity(c);
    }
}

static inline void tc_component_on_added(tc_component* c, void* scene) {
    if (c && c->vtable && c->vtable->on_added) {
        c->vtable->on_added(c, scene);
    }
}

static inline void tc_component_on_removed(tc_component* c) {
    if (c && c->vtable && c->vtable->on_removed) {
        c->vtable->on_removed(c);
    }
}

static inline void tc_component_drop(tc_component* c) {
    if (c && c->vtable && c->vtable->drop) {
        c->vtable->drop(c);
    }
}

static inline const char* tc_component_type_name(const tc_component* c) {
    if (c) {
        // Instance-specific type_name takes precedence (for C++ wrapper)
        if (c->type_name) return c->type_name;
        if (c->vtable && c->vtable->type_name) return c->vtable->type_name;
    }
    return "Component";
}

// ============================================================================
// Drawable dispatch (null-safe vtable dispatch)
// ============================================================================

static inline bool tc_component_is_drawable(const tc_component* c) {
    return c && c->drawable_vtable != NULL;
}

static inline bool tc_component_has_phase(tc_component* c, const char* phase_mark) {
    if (c && c->drawable_vtable && c->drawable_vtable->has_phase) {
        return c->drawable_vtable->has_phase(c, phase_mark);
    }
    return false;
}

static inline void tc_component_draw_geometry(tc_component* c, void* render_context, const char* geometry_id) {
    if (c && c->drawable_vtable && c->drawable_vtable->draw_geometry) {
        c->drawable_vtable->draw_geometry(c, render_context, geometry_id);
    }
}

static inline void* tc_component_get_geometry_draws(tc_component* c, const char* phase_mark) {
    if (c && c->drawable_vtable && c->drawable_vtable->get_geometry_draws) {
        return c->drawable_vtable->get_geometry_draws(c, phase_mark);
    }
    return NULL;
}

static inline void* tc_component_override_shader(tc_component* c, const char* phase_mark, const char* geometry_id, void* original_shader) {
    if (c && c->drawable_vtable && c->drawable_vtable->override_shader) {
        return c->drawable_vtable->override_shader(c, phase_mark, geometry_id, original_shader);
    }
    return original_shader;
}

// ============================================================================
// Component Registry
// ============================================================================

typedef tc_component* (*tc_component_factory)(void);

TC_API void tc_component_registry_register(
    const char* type_name,
    tc_component_factory factory,
    tc_component_kind kind
);

TC_API void tc_component_registry_register_with_parent(
    const char* type_name,
    tc_component_factory factory,
    tc_component_kind kind,
    const char* parent_type_name
);

TC_API void tc_component_registry_unregister(const char* type_name);
TC_API bool tc_component_registry_has(const char* type_name);
TC_API tc_component* tc_component_registry_create(const char* type_name);

TC_API size_t tc_component_registry_type_count(void);
TC_API const char* tc_component_registry_type_at(size_t index);

// Get descendant type names for iteration (includes type itself)
// Returns count, fills out_names array (caller provides buffer)
TC_API size_t tc_component_registry_get_type_and_descendants(
    const char* type_name,
    const char** out_names,
    size_t max_count
);

// Get parent type name (or NULL if none)
TC_API const char* tc_component_registry_get_parent(const char* type_name);

// Get component kind (TC_CXX_COMPONENT or TC_PYTHON_COMPONENT)
TC_API tc_component_kind tc_component_registry_get_kind(const char* type_name);

#ifdef __cplusplus
}
#endif

#endif // TC_COMPONENT_H
