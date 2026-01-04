// tc_scene.c - Scene implementation using entity pool
#include "../include/tc_scene.h"
#include "../include/tc_scene_registry.h"
#include "../include/tc_resource_map.h"
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
    ComponentList before_render_list;

    // Fixed timestep
    double fixed_timestep;
    double accumulated_time;

    // Python wrapper (PyObject* to Python Scene)
    void* py_wrapper;

    // Component type lists: type_name -> tc_component* (head of intrusive list)
    tc_resource_map* type_heads;
};

// ============================================================================
// Creation / Destruction
// ============================================================================

tc_scene* tc_scene_new(void) {
    tc_scene* s = (tc_scene*)calloc(1, sizeof(tc_scene));
    if (!s) return NULL;

    s->pool = tc_entity_pool_create(256);
    tc_entity_pool_set_scene(s->pool, s);
    list_init(&s->pending_start);
    list_init(&s->update_list);
    list_init(&s->fixed_update_list);
    list_init(&s->before_render_list);
    s->fixed_timestep = 1.0 / 60.0;
    s->accumulated_time = 0.0;
    s->type_heads = tc_resource_map_new(NULL);  // No destructor - components are not owned

    // Register in global scene registry
    tc_scene_registry_add(s, NULL);

    return s;
}

void tc_scene_free(tc_scene* s) {
    if (!s) return;

    // Unregister from global scene registry
    tc_scene_registry_remove(s);

    list_free(&s->pending_start);
    list_free(&s->update_list);
    list_free(&s->fixed_update_list);
    list_free(&s->before_render_list);
    tc_resource_map_free(s->type_heads);
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
    if (c->has_before_render && !list_contains(&s->before_render_list, c)) {
        list_push(&s->before_render_list, c);
    }

    // Add to type list (intrusive doubly-linked list)
    const char* type_name = tc_component_type_name(c);
    if (type_name && c->type_prev == NULL && c->type_next == NULL) {
        tc_component* head = (tc_component*)tc_resource_map_get(s->type_heads, type_name);
        if (head == NULL) {
            // First component of this type
            tc_resource_map_add(s->type_heads, type_name, c);
        } else if (head != c) {
            // Insert at head
            c->type_next = head;
            head->type_prev = c;
            tc_resource_map_remove(s->type_heads, type_name);
            tc_resource_map_add(s->type_heads, type_name, c);
        }
    }

    // Call on_added callback
    tc_component_on_added(c, s);
}

