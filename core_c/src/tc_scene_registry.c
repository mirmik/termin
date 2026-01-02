// tc_scene_registry.c - Global scene registry implementation
#include "../include/tc_scene_registry.h"
#include "../include/tc_scene.h"
#include "../include/tc_entity_pool.h"
#include "../include/tc_log.h"
#include "../include/termin_core.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// ============================================================================
// Internal structures
// ============================================================================

#define INITIAL_CAPACITY 8

typedef struct {
    tc_scene* scene;
    const char* name;  // interned string
    int id;
} SceneEntry;

typedef struct {
    SceneEntry* entries;
    size_t count;
    size_t capacity;
    int next_id;
} SceneRegistry;

// ============================================================================
// Global state
// ============================================================================

static SceneRegistry* g_registry = NULL;

// ============================================================================
// Lifecycle
// ============================================================================

void tc_scene_registry_init(void) {
    if (g_registry) {
        tc_log_warn("tc_scene_registry_init: already initialized");
        return;
    }

    g_registry = (SceneRegistry*)calloc(1, sizeof(SceneRegistry));
    if (!g_registry) {
        tc_log_error("tc_scene_registry_init: allocation failed");
        return;
    }

    g_registry->entries = NULL;
    g_registry->count = 0;
    g_registry->capacity = 0;
    g_registry->next_id = 1;
}

void tc_scene_registry_shutdown(void) {
    if (!g_registry) {
        tc_log_warn("tc_scene_registry_shutdown: not initialized");
        return;
    }

    free(g_registry->entries);
    free(g_registry);
    g_registry = NULL;
}

// ============================================================================
// Registration
// ============================================================================

int tc_scene_registry_add(tc_scene* scene, const char* name) {
    // Auto-initialize if needed
    if (!g_registry) {
        tc_scene_registry_init();
    }

    if (!scene) {
        tc_log_error("tc_scene_registry_add: scene is NULL");
        return -1;
    }

    // Check if already registered
    for (size_t i = 0; i < g_registry->count; i++) {
        if (g_registry->entries[i].scene == scene) {
            tc_log_warn("tc_scene_registry_add: scene already registered (id=%d)",
                       g_registry->entries[i].id);
            return g_registry->entries[i].id;
        }
    }

    // Grow if needed
    if (g_registry->count >= g_registry->capacity) {
        size_t new_cap = g_registry->capacity == 0 ? INITIAL_CAPACITY : g_registry->capacity * 2;
        SceneEntry* new_entries = (SceneEntry*)realloc(
            g_registry->entries,
            new_cap * sizeof(SceneEntry)
        );
        if (!new_entries) {
            tc_log_error("tc_scene_registry_add: realloc failed");
            return -1;
        }
        g_registry->entries = new_entries;
        g_registry->capacity = new_cap;
    }

    // Add entry
    int id = g_registry->next_id++;
    SceneEntry* entry = &g_registry->entries[g_registry->count++];
    entry->scene = scene;
    entry->name = name ? tc_intern_string(name) : tc_intern_string("(unnamed)");
    entry->id = id;

    return id;
}

void tc_scene_registry_remove(tc_scene* scene) {
    if (!g_registry || !scene) return;

    for (size_t i = 0; i < g_registry->count; i++) {
        if (g_registry->entries[i].scene == scene) {
            // Swap with last and shrink
            g_registry->entries[i] = g_registry->entries[--g_registry->count];
            return;
        }
    }
}

const char* tc_scene_registry_get_name(const tc_scene* scene) {
    if (!g_registry || !scene) return NULL;

    for (size_t i = 0; i < g_registry->count; i++) {
        if (g_registry->entries[i].scene == scene) {
            return g_registry->entries[i].name;
        }
    }
    return NULL;
}

void tc_scene_registry_set_name(tc_scene* scene, const char* name) {
    if (!g_registry || !scene) return;

    for (size_t i = 0; i < g_registry->count; i++) {
        if (g_registry->entries[i].scene == scene) {
            g_registry->entries[i].name = name ? tc_intern_string(name) : tc_intern_string("(unnamed)");
            return;
        }
    }
}

// ============================================================================
// Queries
// ============================================================================

size_t tc_scene_registry_count(void) {
    return g_registry ? g_registry->count : 0;
}

// ============================================================================
// Iteration and info
// ============================================================================

