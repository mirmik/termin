// tc_type_registry.h - Unified type registry for components and passes
// Uses hash table for O(1) lookup, supports versioning and instance tracking
#ifndef TC_TYPE_REGISTRY_H
#define TC_TYPE_REGISTRY_H

#include "tc_types.h"
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Type Entry Flags
// ============================================================================

#define TC_TYPE_FLAG_DRAWABLE       (1 << 0)
#define TC_TYPE_FLAG_INPUT_HANDLER  (1 << 1)

// ============================================================================
// Type Entry - shared structure for component and pass types
// ============================================================================

typedef struct tc_type_entry tc_type_entry;

// Factory function signature: takes userdata, returns instance pointer
typedef void* (*tc_type_factory_fn)(void* userdata);

struct tc_type_entry {
    // Type identification
    const char* type_name;          // Interned string, stable pointer
    tc_type_factory_fn factory;     // Factory function (takes userdata)
    void* factory_userdata;         // Context passed to factory
    uint32_t version;               // Incremented on re-register
    bool registered;                // false after unregister, entry NOT deleted

    // Intrusive instance list (void* for generic use)
    void* first_instance;
    void* last_instance;
    size_t instance_count;

    // Type hierarchy (for components with inheritance)
    tc_type_entry* parent;
    tc_type_entry** children;
    size_t child_count;
    size_t child_capacity;

    // Flags (is_drawable, is_input_handler, etc.)
    uint32_t flags;

    // Kind (native vs external)
    int kind;
};

// ============================================================================
// Type Registry - hash table of type entries
// ============================================================================

typedef struct tc_type_registry tc_type_registry;

// Create a new type registry
TC_API tc_type_registry* tc_type_registry_new(void);

// Destroy registry and all entries
TC_API void tc_type_registry_free(tc_type_registry* reg);

// ============================================================================
// Type Registration
// ============================================================================

// Register a type (creates entry if new, increments version if exists)
// Returns the type entry (always non-NULL on success)
TC_API tc_type_entry* tc_type_registry_register(
    tc_type_registry* reg,
    const char* type_name,
    tc_type_factory_fn factory,
    void* factory_userdata,
    int kind
);

// Register a type with a parent (for inheritance hierarchy)
TC_API tc_type_entry* tc_type_registry_register_with_parent(
    tc_type_registry* reg,
    const char* type_name,
    tc_type_factory_fn factory,
    void* factory_userdata,
    int kind,
    const char* parent_type_name
);

// Unregister a type (marks registered=false, does NOT delete entry)
TC_API void tc_type_registry_unregister(tc_type_registry* reg, const char* type_name);

// Check if type is registered (entry exists AND registered==true)
TC_API bool tc_type_registry_has(const tc_type_registry* reg, const char* type_name);

// Get type entry by name (returns NULL if not found)
TC_API tc_type_entry* tc_type_registry_get(tc_type_registry* reg, const char* type_name);

// ============================================================================
// Type Enumeration
// ============================================================================

// Get count of registered types (registered==true only)
TC_API size_t tc_type_registry_count(const tc_type_registry* reg);

// Iterator callback: return true to continue, false to stop
typedef bool (*tc_type_iter_fn)(tc_type_entry* entry, void* user_data);

// Iterate over all registered types (registered==true only)
TC_API void tc_type_registry_foreach(
    tc_type_registry* reg,
    tc_type_iter_fn callback,
    void* user_data
);

// Get type name at index (for backward compatibility)
// Iterates in insertion order
TC_API const char* tc_type_registry_type_at(tc_type_registry* reg, size_t index);

// ============================================================================
// Instance Tracking
// ============================================================================

// Link instance to type entry (adds to intrusive list)
// instance_prev_offset and instance_next_offset are offsets of prev/next pointers in instance struct
TC_API void tc_type_entry_link_instance(
    tc_type_entry* entry,
    void* instance,
    size_t instance_prev_offset,
    size_t instance_next_offset
);

// Unlink instance from type entry
TC_API void tc_type_entry_unlink_instance(
    tc_type_entry* entry,
    void* instance,
    size_t instance_prev_offset,
    size_t instance_next_offset
);

// Get instance count for type
static inline size_t tc_type_entry_instance_count(const tc_type_entry* entry) {
    return entry ? entry->instance_count : 0;
}

// Get first instance for type
static inline void* tc_type_entry_first_instance(const tc_type_entry* entry) {
    return entry ? entry->first_instance : NULL;
}

// Create instance via type entry's factory
// Returns NULL if entry is NULL, not registered, or factory is NULL
static inline void* tc_type_entry_create(tc_type_entry* entry) {
    if (!entry || !entry->registered || !entry->factory) return NULL;
    return entry->factory(entry->factory_userdata);
}

// ============================================================================
// Type Hierarchy
// ============================================================================

// Get parent type entry
static inline tc_type_entry* tc_type_entry_parent(const tc_type_entry* entry) {
    return entry ? entry->parent : NULL;
}

// Get descendant types (type itself + all children recursively)
// Returns count, fills out_entries array
TC_API size_t tc_type_entry_get_descendants(
    const tc_type_entry* entry,
    tc_type_entry** out_entries,
    size_t max_count
);

// ============================================================================
// Flags
// ============================================================================

static inline bool tc_type_entry_has_flag(const tc_type_entry* entry, uint32_t flag) {
    return entry && (entry->flags & flag) != 0;
}

static inline void tc_type_entry_set_flag(tc_type_entry* entry, uint32_t flag, bool value) {
    if (!entry) return;
    if (value) {
        entry->flags |= flag;
    } else {
        entry->flags &= ~flag;
    }
}

// ============================================================================
// Version Checking
// ============================================================================

// Check if instance version matches current type version
static inline bool tc_type_version_is_current(const tc_type_entry* entry, uint32_t instance_version) {
    return entry && entry->version == instance_version;
}

#ifdef __cplusplus
}
#endif

#endif // TC_TYPE_REGISTRY_H