void tc_scene_unregister_component(tc_scene* s, tc_component* c) {
    if (!s || !c) return;

    list_remove(&s->pending_start, c);
    list_remove(&s->update_list, c);
    list_remove(&s->fixed_update_list, c);
    list_remove(&s->before_render_list, c);

    // Remove from type list (O(1) unlink)
    const char* type_name = tc_component_type_name(c);
    if (type_name) {
        tc_component* head = (tc_component*)tc_resource_map_get(s->type_heads, type_name);
        if (head == c) {
            // This is the head - update to next
            tc_resource_map_remove(s->type_heads, type_name);
            if (c->type_next) {
                c->type_next->type_prev = NULL;
                tc_resource_map_add(s->type_heads, type_name, c->type_next);
            }
        } else {
            // Not the head - just unlink
            if (c->type_prev) c->type_prev->type_next = c->type_next;
            if (c->type_next) c->type_next->type_prev = c->type_prev;
        }
        c->type_prev = NULL;
        c->type_next = NULL;
    }

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

    bool profile = tc_profiler_enabled();

    // 1. Process pending start
    process_pending_start(s, false);

    // 2. Fixed update loop
    s->accumulated_time += dt;
    while (s->accumulated_time >= s->fixed_timestep) {
        for (size_t i = 0; i < s->fixed_update_list.count; i++) {
            tc_component* c = s->fixed_update_list.items[i];
            if (c->enabled) {
                if (profile) tc_profiler_begin_section(tc_component_type_name(c));
                tc_component_fixed_update(c, (float)s->fixed_timestep);
                if (profile) tc_profiler_end_section();
            }
        }
        s->accumulated_time -= s->fixed_timestep;
    }

    // 3. Regular update
    for (size_t i = 0; i < s->update_list.count; i++) {
        tc_component* c = s->update_list.items[i];
        if (c->enabled) {
            if (profile) tc_profiler_begin_section(tc_component_type_name(c));
            tc_component_update(c, (float)dt);
            if (profile) tc_profiler_end_section();
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

void tc_scene_before_render(tc_scene* s) {
    if (!s) return;

    bool profile = tc_profiler_enabled();

    for (size_t i = 0; i < s->before_render_list.count; i++) {
        tc_component* c = s->before_render_list.items[i];
        if (c->enabled) {
            if (profile) tc_profiler_begin_section(tc_component_type_name(c));
            tc_component_before_render(c);
            if (profile) tc_profiler_end_section();
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

// ============================================================================
// Python Wrapper Access
// ============================================================================

void tc_scene_set_py_wrapper(tc_scene* s, void* py_wrapper) {
    if (s) s->py_wrapper = py_wrapper;
}

void* tc_scene_get_py_wrapper(tc_scene* s) {
    return s ? s->py_wrapper : NULL;
}

// ============================================================================
// Component Type Lists
// ============================================================================

tc_component* tc_scene_first_component_of_type(tc_scene* s, const char* type_name) {
    if (!s || !type_name) return NULL;
    return (tc_component*)tc_resource_map_get(s->type_heads, type_name);
}

size_t tc_scene_count_components_of_type(tc_scene* s, const char* type_name) {
    size_t count = 0;
    for (tc_component* c = tc_scene_first_component_of_type(s, type_name);
         c != NULL; c = c->type_next) {
        count++;
    }
    return count;
}

void tc_scene_foreach_component_of_type(
    tc_scene* s,
    const char* type_name,
    tc_component_iter_fn callback,
    void* user_data
) {
    if (!s || !type_name || !callback) return;

    // Get type and all descendants
    const char* types[64];
    size_t type_count = tc_component_registry_get_type_and_descendants(type_name, types, 64);

    // If type not in registry, fall back to direct lookup
    if (type_count == 0) {
        for (tc_component* c = tc_scene_first_component_of_type(s, type_name);
             c != NULL; c = c->type_next) {
            if (!callback(c, user_data)) return;
        }
        return;
    }

    // Iterate over type and all descendant types
    for (size_t i = 0; i < type_count; i++) {
        for (tc_component* c = tc_scene_first_component_of_type(s, types[i]);
             c != NULL; c = c->type_next) {
            if (!callback(c, user_data)) return;
        }
    }
}

// ============================================================================
// Component Type Enumeration
// ============================================================================

// Helper struct for collecting type info
typedef struct {
    tc_scene_component_type* types;
    size_t count;
    size_t capacity;
} ComponentTypeCollector;

// Callback to count and collect component types
static bool collect_component_type(const char* key, void* value, void* user_data) {
    ComponentTypeCollector* collector = (ComponentTypeCollector*)user_data;
    tc_component* head = (tc_component*)value;

    // Count components in this list
    size_t count = 0;
    for (tc_component* c = head; c != NULL; c = c->type_next) {
        count++;
    }

    if (count == 0) return true;  // Skip empty lists

    // Grow if needed
    if (collector->count >= collector->capacity) {
        size_t new_cap = collector->capacity == 0 ? 16 : collector->capacity * 2;
        tc_scene_component_type* new_types = (tc_scene_component_type*)realloc(
            collector->types,
            new_cap * sizeof(tc_scene_component_type)
        );
        if (!new_types) return false;  // Allocation failed
        collector->types = new_types;
        collector->capacity = new_cap;
    }

    // Add entry
    collector->types[collector->count].type_name = key;
    collector->types[collector->count].count = count;
    collector->count++;

    return true;
}

tc_scene_component_type* tc_scene_get_all_component_types(tc_scene* s, size_t* out_count) {
    if (!out_count) return NULL;
    *out_count = 0;

    if (!s || !s->type_heads) return NULL;

    ComponentTypeCollector collector = {NULL, 0, 0};
    tc_resource_map_foreach(s->type_heads, collect_component_type, &collector);

    *out_count = collector.count;
    return collector.types;
}
