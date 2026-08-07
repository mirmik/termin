// tc_scene.c - Scene implementation using pool with generational indices
#include "core/tc_scene.h"
#include "core/tc_scene_pool.h"
#include "core/tc_scene_extension.h"
#include <tcbase/tc_event.h>
#include <tcbase/tc_resource_map.h>
#include <tcbase/tc_string.h>
#include <tcbase/tc_log.h>
#include <tc_profiler.h>
#include "core/tc_entity_pool_registry.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>

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

static void list_insert_lifecycle_priority(
    ComponentList* list,
    tc_component* c,
    tc_component_lifecycle_stage stage
) {
    if (list->count >= list->capacity) {
        size_t new_cap = list->capacity == 0 ? INITIAL_CAPACITY : list->capacity * 2;
        list->items = realloc(list->items, new_cap * sizeof(tc_component*));
        list->capacity = new_cap;
    }

    const int priority = c->lifecycle_priorities[stage];
    size_t index = 0;
    while (index < list->count) {
        const tc_component* existing = list->items[index];
        const int existing_priority = existing->lifecycle_priorities[stage];
        if (existing_priority < priority) break;
        if (existing_priority == priority &&
            existing->lifecycle_registration_order >
                c->lifecycle_registration_order) {
            break;
        }
        index++;
    }
    memmove(
        &list->items[index + 1],
        &list->items[index],
        (list->count - index) * sizeof(tc_component*)
    );
    list->items[index] = c;
    list->count++;
}

