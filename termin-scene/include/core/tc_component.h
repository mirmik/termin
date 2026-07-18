// tc_component.h - Component base and vtable
#ifndef TC_COMPONENT_H
#define TC_COMPONENT_H

#include "tc_types.h"
#include "core/tc_component_capability.h"
#include "core/tc_entity_pool.h"
#include "core/tc_dlist.h"
#include "inspect/tc_runtime_type_registry.h"
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Component Kind - which language owns the component
// ============================================================================

typedef enum tc_component_kind {
    TC_CXX_COMPONENT = 0,       // C++ component
    TC_PYTHON_COMPONENT = 1,    // Python component
    TC_CSHARP_COMPONENT = 2     // C# component
} tc_component_kind;

// Opaque, call-scoped render attachment context. Its concrete API is owned by
// termin-engine; termin-scene only transports it through lifecycle dispatch.
typedef struct tc_render_attachment_context tc_render_attachment_context;

// ============================================================================
// Reference counting VTable - separate from main vtable
// ============================================================================

struct tc_component_ref_vtable {
    void (*retain)(tc_component* self);
    void (*release)(tc_component* self);
    void (*drop)(tc_component* self);
};

// ============================================================================
// Component VTable - virtual method table for components
// ============================================================================

struct tc_component_vtable {
    // Lifecycle methods (all optional - can be NULL)
    void (*start)(tc_component* self);
    void (*update)(tc_component* self, float dt);
    void (*fixed_update)(tc_component* self, float dt);
    void (*before_render)(tc_component* self);
    void (*on_destroy)(tc_component* self);

    // Entity relationship
    void (*on_added_to_entity)(tc_component* self);
    void (*on_removed_from_entity)(tc_component* self);

    // Lifecycle (called when component is fully attached to entity)
    void (*on_added)(tc_component* self);
    void (*on_removed)(tc_component* self);
    void (*on_scene_inactive)(tc_component* self);
    void (*on_scene_active)(tc_component* self);

    // Render lifecycle (called when scene is attached/detached from rendering)
    // on_render_attach: scene pipelines are compiled, components can find passes
    // on_render_detach: scene pipelines will be destroyed, clear references
    void (*on_render_attach)(tc_component* self, const tc_render_attachment_context* context);
    void (*on_render_detach)(tc_component* self, const tc_render_attachment_context* context);

    // Editor hooks
    void (*on_editor_start)(tc_component* self);
    void (*setup_editor_defaults)(tc_component* self);

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

    // Reference counting vtable (separate from main vtable)
    const tc_component_ref_vtable* ref_vtable;

    // Owner entity handle (set when added to entity, invalid when detached)
    tc_entity_handle owner;

    // Component kind (native or external)
    tc_component_kind kind;

    // Native language - which language owns this component instance
    // TC_LANGUAGE_CXX: component created from C++ code
    // TC_LANGUAGE_PYTHON: component created from Python code
    tc_language native_language;

    // Body pointer - points to the object that owns this tc_component
    // MUST NOT be NULL after component is fully constructed
    // For CxxComponent created from C++: CxxComponent* (this)
    // For CxxComponent created from Python: PyObject* (Python wrapper)
    // For PythonComponent: PyObject* (the PythonComponent object)
    void* body;

    // Declared type name used to lazily attach the common runtime type link.
    const char* declared_type_name;

    // Stable authoring/serialization identity. This is deliberately separate
    // from the runtime component pointer and owner handle.
    const char* source_id;

    // Flags
    const char* display_name;
    bool enabled;
    bool active_in_editor;
    bool _started;
    bool has_update;
    bool has_fixed_update;
    bool has_before_render;
    tc_scene_handle lifecycle_scene;

    // If true, factory already did retain - entity should NOT retain again on add_component.
    // Factory sets this to true after doing its own retain.
    bool factory_retained;

    // Intrusive list for scene's type-based component lists
    // Linked when registered with scene, unlinked on unregister
    // Note: uses raw pointers (not tc_dlist) because head is stored externally
    tc_component* type_prev;
    tc_component* type_next;

    // Type registry link (for global instance tracking and hot reload)
    tc_runtime_type_instance_link runtime_type_link;

