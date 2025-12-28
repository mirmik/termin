// tc_entity_pool.c - Entity pool implementation
#include "../include/tc_entity_pool.h"
#include "../include/tc_component.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// For Py_INCREF/Py_DECREF on Python components
#define PY_SSIZE_T_CLEAN
#include <Python.h>

// ============================================================================
// Internal structures
// ============================================================================

#define INITIAL_CHILDREN_CAPACITY 4
#define INITIAL_COMPONENTS_CAPACITY 4

typedef struct {
    double x, y, z;
} Vec3;

typedef struct {
    double x, y, z, w;
} Quat;

typedef struct {
    Vec3 position;
    Quat rotation;
    Vec3 scale;
} Pose3;

// Dynamic array of entity IDs (for children)
typedef struct {
    tc_entity_id* items;
    size_t count;
    size_t capacity;
} EntityIdArray;

// Dynamic array of components
typedef struct {
    tc_component** items;
    size_t count;
    size_t capacity;
} ComponentArray;

// ============================================================================
// Pool structure - mixed SoA/AoS
// ============================================================================

struct tc_entity_pool {
    size_t capacity;
    size_t count;          // alive entities
    uint64_t next_runtime_id;

    // Free list (stack)
    uint32_t* free_stack;
    size_t free_count;

    // Generations (for all slots)
    uint32_t* generations;
    bool* alive;

    // Hot data - SoA for iteration
    bool* visible;
    bool* active;
    bool* pickable;
    bool* selectable;
    bool* serializable;
    bool* transform_dirty;
    uint32_t* version_for_walking_to_proximal;
    uint32_t* version_for_walking_to_distal;
    uint32_t* version_only_my;
    int* priorities;
    uint64_t* layers;
    uint64_t* entity_flags;
    uint32_t* pick_ids;
    uint32_t next_pick_id;

    // Transform data - SoA
    Vec3* local_positions;
    Quat* local_rotations;
    Vec3* local_scales;
    Vec3* world_positions;
    Quat* world_rotations;
    Vec3* world_scales;
    double* world_matrices;  // 16 doubles per entity

    // Cold data - per entity
    char** names;
    char** uuids;
    uint64_t* runtime_ids;

    // Hierarchy
    uint32_t* parent_indices;  // UINT32_MAX = no parent
    EntityIdArray* children;

    // Components
    ComponentArray* components;

    // User data
    void** user_data;
};

// ============================================================================
// Helper functions
// ============================================================================

static Quat quat_identity(void) {
    return (Quat){0, 0, 0, 1};
}

static Vec3 vec3_one(void) {
    return (Vec3){1, 1, 1};
}

static Vec3 vec3_zero(void) {
    return (Vec3){0, 0, 0};
}

static void entity_id_array_init(EntityIdArray* arr) {
    arr->items = NULL;
    arr->count = 0;
    arr->capacity = 0;
}

static void entity_id_array_free(EntityIdArray* arr) {
    free(arr->items);
    arr->items = NULL;
    arr->count = 0;
    arr->capacity = 0;
}

static void entity_id_array_push(EntityIdArray* arr, tc_entity_id id) {
    if (arr->count >= arr->capacity) {
        size_t new_cap = arr->capacity == 0 ? INITIAL_CHILDREN_CAPACITY : arr->capacity * 2;
        arr->items = realloc(arr->items, new_cap * sizeof(tc_entity_id));
        arr->capacity = new_cap;
    }
    arr->items[arr->count++] = id;
}

static void entity_id_array_remove(EntityIdArray* arr, tc_entity_id id) {
    for (size_t i = 0; i < arr->count; i++) {
        if (tc_entity_id_eq(arr->items[i], id)) {
            arr->items[i] = arr->items[--arr->count];
            return;
        }
    }
}

static void component_array_init(ComponentArray* arr) {
    arr->items = NULL;
    arr->count = 0;
    arr->capacity = 0;
}

static void component_array_free(ComponentArray* arr) {
    free(arr->items);
    arr->items = NULL;
    arr->count = 0;
    arr->capacity = 0;
}

static void component_array_push(ComponentArray* arr, tc_component* c) {
    if (arr->count >= arr->capacity) {
        size_t new_cap = arr->capacity == 0 ? INITIAL_COMPONENTS_CAPACITY : arr->capacity * 2;
        arr->items = realloc(arr->items, new_cap * sizeof(tc_component*));
        arr->capacity = new_cap;
    }
    arr->items[arr->count++] = c;
}

static void component_array_remove(ComponentArray* arr, tc_component* c) {
    for (size_t i = 0; i < arr->count; i++) {
        if (arr->items[i] == c) {
            arr->items[i] = arr->items[--arr->count];
            return;
        }
    }
}

