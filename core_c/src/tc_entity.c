// tc_entity.c - Entity implementation
#include "../include/tc_entity.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// ============================================================================
// Internal structures
// ============================================================================

#define TC_ENTITY_INITIAL_COMPONENTS 4
#define TC_REGISTRY_INITIAL_CAPACITY 64
#define TC_UUID_LENGTH 36

struct tc_entity {
    // Identity
    char* uuid;
    uint64_t runtime_id;
    uint32_t pick_id;
    bool pick_id_computed;

    // Name
    char* name;

    // Transform (owned)
    tc_transform* transform;

    // Components (owned array, component ownership depends on is_native)
    tc_component** components;
    size_t component_count;
    size_t component_capacity;

    // Flags
    bool visible;
    bool active;
    bool pickable;
    bool selectable;
    bool serializable;
    int priority;
    uint64_t layer;
    uint64_t flags;

    // Scene (opaque pointer)
    void* scene;

    // User data (for language bindings - e.g. C++ Entity*)
    void* data;
};

// ============================================================================
// Entity Registry (global singleton)
// ============================================================================

typedef struct {
    tc_entity** entities;
    size_t count;
    size_t capacity;
} tc_entity_registry;

static tc_entity_registry g_registry = {NULL, 0, 0};

static void registry_ensure_capacity(void) {
    if (g_registry.count >= g_registry.capacity) {
        size_t new_capacity = g_registry.capacity == 0
            ? TC_REGISTRY_INITIAL_CAPACITY
            : g_registry.capacity * 2;
        tc_entity** new_entities = (tc_entity**)realloc(
            g_registry.entities, new_capacity * sizeof(tc_entity*));
        if (!new_entities) return;
        g_registry.entities = new_entities;
        g_registry.capacity = new_capacity;
    }
}

static void registry_add(tc_entity* e) {
    registry_ensure_capacity();
    g_registry.entities[g_registry.count++] = e;
}

static void registry_remove(tc_entity* e) {
    for (size_t i = 0; i < g_registry.count; i++) {
        if (g_registry.entities[i] == e) {
            for (size_t j = i; j < g_registry.count - 1; j++) {
                g_registry.entities[j] = g_registry.entities[j + 1];
            }
            g_registry.count--;
            return;
        }
    }
}

// Forward declaration - implemented in tc_core.c
extern void tc_generate_uuid(char* out);
extern uint64_t tc_compute_runtime_id(const char* uuid);

// ============================================================================
// Entity Creation / Destruction
// ============================================================================

tc_entity* tc_entity_new(const char* name) {
    return tc_entity_new_with_uuid(name, NULL);
}

tc_entity* tc_entity_new_with_uuid(const char* name, const char* uuid) {
    tc_entity* e = (tc_entity*)calloc(1, sizeof(tc_entity));
    if (!e) return NULL;

    // UUID
    e->uuid = (char*)malloc(40);
    if (uuid && uuid[0]) {
        strncpy(e->uuid, uuid, 39);
        e->uuid[39] = '\0';
    } else {
        tc_generate_uuid(e->uuid);
    }
    e->runtime_id = tc_compute_runtime_id(e->uuid);
    e->pick_id = 0;
    e->pick_id_computed = false;

    // Name
    e->name = strdup(name ? name : "entity");

    // Transform
    e->transform = tc_transform_new();
    tc_transform_set_entity(e->transform, e);

    // Components
    e->components = NULL;
    e->component_count = 0;
    e->component_capacity = 0;

    // Flags
    e->visible = true;
    e->active = true;
    e->pickable = true;
    e->selectable = true;
    e->serializable = true;
    e->priority = 0;
    e->layer = 1;
    e->flags = 0;

    e->scene = NULL;

    // Register
    registry_add(e);

    return e;
}

tc_entity* tc_entity_new_with_pose(tc_general_pose3 pose, const char* name) {
    tc_entity* e = tc_entity_new(name);
    if (e) {
        tc_transform_set_local_pose(e->transform, pose);
    }
    return e;
}