static void list_remove(ComponentList* list, tc_component* c) {
    for (size_t i = 0; i < list->count; i++) {
        if (list->items[i] == c) {
            memmove(
                &list->items[i],
                &list->items[i + 1],
                (list->count - i - 1) * sizeof(tc_component*)
            );
            list->count--;
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

static void list_set_lifecycle_membership(
    ComponentList* list,
    tc_component* c,
    bool present,
    tc_component_lifecycle_stage stage
) {
    bool contains = list_contains(list, c);
    if (present && !contains) {
        list_insert_lifecycle_priority(list, c, stage);
    } else if (!present && contains) {
        list_remove(list, c);
    }
}

// ============================================================================
// Scene Pool - Global singleton
// ============================================================================

#define MAX_SCENES 256
#define INITIAL_POOL_CAPACITY 16

typedef struct tc_scene_slot {
    uint32_t generation;
    bool alive;

    tc_entity_pool_handle pool_handle;
    tc_scene_mode mode;
    ComponentList pending_starts;
    uint64_t pending_start_revision;
    uint64_t pending_start_processed_revision[2];
    uint64_t pending_start_scan_count;
    uint64_t pending_start_visit_count;
    ComponentList update_list;
    ComponentList fixed_update_list;
    ComponentList late_update_list;
    double fixed_timestep;
    double time_scale;
    double accumulated_time;
    bool render_requested;
    tc_resource_map* type_heads;
    tc_value metadata;  // Extensible metadata storage (dict per scene)
    const char* name;
    const char* source_path;
    const char* uuid;
    tc_component* capability_heads[TC_COMPONENT_MAX_CAPABILITIES];
    size_t capability_counts[TC_COMPONENT_MAX_CAPABILITIES];
    uint64_t next_lifecycle_registration_order;
    tc_event_bus* event_bus;

    // Layer and flag names (64 each per scene, interned strings)
    const char* layer_names[64];
    const char* flag_names[64];
    void* ext_instances[TC_SCENE_EXT_TYPE_COUNT];
} tc_scene_slot;

typedef struct {
    tc_scene_slot* slots;

    // Pool management
    uint32_t* free_stack;
    size_t free_count;
    size_t capacity;
    size_t count;
} ScenePool;

static ScenePool* g_pool = NULL;

#define SCENE_SLOT(idx) (&g_pool->slots[(idx)])
#define CAPABILITY_HEAD(idx, slot) SCENE_SLOT(idx)->capability_heads[(slot)]
#define CAPABILITY_COUNT(idx, slot) SCENE_SLOT(idx)->capability_counts[(slot)]
#define EXT_INSTANCE(idx, slot) SCENE_SLOT(idx)->ext_instances[(slot)]

static void scene_capability_attach(uint32_t idx, tc_component* c, uint32_t slot);
static void scene_capability_detach(uint32_t idx, tc_component* c, uint32_t slot);
static void scene_capability_sync_legacy_bridges(tc_component* c);

static void scene_slot_reset(tc_scene_slot* slot, uint32_t generation) {
    memset(slot, 0, sizeof(*slot));
    slot->generation = generation;
    slot->pool_handle = TC_ENTITY_POOL_HANDLE_INVALID;
    slot->mode = TC_SCENE_MODE_INACTIVE;
    slot->fixed_timestep = 1.0 / 60.0;
    slot->time_scale = 1.0;
}

static tc_entity_pool* scene_slot_entity_pool(const tc_scene_slot* slot) {
    return tc_entity_pool_registry_get(slot->pool_handle);
}

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

    g_pool->slots = (tc_scene_slot*)malloc(cap * sizeof(tc_scene_slot));
    g_pool->free_stack = (uint32_t*)malloc(cap * sizeof(uint32_t));
    if (!g_pool->slots || !g_pool->free_stack) {
        tc_log_error("[tc_scene_pool] slot storage allocation failed");
        free(g_pool->slots);
        free(g_pool->free_stack);
        free(g_pool);
        g_pool = NULL;
        return;
    }

    for (size_t i = 0; i < cap; i++) {
        scene_slot_reset(&g_pool->slots[i], 0);
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
        if (g_pool->slots[i].alive) {
            tc_scene_handle h = { (uint32_t)i, g_pool->slots[i].generation };
            tc_scene_free(h);
        }
    }

    free(g_pool->slots);
    free(g_pool->free_stack);
    free(g_pool);
    g_pool = NULL;
}

// ============================================================================
// Pool Growth
// ============================================================================

static bool pool_grow(void) {
    size_t old_cap = g_pool->capacity;
    size_t new_cap = old_cap * 2;
    if (new_cap > MAX_SCENES) new_cap = MAX_SCENES;
    if (new_cap <= old_cap) {
        tc_log_error("[tc_scene_pool] max capacity reached");
        return false;
    }

    tc_scene_slot* new_slots = (tc_scene_slot*)malloc(
        new_cap * sizeof(tc_scene_slot));
    uint32_t* new_free_stack = (uint32_t*)malloc(
        new_cap * sizeof(uint32_t));
    if (!new_slots || !new_free_stack) {
        tc_log_error("[tc_scene_pool] failed to grow scene pool");
        free(new_slots);
        free(new_free_stack);
        return false;
    }

    memcpy(new_slots, g_pool->slots, old_cap * sizeof(tc_scene_slot));
    memcpy(
        new_free_stack,
        g_pool->free_stack,
        g_pool->free_count * sizeof(uint32_t)
    );
    for (size_t i = old_cap; i < new_cap; i++) {
        scene_slot_reset(&new_slots[i], 0);
    }

    free(g_pool->slots);
    free(g_pool->free_stack);
    g_pool->slots = new_slots;
    g_pool->free_stack = new_free_stack;

    for (size_t i = new_cap; i > old_cap; i--) {
        g_pool->free_stack[g_pool->free_count++] = (uint32_t)(i - 1);
    }

    g_pool->capacity = new_cap;
    return true;
}

// ============================================================================
// Handle validation
// ============================================================================

static inline bool handle_alive(tc_scene_handle h) {
    if (!g_pool) return false;
    if (h.index >= g_pool->capacity) return false;
    return g_pool->slots[h.index].alive && g_pool->slots[h.index].generation == h.generation;
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
        if (!g_pool) {
            tc_log_error("[tc_scene_pool] initialization failed");
            return TC_SCENE_HANDLE_INVALID;
        }
    }

    if (g_pool->free_count == 0) {
        if (!pool_grow()) {
            tc_log_error("[tc_scene_pool] no free slots");
            return TC_SCENE_HANDLE_INVALID;
        }
    }

    uint32_t idx = g_pool->free_stack[--g_pool->free_count];
    uint32_t gen = g_pool->slots[idx].generation;
    tc_scene_slot* slot = &g_pool->slots[idx];
    scene_slot_reset(slot, gen);

    slot->pool_handle = tc_entity_pool_registry_create(512);
    tc_entity_pool* entity_pool = scene_slot_entity_pool(slot);
    if (!tc_entity_pool_handle_valid(slot->pool_handle) || !entity_pool) {
        tc_log_error(
            "[tc_scene_pool] failed to create entity pool for scene slot %u",
            idx
        );
        if (tc_entity_pool_handle_valid(slot->pool_handle)) {
            tc_entity_pool_registry_destroy(slot->pool_handle);
        }
        scene_slot_reset(slot, gen);
        g_pool->free_stack[g_pool->free_count++] = idx;
        return TC_SCENE_HANDLE_INVALID;
    }

    slot->type_heads = tc_resource_map_new(NULL);
    slot->event_bus = tc_event_bus_create();
    if (!slot->type_heads || !slot->event_bus) {
        tc_log_error(
            "[tc_scene_pool] failed to allocate resources for scene slot %u",
            idx
        );
        tc_resource_map_free(slot->type_heads);
        tc_event_bus_destroy(slot->event_bus);
        tc_entity_pool_registry_destroy(slot->pool_handle);
        scene_slot_reset(slot, gen);
        g_pool->free_stack[g_pool->free_count++] = idx;
        return TC_SCENE_HANDLE_INVALID;
    }

    list_init(&slot->pending_starts);
    list_init(&slot->update_list);
    list_init(&slot->fixed_update_list);
    list_init(&slot->late_update_list);
    slot->metadata = tc_value_dict_new();
    slot->name = name ? tc_intern_string(name) : tc_intern_string("(unnamed)");

    tc_scene_handle h = { idx, gen };
    tc_entity_pool_set_scene(entity_pool, h);
    slot->alive = true;
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
    tc_scene_slot* slot = &g_pool->slots[idx];

    // Components must be removed while the scene schedulers, type indices,
    // event bus, and extensions are still alive.  tc_entity_pool_destroy()
    // invokes component destruction and removal callbacks before releasing
    // the entity-owned references.
    if (tc_entity_pool_registry_alive(slot->pool_handle)) {
        tc_entity_pool_registry_destroy(slot->pool_handle);
    } else {
        tc_log_error(
            "[tc_scene_free] scene (%u,%u) owns invalid entity pool handle (%u,%u)",
            h.index,
            h.generation,
            slot->pool_handle.index,
            slot->pool_handle.generation
        );
    }
    slot->pool_handle = TC_ENTITY_POOL_HANDLE_INVALID;

    // Scene-owned extensions may now release resources that referenced
    // entities or components.
    tc_scene_ext_detach_all(h);

    // Free metadata.
    tc_value_free(&slot->metadata);

    // Stop delivering scene events after all component removal notifications.
    tc_event_bus_destroy(slot->event_bus);

    // Free component lists and type heads after components have unregistered.
    list_free(&slot->pending_starts);
    list_free(&slot->update_list);
    list_free(&slot->fixed_update_list);
    list_free(&slot->late_update_list);
    tc_resource_map_free(slot->type_heads);

    uint32_t next_generation = slot->generation + 1;
    scene_slot_reset(slot, next_generation);
    g_pool->free_stack[g_pool->free_count++] = idx;
    g_pool->count--;
}

tc_event_bus* tc_scene_event_bus(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return g_pool->slots[h.index].event_bus;
}

void tc_scene_publish_event(tc_scene_handle h, const tc_event* event) {
    if (!handle_alive(h) || !event) return;
    tc_event_bus_publish(g_pool->slots[h.index].event_bus, event);
}

void* tc_scene_ext_slot_get(tc_scene_handle h, tc_scene_ext_type_id type_id) {
    if (!handle_alive(h)) return NULL;
    if (type_id >= TC_SCENE_EXT_TYPE_COUNT) return NULL;
    return EXT_INSTANCE(h.index, (size_t)type_id);
}

bool tc_scene_ext_slot_set(tc_scene_handle h, tc_scene_ext_type_id type_id, void* instance) {
    if (!handle_alive(h)) return false;
    if (type_id >= TC_SCENE_EXT_TYPE_COUNT) return false;
    EXT_INSTANCE(h.index, (size_t)type_id) = instance;
    return true;
}

void tc_scene_ext_slot_clear(tc_scene_handle h, tc_scene_ext_type_id type_id) {
    if (!handle_alive(h)) return;
    if (type_id >= TC_SCENE_EXT_TYPE_COUNT) return;
    EXT_INSTANCE(h.index, (size_t)type_id) = NULL;
}

// ============================================================================
// Pool Queries
// ============================================================================

size_t tc_scene_pool_count(void) {
    return g_pool ? g_pool->count : 0;
}

const char* tc_scene_pool_get_name(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return g_pool->slots[h.index].name;
}

void tc_scene_pool_set_name(tc_scene_handle h, const char* name) {
    if (!handle_alive(h)) return;
    g_pool->slots[h.index].name = name ? tc_intern_string(name) : tc_intern_string("(unnamed)");
}

const char* tc_scene_get_name(tc_scene_handle h) {
    return tc_scene_pool_get_name(h);
}

void tc_scene_set_name(tc_scene_handle h, const char* name) {
    tc_scene_pool_set_name(h, name);
}

const char* tc_scene_get_source_path(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return g_pool->slots[h.index].source_path;
}

void tc_scene_set_source_path(tc_scene_handle h, const char* path) {
    if (!handle_alive(h)) return;
    g_pool->slots[h.index].source_path = (path && path[0]) ? tc_intern_string(path) : NULL;
}

// ============================================================================
// UUID
// ============================================================================

const char* tc_scene_get_uuid(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return g_pool->slots[h.index].uuid;
}

void tc_scene_set_uuid(tc_scene_handle h, const char* uuid) {
    if (!handle_alive(h)) return;
    g_pool->slots[h.index].uuid = uuid ? tc_intern_string(uuid) : NULL;
}

// ============================================================================
// Layer and Flag Names
// ============================================================================

const char* tc_scene_get_layer_name(tc_scene_handle h, int index) {
    if (!handle_alive(h)) return NULL;
    if (index < 0 || index >= 64) return NULL;
    return g_pool->slots[h.index].layer_names[index];
}

void tc_scene_set_layer_name(tc_scene_handle h, int index, const char* name) {
    if (!handle_alive(h)) return;
    if (index < 0 || index >= 64) return;
    g_pool->slots[h.index].layer_names[index] = (name && name[0]) ? tc_intern_string(name) : NULL;
}

const char* tc_scene_get_flag_name(tc_scene_handle h, int index) {
    if (!handle_alive(h)) return NULL;
    if (index < 0 || index >= 64) return NULL;
    return g_pool->slots[h.index].flag_names[index];
}

void tc_scene_set_flag_name(tc_scene_handle h, int index, const char* name) {
    if (!handle_alive(h)) return;
    if (index < 0 || index >= 64) return;
    g_pool->slots[h.index].flag_names[index] = (name && name[0]) ? tc_intern_string(name) : NULL;
}

// ============================================================================
// Pool Iteration
// ============================================================================

void tc_scene_pool_foreach(tc_scene_pool_iter_fn callback, void* user_data) {
    if (!g_pool || !callback) return;

    for (size_t i = 0; i < g_pool->capacity; i++) {
        if (g_pool->slots[i].alive) {
            tc_scene_handle h = { (uint32_t)i, g_pool->slots[i].generation };
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
        if (g_pool->slots[i].alive) {
            tc_scene_handle h = { (uint32_t)i, g_pool->slots[i].generation };
            tc_entity_pool* entity_pool = scene_slot_entity_pool(
                &g_pool->slots[i]);
            infos[idx].handle = h;
            infos[idx].name = g_pool->slots[i].name;
            infos[idx].entity_count = tc_entity_pool_count(entity_pool);
            infos[idx].pending_count = g_pool->slots[i].pending_starts.count;
            infos[idx].update_count = g_pool->slots[i].update_list.count;
            infos[idx].fixed_update_count = g_pool->slots[i].fixed_update_list.count;
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
    return scene_slot_entity_pool(&g_pool->slots[h.index]);
}

tc_entity_pool_handle tc_scene_entity_pool_handle(tc_scene_handle h) {
    if (!handle_alive(h)) return TC_ENTITY_POOL_HANDLE_INVALID;
    return g_pool->slots[h.index].pool_handle;
}

// ============================================================================
// Component Registration
// ============================================================================

void tc_scene_register_component(tc_scene_handle h, tc_component* c) {
    if (!handle_alive(h) || !c) return;

    if (handle_alive(c->lifecycle_scene) && !tc_scene_handle_eq(c->lifecycle_scene, h)) {
        tc_log(
            TC_LOG_ERROR,
            "[tc_scene_register_component] component is already registered with scene (%u,%u); requested (%u,%u)",
            c->lifecycle_scene.index,
            c->lifecycle_scene.generation,
            h.index,
            h.generation
        );
        return;
    }

    uint32_t idx = h.index;
    c->lifecycle_scene = h;
    if (c->lifecycle_registration_order == 0) {
        c->lifecycle_registration_order =
            ++g_pool->slots[idx].next_lifecycle_registration_order;
    }
    scene_capability_sync_legacy_bridges(c);

    // Add to pending_start if not started
    if (!c->_started && !list_contains(&g_pool->slots[idx].pending_starts, c)) {
        list_push(&g_pool->slots[idx].pending_starts, c);
        tc_scene_mark_component_startability_changed(h);
    }

    // Add to update lists based on flags
    if (c->has_update && !list_contains(&g_pool->slots[idx].update_list, c)) {
        list_insert_lifecycle_priority(
            &g_pool->slots[idx].update_list,
            c,
            TC_COMPONENT_LIFECYCLE_UPDATE
        );
    }
    if (c->has_fixed_update && !list_contains(&g_pool->slots[idx].fixed_update_list, c)) {
        list_insert_lifecycle_priority(
            &g_pool->slots[idx].fixed_update_list,
            c,
            TC_COMPONENT_LIFECYCLE_FIXED_UPDATE
        );
    }
    if (c->has_late_update && !list_contains(&g_pool->slots[idx].late_update_list, c)) {
        list_insert_lifecycle_priority(
            &g_pool->slots[idx].late_update_list,
            c,
            TC_COMPONENT_LIFECYCLE_LATE_UPDATE
        );
    }
    for (uint32_t slot = 0; slot < TC_COMPONENT_MAX_CAPABILITIES; slot++) {
        scene_capability_attach(idx, c, slot);
    }

    tc_scene_ext_on_component_registered(h, c);

    // Add to type list (intrusive doubly-linked list)
    const char* type_name = tc_component_type_name(c);
    if (type_name && c->type_prev == NULL && c->type_next == NULL) {
        tc_component* head = (tc_component*)tc_resource_map_get(g_pool->slots[idx].type_heads, type_name);
        if (head == NULL) {
            tc_resource_map_add(g_pool->slots[idx].type_heads, type_name, c);
        } else if (head != c) {
            c->type_next = head;
            head->type_prev = c;
            tc_resource_map_remove(g_pool->slots[idx].type_heads, type_name);
            tc_resource_map_add(g_pool->slots[idx].type_heads, type_name, c);
        }
    }
}

void tc_scene_unregister_component(tc_scene_handle h, tc_component* c) {
    if (!handle_alive(h) || !c) return;

    if (handle_alive(c->lifecycle_scene) && !tc_scene_handle_eq(c->lifecycle_scene, h)) {
        tc_log(
            TC_LOG_ERROR,
            "[tc_scene_unregister_component] component belongs to scene (%u,%u); requested (%u,%u)",
            c->lifecycle_scene.index,
            c->lifecycle_scene.generation,
            h.index,
            h.generation
        );
        return;
    }

    uint32_t idx = h.index;
    tc_scene_ext_on_component_unregistering(h, c);
    c->lifecycle_scene = TC_SCENE_HANDLE_INVALID;

    list_remove(&g_pool->slots[idx].pending_starts, c);
    list_remove(&g_pool->slots[idx].update_list, c);
    list_remove(&g_pool->slots[idx].fixed_update_list, c);
    list_remove(&g_pool->slots[idx].late_update_list, c);
    c->lifecycle_registration_order = 0;

    for (uint32_t slot = 0; slot < TC_COMPONENT_MAX_CAPABILITIES; slot++) {
        scene_capability_detach(idx, c, slot);
    }

    // Remove from type list
    const char* type_name = tc_component_type_name(c);
    if (type_name) {
        tc_component* head = (tc_component*)tc_resource_map_get(g_pool->slots[idx].type_heads, type_name);
        if (head == c) {
            tc_resource_map_remove(g_pool->slots[idx].type_heads, type_name);
            if (c->type_next) {
                c->type_next->type_prev = NULL;
                tc_resource_map_add(g_pool->slots[idx].type_heads, type_name, c->type_next);
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

void tc_component_set_lifecycle_capabilities(
    tc_component* c,
    bool has_update,
    bool has_fixed_update,
    bool has_late_update
) {
    if (!c) return;

    c->has_update = has_update;
    c->has_fixed_update = has_fixed_update;
    c->has_late_update = has_late_update;

    tc_scene_handle scene = c->lifecycle_scene;
    if (!handle_alive(scene)) return;

    uint32_t idx = scene.index;
    list_set_lifecycle_membership(
        &g_pool->slots[idx].update_list,
        c,
        has_update,
        TC_COMPONENT_LIFECYCLE_UPDATE
    );
    list_set_lifecycle_membership(
        &g_pool->slots[idx].fixed_update_list,
        c,
        has_fixed_update,
        TC_COMPONENT_LIFECYCLE_FIXED_UPDATE
    );
    list_set_lifecycle_membership(
        &g_pool->slots[idx].late_update_list,
        c,
        has_late_update,
        TC_COMPONENT_LIFECYCLE_LATE_UPDATE
    );
}

int tc_component_get_lifecycle_priority(
    const tc_component* c,
    tc_component_lifecycle_stage stage
) {
    if (!c || stage < 0 || stage >= TC_COMPONENT_LIFECYCLE_STAGE_COUNT) return 0;
    return c->lifecycle_priorities[stage];
}

bool tc_component_set_lifecycle_priority(
    tc_component* c,
    tc_component_lifecycle_stage stage,
    int priority
) {
    if (!c || stage < 0 || stage >= TC_COMPONENT_LIFECYCLE_STAGE_COUNT) return false;
    if (c->lifecycle_priorities[stage] == priority) return true;

    c->lifecycle_priorities[stage] = priority;
    if (!handle_alive(c->lifecycle_scene)) return true;

    ComponentList* list = NULL;
    bool present = false;
    tc_scene_slot* scene = &g_pool->slots[c->lifecycle_scene.index];
    switch (stage) {
        case TC_COMPONENT_LIFECYCLE_UPDATE:
            list = &scene->update_list;
            present = c->has_update;
            break;
        case TC_COMPONENT_LIFECYCLE_FIXED_UPDATE:
            list = &scene->fixed_update_list;
            present = c->has_fixed_update;
            break;
        case TC_COMPONENT_LIFECYCLE_LATE_UPDATE:
            list = &scene->late_update_list;
            present = c->has_late_update;
            break;
        default:
            return false;
    }
    if (present && list_contains(list, c)) {
        list_remove(list, c);
        list_insert_lifecycle_priority(list, c, stage);
    }
    return true;
}

// ============================================================================
// Update Loop
// ============================================================================

static void component_profile_name(
    const tc_component* component,
    char out_name[TC_PROFILER_MAX_NAME_LEN]
) {
    const char* type_name = tc_component_type_name(component);
    const char* entity_name = tc_entity_handle_valid(component->owner)
        ? tc_entity_name(component->owner)
        : "detached";

    if (component->source_id && component->source_id[0] != '\0') {
        snprintf(
            out_name,
            TC_PROFILER_MAX_NAME_LEN,
            "%.24s @ %.20s [%.8s]",
            type_name,
            entity_name,
            component->source_id
        );
        return;
    }

    // Directly registered components are allowed to have neither an owner nor
    // an authoring source id. Keep those instances distinct in a live capture.
    snprintf(
        out_name,
        TC_PROFILER_MAX_NAME_LEN,
        "%.24s @ %.16s [%p]",
        type_name,
        entity_name,
        (const void*)component
    );
}

static void profile_component_begin(const tc_component* component) {
    char name[TC_PROFILER_MAX_NAME_LEN];
    component_profile_name(component, name);
    tc_profiler_begin_section(name);
}

static void process_pending_start(uint32_t idx, bool editor_mode, bool profile) {
    tc_scene_slot* slot = &g_pool->slots[idx];
    ComponentList* pending = &slot->pending_starts;
    const size_t mode_index = editor_mode ? 1 : 0;
    const uint64_t revision = slot->pending_start_revision;
    if (slot->pending_start_processed_revision[mode_index] == revision) return;

    size_t count = pending->count;
    if (count == 0) {
        slot->pending_start_processed_revision[mode_index] = revision;
        return;
    }

    tc_component** copy = malloc(count * sizeof(tc_component*));
    if (!copy) {
        tc_log_error(
            "[tc_scene] failed to allocate pending-start snapshot for scene slot %u",
            idx
        );
        return;
    }
    memcpy(copy, pending->items, count * sizeof(tc_component*));
    slot->pending_start_processed_revision[mode_index] = revision;
    slot->pending_start_scan_count++;

    for (size_t i = 0; i < count; i++) {
        tc_component* c = copy[i];
        slot->pending_start_visit_count++;
        if (!list_contains(pending, c)) continue;
        if (!c->enabled) continue;
        if (editor_mode && !c->active_in_editor) continue;

        if (profile) profile_component_begin(c);
        tc_component_start(c);
        if (profile) tc_profiler_end_section();
        list_remove(pending, c);
    }

    free(copy);
}

static inline bool component_entity_enabled(tc_component* c) {
    if (!tc_entity_handle_valid(c->owner)) return true;
    tc_entity_pool* pool = tc_entity_pool_registry_get(c->owner.pool);
    if (!pool) return true;
    return tc_entity_pool_enabled(pool, c->owner.id);
}

static inline bool component_passes_filter(tc_component* c, int filter_flags) {
    if (!c) return false;
    if ((filter_flags & TC_SCENE_FILTER_ENABLED) && !c->enabled) return false;
    if ((filter_flags & TC_SCENE_FILTER_ACTIVE_IN_EDITOR) && !c->active_in_editor) return false;
    if ((filter_flags & TC_SCENE_FILTER_ENTITY_ENABLED) && !component_entity_enabled(c)) return false;
    if ((filter_flags & TC_SCENE_FILTER_VISIBLE) && tc_entity_handle_valid(c->owner) && !tc_entity_visible(c->owner)) return false;
    return true;
}

static void scene_capability_attach(uint32_t idx, tc_component* c, uint32_t slot) {
    if (!c) return;
    if ((c->capability_mask & (UINT64_C(1) << slot)) == 0) return;
    if (CAPABILITY_HEAD(idx, slot) == c || c->capability_prev[slot] || c->capability_next[slot]) return;

    tc_component* head = CAPABILITY_HEAD(idx, slot);
    int priority = c->capability_priorities[slot];

    if (!head || priority > head->capability_priorities[slot]) {
        c->capability_prev[slot] = NULL;
        c->capability_next[slot] = head;
        if (head) {
            head->capability_prev[slot] = c;
        }
        CAPABILITY_HEAD(idx, slot) = c;
        CAPABILITY_COUNT(idx, slot)++;
        return;
    }

    tc_component* prev = head;
    while (prev->capability_next[slot] &&
           prev->capability_next[slot]->capability_priorities[slot] >= priority) {
        prev = prev->capability_next[slot];
    }

    tc_component* next = prev->capability_next[slot];
    c->capability_prev[slot] = prev;
    c->capability_next[slot] = next;
    prev->capability_next[slot] = c;
    if (next) {
        next->capability_prev[slot] = c;
    }
    CAPABILITY_COUNT(idx, slot)++;
}

static void scene_capability_detach(uint32_t idx, tc_component* c, uint32_t slot) {
    if (!c) return;

    tc_component* prev = c->capability_prev[slot];
    tc_component* next = c->capability_next[slot];
    bool was_head = CAPABILITY_HEAD(idx, slot) == c;

    if (!was_head && !prev && !next) {
        return;
    }

    if (prev) {
        prev->capability_next[slot] = next;
    } else if (was_head) {
        CAPABILITY_HEAD(idx, slot) = next;
    }

    if (next) {
        next->capability_prev[slot] = prev;
    }

    c->capability_prev[slot] = NULL;
    c->capability_next[slot] = NULL;

    if (CAPABILITY_COUNT(idx, slot) > 0) {
        CAPABILITY_COUNT(idx, slot)--;
    }
}

static void scene_capability_sync_legacy_bridges(tc_component* c) {
    if (!c) return;

}

void tc_scene_update(tc_scene_handle h, double dt) {
    if (!handle_alive(h)) return;

    uint32_t idx = h.index;
    const bool profile = tc_profiler_enabled();
    const double scaled_dt = dt * g_pool->slots[idx].time_scale;

    // 1. Process pending start
    if (profile) tc_profiler_begin_section("Start");
    process_pending_start(idx, false, profile);
    if (profile) tc_profiler_end_section();

    // 2. Fixed update loop
    if (profile) tc_profiler_begin_section("Fixed Update");
    g_pool->slots[idx].accumulated_time += scaled_dt;
    double fixed_dt = g_pool->slots[idx].fixed_timestep;
    ComponentList* fixed_list = &g_pool->slots[idx].fixed_update_list;

    while (g_pool->slots[idx].accumulated_time >= fixed_dt) {
        for (size_t i = 0; i < fixed_list->count; i++) {
            tc_component* c = fixed_list->items[i];
            if (c->enabled && component_entity_enabled(c)) {
                if (profile) profile_component_begin(c);
                tc_component_fixed_update(c, (float)fixed_dt);
                if (profile) tc_profiler_end_section();
            }
        }
        g_pool->slots[idx].accumulated_time -= fixed_dt;
    }
    if (profile) tc_profiler_end_section();

    // 3. Regular update
    if (profile) tc_profiler_begin_section("Update");
    ComponentList* update_list = &g_pool->slots[idx].update_list;
    for (size_t i = 0; i < update_list->count; i++) {
        tc_component* c = update_list->items[i];
        if (c->enabled && component_entity_enabled(c)) {
            if (profile) profile_component_begin(c);
            tc_component_update(c, (float)scaled_dt);
            if (profile) tc_profiler_end_section();
        }
    }
    if (profile) tc_profiler_end_section();

    // Extension update hooks
    if (profile) tc_profiler_begin_section("Extensions");
    tc_scene_ext_on_scene_update(h, scaled_dt);
    if (profile) tc_profiler_end_section();

    // 4. Late update runs after all regular component and extension updates.
    if (profile) tc_profiler_begin_section("Late Update");
    ComponentList* late_update_list = &g_pool->slots[idx].late_update_list;
    for (size_t i = 0; i < late_update_list->count; i++) {
        tc_component* c = late_update_list->items[i];
        if (c->enabled && component_entity_enabled(c)) {
            if (profile) profile_component_begin(c);
            tc_component_late_update(c, (float)scaled_dt);
            if (profile) tc_profiler_end_section();
        }
    }
    if (profile) tc_profiler_end_section();
}

void tc_scene_editor_update(tc_scene_handle h, double dt) {
    if (!handle_alive(h)) return;

    uint32_t idx = h.index;
    const bool profile = tc_profiler_enabled();

    if (profile) tc_profiler_begin_section("Start");
    process_pending_start(idx, true, profile);
    if (profile) tc_profiler_end_section();

    // Fixed update - only active_in_editor
    if (profile) tc_profiler_begin_section("Fixed Update");
    g_pool->slots[idx].accumulated_time += dt;
    double fixed_dt = g_pool->slots[idx].fixed_timestep;
    ComponentList* fixed_list = &g_pool->slots[idx].fixed_update_list;

    while (g_pool->slots[idx].accumulated_time >= fixed_dt) {
        for (size_t i = 0; i < fixed_list->count; i++) {
            tc_component* c = fixed_list->items[i];
            if (c->enabled && c->active_in_editor && component_entity_enabled(c)) {
                if (profile) profile_component_begin(c);
                tc_component_fixed_update(c, (float)fixed_dt);
                if (profile) tc_profiler_end_section();
            }
        }
        g_pool->slots[idx].accumulated_time -= fixed_dt;
    }
    if (profile) tc_profiler_end_section();

    // Regular update - only active_in_editor
    if (profile) tc_profiler_begin_section("Update");
    ComponentList* update_list = &g_pool->slots[idx].update_list;
    for (size_t i = 0; i < update_list->count; i++) {
        tc_component* c = update_list->items[i];
        if (c->enabled && c->active_in_editor && component_entity_enabled(c)) {
            if (profile) profile_component_begin(c);
            tc_component_update(c, (float)dt);
            if (profile) tc_profiler_end_section();
        }
    }
    if (profile) tc_profiler_end_section();

    // Extension update hooks (editor mode uses same dt callback contract)
    if (profile) tc_profiler_begin_section("Extensions");
    tc_scene_ext_on_scene_update(h, dt);
    if (profile) tc_profiler_end_section();

    // Late update - only active_in_editor
    if (profile) tc_profiler_begin_section("Late Update");
    ComponentList* late_update_list = &g_pool->slots[idx].late_update_list;
    for (size_t i = 0; i < late_update_list->count; i++) {
        tc_component* c = late_update_list->items[i];
        if (c->enabled && c->active_in_editor && component_entity_enabled(c)) {
            if (profile) profile_component_begin(c);
            tc_component_late_update(c, (float)dt);
            if (profile) tc_profiler_end_section();
        }
    }
    if (profile) tc_profiler_end_section();
}

void tc_scene_request_render(tc_scene_handle h) {
    if (!handle_alive(h)) return;
    g_pool->slots[h.index].render_requested = true;
}

bool tc_scene_consume_render_request(tc_scene_handle h) {
    if (!handle_alive(h)) return false;
    bool requested = g_pool->slots[h.index].render_requested;
    g_pool->slots[h.index].render_requested = false;
    return requested;
}

void tc_scene_foreach_with_capability(
    tc_scene_handle h,
    tc_component_cap_id cap_id,
    tc_component_iter_fn callback,
    void* user_data,
    int filter_flags
) {
    if (!handle_alive(h) || !callback) return;

    uint32_t slot = 0;
    if (!tc_component_capability_slot(cap_id, &slot)) return;

    uint32_t idx = h.index;
    for (tc_component* c = CAPABILITY_HEAD(idx, slot); c != NULL; c = c->capability_next[slot]) {
        if (!component_passes_filter(c, filter_flags)) continue;
        if (!callback(c, user_data)) return;
    }
}

size_t tc_scene_capability_count(tc_scene_handle h, tc_component_cap_id cap_id) {
    if (!handle_alive(h)) return 0;
    uint32_t slot = 0;
    if (!tc_component_capability_slot(cap_id, &slot)) return 0;
    return CAPABILITY_COUNT(h.index, slot);
}

void tc_scene_reindex_component_capabilities(tc_scene_handle h, tc_component* c) {
    if (!handle_alive(h) || !c) return;

    uint32_t idx = h.index;
    scene_capability_sync_legacy_bridges(c);

    for (uint32_t slot = 0; slot < TC_COMPONENT_MAX_CAPABILITIES; slot++) {
        scene_capability_detach(idx, c, slot);
    }
    for (uint32_t slot = 0; slot < TC_COMPONENT_MAX_CAPABILITIES; slot++) {
        scene_capability_attach(idx, c, slot);
    }
}

void tc_scene_reindex_component_capability(
    tc_scene_handle h,
    tc_component* c,
    tc_component_cap_id cap_id
) {
    if (!handle_alive(h) || !c) return;

    uint32_t slot = 0;
    if (!tc_component_capability_slot(cap_id, &slot)) return;

    uint32_t idx = h.index;
    scene_capability_sync_legacy_bridges(c);
    scene_capability_detach(idx, c, slot);
    scene_capability_attach(idx, c, slot);
}

void tc_scene_unindex_component_capability(
    tc_scene_handle h,
    tc_component* c,
    tc_component_cap_id cap_id
) {
    if (!handle_alive(h) || !c) return;

    uint32_t slot = 0;
    if (!tc_component_capability_slot(cap_id, &slot)) return;

    scene_capability_detach(h.index, c, slot);
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
    tc_entity_pool_foreach(
        scene_slot_entity_pool(&g_pool->slots[h.index]),
        notify_editor_start_callback,
        NULL
    );
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
    tc_entity_pool_foreach(
        scene_slot_entity_pool(&g_pool->slots[h.index]),
        notify_scene_inactive_callback,
        NULL
    );
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
    tc_entity_pool_foreach(
        scene_slot_entity_pool(&g_pool->slots[h.index]),
        notify_scene_active_callback,
        NULL
    );
}

// ============================================================================
// Fixed Timestep Configuration
// ============================================================================

double tc_scene_fixed_timestep(tc_scene_handle h) {
    if (!handle_alive(h)) return 1.0 / 60.0;
    return g_pool->slots[h.index].fixed_timestep;
}

void tc_scene_set_fixed_timestep(tc_scene_handle h, double dt) {
    if (!handle_alive(h) || dt <= 0) return;
    g_pool->slots[h.index].fixed_timestep = dt;
}

double tc_scene_time_scale(tc_scene_handle h) {
    if (!handle_alive(h)) return 1.0;
    return g_pool->slots[h.index].time_scale;
}

void tc_scene_set_time_scale(tc_scene_handle h, double scale) {
    if (!handle_alive(h)) return;
    if (!isfinite(scale) || scale < 0.0) {
        tc_log_error("[tc_scene] time scale must be finite and non-negative");
        return;
    }
    g_pool->slots[h.index].time_scale = scale;
}

double tc_scene_accumulated_time(tc_scene_handle h) {
    if (!handle_alive(h)) return 0.0;
    return g_pool->slots[h.index].accumulated_time;
}

void tc_scene_reset_accumulated_time(tc_scene_handle h) {
    if (!handle_alive(h)) return;
    g_pool->slots[h.index].accumulated_time = 0.0;
}

// ============================================================================
// Component Queries
// ============================================================================

size_t tc_scene_entity_count(tc_scene_handle h) {
    if (!handle_alive(h)) return 0;
    return tc_entity_pool_count(scene_slot_entity_pool(&g_pool->slots[h.index]));
}

size_t tc_scene_pending_start_count(tc_scene_handle h) {
    if (!handle_alive(h)) return 0;
    return g_pool->slots[h.index].pending_starts.count;
}

uint64_t tc_scene_pending_start_scan_count(tc_scene_handle h) {
    if (!handle_alive(h)) return 0;
    return g_pool->slots[h.index].pending_start_scan_count;
}

uint64_t tc_scene_pending_start_visit_count(tc_scene_handle h) {
    if (!handle_alive(h)) return 0;
    return g_pool->slots[h.index].pending_start_visit_count;
}

size_t tc_scene_update_list_count(tc_scene_handle h) {
    if (!handle_alive(h)) return 0;
    return g_pool->slots[h.index].update_list.count;
}

size_t tc_scene_fixed_update_list_count(tc_scene_handle h) {
    if (!handle_alive(h)) return 0;
    return g_pool->slots[h.index].fixed_update_list.count;
}

size_t tc_scene_late_update_list_count(tc_scene_handle h) {
    if (!handle_alive(h)) return 0;
    return g_pool->slots[h.index].late_update_list.count;
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

    tc_entity_pool_foreach(
        scene_slot_entity_pool(&g_pool->slots[h.index]),
        find_by_name_callback,
        &data
    );
    return data.found_id;
}

// ============================================================================
// Component Type Lists
// ============================================================================

tc_component* tc_scene_first_component_of_type(tc_scene_handle h, const char* type_name) {
    if (!handle_alive(h) || !type_name) return NULL;
    return (tc_component*)tc_resource_map_get(g_pool->slots[h.index].type_heads, type_name);
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
    tc_resource_map_foreach(g_pool->slots[h.index].type_heads, collect_component_type, &collector);

    *out_count = collector.count;
    return collector.types;
}

// ============================================================================
// Scene Mode
// ============================================================================

tc_scene_mode tc_scene_get_mode(tc_scene_handle h) {
    if (!handle_alive(h)) return TC_SCENE_MODE_INACTIVE;
    return g_pool->slots[h.index].mode;
}

void tc_scene_set_mode(tc_scene_handle h, tc_scene_mode mode) {
    if (!handle_alive(h)) return;

    tc_scene_mode old_mode = g_pool->slots[h.index].mode;
    g_pool->slots[h.index].mode = mode;

    if (mode == TC_SCENE_MODE_INACTIVE && old_mode != TC_SCENE_MODE_INACTIVE) {
        tc_scene_notify_scene_inactive(h);
    } else if (mode != TC_SCENE_MODE_INACTIVE && old_mode == TC_SCENE_MODE_INACTIVE) {
        tc_scene_notify_scene_active(h);
    }
}

void tc_scene_mark_component_startability_changed(tc_scene_handle h) {
    if (!handle_alive(h)) return;
    tc_scene_slot* slot = &g_pool->slots[h.index];
    slot->pending_start_revision++;
    if (slot->pending_start_revision == 0) {
        slot->pending_start_revision = 1;
        slot->pending_start_processed_revision[0] = 0;
        slot->pending_start_processed_revision[1] = 0;
    }
}

// ============================================================================
// Metadata
// ============================================================================

tc_value* tc_scene_get_metadata(tc_scene_handle h) {
    if (!handle_alive(h)) return NULL;
    return &g_pool->slots[h.index].metadata;
}

void tc_scene_set_metadata(tc_scene_handle h, tc_value value) {
    if (!handle_alive(h)) return;
    tc_value_free(&g_pool->slots[h.index].metadata);
    g_pool->slots[h.index].metadata = value;
}
