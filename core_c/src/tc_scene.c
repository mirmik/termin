// tc_scene.c - Scene implementation using pool with generational indices
#include "../include/tc_scene.h"
#include "../include/tc_scene_pool.h"
#include "../include/tc_scene_lighting.h"
#include "../include/tc_scene_skybox.h"
#include "../include/tc_resource_map.h"
#include "../include/tc_profiler.h"
#include "../include/tc_mesh.h"
#include "../include/tc_material.h"
#include "../include/tc_log.h"
#include "../include/tc_entity_pool_registry.h"
#include "../include/termin_core.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// ============================================================================
// Scene Lighting Defaults
// ============================================================================

void tc_scene_lighting_init(tc_scene_lighting* lighting) {
    if (!lighting) return;
    lighting->ambient_color[0] = 1.0f;
    lighting->ambient_color[1] = 1.0f;
    lighting->ambient_color[2] = 1.0f;
    lighting->ambient_intensity = 0.1f;
    lighting->shadow_method = TC_SHADOW_METHOD_PCF;
    lighting->shadow_softness = 1.0f;
    lighting->shadow_bias = 0.005f;
}

// ============================================================================
// Dynamic array for components
// ============================================================================

#define INITIAL_CAPACITY 64

typedef struct {
    tc_component** items;
    size_t count;
    size_t capacity;
} ComponentList;

static void list_init(ComponentList* list) {
    list->items = NULL;
    list->count = 0;
    list->capacity = 0;
}

static void list_free(ComponentList* list) {
    free(list->items);
    list->items = NULL;
    list->count = 0;
    list->capacity = 0;
}

static void list_push(ComponentList* list, tc_component* c) {
    if (list->count >= list->capacity) {
        size_t new_cap = list->capacity == 0 ? INITIAL_CAPACITY : list->capacity * 2;
        list->items = realloc(list->items, new_cap * sizeof(tc_component*));
        list->capacity = new_cap;
    }
    list->items[list->count++] = c;
}

static void list_remove(ComponentList* list, tc_component* c) {
    for (size_t i = 0; i < list->count; i++) {
        if (list->items[i] == c) {
            list->items[i] = list->items[--list->count];
            return;
        }
    }
}

static bool list_contains(ComponentList* list, tc_component* c) {
    for (size_t i = 0; i < list->count; i++) {
        if (list->items[i] == c) return true;
    }
    return false;
}

// ============================================================================
// Scene Pool - Global singleton
// ============================================================================

#define MAX_SCENES 256
#define INITIAL_POOL_CAPACITY 16

typedef struct {
    // Generational data
    uint32_t* generations;
    bool* alive;

    // Scene data arrays (SoA)
    tc_entity_pool** pools;
    tc_scene_mode* modes;
    ComponentList* pending_starts;
    ComponentList* update_lists;
    ComponentList* fixed_update_lists;
    ComponentList* before_render_lists;
    double* fixed_timesteps;
    double* accumulated_times;
    void** py_wrappers;
    tc_resource_map** type_heads;
    tc_scene_lighting* lightings;
    tc_scene_skybox* skyboxes;
    void** collision_worlds;
    const char** names;

    // Pool management
    uint32_t* free_stack;
    size_t free_count;
    size_t capacity;
    size_t count;
} ScenePool;

static ScenePool* g_pool = NULL;

// ============================================================================
// Pool Lifecycle
// ============================================================================

void tc_scene_pool_init(void) {
    if (g_pool) {
        tc_log_warn("[tc_scene_pool] already initialized");
        return;
    }

    g_pool = (ScenePool*)calloc(1, sizeof(ScenePool));
    if (!g_pool) {
        tc_log_error("[tc_scene_pool] allocation failed");
        return;
    }

    size_t cap = INITIAL_POOL_CAPACITY;

    g_pool->generations = (uint32_t*)calloc(cap, sizeof(uint32_t));
    g_pool->alive = (bool*)calloc(cap, sizeof(bool));
    g_pool->pools = (tc_entity_pool**)calloc(cap, sizeof(tc_entity_pool*));
    g_pool->modes = (tc_scene_mode*)calloc(cap, sizeof(tc_scene_mode));
    g_pool->pending_starts = (ComponentList*)calloc(cap, sizeof(ComponentList));
    g_pool->update_lists = (ComponentList*)calloc(cap, sizeof(ComponentList));
    g_pool->fixed_update_lists = (ComponentList*)calloc(cap, sizeof(ComponentList));
    g_pool->before_render_lists = (ComponentList*)calloc(cap, sizeof(ComponentList));
    g_pool->fixed_timesteps = (double*)calloc(cap, sizeof(double));
    g_pool->accumulated_times = (double*)calloc(cap, sizeof(double));
    g_pool->py_wrappers = (void**)calloc(cap, sizeof(void*));
    g_pool->type_heads = (tc_resource_map**)calloc(cap, sizeof(tc_resource_map*));
    g_pool->lightings = (tc_scene_lighting*)calloc(cap, sizeof(tc_scene_lighting));
    g_pool->skyboxes = (tc_scene_skybox*)calloc(cap, sizeof(tc_scene_skybox));
    g_pool->collision_worlds = (void**)calloc(cap, sizeof(void*));
    g_pool->names = (const char**)calloc(cap, sizeof(const char*));

    g_pool->free_stack = (uint32_t*)malloc(cap * sizeof(uint32_t));
    for (size_t i = 0; i < cap; i++) {
        g_pool->free_stack[i] = (uint32_t)(cap - 1 - i);
    }
    g_pool->free_count = cap;
    g_pool->capacity = cap;
    g_pool->count = 0;
}

