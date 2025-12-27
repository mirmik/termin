// tc_scene.c - Scene implementation
#include "../include/tc_scene.h"
#include "../include/tc_profiler.h"
#include <stdlib.h>
#include <string.h>

// ============================================================================
// Dynamic Array Helper
// ============================================================================

#define ARRAY_INITIAL_CAPACITY 16

typedef struct {
    void** items;
    size_t count;
    size_t capacity;
} ptr_array;

static void ptr_array_init(ptr_array* arr) {
    arr->items = NULL;
    arr->count = 0;
    arr->capacity = 0;
}

static void ptr_array_free(ptr_array* arr) {
    free(arr->items);
    arr->items = NULL;
    arr->count = 0;
    arr->capacity = 0;
}

static void ptr_array_push(ptr_array* arr, void* item) {
    if (arr->count >= arr->capacity) {
        size_t new_cap = arr->capacity == 0 ? ARRAY_INITIAL_CAPACITY : arr->capacity * 2;
        arr->items = realloc(arr->items, new_cap * sizeof(void*));
        arr->capacity = new_cap;
    }
    arr->items[arr->count++] = item;
}

static bool ptr_array_remove(ptr_array* arr, void* item) {
    for (size_t i = 0; i < arr->count; i++) {
        if (arr->items[i] == item) {
            // Shift remaining elements
            memmove(&arr->items[i], &arr->items[i + 1], (arr->count - i - 1) * sizeof(void*));
            arr->count--;
            return true;
        }
    }
    return false;
}

static bool ptr_array_contains(const ptr_array* arr, void* item) {
    for (size_t i = 0; i < arr->count; i++) {
        if (arr->items[i] == item) return true;
    }
    return false;
}

// ============================================================================
// Scene Structure
// ============================================================================

struct tc_scene {
    // Entity list (sorted by priority)
    ptr_array entities;

    // Component lifecycle lists
    ptr_array pending_start;
    ptr_array update_list;
    ptr_array fixed_update_list;

    // Fixed timestep
    double fixed_timestep;
    double accumulated_time;

    // Callbacks
    tc_scene_entity_callback on_entity_added;
    void* on_entity_added_data;

    tc_scene_entity_callback on_entity_removed;
    void* on_entity_removed_data;

    tc_scene_component_callback on_component_registered;
    void* on_component_registered_data;

    tc_scene_component_callback on_component_unregistered;
    void* on_component_unregistered_data;
};

// ============================================================================
// Scene Creation / Destruction
// ============================================================================

tc_scene* tc_scene_new(void) {
    tc_scene* s = (tc_scene*)calloc(1, sizeof(tc_scene));
    if (!s) return NULL;

    ptr_array_init(&s->entities);
    ptr_array_init(&s->pending_start);
    ptr_array_init(&s->update_list);
    ptr_array_init(&s->fixed_update_list);

    s->fixed_timestep = 1.0 / 60.0;  // 60 Hz default
    s->accumulated_time = 0.0;

    return s;
}

void tc_scene_free(tc_scene* s) {
    if (!s) return;

    ptr_array_free(&s->entities);
    ptr_array_free(&s->pending_start);
    ptr_array_free(&s->update_list);
    ptr_array_free(&s->fixed_update_list);

    free(s);
}

// ============================================================================
// Entity Management
// ============================================================================

// Find insertion point for priority-sorted list
static size_t find_insert_index(tc_scene* s, int priority) {
    size_t left = 0;
    size_t right = s->entities.count;

    while (left < right) {
        size_t mid = left + (right - left) / 2;
        tc_entity* e = (tc_entity*)s->entities.items[mid];
        if (tc_entity_priority(e) < priority) {
            left = mid + 1;
        } else {
            right = mid;
        }
    }
    return left;
}

void tc_scene_add_entity(tc_scene* s, tc_entity* e) {
    if (!s || !e) return;

    // Already in scene?
    if (ptr_array_contains(&s->entities, e)) return;

    // Insert at correct position (sorted by priority)
    int priority = tc_entity_priority(e);
    size_t idx = find_insert_index(s, priority);

    // Make room
    ptr_array_push(&s->entities, NULL);  // Grow if needed

    // Shift elements
    if (idx < s->entities.count - 1) {
        memmove(&s->entities.items[idx + 1],
                &s->entities.items[idx],
                (s->entities.count - 1 - idx) * sizeof(void*));
    }
    s->entities.items[idx] = e;

    // Set scene reference on entity
    tc_entity_set_scene(e, s);

    // Register all components
    size_t comp_count = tc_entity_component_count(e);
    for (size_t i = 0; i < comp_count; i++) {
        tc_component* c = tc_entity_component_at(e, i);
        tc_scene_register_component(s, c);
    }

    // Callback
    if (s->on_entity_added) {
        s->on_entity_added(s, e, s->on_entity_added_data);
    }
}

