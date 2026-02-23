// tc_type_registry.c - Unified type registry implementation
#include "tc_type_registry.h"
#include <tgfx/tc_resource_map.h>
#include "termin_core.h"
#include <tcbase/tc_log.h>
#include <stdlib.h>
#include <string.h>

// ============================================================================
// Type Registry Structure
// ============================================================================

struct tc_type_registry {
    tc_resource_map* entries;       // type_name -> tc_type_entry*
    size_t registered_count;        // Count of entries with registered==true
};

// ============================================================================
// Internal Helpers
// ============================================================================

static void type_entry_free(void* ptr) {
    tc_type_entry* entry = (tc_type_entry*)ptr;
    if (!entry) return;

    // Free children array (entries themselves are in the map)
    free(entry->children);

    // type_name is interned, don't free
    // factory is a function pointer, don't free

    free(entry);
}

static void type_entry_add_child(tc_type_entry* parent, tc_type_entry* child) {
    if (!parent || !child) return;

    if (parent->child_count >= parent->child_capacity) {
        size_t new_cap = parent->child_capacity == 0 ? 4 : parent->child_capacity * 2;
        tc_type_entry** new_arr = (tc_type_entry**)realloc(
            parent->children, new_cap * sizeof(tc_type_entry*)
        );
        if (!new_arr) return;
        parent->children = new_arr;
        parent->child_capacity = new_cap;
    }

    parent->children[parent->child_count++] = child;
}

// ============================================================================
// Registry Lifecycle
// ============================================================================

tc_type_registry* tc_type_registry_new(void) {
    tc_type_registry* reg = (tc_type_registry*)calloc(1, sizeof(tc_type_registry));
    if (!reg) return NULL;

    reg->entries = tc_resource_map_new(type_entry_free);
    if (!reg->entries) {
        free(reg);
        return NULL;
    }

    reg->registered_count = 0;
    return reg;
}

void tc_type_registry_free(tc_type_registry* reg) {
    if (!reg) return;

    tc_resource_map_free(reg->entries);
    free(reg);
}

// ============================================================================
// Type Registration
// ============================================================================

tc_type_entry* tc_type_registry_register(
    tc_type_registry* reg,
    const char* type_name,
    tc_type_factory_fn factory,
    void* factory_userdata,
    int kind
) {
    return tc_type_registry_register_with_parent(reg, type_name, factory, factory_userdata, kind, NULL);
}

tc_type_entry* tc_type_registry_register_with_parent(
    tc_type_registry* reg,
    const char* type_name,
    tc_type_factory_fn factory,
    void* factory_userdata,
    int kind,
    const char* parent_type_name
) {
    if (!reg || !type_name) return NULL;

    // Get parent entry if specified
    tc_type_entry* parent = NULL;
    if (parent_type_name) {
        parent = tc_type_registry_get(reg, parent_type_name);
    }

    // Check if already exists
    tc_type_entry* entry = (tc_type_entry*)tc_resource_map_get(reg->entries, type_name);
    if (entry) {
        // Update existing entry
        entry->factory = factory;
        entry->factory_userdata = factory_userdata;
        entry->kind = kind;
        entry->version++;

        // Update parent if changed
        if (entry->parent != parent) {
            // Note: we don't remove from old parent's children list
            // This is acceptable for hot reload scenarios
            entry->parent = parent;
            if (parent) {
                type_entry_add_child(parent, entry);
            }
        }

        if (!entry->registered) {
            entry->registered = true;
            reg->registered_count++;
        }

        return entry;
    }

    // Create new entry
    entry = (tc_type_entry*)calloc(1, sizeof(tc_type_entry));
    if (!entry) return NULL;

    entry->type_name = tc_intern_string(type_name);
    entry->factory = factory;
    entry->factory_userdata = factory_userdata;
    entry->version = 1;
    entry->registered = true;
    tc_dlist_init_head(&entry->instances);
    entry->instance_count = 0;
    entry->parent = parent;
    entry->children = NULL;
    entry->child_count = 0;
    entry->child_capacity = 0;
    entry->flags = 0;
    entry->kind = kind;

    // Add to map
    if (!tc_resource_map_add(reg->entries, type_name, entry)) {
        free(entry);
        return NULL;
    }

    reg->registered_count++;

    // Add to parent's children list
    if (parent) {
        type_entry_add_child(parent, entry);
    }

    // Add to all ancestors' children lists (for polymorphic queries)
    tc_type_entry* ancestor = parent;
    while (ancestor && ancestor->parent) {
        type_entry_add_child(ancestor->parent, entry);
        ancestor = ancestor->parent;
    }

    return entry;
}

