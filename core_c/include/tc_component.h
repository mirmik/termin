// tc_component.h - Component base and vtable
#ifndef TC_COMPONENT_H
#define TC_COMPONENT_H

#include "tc_types.h"
#include "resources/tc_shader.h"
#include "tc_type_registry.h"
#include "tc_entity_pool.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Component Kind - distinguishes native vs external (scripted) components
// ============================================================================

typedef enum tc_component_kind {
    TC_NATIVE_COMPONENT = 0,    // Native component (C/C++)
    TC_EXTERNAL_COMPONENT = 1   // External component (scripting language, e.g. Python)
} tc_component_kind;

// Backwards compatibility aliases
#define TC_CXX_COMPONENT TC_NATIVE_COMPONENT
#define TC_PYTHON_COMPONENT TC_EXTERNAL_COMPONENT

// Language enum
#include "inspect/tc_binding.h"

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
// Input VTable - for components that handle input events
// ============================================================================

#include "tc_input_event.h"

struct tc_input_vtable {
    // Mouse button press/release
    void (*on_mouse_button)(tc_component* self, tc_mouse_button_event* event);

    // Mouse movement
    void (*on_mouse_move)(tc_component* self, tc_mouse_move_event* event);

    // Scroll wheel
    void (*on_scroll)(tc_component* self, tc_scroll_event* event);

    // Keyboard input
    void (*on_key)(tc_component* self, tc_key_event* event);
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

    // Memory management - called to free component data
    // If NULL, component data is not freed (external ownership)
    void (*drop)(tc_component* self);

    // Reference counting for external wrapper objects
    // retain: called when component gets a new wrapper reference (INCREF equivalent)
    // release: called when wrapper reference is released (DECREF equivalent)
    // These allow language-agnostic reference management
    void (*retain)(tc_component* self);
    void (*release)(tc_component* self);

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

    // Drawable pointer for C++ components (avoids dynamic_cast in callbacks)
    // Set by install_drawable_vtable(), NULL if not drawable
    void* drawable_ptr;

    // Input vtable (NULL if component doesn't handle input)
    const tc_input_vtable* input_vtable;

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

    // If true, component is managed by external language (C#, etc.)
    // When externally_managed: retain/release call body incref/decref
    // When not: retain/release use internal ref_count
    bool externally_managed;

    // Intrusive list for scene's type-based component lists
    // Linked when registered with scene, unlinked on unregister
    tc_component* type_prev;
    tc_component* type_next;

    // Type registry link (for global instance tracking and hot reload)
    tc_type_entry* type_entry;
    uint32_t type_version;

    // Intrusive list for global type registry instance tracking
    tc_component* registry_prev;
    tc_component* registry_next;
};

// ============================================================================
// Component initialization helper
// ============================================================================

static inline void tc_component_init(tc_component* c, const tc_component_vtable* vtable) {
    c->vtable = vtable;
    c->drawable_vtable = NULL;
    c->drawable_ptr = NULL;
    c->input_vtable = NULL;
    c->owner = TC_ENTITY_HANDLE_INVALID;
    c->kind = TC_NATIVE_COMPONENT;
    c->native_language = TC_LANGUAGE_CXX;
    c->body = NULL;
    c->enabled = true;
    c->active_in_editor = false;
    c->_started = false;
    c->has_update = (vtable && vtable->update != NULL);
    c->has_fixed_update = (vtable && vtable->fixed_update != NULL);
    c->has_before_render = (vtable && vtable->before_render != NULL);
    c->factory_retained = false;
    c->externally_managed = false;
    c->type_prev = NULL;
    c->type_next = NULL;
    c->type_entry = NULL;
    c->type_version = 0;
    c->registry_prev = NULL;
    c->registry_next = NULL;
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
    if (c && c->vtable && c->vtable->drop) {
        c->vtable->drop(c);
    }
}

static inline void tc_component_retain(tc_component* c) {
    if (c && c->vtable && c->vtable->retain) {
        c->vtable->retain(c);
    }
}