void tc_scene_pool_shutdown(void) {
    if (!g_pool) {
        tc_log_warn("[tc_scene_pool] not initialized");
        return;
    }

    // Free all alive scenes
    for (size_t i = 0; i < g_pool->capacity; i++) {
        if (g_pool->alive[i]) {
            tc_scene_handle h = { (uint32_t)i, g_pool->generations[i] };
            tc_scene_free(h);
        }
    }

    free(g_pool->generations);
    free(g_pool->alive);
    free(g_pool->pools);
    free(g_pool->modes);
    free(g_pool->pending_starts);
    free(g_pool->update_lists);
    free(g_pool->fixed_update_lists);
    free(g_pool->before_render_lists);
    free(g_pool->fixed_timesteps);
    free(g_pool->accumulated_times);
    free(g_pool->py_wrappers);
    free(g_pool->type_heads);
    free(g_pool->lightings);
    free(g_pool->skyboxes);
    free(g_pool->collision_worlds);
    free(g_pool->names);
    free(g_pool->free_stack);
    free(g_pool);
    g_pool = NULL;
}

// ============================================================================
// Pool Growth
// ============================================================================

static void pool_grow(void) {
    size_t old_cap = g_pool->capacity;
    size_t new_cap = old_cap * 2;
    if (new_cap > MAX_SCENES) new_cap = MAX_SCENES;
    if (new_cap <= old_cap) {
        tc_log_error("[tc_scene_pool] max capacity reached");
        return;
    }

    g_pool->generations = realloc(g_pool->generations, new_cap * sizeof(uint32_t));
    g_pool->alive = realloc(g_pool->alive, new_cap * sizeof(bool));
    g_pool->pools = realloc(g_pool->pools, new_cap * sizeof(tc_entity_pool*));
    g_pool->modes = realloc(g_pool->modes, new_cap * sizeof(tc_scene_mode));
    g_pool->pending_starts = realloc(g_pool->pending_starts, new_cap * sizeof(ComponentList));
    g_pool->update_lists = realloc(g_pool->update_lists, new_cap * sizeof(ComponentList));
    g_pool->fixed_update_lists = realloc(g_pool->fixed_update_lists, new_cap * sizeof(ComponentList));
    g_pool->before_render_lists = realloc(g_pool->before_render_lists, new_cap * sizeof(ComponentList));
    g_pool->fixed_timesteps = realloc(g_pool->fixed_timesteps, new_cap * sizeof(double));
    g_pool->accumulated_times = realloc(g_pool->accumulated_times, new_cap * sizeof(double));
    g_pool->py_wrappers = realloc(g_pool->py_wrappers, new_cap * sizeof(void*));
    g_pool->type_heads = realloc(g_pool->type_heads, new_cap * sizeof(tc_resource_map*));
    g_pool->lightings = realloc(g_pool->lightings, new_cap * sizeof(tc_scene_lighting));
    g_pool->skyboxes = realloc(g_pool->skyboxes, new_cap * sizeof(tc_scene_skybox));
    g_pool->collision_worlds = realloc(g_pool->collision_worlds, new_cap * sizeof(void*));
    g_pool->names = realloc(g_pool->names, new_cap * sizeof(const char*));
    g_pool->free_stack = realloc(g_pool->free_stack, new_cap * sizeof(uint32_t));

    // Initialize new slots
    memset(g_pool->generations + old_cap, 0, (new_cap - old_cap) * sizeof(uint32_t));
    memset(g_pool->alive + old_cap, 0, (new_cap - old_cap) * sizeof(bool));
    memset(g_pool->pools + old_cap, 0, (new_cap - old_cap) * sizeof(tc_entity_pool*));
    memset(g_pool->modes + old_cap, 0, (new_cap - old_cap) * sizeof(tc_scene_mode));
    memset(g_pool->pending_starts + old_cap, 0, (new_cap - old_cap) * sizeof(ComponentList));
    memset(g_pool->update_lists + old_cap, 0, (new_cap - old_cap) * sizeof(ComponentList));
    memset(g_pool->fixed_update_lists + old_cap, 0, (new_cap - old_cap) * sizeof(ComponentList));
    memset(g_pool->before_render_lists + old_cap, 0, (new_cap - old_cap) * sizeof(ComponentList));
    memset(g_pool->fixed_timesteps + old_cap, 0, (new_cap - old_cap) * sizeof(double));
    memset(g_pool->accumulated_times + old_cap, 0, (new_cap - old_cap) * sizeof(double));
    memset(g_pool->py_wrappers + old_cap, 0, (new_cap - old_cap) * sizeof(void*));
    memset(g_pool->type_heads + old_cap, 0, (new_cap - old_cap) * sizeof(tc_resource_map*));
    memset(g_pool->lightings + old_cap, 0, (new_cap - old_cap) * sizeof(tc_scene_lighting));
    memset(g_pool->skyboxes + old_cap, 0, (new_cap - old_cap) * sizeof(tc_scene_skybox));
    memset(g_pool->collision_worlds + old_cap, 0, (new_cap - old_cap) * sizeof(void*));
    memset(g_pool->names + old_cap, 0, (new_cap - old_cap) * sizeof(const char*));

    // Add new slots to free stack
    for (size_t i = old_cap; i < new_cap; i++) {
        g_pool->free_stack[g_pool->free_count++] = (uint32_t)(new_cap - 1 - (i - old_cap));
    }

    g_pool->capacity = new_cap;
}