void tc_type_registry_unregister(tc_type_registry* reg, const char* type_name) {
    if (!reg || !type_name) return;

    tc_type_entry* entry = (tc_type_entry*)tc_resource_map_get(reg->entries, type_name);
    if (!entry) return;

    if (entry->registered) {
        entry->registered = false;
        reg->registered_count--;
    }

    // Note: entry is NOT removed from map, just marked as unregistered
    // This preserves instance tracking for existing instances
}

bool tc_type_registry_has(const tc_type_registry* reg, const char* type_name) {
    if (!reg || !type_name) return false;

    tc_type_entry* entry = (tc_type_entry*)tc_resource_map_get(reg->entries, type_name);
    return entry && entry->registered;
}

tc_type_entry* tc_type_registry_get(tc_type_registry* reg, const char* type_name) {
    if (!reg || !type_name) return NULL;
    return (tc_type_entry*)tc_resource_map_get(reg->entries, type_name);
}

// ============================================================================
// Type Enumeration
// ============================================================================

size_t tc_type_registry_count(const tc_type_registry* reg) {
    return reg ? reg->registered_count : 0;
}

typedef struct {
    tc_type_iter_fn callback;
    void* user_data;
} foreach_ctx;

static bool foreach_wrapper(const char* uuid, void* resource, void* user_data) {
    (void)uuid;
    foreach_ctx* ctx = (foreach_ctx*)user_data;
    tc_type_entry* entry = (tc_type_entry*)resource;

    // Only iterate registered entries
    if (entry && entry->registered) {
        return ctx->callback(entry, ctx->user_data);
    }
    return true;
}

void tc_type_registry_foreach(
    tc_type_registry* reg,
    tc_type_iter_fn callback,
    void* user_data
) {
    if (!reg || !callback) return;

    foreach_ctx ctx = { callback, user_data };
    tc_resource_map_foreach(reg->entries, foreach_wrapper, &ctx);
}

typedef struct {
    size_t target_index;
    size_t current_index;
    const char* result;
} type_at_ctx;

static bool type_at_callback(tc_type_entry* entry, void* user_data) {
    type_at_ctx* ctx = (type_at_ctx*)user_data;

    if (ctx->current_index == ctx->target_index) {
        ctx->result = entry->type_name;
        return false;  // Stop iteration
    }

    ctx->current_index++;
    return true;
}

const char* tc_type_registry_type_at(tc_type_registry* reg, size_t index) {
    if (!reg) return NULL;

    type_at_ctx ctx = { index, 0, NULL };
    tc_type_registry_foreach(reg, type_at_callback, &ctx);
    return ctx.result;
}

// ============================================================================
// Instance Tracking
// ============================================================================

void tc_type_entry_link_instance(
    tc_type_entry* entry,
    void* instance,
    size_t node_offset
) {
    if (!entry || !instance) return;

    tc_dlist_node* node = (tc_dlist_node*)((char*)instance + node_offset);
    tc_dlist_add_tail(node, &entry->instances);
    entry->instance_count++;
}

void tc_type_entry_unlink_instance(
    tc_type_entry* entry,
    void* instance,
    size_t node_offset
) {
    if (!entry || !instance) return;

    tc_dlist_node* node = (tc_dlist_node*)((char*)instance + node_offset);

    // tc_dlist_del is safe to call multiple times (no-op if not linked)
    if (tc_dlist_is_linked(node)) {
        tc_dlist_del(node);
        entry->instance_count--;
    }
}

// ============================================================================
// Type Hierarchy
// ============================================================================

static size_t collect_descendants_recursive(
    const tc_type_entry* entry,
    tc_type_entry** out_entries,
    size_t max_count,
    size_t current_count
) {
    if (!entry || current_count >= max_count) return current_count;

    // Add this entry
    out_entries[current_count++] = (tc_type_entry*)entry;

    // Add all children (which includes grandchildren due to how we register)
    // But to avoid duplicates, we only add direct children here
    // since ancestors already have the full list

    // Actually, the plan says descendants should be collected recursively
    // Let me re-check: children array contains direct children only
    // So we need to recurse
    for (size_t i = 0; i < entry->child_count && current_count < max_count; i++) {
        // Only add direct children (avoid duplicates from ancestor registration)
        tc_type_entry* child = entry->children[i];
        if (child && child->parent == entry) {
            current_count = collect_descendants_recursive(child, out_entries, max_count, current_count);
        }
    }

    return current_count;
}

size_t tc_type_entry_get_descendants(
    const tc_type_entry* entry,
    tc_type_entry** out_entries,
    size_t max_count
) {
    if (!entry || !out_entries || max_count == 0) return 0;
    return collect_descendants_recursive(entry, out_entries, max_count, 0);
}