void tc_scene_remove_entity(tc_scene* s, tc_entity* e) {
    if (!s || !e) return;

    if (!ptr_array_remove(&s->entities, e)) return;

    // Unregister all components
    size_t comp_count = tc_entity_component_count(e);
    for (size_t i = 0; i < comp_count; i++) {
        tc_component* c = tc_entity_component_at(e, i);
        tc_scene_unregister_component(s, c);
    }

    // Clear scene reference
    tc_entity_set_scene(e, NULL);

    // Callback
    if (s->on_entity_removed) {
        s->on_entity_removed(s, e, s->on_entity_removed_data);
    }
}

size_t tc_scene_entity_count(const tc_scene* s) {
    return s ? s->entities.count : 0;
}

tc_entity* tc_scene_get_entity(tc_scene* s, size_t index) {
    if (!s || index >= s->entities.count) return NULL;
    return (tc_entity*)s->entities.items[index];
}

// Recursive UUID search helper
static tc_entity* find_by_uuid_recursive(tc_entity* e, const char* uuid) {
    if (!e || !uuid) return NULL;

    if (strcmp(tc_entity_uuid(e), uuid) == 0) {
        return e;
    }

    // Search children
    size_t child_count = tc_entity_children_count(e);
    for (size_t i = 0; i < child_count; i++) {
        tc_entity* child = tc_entity_child_at(e, i);
        tc_entity* found = find_by_uuid_recursive(child, uuid);
        if (found) return found;
    }

    return NULL;
}

tc_entity* tc_scene_find_by_uuid(tc_scene* s, const char* uuid) {
    if (!s || !uuid) return NULL;

    for (size_t i = 0; i < s->entities.count; i++) {
        tc_entity* found = find_by_uuid_recursive((tc_entity*)s->entities.items[i], uuid);
        if (found) return found;
    }

    return NULL;
}

tc_entity* tc_scene_find_by_runtime_id(tc_scene* s, uint64_t runtime_id) {
    if (!s) return NULL;

    for (size_t i = 0; i < s->entities.count; i++) {
        tc_entity* e = (tc_entity*)s->entities.items[i];
        if (tc_entity_runtime_id(e) == runtime_id) {
            return e;
        }
    }

    return NULL;
}

// ============================================================================
// Component Registration
// ============================================================================

void tc_scene_register_component(tc_scene* s, tc_component* c) {
    if (!s || !c) return;

    // Add to update lists based on flags
    if (c->has_update && !ptr_array_contains(&s->update_list, c)) {
        ptr_array_push(&s->update_list, c);
    }

    if (c->has_fixed_update && !ptr_array_contains(&s->fixed_update_list, c)) {
        ptr_array_push(&s->fixed_update_list, c);
    }

    // Add to pending start if not started
    if (!c->_started && !ptr_array_contains(&s->pending_start, c)) {
        ptr_array_push(&s->pending_start, c);
    }

    // Call on_added with scene
    if (c->vtable && c->vtable->on_added) {
        c->vtable->on_added(c, s);
    }

    // Callback
    if (s->on_component_registered) {
        s->on_component_registered(s, c, s->on_component_registered_data);
    }
}

void tc_scene_unregister_component(tc_scene* s, tc_component* c) {
    if (!s || !c) return;

    ptr_array_remove(&s->update_list, c);
    ptr_array_remove(&s->fixed_update_list, c);
    ptr_array_remove(&s->pending_start, c);

    // Call on_removed
    if (c->vtable && c->vtable->on_removed) {
        c->vtable->on_removed(c);
    }

    // Callback
    if (s->on_component_unregistered) {
        s->on_component_unregistered(s, c, s->on_component_unregistered_data);
    }
}

// ============================================================================
// Update Loop
// ============================================================================

