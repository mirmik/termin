// tc_component.c - Component registry implementation
#include "../include/tc_component.h"
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

void tc_component_registry_register(
    const char* type_name,
    tc_component_factory factory,
    tc_component_kind kind
) {
    if (!type_name || !factory) return;

    // Check if already registered
    int idx = tc_component_registry_find_index(type_name);
    if (idx >= 0) {
        // Update existing
        g_component_registry.entries[idx].factory = factory;
        g_component_registry.entries[idx].kind = kind;
        return;
    }

    // Add new
    tc_component_registry_ensure_capacity();
    if (g_component_registry.count >= g_component_registry.capacity) return;

    // Intern the string (caller must ensure it stays valid, or use tc_intern_string)
    g_component_registry.entries[g_component_registry.count].type_name = type_name;
    g_component_registry.entries[g_component_registry.count].factory = factory;
    g_component_registry.entries[g_component_registry.count].kind = kind;
    g_component_registry.count++;
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

// ============================================================================
// Registry cleanup (called by tc_shutdown)
// ============================================================================

void tc_component_registry_cleanup(void) {
    free(g_component_registry.entries);
    g_component_registry.entries = NULL;
    g_component_registry.count = 0;
    g_component_registry.capacity = 0;
}
