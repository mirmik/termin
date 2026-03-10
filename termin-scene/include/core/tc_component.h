// tc_component.h - Component base and vtable
#ifndef TC_COMPONENT_H
#define TC_COMPONENT_H

#include "tc_types.h"
#include "tc_type_registry.h"
#include "core/tc_component_capability.h"
#include "core/tc_drawable_capability.h"
#include "core/tc_entity_pool.h"
#include "core/tc_dlist.h"
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

// ============================================================================
// Drawable VTable - for components that can render geometry
// ============================================================================

struct tc_drawable_vtable {
    // Check if this drawable participates in a rendering phase
    bool (*has_phase)(tc_component* self, const char* phase_mark);

    // Draw geometry (shader already bound by pass)
    // render_context is opaque (RenderContext* in C++)
    // geometry_id: 0 = default/all, >0 = specific geometry slot
    void (*draw_geometry)(tc_component* self, void* render_context, int geometry_id);

    // Get geometry draw calls for a phase
    // Returns opaque pointer to be interpreted by caller (std::vector<GeometryDrawCall>* in C++)
    // Caller must NOT free the returned pointer
    void* (*get_geometry_draws)(tc_component* self, const char* phase_mark);

    // Override shader for a draw call (for skinning injection, etc.)
    // Pass calls this before applying uniforms to let drawable modify the shader.
    // Returns original_shader if no override needed, or a different shader handle.
    // geometry_id: 0 = default, >0 = specific geometry slot
    tc_shader_handle (*override_shader)(tc_component* self, const char* phase_mark, int geometry_id, tc_shader_handle original_shader);
};

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
    void (*on_render_attach)(tc_component* self);
    void (*on_render_detach)(tc_component* self);

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

    // Declared type name used to lazily attach type_entry on add-to-entity paths.
    // This is optional; registry-created components already have type_entry.
    const char* declared_type_name;

    // Flags
    bool enabled;
    bool active_in_editor;
    bool _started;
    bool has_update;
    bool has_fixed_update;
    bool has_before_render;

    // If true, factory already did retain - entity should NOT retain again on add_component.
    // Factory sets this to true after doing its own retain.
    bool factory_retained;

    // Intrusive list for scene's type-based component lists
    // Linked when registered with scene, unlinked on unregister
    // Note: uses raw pointers (not tc_dlist) because head is stored externally
    tc_component* type_prev;
    tc_component* type_next;

    // Type registry link (for global instance tracking and hot reload)
    tc_type_entry* type_entry;
    uint32_t type_version;

    // Generic component capabilities (slot-based fast path)
    uint64_t capability_mask;
    void* capability_ptrs[TC_COMPONENT_MAX_CAPABILITIES];
    tc_component* capability_prev[TC_COMPONENT_MAX_CAPABILITIES];
    tc_component* capability_next[TC_COMPONENT_MAX_CAPABILITIES];

    // Intrusive list for global type registry instance tracking
    // Uses tc_dlist_node for safe multiple-unlink
    tc_dlist_node registry_node;
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
    c->enabled = true;
    c->active_in_editor = false;
    c->_started = false;
    c->has_update = (vtable && vtable->update != NULL);
    c->has_fixed_update = (vtable && vtable->fixed_update != NULL);
    c->has_before_render = (vtable && vtable->before_render != NULL);
    c->factory_retained = false;
    c->type_prev = NULL;
    c->type_next = NULL;
    c->type_entry = NULL;
    c->type_version = 0;
    c->capability_mask = 0;
    memset(c->capability_ptrs, 0, sizeof(c->capability_ptrs));
    memset(c->capability_prev, 0, sizeof(c->capability_prev));
    memset(c->capability_next, 0, sizeof(c->capability_next));
    tc_dlist_init_node(&c->registry_node);
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

static inline void tc_component_on_render_attach(tc_component* c) {
    if (c && c->vtable && c->vtable->on_render_attach) {
        c->vtable->on_render_attach(c);
    }
}