static char* str_dup(const char* s) {
    if (!s) return NULL;
    size_t len = strlen(s) + 1;
    char* copy = malloc(len);
    memcpy(copy, s, len);
    return copy;
}

// ============================================================================
// Pool lifecycle
// ============================================================================

tc_entity_pool* tc_entity_pool_create(size_t initial_capacity) {
    if (initial_capacity == 0) initial_capacity = 64;

    tc_entity_pool* pool = calloc(1, sizeof(tc_entity_pool));
    pool->capacity = initial_capacity;
    pool->count = 0;
    pool->next_runtime_id = 1;

    // Allocate all arrays
    pool->free_stack = malloc(initial_capacity * sizeof(uint32_t));
    pool->free_count = initial_capacity;
    for (size_t i = 0; i < initial_capacity; i++) {
        pool->free_stack[i] = (uint32_t)(initial_capacity - 1 - i);
    }

    pool->generations = calloc(initial_capacity, sizeof(uint32_t));
    pool->alive = calloc(initial_capacity, sizeof(bool));

    pool->visible = malloc(initial_capacity * sizeof(bool));
    pool->active = malloc(initial_capacity * sizeof(bool));
    pool->pickable = malloc(initial_capacity * sizeof(bool));
    pool->selectable = malloc(initial_capacity * sizeof(bool));
    pool->serializable = malloc(initial_capacity * sizeof(bool));
    pool->transform_dirty = malloc(initial_capacity * sizeof(bool));
    pool->version_for_walking_to_proximal = calloc(initial_capacity, sizeof(uint32_t));
    pool->version_for_walking_to_distal = calloc(initial_capacity, sizeof(uint32_t));
    pool->version_only_my = calloc(initial_capacity, sizeof(uint32_t));
    pool->priorities = calloc(initial_capacity, sizeof(int));
    pool->layers = calloc(initial_capacity, sizeof(uint64_t));
    pool->entity_flags = calloc(initial_capacity, sizeof(uint64_t));
    pool->pick_ids = calloc(initial_capacity, sizeof(uint32_t));
    pool->next_pick_id = 1;

    pool->local_positions = malloc(initial_capacity * sizeof(Vec3));
    pool->local_rotations = malloc(initial_capacity * sizeof(Quat));
    pool->local_scales = malloc(initial_capacity * sizeof(Vec3));
    pool->world_positions = malloc(initial_capacity * sizeof(Vec3));
    pool->world_rotations = malloc(initial_capacity * sizeof(Quat));
    pool->world_scales = malloc(initial_capacity * sizeof(Vec3));
    pool->world_matrices = malloc(initial_capacity * 16 * sizeof(double));

    pool->names = calloc(initial_capacity, sizeof(char*));
    pool->uuids = calloc(initial_capacity, sizeof(char*));
    pool->runtime_ids = calloc(initial_capacity, sizeof(uint64_t));

    pool->parent_indices = malloc(initial_capacity * sizeof(uint32_t));
    for (size_t i = 0; i < initial_capacity; i++) {
        pool->parent_indices[i] = UINT32_MAX;
    }

    pool->children = calloc(initial_capacity, sizeof(EntityIdArray));
    pool->components = calloc(initial_capacity, sizeof(ComponentArray));
    pool->user_data = calloc(initial_capacity, sizeof(void*));

    return pool;
}

void tc_entity_pool_destroy(tc_entity_pool* pool) {
    if (!pool) return;

    // Free strings, release Python refs, and free dynamic arrays
    for (size_t i = 0; i < pool->capacity; i++) {
        free(pool->names[i]);
        free(pool->uuids[i]);
        entity_id_array_free(&pool->children[i]);

        // Release Python references for all components with py_wrap
        ComponentArray* comps = &pool->components[i];
        for (size_t j = 0; j < comps->count; j++) {
            tc_component* c = comps->items[j];
            if (c && c->py_wrap) {
                Py_DECREF((PyObject*)c->py_wrap);
            }
        }
        component_array_free(&pool->components[i]);
    }

    free(pool->free_stack);
    free(pool->generations);
    free(pool->alive);
    free(pool->visible);
    free(pool->active);
    free(pool->pickable);
    free(pool->selectable);
    free(pool->serializable);
    free(pool->transform_dirty);
    free(pool->version_for_walking_to_proximal);
    free(pool->version_for_walking_to_distal);
    free(pool->version_only_my);
    free(pool->priorities);
    free(pool->layers);
    free(pool->entity_flags);
    free(pool->pick_ids);
    free(pool->local_positions);
    free(pool->local_rotations);
    free(pool->local_scales);
    free(pool->world_positions);
    free(pool->world_rotations);
    free(pool->world_scales);
    free(pool->world_matrices);
    free(pool->names);
    free(pool->uuids);
    free(pool->runtime_ids);
    free(pool->parent_indices);
    free(pool->children);
    free(pool->components);
    free(pool->user_data);

    free(pool);
}