void tc_entity_free(tc_entity* e) {
    if (!e) return;

    // Unregister
    registry_remove(e);

    // Destroy components
    for (size_t i = 0; i < e->component_count; i++) {
        tc_component* c = e->components[i];
        if (c) {
            tc_component_on_removed_from_entity(c);
            if (c->is_native) {
                tc_component_drop(c);
                free(c);
            }
        }
    }
    free(e->components);

    // Destroy transform
    tc_transform_free(e->transform);

    // Free strings
    free(e->uuid);
    free(e->name);

    free(e);
}

// ============================================================================
// Identity
// ============================================================================

const char* tc_entity_uuid(const tc_entity* e) {
    return e ? e->uuid : "";
}

uint64_t tc_entity_runtime_id(const tc_entity* e) {
    return e ? e->runtime_id : 0;
}

static void compute_pick_id(tc_entity* e) {
    if (e->pick_id_computed) return;

    // Simple hash from UUID
    uint32_t h = 0;
    const char* s = e->uuid;
    for (int i = 0; i < 8 && *s; i++, s++) {
        char c = *s;
        if (c == '-') { s++; c = *s; }
        int val = 0;
        if (c >= '0' && c <= '9') val = c - '0';
        else if (c >= 'a' && c <= 'f') val = c - 'a' + 10;
        else if (c >= 'A' && c <= 'F') val = c - 'A' + 10;
        h = (h << 4) | val;
    }
    h = h & 0x7FFFFFFF;
    if (h == 0) h = 1;

    e->pick_id = h;
    e->pick_id_computed = true;
}

uint32_t tc_entity_pick_id(tc_entity* e) {
    if (!e) return 0;
    compute_pick_id(e);
    return e->pick_id;
}

const char* tc_entity_name(const tc_entity* e) {
    return e ? e->name : "";
}

void tc_entity_set_name(tc_entity* e, const char* name) {
    if (!e) return;
    free(e->name);
    e->name = strdup(name ? name : "");
}

// ============================================================================
// Transform Access
// ============================================================================

tc_transform* tc_entity_transform(tc_entity* e) {
    return e ? e->transform : NULL;
}

tc_general_pose3 tc_entity_local_pose(const tc_entity* e) {
    return tc_transform_local_pose(e ? e->transform : NULL);
}

void tc_entity_set_local_pose(tc_entity* e, tc_general_pose3 pose) {
    if (e) tc_transform_set_local_pose(e->transform, pose);
}

tc_general_pose3 tc_entity_global_pose(const tc_entity* e) {
    return tc_transform_global_pose(e ? e->transform : NULL);
}

void tc_entity_set_global_pose(tc_entity* e, tc_general_pose3 pose) {
    if (e) tc_transform_set_global_pose(e->transform, pose);
}

// ============================================================================
// Flags
// ============================================================================

bool tc_entity_visible(const tc_entity* e) { return e ? e->visible : false; }
void tc_entity_set_visible(tc_entity* e, bool v) { if (e) e->visible = v; }

bool tc_entity_active(const tc_entity* e) { return e ? e->active : false; }
void tc_entity_set_active(tc_entity* e, bool v) { if (e) e->active = v; }

bool tc_entity_pickable(const tc_entity* e) { return e ? e->pickable : false; }
void tc_entity_set_pickable(tc_entity* e, bool v) { if (e) e->pickable = v; }

bool tc_entity_selectable(const tc_entity* e) { return e ? e->selectable : false; }
void tc_entity_set_selectable(tc_entity* e, bool v) { if (e) e->selectable = v; }

bool tc_entity_serializable(const tc_entity* e) { return e ? e->serializable : false; }
void tc_entity_set_serializable(tc_entity* e, bool v) { if (e) e->serializable = v; }

