// tc_entity_pool_registry.c - Registry for entity pools with generational handles
#include "../include/tc_entity_pool_registry.h"
#include "../include/tc_entity_pool.h"
#include "../include/tc_log.h"
#include <stdlib.h>
#include <string.h>

// ============================================================================
// Registry data structure
// ============================================================================

#define MAX_ENTITY_POOLS 64
#define INITIAL_REGISTRY_CAPACITY 8

typedef struct {
    // Generational data
    uint32_t* generations;
    bool* alive;

    // Pool pointers
    tc_entity_pool** pools;

    // Free list
    uint32_t* free_stack;
    size_t free_count;
    size_t capacity;
    size_t count;
} EntityPoolRegistry;

static EntityPoolRegistry* g_registry = NULL;
static tc_entity_pool_handle g_standalone_handle = {0xFFFFFFFF, 0};

// ============================================================================
// Registry lifecycle
// ============================================================================

void tc_entity_pool_registry_init(void) {
    if (g_registry) {
        return;
    }

    g_registry = (EntityPoolRegistry*)calloc(1, sizeof(EntityPoolRegistry));
    if (!g_registry) {
        tc_log_error("[tc_entity_pool_registry] allocation failed");
        return;
    }

    size_t cap = INITIAL_REGISTRY_CAPACITY;

    g_registry->generations = (uint32_t*)calloc(cap, sizeof(uint32_t));
    g_registry->alive = (bool*)calloc(cap, sizeof(bool));
    g_registry->pools = (tc_entity_pool**)calloc(cap, sizeof(tc_entity_pool*));
    g_registry->free_stack = (uint32_t*)malloc(cap * sizeof(uint32_t));

    // Initialize free stack
    for (size_t i = 0; i < cap; i++) {
        g_registry->free_stack[i] = (uint32_t)(cap - 1 - i);
    }
    g_registry->free_count = cap;
    g_registry->capacity = cap;
    g_registry->count = 0;
}

void tc_entity_pool_registry_shutdown(void) {
    if (!g_registry) {
        return;
    }

    // Destroy all alive pools
    for (size_t i = 0; i < g_registry->capacity; i++) {
        if (g_registry->alive[i] && g_registry->pools[i]) {
            tc_entity_pool_destroy(g_registry->pools[i]);
        }
    }

    free(g_registry->generations);
    free(g_registry->alive);
    free(g_registry->pools);
    free(g_registry->free_stack);
    free(g_registry);
    g_registry = NULL;
    g_standalone_handle = TC_ENTITY_POOL_HANDLE_INVALID;
}

// ============================================================================
// Registry growth
// ============================================================================

static void registry_grow(void) {
    size_t old_cap = g_registry->capacity;
    size_t new_cap = old_cap * 2;
    if (new_cap > MAX_ENTITY_POOLS) new_cap = MAX_ENTITY_POOLS;
    if (new_cap <= old_cap) {
        tc_log_error("[tc_entity_pool_registry] max capacity reached");
        return;
    }

    g_registry->generations = realloc(g_registry->generations, new_cap * sizeof(uint32_t));
    g_registry->alive = realloc(g_registry->alive, new_cap * sizeof(bool));
    g_registry->pools = realloc(g_registry->pools, new_cap * sizeof(tc_entity_pool*));
    g_registry->free_stack = realloc(g_registry->free_stack, new_cap * sizeof(uint32_t));

    // Initialize new slots
    memset(g_registry->generations + old_cap, 0, (new_cap - old_cap) * sizeof(uint32_t));
    memset(g_registry->alive + old_cap, 0, (new_cap - old_cap) * sizeof(bool));
    memset(g_registry->pools + old_cap, 0, (new_cap - old_cap) * sizeof(tc_entity_pool*));

    // Add new slots to free stack
    for (size_t i = old_cap; i < new_cap; i++) {
        g_registry->free_stack[g_registry->free_count++] = (uint32_t)(new_cap - 1 - (i - old_cap));
    }

    g_registry->capacity = new_cap;
}

// ============================================================================
// Handle validation
// ============================================================================