// ============================================================================
// Allocation
// ============================================================================

static void pool_grow(tc_entity_pool* pool) {
    size_t old_cap = pool->capacity;
    size_t new_cap = old_cap * 2;

    pool->free_stack = realloc(pool->free_stack, new_cap * sizeof(uint32_t));
    for (size_t i = old_cap; i < new_cap; i++) {
        pool->free_stack[pool->free_count++] = (uint32_t)(new_cap - 1 - (i - old_cap));
    }

    pool->generations = realloc(pool->generations, new_cap * sizeof(uint32_t));
    pool->alive = realloc(pool->alive, new_cap * sizeof(bool));
    memset(pool->generations + old_cap, 0, (new_cap - old_cap) * sizeof(uint32_t));
    memset(pool->alive + old_cap, 0, (new_cap - old_cap) * sizeof(bool));

    pool->visible = realloc(pool->visible, new_cap * sizeof(bool));
    pool->active = realloc(pool->active, new_cap * sizeof(bool));
    pool->pickable = realloc(pool->pickable, new_cap * sizeof(bool));
    pool->selectable = realloc(pool->selectable, new_cap * sizeof(bool));
    pool->serializable = realloc(pool->serializable, new_cap * sizeof(bool));
    pool->transform_dirty = realloc(pool->transform_dirty, new_cap * sizeof(bool));
    pool->version_for_walking_to_proximal = realloc(pool->version_for_walking_to_proximal, new_cap * sizeof(uint32_t));
    pool->version_for_walking_to_distal = realloc(pool->version_for_walking_to_distal, new_cap * sizeof(uint32_t));
    pool->version_only_my = realloc(pool->version_only_my, new_cap * sizeof(uint32_t));
    memset(pool->version_for_walking_to_proximal + old_cap, 0, (new_cap - old_cap) * sizeof(uint32_t));
    memset(pool->version_for_walking_to_distal + old_cap, 0, (new_cap - old_cap) * sizeof(uint32_t));
    memset(pool->version_only_my + old_cap, 0, (new_cap - old_cap) * sizeof(uint32_t));
    pool->priorities = realloc(pool->priorities, new_cap * sizeof(int));
    pool->layers = realloc(pool->layers, new_cap * sizeof(uint64_t));
    pool->entity_flags = realloc(pool->entity_flags, new_cap * sizeof(uint64_t));
    pool->pick_ids = realloc(pool->pick_ids, new_cap * sizeof(uint32_t));
    memset(pool->priorities + old_cap, 0, (new_cap - old_cap) * sizeof(int));
    memset(pool->layers + old_cap, 0, (new_cap - old_cap) * sizeof(uint64_t));
    memset(pool->entity_flags + old_cap, 0, (new_cap - old_cap) * sizeof(uint64_t));
    memset(pool->pick_ids + old_cap, 0, (new_cap - old_cap) * sizeof(uint32_t));

    pool->local_positions = realloc(pool->local_positions, new_cap * sizeof(Vec3));
    pool->local_rotations = realloc(pool->local_rotations, new_cap * sizeof(Quat));
    pool->local_scales = realloc(pool->local_scales, new_cap * sizeof(Vec3));
    pool->world_positions = realloc(pool->world_positions, new_cap * sizeof(Vec3));
    pool->world_rotations = realloc(pool->world_rotations, new_cap * sizeof(Quat));
    pool->world_scales = realloc(pool->world_scales, new_cap * sizeof(Vec3));
    pool->world_matrices = realloc(pool->world_matrices, new_cap * 16 * sizeof(double));

    pool->names = realloc(pool->names, new_cap * sizeof(char*));
    pool->uuids = realloc(pool->uuids, new_cap * sizeof(char*));
    pool->runtime_ids = realloc(pool->runtime_ids, new_cap * sizeof(uint64_t));
    memset(pool->names + old_cap, 0, (new_cap - old_cap) * sizeof(char*));
    memset(pool->uuids + old_cap, 0, (new_cap - old_cap) * sizeof(char*));
    memset(pool->runtime_ids + old_cap, 0, (new_cap - old_cap) * sizeof(uint64_t));

    pool->parent_indices = realloc(pool->parent_indices, new_cap * sizeof(uint32_t));
    for (size_t i = old_cap; i < new_cap; i++) {
        pool->parent_indices[i] = UINT32_MAX;
    }

    pool->children = realloc(pool->children, new_cap * sizeof(EntityIdArray));
    pool->components = realloc(pool->components, new_cap * sizeof(ComponentArray));
    pool->user_data = realloc(pool->user_data, new_cap * sizeof(void*));
    memset(pool->children + old_cap, 0, (new_cap - old_cap) * sizeof(EntityIdArray));
    memset(pool->components + old_cap, 0, (new_cap - old_cap) * sizeof(ComponentArray));
    memset(pool->user_data + old_cap, 0, (new_cap - old_cap) * sizeof(void*));

    pool->capacity = new_cap;
}

