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
// Component VTable - virtual method table for components
// ============================================================================

struct tc_component_vtable {
    // Type identification
    const char* type_name;

    // Lifecycle methods (all optional - can be NULL)
    void (*start)(tc_component* self);
    void (*update)(tc_component* self, float dt);
    void (*fixed_update)(tc_component* self, float dt);
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
};

// ============================================================================
// Component initialization helper
// ============================================================================

static inline void tc_component_init(tc_component* c, const tc_component_vtable* vtable) {
    c->vtable = vtable;
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
// Component Registry
// ============================================================================

typedef tc_component* (*tc_component_factory)(void);

TC_API void tc_component_registry_register(
    const char* type_name,
    tc_component_factory factory,
    tc_component_kind kind
);

TC_API void tc_component_registry_unregister(const char* type_name);
TC_API bool tc_component_registry_has(const char* type_name);
TC_API tc_component* tc_component_registry_create(const char* type_name);

TC_API size_t tc_component_registry_type_count(void);
TC_API const char* tc_component_registry_type_at(size_t index);

#ifdef __cplusplus
}
#endif

#endif // TC_COMPONENT_H