static inline void tc_component_release(tc_component* c) {
    if (c && c->vtable && c->vtable->release) {
        c->vtable->release(c);
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
    return c && c->drawable_vtable != NULL;
}

static inline bool tc_component_has_phase(tc_component* c, const char* phase_mark) {
    if (c && c->drawable_vtable && c->drawable_vtable->has_phase) {
        return c->drawable_vtable->has_phase(c, phase_mark);
    }
    return false;
}

static inline void tc_component_draw_geometry(tc_component* c, void* render_context, int geometry_id) {
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

static inline tc_shader_handle tc_component_override_shader(tc_component* c, const char* phase_mark, int geometry_id, tc_shader_handle original_shader) {
    if (c && c->drawable_vtable && c->drawable_vtable->override_shader) {
        return c->drawable_vtable->override_shader(c, phase_mark, geometry_id, original_shader);
    }
    return original_shader;
}

// ============================================================================
// Input dispatch (null-safe vtable dispatch)
// ============================================================================

static inline bool tc_component_is_input_handler(const tc_component* c) {
    return c && c->input_vtable != NULL;
}

static inline void tc_component_on_mouse_button(tc_component* c, tc_mouse_button_event* event) {
    if (c && c->enabled && c->input_vtable && c->input_vtable->on_mouse_button) {
        c->input_vtable->on_mouse_button(c, event);
    }
}

static inline void tc_component_on_mouse_move(tc_component* c, tc_mouse_move_event* event) {
    if (c && c->enabled && c->input_vtable && c->input_vtable->on_mouse_move) {
        c->input_vtable->on_mouse_move(c, event);
    }
}

static inline void tc_component_on_scroll(tc_component* c, tc_scroll_event* event) {
    if (c && c->enabled && c->input_vtable && c->input_vtable->on_scroll) {
        c->input_vtable->on_scroll(c, event);
    }
}

static inline void tc_component_on_key(tc_component* c, tc_key_event* event) {
    if (c && c->enabled && c->input_vtable && c->input_vtable->on_key) {
        c->input_vtable->on_key(c, event);
    }
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

// Drawable type management
// Mark a component type as drawable (can render geometry)
TC_API void tc_component_registry_set_drawable(const char* type_name, bool is_drawable);

// Check if a component type is drawable
TC_API bool tc_component_registry_is_drawable(const char* type_name);

// Get all drawable type names
// Returns count, fills out_names array (caller provides buffer)
TC_API size_t tc_component_registry_get_drawable_types(
    const char** out_names,
    size_t max_count
);

// Input handler type management
// Mark a component type as input handler
TC_API void tc_component_registry_set_input_handler(const char* type_name, bool is_input_handler);

// Check if a component type is an input handler
TC_API bool tc_component_registry_is_input_handler(const char* type_name);

// Get all input handler type names
// Returns count, fills out_names array (caller provides buffer)
TC_API size_t tc_component_registry_get_input_handler_types(
    const char** out_names,
    size_t max_count
);

// Get type entry for a component type
TC_API tc_type_entry* tc_component_registry_get_entry(const char* type_name);

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
// External body management (for C#, Rust, etc.)
// When externally_managed=true, retain/release call these on body
// ============================================================================

// Callbacks for external language reference counting
typedef void (*tc_component_body_incref_fn)(void* body);
typedef void (*tc_component_body_decref_fn)(void* body);

// Global callbacks for external body management
typedef struct {
    tc_component_body_incref_fn incref;
    tc_component_body_decref_fn decref;
} tc_component_external_callbacks;

// Set global external callbacks (call once at startup)
TC_API void tc_component_set_external_callbacks(const tc_component_external_callbacks* callbacks);

// Call external incref/decref on body (for externally_managed native components)
TC_API void tc_component_body_incref(void* body);
TC_API void tc_component_body_decref(void* body);

// Set component as externally managed with body pointer
static inline void tc_component_set_external_body(tc_component* c, void* body) {
    if (!c) return;
    c->body = body;
    c->externally_managed = true;
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
TC_API bool tc_component_get_is_input_handler(const tc_component* c);
TC_API tc_component_kind tc_component_get_kind(const tc_component* c);
TC_API tc_entity_handle tc_component_get_owner(const tc_component* c);

#ifdef __cplusplus
}
#endif

#endif // TC_COMPONENT_H
