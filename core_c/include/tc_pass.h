// tc_pass.h - Render pass base and vtable
// Same pattern as tc_component for language-agnostic pass system
#ifndef TC_PASS_H
#define TC_PASS_H

#include "tc_types.h"
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
typedef struct tc_resource_spec tc_resource_spec;

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
    void* graphics;              // GraphicsBackend*
    void* reads_fbos;            // FBO map for inputs
    void* writes_fbos;           // FBO map for outputs
    int rect_x;
    int rect_y;
    int rect_width;
    int rect_height;
    void* scene;                 // tc_scene*
    void* camera;                // Camera*
    int64_t context_key;         // For VAO/shader caching
    void* lights;                // Light array
    size_t light_count;
    uint64_t layer_mask;
};

// ============================================================================
// Resource Spec - declares resource requirements
// ============================================================================

struct tc_resource_spec {
    const char* resource;        // Resource name
    int fixed_width;             // 0 = use viewport size
    int fixed_height;            // 0 = use viewport size
    float clear_color[4];        // RGBA clear color
    float clear_depth;           // Depth clear value
    bool has_clear_color;        // Whether to clear color
    bool has_clear_depth;        // Whether to clear depth
    const char* format;          // FBO format (NULL = default)
};

// ============================================================================
// Pass VTable - virtual method table for passes
// ============================================================================

struct tc_pass_vtable {
    // Type identification
    const char* type_name;

    // Core execution
    void (*execute)(tc_pass* self, tc_execute_context* ctx);

    // Resource declarations (return count, fill arrays)
    size_t (*get_reads)(tc_pass* self, const char** out_reads, size_t max_count);
    size_t (*get_writes)(tc_pass* self, const char** out_writes, size_t max_count);

    // Inplace aliases: pairs of (read_name, write_name) interleaved
    // Returns number of pairs (not elements)
    size_t (*get_inplace_aliases)(tc_pass* self, const char** out_pairs, size_t max_pairs);

    // Resource specs
    size_t (*get_resource_specs)(tc_pass* self, tc_resource_spec* out_specs, size_t max_count);

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

    // External language support
    tc_pass_kind kind;
    bool externally_managed;
    void* wrapper;               // External object (PyObject*, etc.)

    // Linked list for pipeline iteration
    tc_pass* next;
    tc_pass* prev;
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
    p->externally_managed = false;
    p->wrapper = NULL;
    p->next = NULL;
    p->prev = NULL;
}

// ============================================================================
// Pass Lifecycle Dispatch (null-safe)
// ============================================================================

static inline void tc_pass_execute(tc_pass* p, tc_execute_context* ctx) {
    if (p && p->enabled && !p->passthrough && p->vtable && p->vtable->execute) {
        p->vtable->execute(p, ctx);
    }
}

static inline const char* tc_pass_type_name(const tc_pass* p) {
    if (p) {
        if (p->vtable && p->vtable->type_name) return p->vtable->type_name;
    }
    return "Pass";
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

static inline size_t tc_pass_get_resource_specs(tc_pass* p, tc_resource_spec* out, size_t max) {
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
// Pass Registry
// ============================================================================

typedef tc_pass* (*tc_pass_factory)(void);

TC_API void tc_pass_registry_register(
    const char* type_name,
    tc_pass_factory factory,
    tc_pass_kind kind
);

TC_API void tc_pass_registry_unregister(const char* type_name);
TC_API bool tc_pass_registry_has(const char* type_name);
TC_API tc_pass* tc_pass_registry_create(const char* type_name);
TC_API size_t tc_pass_registry_type_count(void);
TC_API const char* tc_pass_registry_type_at(size_t index);
TC_API tc_pass_kind tc_pass_registry_get_kind(const char* type_name);

// ============================================================================
// External Pass Support (for Python/Rust/C#)
// ============================================================================

typedef struct {
    void (*execute)(void* wrapper, tc_execute_context* ctx);
    size_t (*get_reads)(void* wrapper, const char** out, size_t max);
    size_t (*get_writes)(void* wrapper, const char** out, size_t max);
    size_t (*get_inplace_aliases)(void* wrapper, const char** out, size_t max);
    size_t (*get_resource_specs)(void* wrapper, tc_resource_spec* out, size_t max);
    size_t (*get_internal_symbols)(void* wrapper, const char** out, size_t max);
    void (*destroy)(void* wrapper);
    void (*incref)(void* wrapper);
    void (*decref)(void* wrapper);
} tc_external_pass_callbacks;

TC_API void tc_pass_set_external_callbacks(const tc_external_pass_callbacks* callbacks);
TC_API tc_pass* tc_pass_new_external(void* wrapper, const char* type_name);
TC_API void tc_pass_free_external(tc_pass* p);

#ifdef __cplusplus
}
#endif

#endif // TC_PASS_H