    // Generic component capabilities (slot-based fast path)
    uint64_t capability_mask;
    void* capability_ptrs[TC_COMPONENT_MAX_CAPABILITIES];
    int capability_priorities[TC_COMPONENT_MAX_CAPABILITIES];
    tc_component* capability_prev[TC_COMPONENT_MAX_CAPABILITIES];
    tc_component* capability_next[TC_COMPONENT_MAX_CAPABILITIES];

};

// ============================================================================
// Component initialization helper
// ============================================================================

static inline void tc_component_init(tc_component* c, const tc_component_vtable* vtable) {
    c->vtable = vtable;
    c->ref_vtable = NULL;
    c->owner = TC_ENTITY_HANDLE_INVALID;
    c->kind = TC_CXX_COMPONENT;
    c->native_language = TC_LANGUAGE_CXX;
    c->body = NULL;
    c->declared_type_name = NULL;
    c->source_id = NULL;
    c->display_name = NULL;
    c->enabled = true;
    c->active_in_editor = false;
    c->_started = false;
    c->has_update = (vtable && vtable->update != NULL);
    c->has_fixed_update = (vtable && vtable->fixed_update != NULL);
    c->has_before_render = (vtable && vtable->before_render != NULL);
    c->lifecycle_scene = TC_SCENE_HANDLE_INVALID;
    c->factory_retained = false;
    c->type_prev = NULL;
    c->type_next = NULL;
    tc_runtime_type_instance_link_init(&c->runtime_type_link);
    c->capability_mask = 0;
    memset(c->capability_ptrs, 0, sizeof(c->capability_ptrs));
    memset(c->capability_priorities, 0, sizeof(c->capability_priorities));
    memset(c->capability_prev, 0, sizeof(c->capability_prev));
    memset(c->capability_next, 0, sizeof(c->capability_next));
}