tc_entity_id tc_entity_pool_alloc(tc_entity_pool* pool, const char* name) {
    if (pool->free_count == 0) {
        pool_grow(pool);
    }

    uint32_t idx = pool->free_stack[--pool->free_count];
    uint32_t gen = pool->generations[idx];

    pool->alive[idx] = true;
    pool->visible[idx] = true;
    pool->active[idx] = true;
    pool->pickable[idx] = true;
    pool->selectable[idx] = true;
    pool->serializable[idx] = true;
    pool->transform_dirty[idx] = true;
    pool->version_for_walking_to_proximal[idx] = 0;
    pool->version_for_walking_to_distal[idx] = 0;
    pool->version_only_my[idx] = 0;
    pool->priorities[idx] = 0;
    pool->layers[idx] = 0;
    pool->entity_flags[idx] = 0;
    pool->pick_ids[idx] = pool->next_pick_id++;

    pool->local_positions[idx] = vec3_zero();
    pool->local_rotations[idx] = quat_identity();
    pool->local_scales[idx] = vec3_one();
    pool->world_positions[idx] = vec3_zero();
    pool->world_rotations[idx] = quat_identity();
    pool->world_scales[idx] = vec3_one();

    free(pool->names[idx]);
    pool->names[idx] = str_dup(name ? name : "entity");

    // Generate UUID
    free(pool->uuids[idx]);
    char uuid_buf[64];
    snprintf(uuid_buf, sizeof(uuid_buf), "%016llx", (unsigned long long)pool->next_runtime_id);
    pool->uuids[idx] = str_dup(uuid_buf);

    pool->runtime_ids[idx] = pool->next_runtime_id++;
    pool->parent_indices[idx] = UINT32_MAX;

    entity_id_array_free(&pool->children[idx]);
    entity_id_array_init(&pool->children[idx]);

    component_array_free(&pool->components[idx]);
    component_array_init(&pool->components[idx]);

    pool->user_data[idx] = NULL;
    pool->count++;

    return (tc_entity_id){idx, gen};
}

void tc_entity_pool_free(tc_entity_pool* pool, tc_entity_id id) {
    if (!pool || !tc_entity_pool_alive(pool, id)) return;

    uint32_t idx = id.index;

    // Release Python references for all components with py_wrap
    ComponentArray* comps = &pool->components[idx];
    for (size_t i = 0; i < comps->count; i++) {
        tc_component* c = comps->items[i];
        if (c && c->py_wrap) {
            Py_DECREF((PyObject*)c->py_wrap);
        }
    }

    // Remove from parent's children
    if (pool->parent_indices[idx] != UINT32_MAX) {
        uint32_t parent_idx = pool->parent_indices[idx];
        if (pool->alive[parent_idx]) {
            entity_id_array_remove(&pool->children[parent_idx], id);
        }
    }

    // Orphan children (or could recursively delete)
    for (size_t i = 0; i < pool->children[idx].count; i++) {
        tc_entity_id child = pool->children[idx].items[i];
        if (tc_entity_pool_alive(pool, child)) {
            pool->parent_indices[child.index] = UINT32_MAX;
        }
    }

    pool->alive[idx] = false;
    pool->generations[idx]++;
    pool->free_stack[pool->free_count++] = idx;
    pool->count--;
}

bool tc_entity_pool_alive(const tc_entity_pool* pool, tc_entity_id id) {
    if (!pool || id.index >= pool->capacity) return false;
    return pool->alive[id.index] && pool->generations[id.index] == id.generation;
}

size_t tc_entity_pool_count(const tc_entity_pool* pool) {
    return pool ? pool->count : 0;
}

size_t tc_entity_pool_capacity(const tc_entity_pool* pool) {
    return pool ? pool->capacity : 0;
}

// ============================================================================
// Data access
// ============================================================================

