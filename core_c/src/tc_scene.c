// tc_scene.c - Scene implementation using entity pool
#include "../include/tc_scene.h"
#include "../include/tc_profiler.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

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
// Scene structure
// ============================================================================

struct tc_scene {
    // Owned entity pool
    tc_entity_pool* pool;

    // Component lifecycle lists
    ComponentList pending_start;
    ComponentList update_list;
    ComponentList fixed_update_list;

    // Fixed timestep
    double fixed_timestep;
    double accumulated_time;
};

// ============================================================================
// Creation / Destruction
// ============================================================================

tc_scene* tc_scene_new(void) {
    tc_scene* s = (tc_scene*)calloc(1, sizeof(tc_scene));
    if (!s) return NULL;

    s->pool = tc_entity_pool_create(256);
    list_init(&s->pending_start);
    list_init(&s->update_list);
    list_init(&s->fixed_update_list);
    s->fixed_timestep = 1.0 / 60.0;
    s->accumulated_time = 0.0;

    return s;
}

void tc_scene_free(tc_scene* s) {
    if (!s) return;

    list_free(&s->pending_start);
    list_free(&s->update_list);
    list_free(&s->fixed_update_list);
    tc_entity_pool_destroy(s->pool);
    free(s);
}

tc_entity_pool* tc_scene_entity_pool(tc_scene* s) {
    return s ? s->pool : NULL;
}

// ============================================================================
// Component Registration
// ============================================================================

void tc_scene_register_component(tc_scene* s, tc_component* c) {
    if (!s || !c) return;

    // Add to pending_start if not started
    if (!c->_started && !list_contains(&s->pending_start, c)) {
        list_push(&s->pending_start, c);
    }

    // Add to update lists based on flags
    if (c->has_update && !list_contains(&s->update_list, c)) {
        list_push(&s->update_list, c);
    }
    if (c->has_fixed_update && !list_contains(&s->fixed_update_list, c)) {
        list_push(&s->fixed_update_list, c);
    }

    // Call on_added callback
    tc_component_on_added(c, s);
}

void tc_scene_unregister_component(tc_scene* s, tc_component* c) {
    if (!s || !c) return;

    list_remove(&s->pending_start, c);
    list_remove(&s->update_list, c);
    list_remove(&s->fixed_update_list, c);

    // Call on_removed callback
    tc_component_on_removed(c);
}

// ============================================================================
// Update Loop
// ============================================================================

static void process_pending_start(tc_scene* s, bool editor_mode) {
    // Process pending_start - call start() on enabled components
    // Copy list since start() might modify it
    size_t count = s->pending_start.count;
    if (count == 0) return;

    tc_component** copy = malloc(count * sizeof(tc_component*));
    memcpy(copy, s->pending_start.items, count * sizeof(tc_component*));

    for (size_t i = 0; i < count; i++) {
        tc_component* c = copy[i];
        if (!c->enabled) continue;
        if (editor_mode && !c->active_in_editor) continue;

        tc_component_start(c);
        list_remove(&s->pending_start, c);
    }

    free(copy);
}

void tc_scene_update(tc_scene* s, double dt) {
    if (!s) return;

    // 1. Process pending start
    process_pending_start(s, false);

    // 2. Fixed update loop
    s->accumulated_time += dt;
    while (s->accumulated_time >= s->fixed_timestep) {
        for (size_t i = 0; i < s->fixed_update_list.count; i++) {
            tc_component* c = s->fixed_update_list.items[i];
            if (c->enabled) {
                tc_component_fixed_update(c, (float)s->fixed_timestep);
            }
        }
        s->accumulated_time -= s->fixed_timestep;
    }

    // 3. Regular update
    for (size_t i = 0; i < s->update_list.count; i++) {
        tc_component* c = s->update_list.items[i];
        if (c->enabled) {
            tc_component_update(c, (float)dt);
        }
    }

    // 4. Update entity transforms
    tc_entity_pool_update_transforms(s->pool);
}

void tc_scene_editor_update(tc_scene* s, double dt) {
    if (!s) return;

    bool profile = tc_profiler_enabled();

    // Process pending start (editor mode)
    process_pending_start(s, true);

    // Fixed update - only active_in_editor components
    s->accumulated_time += dt;
    while (s->accumulated_time >= s->fixed_timestep) {
        for (size_t i = 0; i < s->fixed_update_list.count; i++) {
            tc_component* c = s->fixed_update_list.items[i];
            if (c->enabled && c->active_in_editor) {
                if (profile) tc_profiler_begin_section(tc_component_type_name(c));
                tc_component_fixed_update(c, (float)s->fixed_timestep);
                if (profile) tc_profiler_end_section();
            }
        }
        s->accumulated_time -= s->fixed_timestep;
    }

    // Regular update - only active_in_editor components
    for (size_t i = 0; i < s->update_list.count; i++) {
        tc_component* c = s->update_list.items[i];
        if (c->enabled && c->active_in_editor) {
            if (profile) tc_profiler_begin_section(tc_component_type_name(c));
            tc_component_update(c, (float)dt);
            if (profile) tc_profiler_end_section();
        }
    }

    // Update entity transforms
    tc_entity_pool_update_transforms(s->pool);
}

// ============================================================================
// Fixed Timestep Configuration
// ============================================================================

double tc_scene_fixed_timestep(const tc_scene* s) {
    return s ? s->fixed_timestep : 1.0 / 60.0;
}

void tc_scene_set_fixed_timestep(tc_scene* s, double dt) {
    if (s && dt > 0) s->fixed_timestep = dt;
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

size_t tc_scene_entity_count(const tc_scene* s) {
    return s ? tc_entity_pool_count(s->pool) : 0;
}

size_t tc_scene_pending_start_count(const tc_scene* s) {
    return s ? s->pending_start.count : 0;
}

size_t tc_scene_update_list_count(const tc_scene* s) {
    return s ? s->update_list.count : 0;
}

size_t tc_scene_fixed_update_list_count(const tc_scene* s) {
    return s ? s->fixed_update_list.count : 0;
}