static inline bool handle_alive(tc_entity_pool_handle h) {
    if (!g_registry) return false;
    if (h.index >= g_registry->capacity) return false;
    return g_registry->alive[h.index] && g_registry->generations[h.index] == h.generation;
}

bool tc_entity_pool_registry_alive(tc_entity_pool_handle h) {
    return handle_alive(h);
}

// ============================================================================
// Pool allocation
// ============================================================================

tc_entity_pool_handle tc_entity_pool_registry_create(size_t initial_capacity) {
    // Auto-init
    if (!g_registry) {
        tc_entity_pool_registry_init();
    }

    if (g_registry->free_count == 0) {
        registry_grow();
        if (g_registry->free_count == 0) {
            tc_log_error("[tc_entity_pool_registry] no free slots");
            return TC_ENTITY_POOL_HANDLE_INVALID;
        }
    }

    uint32_t idx = g_registry->free_stack[--g_registry->free_count];
    uint32_t gen = g_registry->generations[idx];

    // Create the actual pool
    tc_entity_pool* pool = tc_entity_pool_create(initial_capacity);
    if (!pool) {
        // Return slot to free stack
        g_registry->free_stack[g_registry->free_count++] = idx;
        return TC_ENTITY_POOL_HANDLE_INVALID;
    }

    g_registry->alive[idx] = true;
    g_registry->pools[idx] = pool;
    g_registry->count++;

    tc_entity_pool_handle h = { idx, gen };
    return h;
}

void tc_entity_pool_registry_destroy(tc_entity_pool_handle h) {
    if (!handle_alive(h)) return;

    uint32_t idx = h.index;

    // Destroy the pool
    if (g_registry->pools[idx]) {
        tc_entity_pool_destroy(g_registry->pools[idx]);
        g_registry->pools[idx] = NULL;
    }

    // Mark as dead and bump generation
    g_registry->alive[idx] = false;
    g_registry->generations[idx]++;
    g_registry->free_stack[g_registry->free_count++] = idx;
    g_registry->count--;
}

tc_entity_pool* tc_entity_pool_registry_get(tc_entity_pool_handle h) {
    if (!handle_alive(h)) return NULL;
    return g_registry->pools[h.index];
}

tc_entity_pool_handle tc_entity_pool_registry_find(tc_entity_pool* pool) {
    if (!g_registry || !pool) return TC_ENTITY_POOL_HANDLE_INVALID;

    for (size_t i = 0; i < g_registry->capacity; i++) {
        if (g_registry->alive[i] && g_registry->pools[i] == pool) {
            tc_entity_pool_handle h = { (uint32_t)i, g_registry->generations[i] };
            return h;
        }
    }

    return TC_ENTITY_POOL_HANDLE_INVALID;
}

tc_entity_pool_handle tc_entity_pool_registry_register(tc_entity_pool* pool) {
    if (!pool) return TC_ENTITY_POOL_HANDLE_INVALID;

    // Auto-init
    if (!g_registry) {
        tc_entity_pool_registry_init();
    }

    // Check if already registered
    tc_entity_pool_handle existing = tc_entity_pool_registry_find(pool);
    if (tc_entity_pool_handle_valid(existing)) {
        return existing;
    }

    if (g_registry->free_count == 0) {
        registry_grow();
        if (g_registry->free_count == 0) {
            tc_log_error("[tc_entity_pool_registry] no free slots for register");
            return TC_ENTITY_POOL_HANDLE_INVALID;
        }
    }

    uint32_t idx = g_registry->free_stack[--g_registry->free_count];
    uint32_t gen = g_registry->generations[idx];

    g_registry->alive[idx] = true;
    g_registry->pools[idx] = pool;
    g_registry->count++;

    tc_entity_pool_handle h = { idx, gen };
    return h;
}

// ============================================================================
// Standalone pool
// ============================================================================

tc_entity_pool_handle tc_entity_pool_standalone_handle(void) {
    if (!tc_entity_pool_handle_valid(g_standalone_handle)) {
        g_standalone_handle = tc_entity_pool_registry_create(1024);
    }
    return g_standalone_handle;
}