const char* tc_entity_pool_name(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return NULL;
    return pool->names[id.index];
}

void tc_entity_pool_set_name(tc_entity_pool* pool, tc_entity_id id, const char* name) {
    if (!tc_entity_pool_alive(pool, id)) return;
    free(pool->names[id.index]);
    pool->names[id.index] = str_dup(name);
}

const char* tc_entity_pool_uuid(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return NULL;
    return pool->uuids[id.index];
}

uint64_t tc_entity_pool_runtime_id(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return 0;
    return pool->runtime_ids[id.index];
}

bool tc_entity_pool_visible(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return false;
    return pool->visible[id.index];
}

void tc_entity_pool_set_visible(tc_entity_pool* pool, tc_entity_id id, bool v) {
    if (!tc_entity_pool_alive(pool, id)) return;
    pool->visible[id.index] = v;
}

bool tc_entity_pool_active(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return false;
    return pool->active[id.index];
}

void tc_entity_pool_set_active(tc_entity_pool* pool, tc_entity_id id, bool v) {
    if (!tc_entity_pool_alive(pool, id)) return;
    pool->active[id.index] = v;
}

bool tc_entity_pool_pickable(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return false;
    return pool->pickable[id.index];
}

void tc_entity_pool_set_pickable(tc_entity_pool* pool, tc_entity_id id, bool v) {
    if (!tc_entity_pool_alive(pool, id)) return;
    pool->pickable[id.index] = v;
}

bool tc_entity_pool_selectable(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return false;
    return pool->selectable[id.index];
}

void tc_entity_pool_set_selectable(tc_entity_pool* pool, tc_entity_id id, bool v) {
    if (!tc_entity_pool_alive(pool, id)) return;
    pool->selectable[id.index] = v;
}

bool tc_entity_pool_serializable(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return false;
    return pool->serializable[id.index];
}

void tc_entity_pool_set_serializable(tc_entity_pool* pool, tc_entity_id id, bool v) {
    if (!tc_entity_pool_alive(pool, id)) return;
    pool->serializable[id.index] = v;
}

int tc_entity_pool_priority(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return 0;
    return pool->priorities[id.index];
}

void tc_entity_pool_set_priority(tc_entity_pool* pool, tc_entity_id id, int v) {
    if (!tc_entity_pool_alive(pool, id)) return;
    pool->priorities[id.index] = v;
}

uint64_t tc_entity_pool_layer(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return 0;
    return pool->layers[id.index];
}

void tc_entity_pool_set_layer(tc_entity_pool* pool, tc_entity_id id, uint64_t v) {
    if (!tc_entity_pool_alive(pool, id)) return;
    pool->layers[id.index] = v;
}

uint64_t tc_entity_pool_flags(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return 0;
    return pool->entity_flags[id.index];
}

void tc_entity_pool_set_flags(tc_entity_pool* pool, tc_entity_id id, uint64_t v) {
    if (!tc_entity_pool_alive(pool, id)) return;
    pool->entity_flags[id.index] = v;
}

uint32_t tc_entity_pool_pick_id(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return 0;
    return pool->pick_ids[id.index];
}

tc_entity_id tc_entity_pool_find_by_pick_id(tc_entity_pool* pool, uint32_t pick_id) {
    if (!pool || pick_id == 0) return TC_ENTITY_ID_INVALID;
    for (size_t i = 0; i < pool->capacity; i++) {
        if (pool->alive[i] && pool->pick_ids[i] == pick_id) {
            return (tc_entity_id){(uint32_t)i, pool->generations[i]};
        }
    }
    return TC_ENTITY_ID_INVALID;
}

// ============================================================================
// Transform
// ============================================================================

void tc_entity_pool_get_local_position(const tc_entity_pool* pool, tc_entity_id id, double* xyz) {
    if (!tc_entity_pool_alive(pool, id)) return;
    Vec3 p = pool->local_positions[id.index];
    xyz[0] = p.x; xyz[1] = p.y; xyz[2] = p.z;
}

void tc_entity_pool_set_local_position(tc_entity_pool* pool, tc_entity_id id, const double* xyz) {
    if (!tc_entity_pool_alive(pool, id)) return;
    pool->local_positions[id.index] = (Vec3){xyz[0], xyz[1], xyz[2]};
    tc_entity_pool_mark_dirty(pool, id);
}

void tc_entity_pool_get_local_rotation(const tc_entity_pool* pool, tc_entity_id id, double* xyzw) {
    if (!tc_entity_pool_alive(pool, id)) return;
    Quat r = pool->local_rotations[id.index];
    xyzw[0] = r.x; xyzw[1] = r.y; xyzw[2] = r.z; xyzw[3] = r.w;
}

