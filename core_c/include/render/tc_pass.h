// tc_pass.h - Render pass base and vtable
// Same pattern as tc_component for language-agnostic pass system
#ifndef TC_PASS_H
#define TC_PASS_H

#include "tc_types.h"
#include "resources/tc_binding.h"
#include "tc_type_registry.h"
#include "tc_scene_pool.h"
#include "render/tc_viewport_pool.h"
#include "render/tc_pipeline_pool.h"
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Forward declarations
typedef struct tc_pass tc_pass;
typedef struct tc_pass_vtable tc_pass_vtable;
typedef struct tc_execute_context tc_execute_context;

// ============================================================================
// Pass Kind - distinguishes native vs external passes
// ============================================================================

typedef enum tc_pass_kind {
    TC_NATIVE_PASS = 0,     // Native pass (C/C++)
    TC_EXTERNAL_PASS = 1    // External pass (Python/Rust/C#)
} tc_pass_kind;

// ============================================================================
// Execute Context - data passed to pass execute
// ============================================================================

struct tc_execute_context {
    void* graphics;              // GraphicsBackend* (C++)
    void* reads_fbos;            // FBO map for inputs (C++)
    void* writes_fbos;           // FBO map for outputs (C++)
    int rect_x;
    int rect_y;
    int rect_width;
    int rect_height;
    tc_scene_handle scene;       // Scene handle
    tc_viewport_handle viewport; // Viewport handle (resolution, camera context)
    void* camera;                // CameraComponent* (C++)
    void* lights;                // Light array (C++)
    size_t light_count;
    uint64_t layer_mask;
};

// ============================================================================
// Pass VTable - virtual method table for passes
// ============================================================================

struct tc_pass_vtable {
    // Core execution
    // ctx is ExecuteContext* for C++ passes, or language-specific context for external passes
    void (*execute)(tc_pass* self, void* ctx);

    // Resource declarations (return count, fill arrays)
    size_t (*get_reads)(tc_pass* self, const char** out_reads, size_t max_count);
    size_t (*get_writes)(tc_pass* self, const char** out_writes, size_t max_count);

    // Inplace aliases: pairs of (read_name, write_name) interleaved
    // Returns number of pairs (not elements)
    size_t (*get_inplace_aliases)(tc_pass* self, const char** out_pairs, size_t max_pairs);

    // Resource specs (out_specs is ResourceSpec* from C++)
    size_t (*get_resource_specs)(tc_pass* self, void* out_specs, size_t max_count);

    // Debug symbols (entity names for step-through debugging)
    size_t (*get_internal_symbols)(tc_pass* self, const char** out_symbols, size_t max_count);

    // Cleanup
    void (*destroy)(tc_pass* self);

    // Memory management
    void (*drop)(tc_pass* self);

    // Reference counting for external wrappers
    void (*retain)(tc_pass* self);
    void (*release)(tc_pass* self);

    // Serialization (optional)
    void* (*serialize)(const tc_pass* self);
    void (*deserialize)(tc_pass* self, const void* data);
};

// ============================================================================
// Pass Structure
// ============================================================================

struct tc_pass {
    // Virtual method table
    const tc_pass_vtable* vtable;

    // Basic fields
    char* pass_name;
    bool enabled;
    bool passthrough;            // Skip execution, just pass resources through
    char* viewport_name;         // NULL = offscreen pass

    // Debug
    char* debug_internal_symbol;

    // Language support
    tc_pass_kind kind;
    tc_language native_language; // Which language the pass type is defined in
    bool externally_managed;
    void* body;                  // External object (PyObject*, etc.) for TC_EXTERNAL_PASS

    // Language bindings - wrappers for accessing this pass from other languages
    // bindings[TC_LANGUAGE_PYTHON] = PyObject* wrapper for accessing native pass from Python
    void* bindings[TC_LANGUAGE_MAX];

    // Owner pipeline (set when added to pipeline)
    tc_pipeline_handle owner_pipeline;

    // Type registry link (for global instance tracking and hot reload)
    tc_type_entry* type_entry;
    uint32_t type_version;

    // Intrusive list for global type registry instance tracking
    tc_pass* registry_prev;
    tc_pass* registry_next;
};

// ============================================================================
// Pass Initialization
// ============================================================================

static inline void tc_pass_init(tc_pass* p, const tc_pass_vtable* vtable) {
    p->vtable = vtable;
    p->pass_name = NULL;
    p->enabled = true;
    p->passthrough = false;
    p->viewport_name = NULL;
    p->debug_internal_symbol = NULL;
    p->kind = TC_NATIVE_PASS;
    p->native_language = TC_LANGUAGE_CXX;
    p->externally_managed = false;
    p->body = NULL;
    for (int i = 0; i < TC_LANGUAGE_MAX; i++) {
        p->bindings[i] = NULL;
    }
    p->owner_pipeline = TC_PIPELINE_HANDLE_INVALID;
    p->type_entry = NULL;
    p->type_version = 0;
    p->registry_prev = NULL;
    p->registry_next = NULL;
}

// ============================================================================
// Binding Helpers
// ============================================================================

static inline void* tc_pass_get_binding(tc_pass* p, tc_language lang) {
    if (!p || lang < 0 || lang >= TC_LANGUAGE_MAX) return NULL;
    return p->bindings[lang];
}

static inline void tc_pass_set_binding(tc_pass* p, tc_language lang, void* binding) {
    if (!p || lang < 0 || lang >= TC_LANGUAGE_MAX) return;
    p->bindings[lang] = binding;
}