void tc_scene_registry_foreach(tc_scene_iter_fn callback, void* user_data) {
    if (!g_registry || !callback) return;

    for (size_t i = 0; i < g_registry->count; i++) {
        SceneEntry* entry = &g_registry->entries[i];
        if (!callback(entry->scene, entry->id, user_data)) {
            break;
        }
    }
}

tc_scene_info* tc_scene_registry_get_all_info(size_t* count) {
    if (!count) return NULL;
    *count = 0;

    if (!g_registry || g_registry->count == 0) return NULL;

    tc_scene_info* infos = (tc_scene_info*)malloc(
        g_registry->count * sizeof(tc_scene_info)
    );
    if (!infos) {
        tc_log_error("tc_scene_registry_get_all_info: allocation failed");
        return NULL;
    }

    for (size_t i = 0; i < g_registry->count; i++) {
        SceneEntry* entry = &g_registry->entries[i];
        tc_scene* scene = entry->scene;

        infos[i].id = entry->id;
        infos[i].name = entry->name;
        infos[i].entity_count = tc_scene_entity_count(scene);
        infos[i].pending_count = tc_scene_pending_start_count(scene);
        infos[i].update_count = tc_scene_update_list_count(scene);
        infos[i].fixed_update_count = tc_scene_fixed_update_list_count(scene);
    }

    *count = g_registry->count;
    return infos;
}

// ============================================================================
// Entity enumeration
// ============================================================================

// Helper for collecting entity info
typedef struct {
    tc_scene_entity_info* infos;
    size_t count;
    size_t capacity;
    tc_entity_pool* pool;
} EntityCollector;

static bool collect_entity_info(tc_entity_pool* pool, tc_entity_id id, void* user_data) {
    EntityCollector* c = (EntityCollector*)user_data;

    if (c->count >= c->capacity) {
        // Grow array
        size_t new_cap = c->capacity == 0 ? 64 : c->capacity * 2;
        tc_scene_entity_info* new_infos = (tc_scene_entity_info*)realloc(
            c->infos, new_cap * sizeof(tc_scene_entity_info)
        );
        if (!new_infos) return false;
        c->infos = new_infos;
        c->capacity = new_cap;
    }

    tc_scene_entity_info* info = &c->infos[c->count++];
    info->name = tc_entity_pool_name(pool, id);
    info->uuid = tc_entity_pool_uuid(pool, id);
    info->component_count = tc_entity_pool_component_count(pool, id);
    info->visible = tc_entity_pool_visible(pool, id);
    info->active = tc_entity_pool_active(pool, id);

    return true;
}

tc_scene_entity_info* tc_scene_get_entities(int scene_id, size_t* count) {
    if (!count) return NULL;
    *count = 0;

    if (!g_registry) return NULL;

    // Find scene by ID
    tc_scene* scene = NULL;
    for (size_t i = 0; i < g_registry->count; i++) {
        if (g_registry->entries[i].id == scene_id) {
            scene = g_registry->entries[i].scene;
            break;
        }
    }

    if (!scene) return NULL;

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    if (!pool) return NULL;

    size_t entity_count = tc_entity_pool_count(pool);
    if (entity_count == 0) return NULL;

    EntityCollector collector = { NULL, 0, 0, pool };

    tc_entity_pool_foreach(pool, collect_entity_info, &collector);

    *count = collector.count;
    return collector.infos;
}

// ============================================================================
// Component type enumeration
// ============================================================================

tc_scene_component_type_info* tc_scene_get_component_types(int scene_id, size_t* count) {
    if (!count) return NULL;
    *count = 0;

    if (!g_registry) return NULL;

    // Find scene by ID
    tc_scene* scene = NULL;
    for (size_t i = 0; i < g_registry->count; i++) {
        if (g_registry->entries[i].id == scene_id) {
            scene = g_registry->entries[i].scene;
            break;
        }
    }

    if (!scene) return NULL;

    // Get component types directly from scene's type_heads
    size_t type_count = 0;
    tc_scene_component_type* types = tc_scene_get_all_component_types(scene, &type_count);

    if (!types || type_count == 0) return NULL;

    // Convert to tc_scene_component_type_info (same structure, different typedef)
    tc_scene_component_type_info* infos = (tc_scene_component_type_info*)malloc(
        type_count * sizeof(tc_scene_component_type_info)
    );
    if (!infos) {
        free(types);
        return NULL;
    }

    for (size_t i = 0; i < type_count; i++) {
        infos[i].type_name = types[i].type_name;
        infos[i].count = types[i].count;
    }

    free(types);
    *count = type_count;
    return infos;
}