void tc_entity_pool_set_local_rotation(tc_entity_pool* pool, tc_entity_id id, const double* xyzw) {
    if (!tc_entity_pool_alive(pool, id)) return;
    pool->local_rotations[id.index] = (Quat){xyzw[0], xyzw[1], xyzw[2], xyzw[3]};
    tc_entity_pool_mark_dirty(pool, id);
}

void tc_entity_pool_get_local_scale(const tc_entity_pool* pool, tc_entity_id id, double* xyz) {
    if (!tc_entity_pool_alive(pool, id)) return;
    Vec3 s = pool->local_scales[id.index];
    xyz[0] = s.x; xyz[1] = s.y; xyz[2] = s.z;
}

void tc_entity_pool_set_local_scale(tc_entity_pool* pool, tc_entity_id id, const double* xyz) {
    if (!tc_entity_pool_alive(pool, id)) return;
    pool->local_scales[id.index] = (Vec3){xyz[0], xyz[1], xyz[2]};
    tc_entity_pool_mark_dirty(pool, id);
}

static uint32_t increment_version(uint32_t v) {
    return (v + 1) % 0x7FFFFFFF;
}

// Spread changes toward leaves (distal) - increments version_for_walking_to_proximal
static void spread_changes_to_distal(tc_entity_pool* pool, uint32_t idx) {
    pool->version_for_walking_to_proximal[idx] = increment_version(pool->version_for_walking_to_proximal[idx]);
    pool->transform_dirty[idx] = true;

    EntityIdArray* ch = &pool->children[idx];
    for (size_t i = 0; i < ch->count; i++) {
        tc_entity_id child = ch->items[i];
        if (pool->alive[child.index]) {
            spread_changes_to_distal(pool, child.index);
        }
    }
}

// Spread changes toward root (proximal) - increments version_for_walking_to_distal
static void spread_changes_to_proximal(tc_entity_pool* pool, uint32_t idx) {
    pool->version_for_walking_to_distal[idx] = increment_version(pool->version_for_walking_to_distal[idx]);

    uint32_t parent_idx = pool->parent_indices[idx];
    if (parent_idx != UINT32_MAX && pool->alive[parent_idx]) {
        spread_changes_to_proximal(pool, parent_idx);
    }
}

void tc_entity_pool_mark_dirty(tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return;

    uint32_t idx = id.index;

    // Increment own version
    pool->version_only_my[idx] = increment_version(pool->version_only_my[idx]);

    // Spread to ancestors (they know something below changed)
    spread_changes_to_proximal(pool, idx);

    // Spread to descendants (they need to recalculate world transform)
    spread_changes_to_distal(pool, idx);
}

// Forward declarations for lazy update
static void update_entity_transform(tc_entity_pool* pool, uint32_t idx);

void tc_entity_pool_get_world_position(const tc_entity_pool* pool, tc_entity_id id, double* xyz) {
    if (!tc_entity_pool_alive(pool, id)) return;
    // Lazy update if dirty
    if (pool->transform_dirty[id.index]) {
        update_entity_transform((tc_entity_pool*)pool, id.index);
    }
    Vec3 p = pool->world_positions[id.index];
    xyz[0] = p.x; xyz[1] = p.y; xyz[2] = p.z;
}

void tc_entity_pool_get_world_matrix(const tc_entity_pool* pool, tc_entity_id id, double* m16) {
    if (!tc_entity_pool_alive(pool, id)) return;
    // Lazy update if dirty
    if (pool->transform_dirty[id.index]) {
        update_entity_transform((tc_entity_pool*)pool, id.index);
    }
    memcpy(m16, &pool->world_matrices[id.index * 16], 16 * sizeof(double));
}

// Simple quaternion multiply
static Quat quat_mul(Quat a, Quat b) {
    return (Quat){
        a.w*b.x + a.x*b.w + a.y*b.z - a.z*b.y,
        a.w*b.y - a.x*b.z + a.y*b.w + a.z*b.x,
        a.w*b.z + a.x*b.y - a.y*b.x + a.z*b.w,
        a.w*b.w - a.x*b.x - a.y*b.y - a.z*b.z
    };
}