// ============================================================================
// Handle validation
// ============================================================================

static inline bool handle_alive(tc_scene_handle h) {
    if (!g_pool) return false;
    if (h.index >= g_pool->capacity) return false;
    return g_pool->alive[h.index] && g_pool->generations[h.index] == h.generation;
}

bool tc_scene_pool_alive(tc_scene_handle h) {
    return handle_alive(h);
}

bool tc_scene_alive(tc_scene_handle h) {
    return handle_alive(h);
}

// ============================================================================
// Scene Creation / Destruction
// ============================================================================

tc_scene_handle tc_scene_pool_alloc(const char* name) {
    // Auto-init if needed
    if (!g_pool) {
        tc_scene_pool_init();
    }

    if (g_pool->free_count == 0) {
        pool_grow();
        if (g_pool->free_count == 0) {
            tc_log_error("[tc_scene_pool] no free slots");
            return TC_SCENE_HANDLE_INVALID;
        }
    }

    uint32_t idx = g_pool->free_stack[--g_pool->free_count];
    uint32_t gen = g_pool->generations[idx];

    // Initialize slot
    g_pool->alive[idx] = true;
    // Create pool and register it in the entity pool registry for safe handle-based access
    g_pool->pools[idx] = tc_entity_pool_create(512);
    tc_entity_pool_registry_register(g_pool->pools[idx]);
    g_pool->modes[idx] = TC_SCENE_MODE_INACTIVE;
    list_init(&g_pool->pending_starts[idx]);
    list_init(&g_pool->update_lists[idx]);
    list_init(&g_pool->fixed_update_lists[idx]);
    list_init(&g_pool->before_render_lists[idx]);
    g_pool->fixed_timesteps[idx] = 1.0 / 60.0;
    g_pool->accumulated_times[idx] = 0.0;
    g_pool->py_wrappers[idx] = NULL;
    g_pool->type_heads[idx] = tc_resource_map_new(NULL);
    tc_scene_lighting_init(&g_pool->lightings[idx]);
    tc_scene_skybox_init(&g_pool->skyboxes[idx]);
    g_pool->collision_worlds[idx] = NULL;
    g_pool->names[idx] = name ? tc_intern_string(name) : tc_intern_string("(unnamed)");

    tc_scene_handle h = { idx, gen };

    // Set scene handle on entity pool
    tc_entity_pool_set_scene(g_pool->pools[idx], h);

    g_pool->count++;

    return h;
}

tc_scene_handle tc_scene_new(void) {
    return tc_scene_pool_alloc(NULL);
}

tc_scene_handle tc_scene_new_named(const char* name) {
    return tc_scene_pool_alloc(name);
}

void tc_scene_pool_free(tc_scene_handle h) {
    tc_scene_free(h);
}

void tc_scene_free(tc_scene_handle h) {
    if (!handle_alive(h)) return;

    uint32_t idx = h.index;

    // Release skybox resources
    tc_scene_skybox_free(&g_pool->skyboxes[idx]);

    // Free component lists
    list_free(&g_pool->pending_starts[idx]);
    list_free(&g_pool->update_lists[idx]);
    list_free(&g_pool->fixed_update_lists[idx]);
    list_free(&g_pool->before_render_lists[idx]);

    // Free type heads map
    tc_resource_map_free(g_pool->type_heads[idx]);
    g_pool->type_heads[idx] = NULL;

    // Destroy entity pool via registry to invalidate handles
    tc_entity_pool_handle pool_handle = tc_entity_pool_registry_find(g_pool->pools[idx]);
    if (tc_entity_pool_handle_valid(pool_handle)) {
        tc_entity_pool_registry_destroy(pool_handle);
    } else {
        // Fallback: pool not in registry, destroy directly
        tc_entity_pool_destroy(g_pool->pools[idx]);
    }
    g_pool->pools[idx] = NULL;

    // Mark as dead
    g_pool->alive[idx] = false;
    g_pool->generations[idx]++;
    g_pool->free_stack[g_pool->free_count++] = idx;
    g_pool->count--;
}

// ============================================================================
// Pool Queries
// ============================================================================

size_t tc_scene_pool_count(void) {
    return g_pool ? g_pool->count : 0;
}

const char* tc_scene_pool_get_name(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return g_pool->names[h.index];
}

void tc_scene_pool_set_name(tc_scene_handle h, const char* name) {
    if (!handle_alive(h)) return;
    g_pool->names[h.index] = name ? tc_intern_string(name) : tc_intern_string("(unnamed)");
}

const char* tc_scene_get_name(tc_scene_handle h) {
    return tc_scene_pool_get_name(h);
}