static inline void tc_pass_clear_binding(tc_pass* p, tc_language lang) {
    if (!p || lang < 0 || lang >= TC_LANGUAGE_MAX) return;
    p->bindings[lang] = NULL;
}

// ============================================================================
// Pass Lifecycle Dispatch (null-safe)
// ============================================================================

static inline void tc_pass_execute(tc_pass* p, void* ctx) {
    if (p && p->enabled && !p->passthrough && p->vtable && p->vtable->execute) {
        p->vtable->execute(p, ctx);
    }
}

static inline const char* tc_pass_type_name(const tc_pass* p) {
    if (p && p->type_entry && p->type_entry->type_name) {
        return p->type_entry->type_name;
    }
    return "BrokenPass_NoTypeEntry";
}

static inline size_t tc_pass_get_reads(tc_pass* p, const char** out, size_t max) {
    if (p && p->vtable && p->vtable->get_reads) {
        return p->vtable->get_reads(p, out, max);
    }
    return 0;
}

static inline size_t tc_pass_get_writes(tc_pass* p, const char** out, size_t max) {
    if (p && p->vtable && p->vtable->get_writes) {
        return p->vtable->get_writes(p, out, max);
    }
    return 0;
}

static inline size_t tc_pass_get_inplace_aliases(tc_pass* p, const char** out, size_t max) {
    if (p && p->vtable && p->vtable->get_inplace_aliases) {
        return p->vtable->get_inplace_aliases(p, out, max);
    }
    return 0;
}

static inline bool tc_pass_is_inplace(tc_pass* p) {
    const char* dummy[2];
    return tc_pass_get_inplace_aliases(p, dummy, 1) > 0;
}

// out is ResourceSpec* from C++
static inline size_t tc_pass_get_resource_specs(tc_pass* p, void* out, size_t max) {
    if (p && p->vtable && p->vtable->get_resource_specs) {
        return p->vtable->get_resource_specs(p, out, max);
    }
    return 0;
}

static inline size_t tc_pass_get_internal_symbols(tc_pass* p, const char** out, size_t max) {
    if (p && p->vtable && p->vtable->get_internal_symbols) {
        return p->vtable->get_internal_symbols(p, out, max);
    }
    return 0;
}

static inline void tc_pass_destroy(tc_pass* p) {
    if (p && p->vtable && p->vtable->destroy) {
        p->vtable->destroy(p);
    }
}

static inline void tc_pass_drop(tc_pass* p) {
    if (p && p->vtable && p->vtable->drop) {
        p->vtable->drop(p);
    }
}

static inline void tc_pass_retain(tc_pass* p) {
    if (p && p->vtable && p->vtable->retain) {
        p->vtable->retain(p);
    }
}

static inline void tc_pass_release(tc_pass* p) {
    if (p && p->vtable && p->vtable->release) {
        p->vtable->release(p);
    }
}

// ============================================================================
// Pass Property Setters
// ============================================================================

TC_API void tc_pass_set_name(tc_pass* p, const char* name);
TC_API void tc_pass_set_enabled(tc_pass* p, bool enabled);
TC_API void tc_pass_set_passthrough(tc_pass* p, bool passthrough);

// ============================================================================
// Pass Registry
// ============================================================================

// Pass factory: takes userdata, returns tc_pass*
typedef tc_pass* (*tc_pass_factory)(void* userdata);

TC_API void tc_pass_registry_register(
    const char* type_name,
    tc_pass_factory factory,
    void* factory_userdata,
    tc_pass_kind kind
);

TC_API void tc_pass_registry_unregister(const char* type_name);
TC_API bool tc_pass_registry_has(const char* type_name);
TC_API tc_pass* tc_pass_registry_create(const char* type_name);
TC_API size_t tc_pass_registry_type_count(void);
TC_API const char* tc_pass_registry_type_at(size_t index);
TC_API tc_pass_kind tc_pass_registry_get_kind(const char* type_name);

// Get type entry for a pass type
TC_API tc_type_entry* tc_pass_registry_get_entry(const char* type_name);

// Get instance count for a type
TC_API size_t tc_pass_registry_instance_count(const char* type_name);

// Unlink pass from type registry (called when pass is destroyed)
TC_API void tc_pass_unlink_from_registry(tc_pass* p);

// Check if pass's type version is current (for hot reload detection)
static inline bool tc_pass_type_is_current(const tc_pass* p) {
    if (!p || !p->type_entry) return true;
    return tc_type_version_is_current(p->type_entry, p->type_version);
}

// ============================================================================
// External Pass Support (for Python/Rust/C#)
// ============================================================================

typedef struct {
    void (*execute)(void* body, void* ctx);  // ctx is ExecuteContext* (C++)
    size_t (*get_reads)(void* body, const char** out, size_t max);
    size_t (*get_writes)(void* body, const char** out, size_t max);
    size_t (*get_inplace_aliases)(void* body, const char** out, size_t max);
    size_t (*get_resource_specs)(void* body, void* out, size_t max);  // out is ResourceSpec* (C++)
    size_t (*get_internal_symbols)(void* body, const char** out, size_t max);
    void (*destroy)(void* body);
    void (*incref)(void* body);
    void (*decref)(void* body);
} tc_external_pass_callbacks;

TC_API void tc_pass_set_external_callbacks(const tc_external_pass_callbacks* callbacks);
TC_API tc_pass* tc_pass_new_external(void* body, const char* type_name);
TC_API void tc_pass_free_external(tc_pass* p);

// Call external incref/decref on body (for externally_managed native passes)
TC_API void tc_pass_body_incref(void* body);
TC_API void tc_pass_body_decref(void* body);

#ifdef __cplusplus
}
#endif

#endif // TC_PASS_H