// Rotate vector by quaternion
static Vec3 quat_rotate(Quat q, Vec3 v) {
    Vec3 u = {q.x, q.y, q.z};
    double s = q.w;

    double dot_uv = u.x*v.x + u.y*v.y + u.z*v.z;
    double dot_uu = u.x*u.x + u.y*u.y + u.z*u.z;

    Vec3 cross = {
        u.y*v.z - u.z*v.y,
        u.z*v.x - u.x*v.z,
        u.x*v.y - u.y*v.x
    };

    return (Vec3){
        2.0*dot_uv*u.x + (s*s - dot_uu)*v.x + 2.0*s*cross.x,
        2.0*dot_uv*u.y + (s*s - dot_uu)*v.y + 2.0*s*cross.y,
        2.0*dot_uv*u.z + (s*s - dot_uu)*v.z + 2.0*s*cross.z
    };
}

static void compute_world_matrix(double* m, Vec3 pos, Quat rot, Vec3 scale) {
    // Rotation matrix from quaternion - OUTPUT ROW-MAJOR for Python compatibility
    // Row-major layout: m[row * 4 + col]
    double xx = rot.x * rot.x, yy = rot.y * rot.y, zz = rot.z * rot.z;
    double xy = rot.x * rot.y, xz = rot.x * rot.z, yz = rot.y * rot.z;
    double wx = rot.w * rot.x, wy = rot.w * rot.y, wz = rot.w * rot.z;

    // Row 0
    m[0]  = (1 - 2*(yy + zz)) * scale.x;
    m[1]  = 2*(xy - wz) * scale.y;
    m[2]  = 2*(xz + wy) * scale.z;
    m[3]  = pos.x;

    // Row 1
    m[4]  = 2*(xy + wz) * scale.x;
    m[5]  = (1 - 2*(xx + zz)) * scale.y;
    m[6]  = 2*(yz - wx) * scale.z;
    m[7]  = pos.y;

    // Row 2
    m[8]  = 2*(xz - wy) * scale.x;
    m[9]  = 2*(yz + wx) * scale.y;
    m[10] = (1 - 2*(xx + yy)) * scale.z;
    m[11] = pos.z;

    // Row 3
    m[12] = 0;
    m[13] = 0;
    m[14] = 0;
    m[15] = 1;
}

// Lazy update of a single entity's world transform
static void update_entity_transform(tc_entity_pool* pool, uint32_t idx) {
    if (!pool->transform_dirty[idx]) return;

    uint32_t parent_idx = pool->parent_indices[idx];

    if (parent_idx == UINT32_MAX) {
        // Root entity - world = local
        pool->world_positions[idx] = pool->local_positions[idx];
        pool->world_rotations[idx] = pool->local_rotations[idx];
        pool->world_scales[idx] = pool->local_scales[idx];
    } else {
        // Has parent - update parent first if dirty, then combine
        if (pool->alive[parent_idx] && pool->transform_dirty[parent_idx]) {
            update_entity_transform(pool, parent_idx);
        }

        Vec3 pw = pool->world_positions[parent_idx];
        Quat rw = pool->world_rotations[parent_idx];
        Vec3 sw = pool->world_scales[parent_idx];

        Vec3 lp = pool->local_positions[idx];
        Quat lr = pool->local_rotations[idx];
        Vec3 ls = pool->local_scales[idx];

        // Scale local position by parent scale, rotate, add parent position
        Vec3 scaled_pos = {lp.x * sw.x, lp.y * sw.y, lp.z * sw.z};
        Vec3 rotated_pos = quat_rotate(rw, scaled_pos);

        pool->world_positions[idx] = (Vec3){
            pw.x + rotated_pos.x,
            pw.y + rotated_pos.y,
            pw.z + rotated_pos.z
        };
        pool->world_rotations[idx] = quat_mul(rw, lr);
        pool->world_scales[idx] = (Vec3){sw.x * ls.x, sw.y * ls.y, sw.z * ls.z};
    }

    compute_world_matrix(
        &pool->world_matrices[idx * 16],
        pool->world_positions[idx],
        pool->world_rotations[idx],
        pool->world_scales[idx]
    );

    pool->transform_dirty[idx] = false;
}