void tc_scene_set_name(tc_scene_handle h, const char* name) {
    tc_scene_pool_set_name(h, name);
}

// ============================================================================
// Pool Iteration
// ============================================================================

void tc_scene_pool_foreach(tc_scene_pool_iter_fn callback, void* user_data) {
    if (!g_pool || !callback) return;

    for (size_t i = 0; i < g_pool->capacity; i++) {
        if (g_pool->alive[i]) {
            tc_scene_handle h = { (uint32_t)i, g_pool->generations[i] };
            if (!callback(h, user_data)) {
                break;
            }
        }
    }
}

tc_scene_info* tc_scene_pool_get_all_info(size_t* count) {
    if (!count) return NULL;
    *count = 0;

    if (!g_pool || g_pool->count == 0) return NULL;

    tc_scene_info* infos = (tc_scene_info*)malloc(g_pool->count * sizeof(tc_scene_info));
    if (!infos) return NULL;

    size_t idx = 0;
    for (size_t i = 0; i < g_pool->capacity && idx < g_pool->count; i++) {
        if (g_pool->alive[i]) {
            tc_scene_handle h = { (uint32_t)i, g_pool->generations[i] };
            infos[idx].handle = h;
            infos[idx].name = g_pool->names[i];
            infos[idx].entity_count = tc_entity_pool_count(g_pool->pools[i]);
            infos[idx].pending_count = g_pool->pending_starts[i].count;
            infos[idx].update_count = g_pool->update_lists[i].count;
            infos[idx].fixed_update_count = g_pool->fixed_update_lists[i].count;
            idx++;
        }
    }

    *count = idx;
    return infos;
}

// ============================================================================
// Entity Pool Access
// ============================================================================

tc_entity_pool* tc_scene_entity_pool(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return g_pool->pools[h.index];
}

// ============================================================================
// Collision World
// ============================================================================

void* tc_scene_get_collision_world(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return g_pool->collision_worlds[h.index];
}

void tc_scene_set_collision_world(tc_scene_handle h, void* cw) {
    if (!handle_alive(h)) return;
    g_pool->collision_worlds[h.index] = cw;
}

// ============================================================================
// Component Registration
// ============================================================================

void tc_scene_register_component(tc_scene_handle h, tc_component* c) {
    if (!handle_alive(h) || !c) return;

    uint32_t idx = h.index;

    // Add to pending_start if not started
    if (!c->_started && !list_contains(&g_pool->pending_starts[idx], c)) {
        list_push(&g_pool->pending_starts[idx], c);
    }

    // Add to update lists based on flags
    if (c->has_update && !list_contains(&g_pool->update_lists[idx], c)) {
        list_push(&g_pool->update_lists[idx], c);
    }
    if (c->has_fixed_update && !list_contains(&g_pool->fixed_update_lists[idx], c)) {
        list_push(&g_pool->fixed_update_lists[idx], c);
    }
    if (c->has_before_render && !list_contains(&g_pool->before_render_lists[idx], c)) {
        list_push(&g_pool->before_render_lists[idx], c);
    }

    // Add to type list (intrusive doubly-linked list)
    const char* type_name = tc_component_type_name(c);
    if (type_name && c->type_prev == NULL && c->type_next == NULL) {
        tc_component* head = (tc_component*)tc_resource_map_get(g_pool->type_heads[idx], type_name);
        if (head == NULL) {
            tc_resource_map_add(g_pool->type_heads[idx], type_name, c);
        } else if (head != c) {
            c->type_next = head;
            head->type_prev = c;
            tc_resource_map_remove(g_pool->type_heads[idx], type_name);
            tc_resource_map_add(g_pool->type_heads[idx], type_name, c);
        }
    }
}

void tc_scene_unregister_component(tc_scene_handle h, tc_component* c) {
    if (!handle_alive(h) || !c) return;

    uint32_t idx = h.index;

    list_remove(&g_pool->pending_starts[idx], c);
    list_remove(&g_pool->update_lists[idx], c);
    list_remove(&g_pool->fixed_update_lists[idx], c);
    list_remove(&g_pool->before_render_lists[idx], c);

    // Remove from type list
    const char* type_name = tc_component_type_name(c);
    if (type_name) {
        tc_component* head = (tc_component*)tc_resource_map_get(g_pool->type_heads[idx], type_name);
        if (head == c) {
            tc_resource_map_remove(g_pool->type_heads[idx], type_name);
            if (c->type_next) {
                c->type_next->type_prev = NULL;
                tc_resource_map_add(g_pool->type_heads[idx], type_name, c->type_next);
            }
        } else {
            if (c->type_prev) c->type_prev->type_next = c->type_next;
            if (c->type_next) c->type_next->type_prev = c->type_prev;
        }
        c->type_prev = NULL;
        c->type_next = NULL;
    }

    tc_component_on_removed(c);
}

// ============================================================================
// Update Loop
// ============================================================================

