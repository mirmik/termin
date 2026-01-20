// tc_component.c - Component registry implementation
#include "../include/tc_component.h"
#include "../include/termin_core.h"
#include <stdlib.h>
#include <string.h>

// ============================================================================
// Component Registry - stores type factories
// ============================================================================

#define TC_COMPONENT_REGISTRY_INITIAL_CAPACITY 32

typedef struct tc_component_type_entry {
    const char* type_name;  // Interned string
    tc_component_factory factory;
    tc_component_kind kind;
    int parent_index;  // -1 if no parent
    int* descendant_indices;
    size_t descendant_count;
    size_t descendant_capacity;
    bool is_drawable;       // True if this component type can render geometry
    bool is_input_handler;  // True if this component type handles input events
} tc_component_type_entry;

typedef struct tc_component_registry {
    tc_component_type_entry* entries;
    size_t count;
    size_t capacity;
} tc_component_registry;

static tc_component_registry g_component_registry = {NULL, 0, 0};

// ============================================================================
// Registry Implementation
// ============================================================================

static void tc_component_registry_ensure_capacity(void) {
    if (g_component_registry.count >= g_component_registry.capacity) {
        size_t new_capacity = g_component_registry.capacity == 0
            ? TC_COMPONENT_REGISTRY_INITIAL_CAPACITY
            : g_component_registry.capacity * 2;

        tc_component_type_entry* new_entries = (tc_component_type_entry*)realloc(
            g_component_registry.entries,
            new_capacity * sizeof(tc_component_type_entry)
        );

        if (!new_entries) return;

        g_component_registry.entries = new_entries;
        g_component_registry.capacity = new_capacity;
    }
}

static int tc_component_registry_find_index(const char* type_name) {
    for (size_t i = 0; i < g_component_registry.count; i++) {
        if (strcmp(g_component_registry.entries[i].type_name, type_name) == 0) {
            return (int)i;
        }
    }
    return -1;
}

static void tc_component_type_entry_add_descendant(tc_component_type_entry* entry, int descendant_idx) {
    if (entry->descendant_count >= entry->descendant_capacity) {
        size_t new_cap = entry->descendant_capacity == 0 ? 4 : entry->descendant_capacity * 2;
        int* new_arr = (int*)realloc(entry->descendant_indices, new_cap * sizeof(int));
        if (!new_arr) return;
        entry->descendant_indices = new_arr;
        entry->descendant_capacity = new_cap;
    }
    entry->descendant_indices[entry->descendant_count++] = descendant_idx;
}

void tc_component_registry_register(
    const char* type_name,
    tc_component_factory factory,
    tc_component_kind kind
) {
    tc_component_registry_register_with_parent(type_name, factory, kind, NULL);
}

void tc_component_registry_register_with_parent(
    const char* type_name,
    tc_component_factory factory,
    tc_component_kind kind,
    const char* parent_type_name
) {
    if (!type_name) return;

    // Find parent index
    int parent_idx = parent_type_name ? tc_component_registry_find_index(parent_type_name) : -1;

    // Check if already registered
    int idx = tc_component_registry_find_index(type_name);
    if (idx >= 0) {
        // Update existing
        g_component_registry.entries[idx].factory = factory;
        g_component_registry.entries[idx].kind = kind;
        g_component_registry.entries[idx].parent_index = parent_idx;
        return;
    }

    // Add new
    tc_component_registry_ensure_capacity();
    if (g_component_registry.count >= g_component_registry.capacity) return;

    idx = (int)g_component_registry.count;
    tc_component_type_entry* entry = &g_component_registry.entries[idx];
    entry->type_name = tc_intern_string(type_name);
    entry->factory = factory;
    entry->kind = kind;
    entry->parent_index = parent_idx;
    entry->descendant_indices = NULL;
    entry->descendant_count = 0;
    entry->descendant_capacity = 0;
    entry->is_drawable = false;
    entry->is_input_handler = false;
    g_component_registry.count++;

    // Add this type to all ancestors' descendant lists
    int ancestor_idx = parent_idx;
    while (ancestor_idx >= 0) {
        tc_component_type_entry_add_descendant(&g_component_registry.entries[ancestor_idx], idx);
        ancestor_idx = g_component_registry.entries[ancestor_idx].parent_index;
    }
}

void tc_component_registry_unregister(const char* type_name) {
    if (!type_name) return;

    int idx = tc_component_registry_find_index(type_name);
    if (idx < 0) return;

    // Shift remaining entries
    for (size_t i = (size_t)idx; i < g_component_registry.count - 1; i++) {
        g_component_registry.entries[i] = g_component_registry.entries[i + 1];
    }
    g_component_registry.count--;
}