static inline void tc_component_on_render_detach(tc_component* c) {
    if (c && c->vtable && c->vtable->on_render_detach) {
        c->vtable->on_render_detach(c);
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
    if (c && c->type_entry && c->type_entry->type_name) {
        return c->type_entry->type_name;
    }
    return "Component";
}

// ============================================================================
// Drawable dispatch (null-safe vtable dispatch)
// ============================================================================

static inline bool tc_component_is_drawable(const tc_component* c) {
    return c && tc_drawable_capability_get(c) != NULL;
}

static inline const tc_drawable_vtable* tc_component_get_drawable_vtable(const tc_component* c) {
    if (!c) return NULL;
    const tc_drawable_capability* cap = tc_drawable_capability_get(c);
    return cap ? cap->vtable : NULL;
}

static inline void* tc_component_get_drawable_userdata(const tc_component* c) {
    if (!c) return NULL;
    const tc_drawable_capability* cap = tc_drawable_capability_get(c);
    return cap ? cap->userdata : NULL;
}

static inline bool tc_component_has_phase(tc_component* c, const char* phase_mark) {
    const tc_drawable_vtable* vt = tc_component_get_drawable_vtable(c);
    if (c && vt && vt->has_phase) {
        return vt->has_phase(c, phase_mark);
    }
    return false;
}

static inline void tc_component_draw_geometry(tc_component* c, void* render_context, int geometry_id) {
    const tc_drawable_vtable* vt = tc_component_get_drawable_vtable(c);
    if (c && vt && vt->draw_geometry) {
        vt->draw_geometry(c, render_context, geometry_id);
    }
}

static inline void* tc_component_get_geometry_draws(tc_component* c, const char* phase_mark) {
    const tc_drawable_vtable* vt = tc_component_get_drawable_vtable(c);
    if (c && vt && vt->get_geometry_draws) {
        return vt->get_geometry_draws(c, phase_mark);
    }
    return NULL;
}

static inline tc_shader_handle tc_component_override_shader(tc_component* c, const char* phase_mark, int geometry_id, tc_shader_handle original_shader) {
    const tc_drawable_vtable* vt = tc_component_get_drawable_vtable(c);
    if (c && vt && vt->override_shader) {
        return vt->override_shader(c, phase_mark, geometry_id, original_shader);
    }
    return original_shader;
}

// ============================================================================
// Component Registry
// ============================================================================

// Component factory: takes userdata, returns tc_component*
typedef tc_component* (*tc_component_factory)(void* userdata);

TC_API void tc_component_registry_register(
    const char* type_name,
    tc_component_factory factory,
    void* factory_userdata,
    tc_component_kind kind
);

TC_API void tc_component_registry_register_with_parent(
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
TC_API tc_type_entry* tc_component_registry_get_entry(const char* type_name);
TC_API void tc_component_set_declared_type_name(tc_component* c, const char* type_name);
TC_API void tc_component_try_link_declared_type(tc_component* c);

// Get instance count for a type
TC_API size_t tc_component_registry_instance_count(const char* type_name);

// Check if component's type version is current (for hot reload detection)
static inline bool tc_component_type_is_current(const tc_component* c) {
    if (!c || !c->type_entry) return true;
    return tc_type_version_is_current(c->type_entry, c->type_version);
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
TC_API bool tc_component_get_enabled(const tc_component* c);
TC_API void tc_component_set_enabled(tc_component* c, bool enabled);
TC_API bool tc_component_get_active_in_editor(const tc_component* c);
TC_API void tc_component_set_active_in_editor(tc_component* c, bool active);
TC_API bool tc_component_get_is_drawable(const tc_component* c);
TC_API tc_component_kind tc_component_get_kind(const tc_component* c);
TC_API tc_entity_handle tc_component_get_owner(const tc_component* c);

#ifdef __cplusplus
}
#endif

#endif // TC_COMPONENT_H