int tc_entity_priority(const tc_entity* e) { return e ? e->priority : 0; }
void tc_entity_set_priority(tc_entity* e, int p) { if (e) e->priority = p; }

uint64_t tc_entity_layer(const tc_entity* e) { return e ? e->layer : 0; }
void tc_entity_set_layer(tc_entity* e, uint64_t l) { if (e) e->layer = l; }

uint64_t tc_entity_flags(const tc_entity* e) { return e ? e->flags : 0; }
void tc_entity_set_flags(tc_entity* e, uint64_t f) { if (e) e->flags = f; }

// ============================================================================
// Component Management
// ============================================================================

static void entity_ensure_component_capacity(tc_entity* e) {
    if (e->component_count >= e->component_capacity) {
        size_t new_capacity = e->component_capacity == 0
            ? TC_ENTITY_INITIAL_COMPONENTS
            : e->component_capacity * 2;
        tc_component** new_comps = (tc_component**)realloc(
            e->components, new_capacity * sizeof(tc_component*));
        if (!new_comps) return;
        e->components = new_comps;
        e->component_capacity = new_capacity;
    }
}

void tc_entity_add_component(tc_entity* e, tc_component* c) {
    if (!e || !c) return;

    c->entity = e;
    entity_ensure_component_capacity(e);
    e->components[e->component_count++] = c;

    tc_component_on_added_to_entity(c);
}

void tc_entity_remove_component(tc_entity* e, tc_component* c) {
    if (!e || !c) return;

    for (size_t i = 0; i < e->component_count; i++) {
        if (e->components[i] == c) {
            tc_component_on_removed_from_entity(c);
            c->entity = NULL;

            for (size_t j = i; j < e->component_count - 1; j++) {
                e->components[j] = e->components[j + 1];
            }
            e->component_count--;
            return;
        }
    }
}

tc_component* tc_entity_get_component(tc_entity* e, const char* type_name) {
    if (!e || !type_name) return NULL;

    for (size_t i = 0; i < e->component_count; i++) {
        const char* tn = tc_component_type_name(e->components[i]);
        if (tn && strcmp(tn, type_name) == 0) {
            return e->components[i];
        }
    }
    return NULL;
}

size_t tc_entity_component_count(const tc_entity* e) {
    return e ? e->component_count : 0;
}

tc_component* tc_entity_component_at(tc_entity* e, size_t index) {
    if (!e || index >= e->component_count) return NULL;
    return e->components[index];
}

// ============================================================================
// Hierarchy
// ============================================================================

void tc_entity_set_parent(tc_entity* e, tc_entity* parent) {
    if (!e) return;
    tc_transform* pt = parent ? parent->transform : NULL;
    tc_transform_set_parent(e->transform, pt);
}

tc_entity* tc_entity_parent(const tc_entity* e) {
    if (!e) return NULL;
    tc_transform* pt = tc_transform_parent(e->transform);
    return pt ? tc_transform_entity(pt) : NULL;
}

size_t tc_entity_children_count(const tc_entity* e) {
    return e ? tc_transform_children_count(e->transform) : 0;
}

tc_entity* tc_entity_child_at(const tc_entity* e, size_t index) {
    if (!e) return NULL;
    tc_transform* ct = tc_transform_child_at(e->transform, index);
    return ct ? tc_transform_entity(ct) : NULL;
}

// ============================================================================
// Scene
// ============================================================================

void tc_entity_set_scene(tc_entity* e, void* scene) {
    if (e) e->scene = scene;
}

void* tc_entity_scene(const tc_entity* e) {
    return e ? e->scene : NULL;
}

void tc_entity_set_data(tc_entity* e, void* data) {
    if (e) e->data = data;
}

void* tc_entity_data(const tc_entity* e) {
    return e ? e->data : NULL;
}

// ============================================================================
// Lifecycle
// ============================================================================

void tc_entity_update(tc_entity* e, float dt) {
    if (!e || !e->active) return;

    for (size_t i = 0; i < e->component_count; i++) {
        tc_component_update(e->components[i], dt);
    }
}