void tc_scene_update(tc_scene* s, double dt) {
    if (!s) return;

    bool profiling = tc_profiler_enabled();

    // 1. Process pending start
    if (profiling) tc_profiler_begin_section("Start");
    size_t pending_count = s->pending_start.count;
    if (pending_count > 0) {
        // Take snapshot - start() might add more components
        void** pending_copy = (void**)malloc(pending_count * sizeof(void*));
        memcpy(pending_copy, s->pending_start.items, pending_count * sizeof(void*));
        s->pending_start.count = 0;

        for (size_t i = 0; i < pending_count; i++) {
            tc_component* c = (tc_component*)pending_copy[i];
            if (c->enabled) {
                tc_component_start(c);
            } else {
                // Keep disabled components pending
                ptr_array_push(&s->pending_start, c);
            }
        }

        free(pending_copy);
    }
    if (profiling) tc_profiler_end_section();

    // 2. Fixed update (accumulator-based)
    if (profiling) tc_profiler_begin_section("FixedUpdate");
    s->accumulated_time += dt;
    while (s->accumulated_time >= s->fixed_timestep) {
        for (size_t i = 0; i < s->fixed_update_list.count; i++) {
            tc_component* c = (tc_component*)s->fixed_update_list.items[i];
            if (c->enabled) {
                tc_component_fixed_update(c, (float)s->fixed_timestep);
            }
        }
        s->accumulated_time -= s->fixed_timestep;
    }
    if (profiling) tc_profiler_end_section();

    // 3. Regular update
    if (profiling) tc_profiler_begin_section("Update");
    for (size_t i = 0; i < s->update_list.count; i++) {
        tc_component* c = (tc_component*)s->update_list.items[i];
        if (c->enabled) {
            tc_component_update(c, (float)dt);
        }
    }
    if (profiling) tc_profiler_end_section();
}

void tc_scene_editor_update(tc_scene* s, double dt) {
    if (!s) return;

    // Only update components with active_in_editor=true
    for (size_t i = 0; i < s->update_list.count; i++) {
        tc_component* c = (tc_component*)s->update_list.items[i];
        if (c->enabled && c->active_in_editor) {
            // Start if not started
            if (!c->_started) {
                if (c->vtable && c->vtable->on_editor_start) {
                    c->vtable->on_editor_start(c);
                }
                c->_started = true;
            }
            tc_component_update(c, (float)dt);
        }
    }
}

// ============================================================================
// Fixed Timestep Configuration
// ============================================================================

double tc_scene_fixed_timestep(const tc_scene* s) {
    return s ? s->fixed_timestep : 1.0 / 60.0;
}

void tc_scene_set_fixed_timestep(tc_scene* s, double dt) {
    if (s && dt > 0.0) {
        s->fixed_timestep = dt;
    }
}

double tc_scene_accumulated_time(const tc_scene* s) {
    return s ? s->accumulated_time : 0.0;
}

void tc_scene_reset_accumulated_time(tc_scene* s) {
    if (s) s->accumulated_time = 0.0;
}

// ============================================================================
// Component Queries
// ============================================================================

size_t tc_scene_pending_start_count(const tc_scene* s) {
    return s ? s->pending_start.count : 0;
}

size_t tc_scene_update_list_count(const tc_scene* s) {
    return s ? s->update_list.count : 0;
}

size_t tc_scene_fixed_update_list_count(const tc_scene* s) {
    return s ? s->fixed_update_list.count : 0;
}

tc_component* tc_scene_find_component(tc_scene* s, const char* type_name) {
    if (!s || !type_name) return NULL;

    for (size_t i = 0; i < s->entities.count; i++) {
        tc_entity* e = (tc_entity*)s->entities.items[i];
        tc_component* c = tc_entity_get_component(e, type_name);
        if (c) return c;
    }

    return NULL;
}

// ============================================================================
// Callbacks
// ============================================================================

void tc_scene_set_on_entity_added(tc_scene* s, tc_scene_entity_callback cb, void* user_data) {
    if (!s) return;
    s->on_entity_added = cb;
    s->on_entity_added_data = user_data;
}

void tc_scene_set_on_entity_removed(tc_scene* s, tc_scene_entity_callback cb, void* user_data) {
    if (!s) return;
    s->on_entity_removed = cb;
    s->on_entity_removed_data = user_data;
}

void tc_scene_set_on_component_registered(tc_scene* s, tc_scene_component_callback cb, void* user_data) {
    if (!s) return;
    s->on_component_registered = cb;
    s->on_component_registered_data = user_data;
}

void tc_scene_set_on_component_unregistered(tc_scene* s, tc_scene_component_callback cb, void* user_data) {
    if (!s) return;
    s->on_component_unregistered = cb;
    s->on_component_unregistered_data = user_data;
}