static void process_pending_start(uint32_t idx, bool editor_mode) {
    ComponentList* pending = &g_pool->pending_starts[idx];
    size_t count = pending->count;
    if (count == 0) return;

    tc_component** copy = malloc(count * sizeof(tc_component*));
    memcpy(copy, pending->items, count * sizeof(tc_component*));

    for (size_t i = 0; i < count; i++) {
        tc_component* c = copy[i];
        if (!c->enabled) continue;
        if (editor_mode && !c->active_in_editor) continue;

        tc_component_start(c);
        list_remove(pending, c);
    }

    free(copy);
}

static inline bool component_entity_enabled(tc_component* c) {
    if (!c->owner_pool) return true;
    return tc_entity_pool_enabled(c->owner_pool, c->owner_entity_id);
}

void tc_scene_update(tc_scene_handle h, double dt) {
    if (!handle_alive(h)) return;

    uint32_t idx = h.index;
    bool profile = tc_profiler_enabled();

    // 1. Process pending start
    if (profile) tc_profiler_begin_section("Pending Start");
    process_pending_start(idx, false);
    if (profile) tc_profiler_end_section();

    // 2. Fixed update loop
    if (profile) tc_profiler_begin_section("Fixed Update");
    g_pool->accumulated_times[idx] += dt;
    double fixed_dt = g_pool->fixed_timesteps[idx];
    ComponentList* fixed_list = &g_pool->fixed_update_lists[idx];

    while (g_pool->accumulated_times[idx] >= fixed_dt) {
        for (size_t i = 0; i < fixed_list->count; i++) {
            tc_component* c = fixed_list->items[i];
            if (c->enabled && component_entity_enabled(c)) {
                if (profile) tc_profiler_begin_section(tc_component_type_name(c));
                tc_component_fixed_update(c, (float)fixed_dt);
                if (profile) tc_profiler_end_section();
            }
        }
        g_pool->accumulated_times[idx] -= fixed_dt;
    }
    if (profile) tc_profiler_end_section();

    // 3. Regular update
    if (profile) tc_profiler_begin_section("Update");
    ComponentList* update_list = &g_pool->update_lists[idx];
    for (size_t i = 0; i < update_list->count; i++) {
        tc_component* c = update_list->items[i];
        if (c->enabled && component_entity_enabled(c)) {
            if (profile) tc_profiler_begin_section(tc_component_type_name(c));
            tc_component_update(c, (float)dt);
            if (profile) tc_profiler_end_section();
        }
    }
    if (profile) tc_profiler_end_section();
}

void tc_scene_editor_update(tc_scene_handle h, double dt) {
    if (!handle_alive(h)) return;

    uint32_t idx = h.index;
    bool profile = tc_profiler_enabled();

    if (profile) tc_profiler_begin_section("Pending Start");
    process_pending_start(idx, true);
    if (profile) tc_profiler_end_section();

    // Fixed update - only active_in_editor
    if (profile) tc_profiler_begin_section("Fixed Update");
    g_pool->accumulated_times[idx] += dt;
    double fixed_dt = g_pool->fixed_timesteps[idx];
    ComponentList* fixed_list = &g_pool->fixed_update_lists[idx];

    while (g_pool->accumulated_times[idx] >= fixed_dt) {
        for (size_t i = 0; i < fixed_list->count; i++) {
            tc_component* c = fixed_list->items[i];
            if (c->enabled && c->active_in_editor && component_entity_enabled(c)) {
                if (profile) tc_profiler_begin_section(tc_component_type_name(c));
                tc_component_fixed_update(c, (float)fixed_dt);
                if (profile) tc_profiler_end_section();
            }
        }
        g_pool->accumulated_times[idx] -= fixed_dt;
    }
    if (profile) tc_profiler_end_section();

    // Regular update - only active_in_editor
    if (profile) tc_profiler_begin_section("Update");
    ComponentList* update_list = &g_pool->update_lists[idx];
    for (size_t i = 0; i < update_list->count; i++) {
        tc_component* c = update_list->items[i];
        if (c->enabled && c->active_in_editor && component_entity_enabled(c)) {
            if (profile) tc_profiler_begin_section(tc_component_type_name(c));
            tc_component_update(c, (float)dt);
            if (profile) tc_profiler_end_section();
        }
    }
    if (profile) tc_profiler_end_section();
}

void tc_scene_before_render(tc_scene_handle h) {
    if (!handle_alive(h)) return;

    uint32_t idx = h.index;
    bool profile = tc_profiler_enabled();
    ComponentList* list = &g_pool->before_render_lists[idx];

    for (size_t i = 0; i < list->count; i++) {
        tc_component* c = list->items[i];
        if (c->enabled && component_entity_enabled(c)) {
            if (profile) tc_profiler_begin_section(tc_component_type_name(c));
            tc_component_before_render(c);
            if (profile) tc_profiler_end_section();
        }
    }
}

// ============================================================================
// Notification helpers
// ============================================================================

static bool notify_editor_start_callback(tc_entity_pool* pool, tc_entity_id id, void* user_data) {
    (void)user_data;
    size_t count = tc_entity_pool_component_count(pool, id);
    for (size_t i = 0; i < count; i++) {
        tc_component* c = tc_entity_pool_component_at(pool, id, i);
        if (c && c->vtable && c->vtable->on_editor_start) {
            c->vtable->on_editor_start(c);
        }
    }
    return true;
}