void tc_entity_fixed_update(tc_entity* e, float dt) {
    if (!e || !e->active) return;

    for (size_t i = 0; i < e->component_count; i++) {
        tc_component_fixed_update(e->components[i], dt);
    }
}

void tc_entity_on_added_to_scene(tc_entity* e, void* scene) {
    if (!e) return;
    e->scene = scene;

    for (size_t i = 0; i < e->component_count; i++) {
        tc_component_start(e->components[i]);
    }
}

void tc_entity_on_removed_from_scene(tc_entity* e) {
    if (!e) return;

    for (size_t i = 0; i < e->component_count; i++) {
        tc_component_on_destroy(e->components[i]);
    }
    e->scene = NULL;
}

// ============================================================================
// EntityHandle
// ============================================================================

tc_entity_handle tc_entity_handle_from_uuid(const char* uuid) {
    tc_entity_handle h = {{0}};
    if (uuid) {
        strncpy(h.uuid, uuid, 39);
        h.uuid[39] = '\0';
    }
    return h;
}

tc_entity_handle tc_entity_handle_from_entity(const tc_entity* e) {
    if (!e) return tc_entity_handle_empty();
    return tc_entity_handle_from_uuid(e->uuid);
}

tc_entity* tc_entity_handle_get(tc_entity_handle h) {
    if (!h.uuid[0]) return NULL;
    return tc_entity_registry_find_by_uuid(h.uuid);
}

bool tc_entity_handle_is_valid(tc_entity_handle h) {
    return h.uuid[0] != '\0';
}

// ============================================================================
// Entity Registry
// ============================================================================

tc_entity* tc_entity_registry_find_by_uuid(const char* uuid) {
    if (!uuid) return NULL;

    for (size_t i = 0; i < g_registry.count; i++) {
        if (strcmp(g_registry.entities[i]->uuid, uuid) == 0) {
            return g_registry.entities[i];
        }
    }
    return NULL;
}

tc_entity* tc_entity_registry_find_by_runtime_id(uint64_t id) {
    for (size_t i = 0; i < g_registry.count; i++) {
        if (g_registry.entities[i]->runtime_id == id) {
            return g_registry.entities[i];
        }
    }
    return NULL;
}

tc_entity* tc_entity_registry_find_by_pick_id(uint32_t id) {
    for (size_t i = 0; i < g_registry.count; i++) {
        if (tc_entity_pick_id(g_registry.entities[i]) == id) {
            return g_registry.entities[i];
        }
    }
    return NULL;
}

size_t tc_entity_registry_count(void) {
    return g_registry.count;
}

tc_entity* tc_entity_registry_at(size_t index) {
    if (index >= g_registry.count) return NULL;
    return g_registry.entities[index];
}

size_t tc_entity_registry_snapshot(tc_entity** out, size_t max_count) {
    size_t count = g_registry.count < max_count ? g_registry.count : max_count;
    for (size_t i = 0; i < count; i++) {
        out[i] = g_registry.entities[i];
    }
    return count;
}

// ============================================================================
// Registry cleanup (called by tc_shutdown)
// ============================================================================

void tc_entity_registry_cleanup(void) {
    // Free all remaining entities
    for (size_t i = 0; i < g_registry.count; i++) {
        tc_entity* e = g_registry.entities[i];
        if (e) {
            // Destroy components
            for (size_t j = 0; j < e->component_count; j++) {
                tc_component* c = e->components[j];
                if (c) {
                    tc_component_on_removed_from_entity(c);
                    if (c->is_native) {
                        tc_component_drop(c);
                        free(c);
                    }
                }
            }
            free(e->components);
            tc_transform_free(e->transform);
            free(e->uuid);
            free(e->name);
            free(e);
        }
    }

    free(g_registry.entities);
    g_registry.entities = NULL;
    g_registry.count = 0;
    g_registry.capacity = 0;
}