// Change the complete lifecycle scheduling contract in one operation. If the
// component is registered with a scene, its scheduler indexes are updated
// before this function returns. Detached components only store the flags.
TC_API void tc_component_set_lifecycle_capabilities(
    tc_component* c,
    bool has_update,
    bool has_fixed_update,
    bool has_before_render
);

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
    if (c) {
        tc_component_clear_capabilities(c);
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

static inline void tc_component_on_added(tc_component* c) {
    if (c && c->vtable && c->vtable->on_added) {
        c->vtable->on_added(c);
    }
}

static inline void tc_component_on_removed(tc_component* c) {
    if (c && c->vtable && c->vtable->on_removed) {
        c->vtable->on_removed(c);
    }
}

static inline void tc_component_on_scene_inactive(tc_component* c) {
    if (c && c->vtable && c->vtable->on_scene_inactive) {
        c->vtable->on_scene_inactive(c);
    }
}

static inline void tc_component_on_scene_active(tc_component* c) {
    if (c && c->vtable && c->vtable->on_scene_active) {
        c->vtable->on_scene_active(c);
    }
}

static inline void tc_component_on_render_attach(
    tc_component* c,
    const tc_render_attachment_context* context
) {
    if (c && c->vtable && c->vtable->on_render_attach) {
        c->vtable->on_render_attach(c, context);
    }
}

static inline void tc_component_on_render_detach(
    tc_component* c,
    const tc_render_attachment_context* context
) {
    if (c && c->vtable && c->vtable->on_render_detach) {
        c->vtable->on_render_detach(c, context);
    }
}

static inline void tc_component_drop(tc_component* c) {
    if (c && c->ref_vtable && c->ref_vtable->drop) {
        c->ref_vtable->drop(c);
    }
}

static inline void tc_component_retain(tc_component* c) {
    if (c && c->ref_vtable && c->ref_vtable->retain) {
        c->ref_vtable->retain(c);
    }
}

static inline void tc_component_release(tc_component* c) {
    if (c && c->ref_vtable && c->ref_vtable->release) {
        c->ref_vtable->release(c);
    }
}

static inline const char* tc_component_type_name(const tc_component* c) {
    if (c && c->runtime_type_link.type_name) {
        return c->runtime_type_link.type_name;
    }
    if (c && c->declared_type_name) {
        return c->declared_type_name;
    }
    return "Component";
}

// ============================================================================
// Component Registry
// ============================================================================

// Component factory: takes userdata, returns tc_component*
typedef tc_component* (*tc_component_factory)(void* userdata);
typedef bool (*tc_component_prepare_unload_fn)(
    const char* type_name,
    void* context,
    void* user_data
);

TC_API void tc_component_registry_register(
    const char* type_name,
    tc_component_factory factory,
    void* factory_userdata,
    tc_component_kind kind
);

TC_API bool tc_component_registry_register_with_parent(
    const char* type_name,
    tc_component_factory factory,
    void* factory_userdata,
    tc_component_kind kind,
    const char* parent_type_name
);

// Register abstract component type (no factory, can't be instantiated)
TC_API void tc_component_registry_register_abstract(
    const char* type_name,
    tc_component_kind kind,
    const char* parent_type_name
);

TC_API void tc_component_registry_unregister(const char* type_name);
TC_API bool tc_component_registry_has(const char* type_name);
TC_API tc_component* tc_component_registry_create(const char* type_name);
TC_API void tc_component_registry_cleanup(void);

TC_API void tc_component_registry_set_registration_owner(const char* owner);
TC_API const char* tc_component_registry_get_registration_owner(void);
TC_API const char* tc_component_registry_get_owner(const char* type_name);
TC_API size_t tc_component_registry_unregister_owner(const char* owner);
TC_API void tc_component_registry_set_prepare_unload_callback(
    tc_component_prepare_unload_fn callback,
    void* user_data
);

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
TC_API bool tc_component_registry_is_a(
    const char* type_name,
    const char* base_type_name
);

TC_API void tc_component_registry_add_requirement(
    const char* type_name,
    const char* required_type_name
);

TC_API size_t tc_component_registry_requirement_count(const char* type_name);
TC_API const char* tc_component_registry_requirement_at(
    const char* type_name,
    size_t index
);
TC_API bool tc_component_registry_has_requirement(
    const char* type_name,
    const char* required_type_name
);

// Get component kind (TC_CXX_COMPONENT or TC_PYTHON_COMPONENT)
TC_API tc_component_kind tc_component_registry_get_kind(const char* type_name);
TC_API bool tc_component_registry_is_abstract(const char* type_name);

TC_API void tc_component_registry_set_display_name(
    const char* type_name,
    const char* display_name
);
TC_API const char* tc_component_registry_get_display_name(const char* type_name);

TC_API void tc_component_registry_set_category(
    const char* type_name,
    const char* category
);
TC_API const char* tc_component_registry_get_category(const char* type_name);

TC_API void tc_component_registry_set_capability(
    const char* type_name,
    tc_component_cap_id cap_id,
    bool enabled
);

TC_API bool tc_component_registry_has_capability(
    const char* type_name,
    tc_component_cap_id cap_id
);

TC_API size_t tc_component_registry_get_types_with_capability(
    tc_component_cap_id cap_id,
    const char** out_names,
    size_t max_count
);

// Get type entry for a component type
TC_API void tc_component_set_declared_type_name(tc_component* c, const char* type_name);
TC_API void tc_component_try_link_declared_type(tc_component* c);

// Get instance count for a type
TC_API size_t tc_component_registry_instance_count(const char* type_name);

// Check if component's type version is current (for hot reload detection)
static inline bool tc_component_type_is_current(const tc_component* c) {
    if (!c || !c->runtime_type_link.type_name) return true;
    return tc_runtime_type_registry_instance_is_current(&c->runtime_type_link);
}

// Unlink component from type registry (called when component is destroyed)
TC_API void tc_component_unlink_from_registry(tc_component* c);

static inline bool tc_component_is_language(tc_component* c, tc_language lang) {
    if (!c) return false;
    return c->native_language == lang;
}

// ============================================================================
// Component property accessors (for FFI bindings)
// ============================================================================

TC_API const char* tc_component_get_type_name(const tc_component* c);
TC_API const char* tc_component_get_source_id(const tc_component* c);
TC_API void tc_component_set_source_id(tc_component* c, const char* source_id);
TC_API const char* tc_component_ensure_source_id(tc_component* c);
TC_API const char* tc_component_get_display_name(const tc_component* c);
TC_API void tc_component_set_display_name(tc_component* c, const char* display_name);
TC_API bool tc_component_get_enabled(const tc_component* c);
TC_API void tc_component_set_enabled(tc_component* c, bool enabled);
TC_API bool tc_component_get_active_in_editor(const tc_component* c);
TC_API void tc_component_set_active_in_editor(tc_component* c, bool active);
TC_API tc_component_kind tc_component_get_kind(const tc_component* c);
TC_API tc_entity_handle tc_component_get_owner(const tc_component* c);

#ifdef __cplusplus
}
#endif

#endif // TC_COMPONENT_H