void tc_scene_notify_editor_start(tc_scene_handle h) {
    if (!handle_alive(h)) return;
    tc_entity_pool_foreach(g_pool->pools[h.index], notify_editor_start_callback, NULL);
}

static bool notify_scene_inactive_callback(tc_entity_pool* pool, tc_entity_id id, void* user_data) {
    (void)user_data;
    size_t count = tc_entity_pool_component_count(pool, id);
    for (size_t i = 0; i < count; i++) {
        tc_component* c = tc_entity_pool_component_at(pool, id, i);
        if (c && c->vtable && c->vtable->on_scene_inactive) {
            c->vtable->on_scene_inactive(c);
        }
    }
    return true;
}

void tc_scene_notify_scene_inactive(tc_scene_handle h) {
    if (!handle_alive(h)) return;
    tc_entity_pool_foreach(g_pool->pools[h.index], notify_scene_inactive_callback, NULL);
}

static bool notify_scene_active_callback(tc_entity_pool* pool, tc_entity_id id, void* user_data) {
    (void)user_data;
    size_t count = tc_entity_pool_component_count(pool, id);
    for (size_t i = 0; i < count; i++) {
        tc_component* c = tc_entity_pool_component_at(pool, id, i);
        if (c && c->vtable && c->vtable->on_scene_active) {
            c->vtable->on_scene_active(c);
        }
    }
    return true;
}

void tc_scene_notify_scene_active(tc_scene_handle h) {
    if (!handle_alive(h)) return;
    tc_entity_pool_foreach(g_pool->pools[h.index], notify_scene_active_callback, NULL);
}

// ============================================================================
// Fixed Timestep Configuration
// ============================================================================

double tc_scene_fixed_timestep(tc_scene_handle h) {
    if (!handle_alive(h)) return 1.0 / 60.0;
    return g_pool->fixed_timesteps[h.index];
}

void tc_scene_set_fixed_timestep(tc_scene_handle h, double dt) {
    if (!handle_alive(h) || dt <= 0) return;
    g_pool->fixed_timesteps[h.index] = dt;
}

double tc_scene_accumulated_time(tc_scene_handle h) {
    if (!handle_alive(h)) return 0.0;
    return g_pool->accumulated_times[h.index];
}

void tc_scene_reset_accumulated_time(tc_scene_handle h) {
    if (!handle_alive(h)) return;
    g_pool->accumulated_times[h.index] = 0.0;
}

// ============================================================================
// Component Queries
// ============================================================================

size_t tc_scene_entity_count(tc_scene_handle h) {
    if (!handle_alive(h)) return 0;
    return tc_entity_pool_count(g_pool->pools[h.index]);
}

size_t tc_scene_pending_start_count(tc_scene_handle h) {
    if (!handle_alive(h)) return 0;
    return g_pool->pending_starts[h.index].count;
}

size_t tc_scene_update_list_count(tc_scene_handle h) {
    if (!handle_alive(h)) return 0;
    return g_pool->update_lists[h.index].count;
}

size_t tc_scene_fixed_update_list_count(tc_scene_handle h) {
    if (!handle_alive(h)) return 0;
    return g_pool->fixed_update_lists[h.index].count;
}

// ============================================================================
// Python Wrapper Access
// ============================================================================

void tc_scene_set_py_wrapper(tc_scene_handle h, void* py_wrapper) {
    if (!handle_alive(h)) return;
    g_pool->py_wrappers[h.index] = py_wrapper;
}

void* tc_scene_get_py_wrapper(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return g_pool->py_wrappers[h.index];
}

// ============================================================================
// Entity Queries
// ============================================================================

typedef struct {
    const char* target_name;
    tc_entity_id found_id;
} FindByNameData;

static bool find_by_name_callback(tc_entity_pool* pool, tc_entity_id id, void* user_data) {
    FindByNameData* data = (FindByNameData*)user_data;
    const char* name = tc_entity_pool_name(pool, id);
    if (name && strcmp(name, data->target_name) == 0) {
        data->found_id = id;
        return false;
    }
    return true;
}

tc_entity_id tc_scene_find_entity_by_name(tc_scene_handle h, const char* name) {
    if (!handle_alive(h) || !name) return TC_ENTITY_ID_INVALID;

    FindByNameData data;
    data.target_name = name;
    data.found_id = TC_ENTITY_ID_INVALID;

    tc_entity_pool_foreach(g_pool->pools[h.index], find_by_name_callback, &data);
    return data.found_id;
}

// ============================================================================
// Component Type Lists
// ============================================================================

tc_component* tc_scene_first_component_of_type(tc_scene_handle h, const char* type_name) {
    if (!handle_alive(h) || !type_name) return NULL;
    return (tc_component*)tc_resource_map_get(g_pool->type_heads[h.index], type_name);
}

size_t tc_scene_count_components_of_type(tc_scene_handle h, const char* type_name) {
    size_t count = 0;
    for (tc_component* c = tc_scene_first_component_of_type(h, type_name);
         c != NULL; c = c->type_next) {
        count++;
    }
    return count;
}

