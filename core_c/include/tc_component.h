// tc_component.h - Component base and vtable
#ifndef TC_COMPONENT_H
#define TC_COMPONENT_H

#include "tc_types.h"
#include "tc_shader.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Forward declarations for entity pool types
typedef struct tc_entity_pool tc_entity_pool;
#ifndef TC_ENTITY_ID_DEFINED
#define TC_ENTITY_ID_DEFINED
typedef struct {
    uint32_t index;
    uint32_t generation;
} tc_entity_id;
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

// ============================================================================
// Binding Types - for language-specific wrappers
// ============================================================================

typedef enum tc_binding_type {
    TC_BINDING_NONE = 0,        // No binding / native C
    TC_BINDING_PYTHON = 1,
    TC_BINDING_CSHARP = 2,
    TC_BINDING_RUST = 3,
    TC_BINDING_MAX = 8          // Reserve space for future languages
} tc_binding_type;

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

// Forward declarations for input event types (opaque pointers)
typedef struct tc_mouse_button_event tc_mouse_button_event;
typedef struct tc_mouse_move_event tc_mouse_move_event;
typedef struct tc_scroll_event tc_scroll_event;
typedef struct tc_key_event tc_key_event;

struct tc_input_vtable {
    // Mouse button press/release
    void (*on_mouse_button)(tc_component* self, void* event);

    // Mouse movement
    void (*on_mouse_move)(tc_component* self, void* event);

    // Scroll wheel
    void (*on_scroll)(tc_component* self, void* event);

    // Keyboard input
    void (*on_key)(tc_component* self, void* event);
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

    // Lifecycle (called when component is fully attached to entity)
    void (*on_added)(tc_component* self);
    void (*on_removed)(tc_component* self);
    void (*on_scene_inactive)(tc_component* self);
    void (*on_scene_active)(tc_component* self);

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

    // Input vtable (NULL if component doesn't handle input)
    const tc_input_vtable* input_vtable;

    // Owner entity (set by entity_add_component) - DEPRECATED, use owner_entity_id
    tc_entity* entity;

    // Owner entity ID and pool (set when added to entity)
    tc_entity_id owner_entity_id;
    tc_entity_pool* owner_pool;

    // Instance-specific type name (takes precedence over vtable->type_name)
    const char* type_name;

    // Component kind (native or external)
    tc_component_kind kind;

    // Native language - where the component "body" lives
    // TC_BINDING_NONE for C/C++ components (body is the CxxComponent itself)
    // TC_BINDING_PYTHON for Python components (body points to PyObject)
    tc_binding_type native_language;

    // Body pointer - points to the actual component implementation
    // For TC_BINDING_PYTHON: PyObject* of the PythonComponent
    // For TC_BINDING_NONE (C++): NULL (body is the CxxComponent containing this tc_component)
    void* body;

    // Language bindings - wrappers for accessing this component from other languages
    // bindings[TC_BINDING_PYTHON] = PyObject* wrapper for accessing CxxComponent from Python
    // Each binding holds a reference (via retain) to keep the component alive
    void* bindings[TC_BINDING_MAX];

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
    tc_component* type_prev;
    tc_component* type_next;
};

// ============================================================================
// Component initialization helper
// ============================================================================

static inline void tc_component_init(tc_component* c, const tc_component_vtable* vtable) {
    c->vtable = vtable;
    c->drawable_vtable = NULL;
    c->input_vtable = NULL;
    c->entity = NULL;
#ifdef __cplusplus
    c->owner_entity_id = tc_entity_id{0xFFFFFFFF, 0};  // invalid
#else
    c->owner_entity_id = (tc_entity_id){0xFFFFFFFF, 0};  // invalid
#endif
    c->owner_pool = NULL;
    c->type_name = NULL;
    c->kind = TC_NATIVE_COMPONENT;
    c->native_language = TC_BINDING_NONE;
    c->body = NULL;
    for (int i = 0; i < TC_BINDING_MAX; i++) {
        c->bindings[i] = NULL;
    }
    c->enabled = true;
    c->active_in_editor = false;
    c->_started = false;
    c->has_update = (vtable && vtable->update != NULL);
    c->has_fixed_update = (vtable && vtable->fixed_update != NULL);
    c->has_before_render = (vtable && vtable->before_render != NULL);
    c->factory_retained = false;
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

static inline void tc_component_on_mouse_button(tc_component* c, void* event) {
    if (c && c->enabled && c->input_vtable && c->input_vtable->on_mouse_button) {
        c->input_vtable->on_mouse_button(c, event);
    }
}

static inline void tc_component_on_mouse_move(tc_component* c, void* event) {
    if (c && c->enabled && c->input_vtable && c->input_vtable->on_mouse_move) {
        c->input_vtable->on_mouse_move(c, event);
    }
}

static inline void tc_component_on_scroll(tc_component* c, void* event) {
    if (c && c->enabled && c->input_vtable && c->input_vtable->on_scroll) {
        c->input_vtable->on_scroll(c, event);
    }
}

static inline void tc_component_on_key(tc_component* c, void* event) {
    if (c && c->enabled && c->input_vtable && c->input_vtable->on_key) {
        c->input_vtable->on_key(c, event);
    }
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

// ============================================================================
// Binding management helpers
// ============================================================================

static inline void* tc_component_get_binding(tc_component* c, tc_binding_type lang) {
    if (!c || lang <= TC_BINDING_NONE || lang >= TC_BINDING_MAX) return NULL;
    return c->bindings[lang];
}

static inline void tc_component_set_binding(tc_component* c, tc_binding_type lang, void* binding) {
    if (!c || lang <= TC_BINDING_NONE || lang >= TC_BINDING_MAX) return;
    c->bindings[lang] = binding;
}

static inline void tc_component_clear_binding(tc_component* c, tc_binding_type lang) {
    if (!c || lang <= TC_BINDING_NONE || lang >= TC_BINDING_MAX) return;
    c->bindings[lang] = NULL;
}

static inline bool tc_component_is_native(tc_component* c, tc_binding_type lang) {
    if (!c) return false;
    return c->native_language == lang;
}

#ifdef __cplusplus
}
#endif

#endif // TC_COMPONENT_H