bool tc_component_registry_has(const char* type_name) {
    return tc_component_registry_find_index(type_name) >= 0;
}

tc_component* tc_component_registry_create(const char* type_name) {
    int idx = tc_component_registry_find_index(type_name);
    if (idx < 0) return NULL;

    tc_component_factory factory = g_component_registry.entries[idx].factory;
    if (!factory) return NULL;

    tc_component* c = factory();
    if (c) {
        c->kind = g_component_registry.entries[idx].kind;
    }
    return c;
}

size_t tc_component_registry_type_count(void) {
    return g_component_registry.count;
}

const char* tc_component_registry_type_at(size_t index) {
    if (index >= g_component_registry.count) return NULL;
    return g_component_registry.entries[index].type_name;
}

size_t tc_component_registry_get_type_and_descendants(
    const char* type_name,
    const char** out_names,
    size_t max_count
) {
    if (!type_name || !out_names || max_count == 0) return 0;

    int idx = tc_component_registry_find_index(type_name);
    if (idx < 0) return 0;

    size_t count = 0;

    // Add the type itself
    out_names[count++] = g_component_registry.entries[idx].type_name;

    // Add all descendants
    tc_component_type_entry* entry = &g_component_registry.entries[idx];
    for (size_t i = 0; i < entry->descendant_count && count < max_count; i++) {
        int desc_idx = entry->descendant_indices[i];
        if (desc_idx >= 0 && (size_t)desc_idx < g_component_registry.count) {
            out_names[count++] = g_component_registry.entries[desc_idx].type_name;
        }
    }

    return count;
}

const char* tc_component_registry_get_parent(const char* type_name) {
    if (!type_name) return NULL;

    int idx = tc_component_registry_find_index(type_name);
    if (idx < 0) return NULL;

    int parent_idx = g_component_registry.entries[idx].parent_index;
    if (parent_idx < 0) return NULL;

    return g_component_registry.entries[parent_idx].type_name;
}

tc_component_kind tc_component_registry_get_kind(const char* type_name) {
    if (!type_name) return TC_PYTHON_COMPONENT;

    int idx = tc_component_registry_find_index(type_name);
    if (idx < 0) return TC_PYTHON_COMPONENT;

    return g_component_registry.entries[idx].kind;
}

void tc_component_registry_set_drawable(const char* type_name, bool is_drawable) {
    if (!type_name) return;

    int idx = tc_component_registry_find_index(type_name);
    if (idx < 0) return;

    g_component_registry.entries[idx].is_drawable = is_drawable;
}

bool tc_component_registry_is_drawable(const char* type_name) {
    if (!type_name) return false;

    int idx = tc_component_registry_find_index(type_name);
    if (idx < 0) return false;

    return g_component_registry.entries[idx].is_drawable;
}

size_t tc_component_registry_get_drawable_types(const char** out_names, size_t max_count) {
    if (!out_names || max_count == 0) return 0;

    size_t count = 0;
    for (size_t i = 0; i < g_component_registry.count && count < max_count; i++) {
        if (g_component_registry.entries[i].is_drawable) {
            out_names[count++] = g_component_registry.entries[i].type_name;
        }
    }
    return count;
}

void tc_component_registry_set_input_handler(const char* type_name, bool is_input_handler) {
    if (!type_name) return;

    int idx = tc_component_registry_find_index(type_name);
    if (idx < 0) return;

    g_component_registry.entries[idx].is_input_handler = is_input_handler;
}

bool tc_component_registry_is_input_handler(const char* type_name) {
    if (!type_name) return false;

    int idx = tc_component_registry_find_index(type_name);
    if (idx < 0) return false;

    return g_component_registry.entries[idx].is_input_handler;
}

size_t tc_component_registry_get_input_handler_types(const char** out_names, size_t max_count) {
    if (!out_names || max_count == 0) return 0;

    size_t count = 0;
    for (size_t i = 0; i < g_component_registry.count && count < max_count; i++) {
        if (g_component_registry.entries[i].is_input_handler) {
            out_names[count++] = g_component_registry.entries[i].type_name;
        }
    }
    return count;
}

// ============================================================================
// Registry cleanup (called by tc_shutdown)
// ============================================================================

void tc_component_registry_cleanup(void) {
    for (size_t i = 0; i < g_component_registry.count; i++) {
        free(g_component_registry.entries[i].descendant_indices);
    }
    free(g_component_registry.entries);
    g_component_registry.entries = NULL;
    g_component_registry.count = 0;
    g_component_registry.capacity = 0;
}