void tc_scene_foreach_component_of_type(
    tc_scene_handle h,
    const char* type_name,
    tc_component_iter_fn callback,
    void* user_data
) {
    if (!handle_alive(h) || !type_name || !callback) return;

    const char* types[64];
    size_t type_count = tc_component_registry_get_type_and_descendants(type_name, types, 64);

    if (type_count == 0) {
        for (tc_component* c = tc_scene_first_component_of_type(h, type_name);
             c != NULL; c = c->type_next) {
            if (!callback(c, user_data)) return;
        }
        return;
    }

    for (size_t i = 0; i < type_count; i++) {
        for (tc_component* c = tc_scene_first_component_of_type(h, types[i]);
             c != NULL; c = c->type_next) {
            if (!callback(c, user_data)) return;
        }
    }
}

void tc_scene_foreach_drawable(
    tc_scene_handle h,
    tc_component_iter_fn callback,
    void* user_data,
    int filter_flags,
    uint64_t layer_mask
) {
    if (!handle_alive(h) || !callback) return;

    const char* drawable_types[64];
    size_t drawable_count = tc_component_registry_get_drawable_types(drawable_types, 64);
    if (drawable_count == 0) return;

    bool check_enabled = (filter_flags & TC_DRAWABLE_FILTER_ENABLED) != 0;
    bool check_visible = (filter_flags & TC_DRAWABLE_FILTER_VISIBLE) != 0;
    bool check_entity_enabled = (filter_flags & TC_DRAWABLE_FILTER_ENTITY_ENABLED) != 0;
    bool check_layer = (layer_mask != 0);

    for (size_t t = 0; t < drawable_count; t++) {
        tc_component* first = tc_scene_first_component_of_type(h, drawable_types[t]);
        for (tc_component* c = first; c != NULL; c = c->type_next) {
            if (check_enabled && !c->enabled) continue;

            if (c->owner_pool && (check_visible || check_entity_enabled || check_layer)) {
                if (check_visible && !tc_entity_pool_visible(c->owner_pool, c->owner_entity_id)) continue;
                if (check_entity_enabled && !tc_entity_pool_enabled(c->owner_pool, c->owner_entity_id)) continue;
                if (check_layer) {
                    uint64_t entity_layer = tc_entity_pool_layer(c->owner_pool, c->owner_entity_id);
                    if (!(layer_mask & (1ULL << entity_layer))) continue;
                }
            }

            if (!callback(c, user_data)) return;
        }
    }
}

void tc_scene_foreach_input_handler(
    tc_scene_handle h,
    tc_component_iter_fn callback,
    void* user_data,
    int filter_flags
) {
    if (!handle_alive(h) || !callback) return;

    const char* input_types[64];
    size_t input_count = tc_component_registry_get_input_handler_types(input_types, 64);
    if (input_count == 0) return;

    bool check_enabled = (filter_flags & TC_DRAWABLE_FILTER_ENABLED) != 0;
    bool check_entity_enabled = (filter_flags & TC_DRAWABLE_FILTER_ENTITY_ENABLED) != 0;
    bool check_active_in_editor = (filter_flags & TC_DRAWABLE_FILTER_ACTIVE_IN_EDITOR) != 0;

    for (size_t t = 0; t < input_count; t++) {
        for (tc_component* c = tc_scene_first_component_of_type(h, input_types[t]);
             c != NULL; c = c->type_next) {
            if (check_enabled && !c->enabled) continue;
            if (check_active_in_editor && !c->active_in_editor) continue;

            if (c->owner_pool && check_entity_enabled) {
                if (!tc_entity_pool_enabled(c->owner_pool, c->owner_entity_id)) continue;
            }

            if (!callback(c, user_data)) return;
        }
    }
}

// ============================================================================
// Component Type Enumeration
// ============================================================================

typedef struct {
    tc_scene_component_type* types;
    size_t count;
    size_t capacity;
} ComponentTypeCollector;

static bool collect_component_type(const char* key, void* value, void* user_data) {
    ComponentTypeCollector* collector = (ComponentTypeCollector*)user_data;
    tc_component* head = (tc_component*)value;

    size_t count = 0;
    for (tc_component* c = head; c != NULL; c = c->type_next) {
        count++;
    }

    if (count == 0) return true;

    if (collector->count >= collector->capacity) {
        size_t new_cap = collector->capacity == 0 ? 16 : collector->capacity * 2;
        tc_scene_component_type* new_types = (tc_scene_component_type*)realloc(
            collector->types,
            new_cap * sizeof(tc_scene_component_type)
        );
        if (!new_types) return false;
        collector->types = new_types;
        collector->capacity = new_cap;
    }

    collector->types[collector->count].type_name = key;
    collector->types[collector->count].count = count;
    collector->count++;

    return true;
}

tc_scene_component_type* tc_scene_get_all_component_types(tc_scene_handle h, size_t* out_count) {
    if (!out_count) return NULL;
    *out_count = 0;

    if (!handle_alive(h)) return NULL;

    ComponentTypeCollector collector = {NULL, 0, 0};
    tc_resource_map_foreach(g_pool->type_heads[h.index], collect_component_type, &collector);

    *out_count = collector.count;
    return collector.types;
}

// ============================================================================
// Scene Mode
// ============================================================================

tc_scene_mode tc_scene_get_mode(tc_scene_handle h) {
    if (!handle_alive(h)) return TC_SCENE_MODE_INACTIVE;
    return g_pool->modes[h.index];
}