void tc_entity_pool_update_transforms(tc_entity_pool* pool) {
    if (!pool) return;

    // TODO: proper hierarchical update order
    // For now: simple iteration, parents should be processed before children
    for (size_t i = 0; i < pool->capacity; i++) {
        if (!pool->alive[i] || !pool->transform_dirty[i]) continue;

        uint32_t parent_idx = pool->parent_indices[i];

        if (parent_idx == UINT32_MAX) {
            // Root entity - world = local
            pool->world_positions[i] = pool->local_positions[i];
            pool->world_rotations[i] = pool->local_rotations[i];
            pool->world_scales[i] = pool->local_scales[i];
        } else {
            // Has parent - combine transforms
            Vec3 pw = pool->world_positions[parent_idx];
            Quat rw = pool->world_rotations[parent_idx];
            Vec3 sw = pool->world_scales[parent_idx];

            Vec3 lp = pool->local_positions[i];
            Quat lr = pool->local_rotations[i];
            Vec3 ls = pool->local_scales[i];

            // Scale local position by parent scale, rotate, add parent position
            Vec3 scaled_pos = {lp.x * sw.x, lp.y * sw.y, lp.z * sw.z};
            Vec3 rotated_pos = quat_rotate(rw, scaled_pos);

            pool->world_positions[i] = (Vec3){
                pw.x + rotated_pos.x,
                pw.y + rotated_pos.y,
                pw.z + rotated_pos.z
            };
            pool->world_rotations[i] = quat_mul(rw, lr);
            pool->world_scales[i] = (Vec3){sw.x * ls.x, sw.y * ls.y, sw.z * ls.z};
        }

        compute_world_matrix(
            &pool->world_matrices[i * 16],
            pool->world_positions[i],
            pool->world_rotations[i],
            pool->world_scales[i]
        );

        pool->transform_dirty[i] = false;
    }
}

// ============================================================================
// Hierarchy
// ============================================================================

tc_entity_id tc_entity_pool_parent(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return TC_ENTITY_ID_INVALID;

    uint32_t parent_idx = pool->parent_indices[id.index];
    if (parent_idx == UINT32_MAX) return TC_ENTITY_ID_INVALID;

    // Return parent with current generation
    return (tc_entity_id){parent_idx, pool->generations[parent_idx]};
}

void tc_entity_pool_set_parent(tc_entity_pool* pool, tc_entity_id id, tc_entity_id parent) {
    if (!tc_entity_pool_alive(pool, id)) return;

    uint32_t idx = id.index;
    uint32_t old_parent_idx = pool->parent_indices[idx];

    // Remove from old parent
    if (old_parent_idx != UINT32_MAX && pool->alive[old_parent_idx]) {
        entity_id_array_remove(&pool->children[old_parent_idx], id);
    }

    // Set new parent
    if (tc_entity_id_valid(parent) && tc_entity_pool_alive(pool, parent)) {
        pool->parent_indices[idx] = parent.index;
        entity_id_array_push(&pool->children[parent.index], id);
    } else {
        pool->parent_indices[idx] = UINT32_MAX;
    }

    tc_entity_pool_mark_dirty(pool, id);
}

size_t tc_entity_pool_children_count(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return 0;
    return pool->children[id.index].count;
}

tc_entity_id tc_entity_pool_child_at(const tc_entity_pool* pool, tc_entity_id id, size_t index) {
    if (!tc_entity_pool_alive(pool, id)) return TC_ENTITY_ID_INVALID;
    if (index >= pool->children[id.index].count) return TC_ENTITY_ID_INVALID;
    return pool->children[id.index].items[index];
}

// ============================================================================
// Components
// ============================================================================

void tc_entity_pool_add_component(tc_entity_pool* pool, tc_entity_id id, tc_component* c) {
    if (!tc_entity_pool_alive(pool, id) || !c) return;

    // Keep Python object alive while attached to entity
    if (c->kind == TC_PYTHON_COMPONENT && c->py_wrap) {
        Py_INCREF((PyObject*)c->py_wrap);
    }

    component_array_push(&pool->components[id.index], c);
}

void tc_entity_pool_remove_component(tc_entity_pool* pool, tc_entity_id id, tc_component* c) {
    if (!tc_entity_pool_alive(pool, id) || !c) return;

    component_array_remove(&pool->components[id.index], c);

    // Release Python reference (matches incref in add_component/set_py_wrap)
    // For Python components: INCREF was done in add_component
    // For C++ components: INCREF was done via set_py_wrap in bindings
    if (c->py_wrap) {
        Py_DECREF((PyObject*)c->py_wrap);
    }
}

size_t tc_entity_pool_component_count(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return 0;
    return pool->components[id.index].count;
}

tc_component* tc_entity_pool_component_at(const tc_entity_pool* pool, tc_entity_id id, size_t index) {
    if (!tc_entity_pool_alive(pool, id)) return NULL;
    if (index >= pool->components[id.index].count) return NULL;
    return pool->components[id.index].items[index];
}

// ============================================================================
// User data
// ============================================================================

void* tc_entity_pool_data(const tc_entity_pool* pool, tc_entity_id id) {
    if (!tc_entity_pool_alive(pool, id)) return NULL;
    return pool->user_data[id.index];
}

void tc_entity_pool_set_data(tc_entity_pool* pool, tc_entity_id id, void* data) {
    if (!tc_entity_pool_alive(pool, id)) return;
    pool->user_data[id.index] = data;
}