void tc_scene_set_mode(tc_scene_handle h, tc_scene_mode mode) {
    if (!handle_alive(h)) return;

    tc_scene_mode old_mode = g_pool->modes[h.index];
    g_pool->modes[h.index] = mode;

    if (mode == TC_SCENE_MODE_INACTIVE && old_mode != TC_SCENE_MODE_INACTIVE) {
        tc_scene_notify_scene_inactive(h);
    } else if (mode != TC_SCENE_MODE_INACTIVE && old_mode == TC_SCENE_MODE_INACTIVE) {
        tc_scene_notify_scene_active(h);
    }
}

// ============================================================================
// Skybox
// ============================================================================

tc_scene_skybox* tc_scene_get_skybox(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return &g_pool->skyboxes[h.index];
}

void tc_scene_set_skybox_type(tc_scene_handle h, int type) {
    if (!handle_alive(h)) return;
    g_pool->skyboxes[h.index].type = type;
}

int tc_scene_get_skybox_type(tc_scene_handle h) {
    if (!handle_alive(h)) return TC_SKYBOX_GRADIENT;
    return g_pool->skyboxes[h.index].type;
}

void tc_scene_set_skybox_color(tc_scene_handle h, float r, float g, float b) {
    if (!handle_alive(h)) return;
    g_pool->skyboxes[h.index].color[0] = r;
    g_pool->skyboxes[h.index].color[1] = g;
    g_pool->skyboxes[h.index].color[2] = b;
}

void tc_scene_get_skybox_color(tc_scene_handle h, float* r, float* g, float* b) {
    if (!handle_alive(h)) return;
    if (r) *r = g_pool->skyboxes[h.index].color[0];
    if (g) *g = g_pool->skyboxes[h.index].color[1];
    if (b) *b = g_pool->skyboxes[h.index].color[2];
}

void tc_scene_set_skybox_top_color(tc_scene_handle h, float r, float g, float b) {
    if (!handle_alive(h)) return;
    g_pool->skyboxes[h.index].top_color[0] = r;
    g_pool->skyboxes[h.index].top_color[1] = g;
    g_pool->skyboxes[h.index].top_color[2] = b;
}

void tc_scene_get_skybox_top_color(tc_scene_handle h, float* r, float* g, float* b) {
    if (!handle_alive(h)) return;
    if (r) *r = g_pool->skyboxes[h.index].top_color[0];
    if (g) *g = g_pool->skyboxes[h.index].top_color[1];
    if (b) *b = g_pool->skyboxes[h.index].top_color[2];
}

void tc_scene_set_skybox_bottom_color(tc_scene_handle h, float r, float g, float b) {
    if (!handle_alive(h)) return;
    g_pool->skyboxes[h.index].bottom_color[0] = r;
    g_pool->skyboxes[h.index].bottom_color[1] = g;
    g_pool->skyboxes[h.index].bottom_color[2] = b;
}

void tc_scene_get_skybox_bottom_color(tc_scene_handle h, float* r, float* g, float* b) {
    if (!handle_alive(h)) return;
    if (r) *r = g_pool->skyboxes[h.index].bottom_color[0];
    if (g) *g = g_pool->skyboxes[h.index].bottom_color[1];
    if (b) *b = g_pool->skyboxes[h.index].bottom_color[2];
}

void tc_scene_set_skybox_mesh(tc_scene_handle h, tc_mesh* mesh) {
    if (!handle_alive(h)) return;
    tc_scene_skybox* skybox = &g_pool->skyboxes[h.index];
    if (skybox->mesh) {
        tc_mesh_release(skybox->mesh);
    }
    skybox->mesh = mesh;
    if (mesh) {
        tc_mesh_add_ref(mesh);
    }
}

tc_mesh* tc_scene_get_skybox_mesh(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return tc_scene_skybox_ensure_mesh(&g_pool->skyboxes[h.index]);
}

void tc_scene_set_skybox_material(tc_scene_handle h, tc_material* material) {
    if (!handle_alive(h)) return;
    tc_scene_skybox* skybox = &g_pool->skyboxes[h.index];
    if (skybox->material) {
        tc_material_release(skybox->material);
    }
    skybox->material = material;
    if (material) {
        tc_material_add_ref(material);
    }
}

tc_material* tc_scene_get_skybox_material(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return g_pool->skyboxes[h.index].material;
}

// ============================================================================
// Lighting
// ============================================================================

tc_scene_lighting* tc_scene_get_lighting(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return &g_pool->lightings[h.index];
}

void tc_scene_set_ambient(tc_scene_handle h, float r, float g, float b, float intensity) {
    if (!handle_alive(h)) return;
    g_pool->lightings[h.index].ambient_color[0] = r;
    g_pool->lightings[h.index].ambient_color[1] = g;
    g_pool->lightings[h.index].ambient_color[2] = b;
    g_pool->lightings[h.index].ambient_intensity = intensity;
}

void tc_scene_set_shadow_settings(tc_scene_handle h, int method, float softness, float bias) {
    if (!handle_alive(h)) return;
    g_pool->lightings[h.index].shadow_method = method;
    g_pool->lightings[h.index].shadow_softness = softness;
    g_pool->lightings[h.index].shadow_bias = bias;
}
