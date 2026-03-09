// tc_scene_extension.c - Scene extension registry and instances
#include "core/tc_scene_extension.h"
#include "core/tc_scene.h"
#include <tcbase/tc_log.h>
#include <stdlib.h>
#include <string.h>

#define INITIAL_TYPE_CAPACITY 8
#define INITIAL_INSTANCE_CAPACITY 16

typedef struct {
    tc_scene_ext_type_id type_id;
    const char* debug_name;
    const char* persistence_key;
    tc_scene_ext_vtable vtable;
    void* type_userdata;
    bool used;
} tc_scene_ext_type_entry;

typedef struct {
    tc_scene_handle scene;
    tc_scene_ext_type_id type_id;
    void* instance;
    const char* persistence_key;
    tc_scene_ext_vtable vtable;
    void* type_userdata;
    bool used;
} tc_scene_ext_instance_entry;

typedef struct {
    tc_scene_ext_type_entry* types;
    size_t type_count;
    size_t type_capacity;

    tc_scene_ext_instance_entry* instances;
    size_t instance_count;
    size_t instance_capacity;
} tc_scene_ext_registry;

static tc_scene_ext_registry* g_registry = NULL;

static void ensure_registry(void) {
    if (g_registry) return;
    g_registry = (tc_scene_ext_registry*)calloc(1, sizeof(tc_scene_ext_registry));
}

static tc_scene_ext_type_entry* find_type(tc_scene_ext_type_id type_id) {
    if (!g_registry) return NULL;
    for (size_t i = 0; i < g_registry->type_count; i++) {
        tc_scene_ext_type_entry* e = &g_registry->types[i];
        if (e->used && e->type_id == type_id) return e;
    }
    return NULL;
}

static tc_scene_ext_instance_entry* find_instance(tc_scene_handle scene, tc_scene_ext_type_id type_id) {
    if (!g_registry) return NULL;
    for (size_t i = 0; i < g_registry->instance_count; i++) {
        tc_scene_ext_instance_entry* e = &g_registry->instances[i];
        if (!e->used) continue;
        if (tc_scene_handle_eq(e->scene, scene) && e->type_id == type_id) return e;
    }
    return NULL;
}

static bool grow_types_if_needed(void) {
    if (g_registry->type_count < g_registry->type_capacity) return true;
    size_t new_capacity = g_registry->type_capacity == 0 ? INITIAL_TYPE_CAPACITY : g_registry->type_capacity * 2;
    tc_scene_ext_type_entry* p = (tc_scene_ext_type_entry*)realloc(
        g_registry->types,
        new_capacity * sizeof(tc_scene_ext_type_entry)
    );
    if (!p) return false;
    g_registry->types = p;
    g_registry->type_capacity = new_capacity;
    return true;
}

static bool grow_instances_if_needed(void) {
    if (g_registry->instance_count < g_registry->instance_capacity) return true;
    size_t new_capacity = g_registry->instance_capacity == 0 ? INITIAL_INSTANCE_CAPACITY : g_registry->instance_capacity * 2;
    tc_scene_ext_instance_entry* p = (tc_scene_ext_instance_entry*)realloc(
        g_registry->instances,
        new_capacity * sizeof(tc_scene_ext_instance_entry)
    );
    if (!p) return false;
    g_registry->instances = p;
    g_registry->instance_capacity = new_capacity;
    return true;
}

void tc_scene_ext_registry_init(void) {
    ensure_registry();
}

void tc_scene_ext_registry_shutdown(void) {
    if (!g_registry) return;

    // Detach all instances before freeing registry storage.
    for (size_t i = 0; i < g_registry->instance_count; i++) {
        tc_scene_ext_instance_entry* e = &g_registry->instances[i];
        if (!e->used) continue;
        if (e->vtable.destroy) {
            e->vtable.destroy(e->instance, e->type_userdata);
        }
        e->used = false;
    }

    free(g_registry->types);
    free(g_registry->instances);
    free(g_registry);
    g_registry = NULL;
}

bool tc_scene_ext_register(
    tc_scene_ext_type_id type_id,
    const char* debug_name,
    const char* persistence_key,
    const tc_scene_ext_vtable* vtable,
    void* type_userdata
) {
    if (!vtable) return false;
    if (!vtable->create) {
        tc_log_error("[tc_scene_ext_register] create callback is NULL");
        return false;
    }

    ensure_registry();
    tc_scene_ext_type_entry* existing = find_type(type_id);
    if (existing) {
        tc_log_error("[tc_scene_ext_register] type_id already registered: %llu", (unsigned long long)type_id);
        return false;
    }

    if (!grow_types_if_needed()) {
        tc_log_error("[tc_scene_ext_register] failed to grow type registry");
        return false;
    }

    tc_scene_ext_type_entry* e = &g_registry->types[g_registry->type_count++];
    e->type_id = type_id;
    e->debug_name = debug_name;
    e->persistence_key = persistence_key ? persistence_key : debug_name;
    e->vtable = *vtable;
    e->type_userdata = type_userdata;
    e->used = true;
    return true;
}

bool tc_scene_ext_is_registered(tc_scene_ext_type_id type_id) {
    return find_type(type_id) != NULL;
}

bool tc_scene_ext_attach(tc_scene_handle scene, tc_scene_ext_type_id type_id) {
    if (!tc_scene_alive(scene)) return false;

    ensure_registry();
    tc_scene_ext_type_entry* type_entry = find_type(type_id);
    if (!type_entry) {
        tc_log_error("[tc_scene_ext_attach] type_id is not registered: %llu", (unsigned long long)type_id);
        return false;
    }

    if (find_instance(scene, type_id)) {
        return true;
    }

    if (!grow_instances_if_needed()) {
        tc_log_error("[tc_scene_ext_attach] failed to grow instance registry");
        return false;
    }

    void* instance = type_entry->vtable.create(scene, type_entry->type_userdata);
    if (!instance) {
        tc_log_error("[tc_scene_ext_attach] create returned NULL for type_id=%llu", (unsigned long long)type_id);
        return false;
    }

    tc_scene_ext_instance_entry* e = &g_registry->instances[g_registry->instance_count++];
    e->scene = scene;
    e->type_id = type_id;
    e->instance = instance;
    e->persistence_key = type_entry->persistence_key;
    e->vtable = type_entry->vtable;
    e->type_userdata = type_entry->type_userdata;
    e->used = true;
    return true;
}

void tc_scene_ext_detach(tc_scene_handle scene, tc_scene_ext_type_id type_id) {
    if (!g_registry) return;
    tc_scene_ext_instance_entry* e = find_instance(scene, type_id);
    if (!e) return;

    if (e->vtable.destroy) {
        e->vtable.destroy(e->instance, e->type_userdata);
    }

    size_t idx = (size_t)(e - g_registry->instances);
    size_t last = g_registry->instance_count - 1;
    if (idx != last) {
        g_registry->instances[idx] = g_registry->instances[last];
    }
    g_registry->instance_count--;
}

void tc_scene_ext_detach_all(tc_scene_handle scene) {
    if (!g_registry) return;

    size_t i = 0;
    while (i < g_registry->instance_count) {
        tc_scene_ext_instance_entry* e = &g_registry->instances[i];
        if (!e->used || !tc_scene_handle_eq(e->scene, scene)) {
            i++;
            continue;
        }

        if (e->vtable.destroy) {
            e->vtable.destroy(e->instance, e->type_userdata);
        }

        size_t last = g_registry->instance_count - 1;
        if (i != last) {
            g_registry->instances[i] = g_registry->instances[last];
        }
        g_registry->instance_count--;
    }
}

void* tc_scene_ext_get(tc_scene_handle scene, tc_scene_ext_type_id type_id) {
    if (!tc_scene_alive(scene)) return NULL;
    tc_scene_ext_instance_entry* e = find_instance(scene, type_id);
    return e ? e->instance : NULL;
}

bool tc_scene_ext_has(tc_scene_handle scene, tc_scene_ext_type_id type_id) {
    if (!tc_scene_alive(scene)) return false;
    return find_instance(scene, type_id) != NULL;
}

size_t tc_scene_ext_get_attached_types(
    tc_scene_handle scene,
    tc_scene_ext_type_id* out_ids,
    size_t max_count
) {
    if (!tc_scene_alive(scene) || !out_ids || max_count == 0) return 0;
    if (!g_registry) return 0;

    size_t count = 0;
    for (size_t i = 0; i < g_registry->instance_count && count < max_count; i++) {
        tc_scene_ext_instance_entry* e = &g_registry->instances[i];
        if (!e->used) continue;
        if (!tc_scene_handle_eq(e->scene, scene)) continue;
        out_ids[count++] = e->type_id;
    }
    return count;
}

tc_value tc_scene_ext_serialize_scene(tc_scene_handle scene) {
    tc_value result = tc_value_dict_new();
    if (!tc_scene_alive(scene)) return result;
    if (!g_registry) return result;

    for (size_t i = 0; i < g_registry->instance_count; i++) {
        tc_scene_ext_instance_entry* e = &g_registry->instances[i];
        if (!e->used) continue;
        if (!tc_scene_handle_eq(e->scene, scene)) continue;
        if (!e->persistence_key || !e->persistence_key[0]) continue;

        tc_value payload = tc_value_dict_new();
        if (e->vtable.serialize) {
            if (!e->vtable.serialize(e->instance, &payload, e->type_userdata)) {
                tc_log_warn(
                    "[tc_scene_ext_serialize_scene] serialize failed: type_id=%llu",
                    (unsigned long long)e->type_id
                );
            }
        }
        tc_value_dict_set(&result, e->persistence_key, payload);
    }

    return result;
}

void tc_scene_ext_deserialize_scene(tc_scene_handle scene, const tc_value* extensions_dict) {
    if (!tc_scene_alive(scene)) return;
    if (!g_registry) return;
    if (!extensions_dict || extensions_dict->type != TC_VALUE_DICT) return;

    for (size_t i = 0; i < g_registry->type_count; i++) {
        tc_scene_ext_type_entry* type_entry = &g_registry->types[i];
        if (!type_entry->used) continue;
        if (!type_entry->persistence_key || !type_entry->persistence_key[0]) continue;

        tc_value* payload = tc_value_dict_get((tc_value*)extensions_dict, type_entry->persistence_key);
        if (!payload) continue;
        if (payload->type != TC_VALUE_DICT) continue;

        if (!tc_scene_ext_has(scene, type_entry->type_id)) {
            if (!tc_scene_ext_attach(scene, type_entry->type_id)) {
                tc_log_warn(
                    "[tc_scene_ext_deserialize_scene] attach failed: type_id=%llu",
                    (unsigned long long)type_entry->type_id
                );
                continue;
            }
        }

        tc_scene_ext_instance_entry* inst = find_instance(scene, type_entry->type_id);
        if (!inst) continue;
        if (!inst->vtable.deserialize) continue;

        if (!inst->vtable.deserialize(inst->instance, payload, inst->type_userdata)) {
            tc_log_warn(
                "[tc_scene_ext_deserialize_scene] deserialize failed: type_id=%llu",
                (unsigned long long)inst->type_id
            );
        }
    }
}

void tc_scene_ext_on_scene_update(tc_scene_handle scene, double dt) {
    if (!tc_scene_alive(scene)) return;
    if (!g_registry) return;

    for (size_t i = 0; i < g_registry->instance_count; i++) {
        tc_scene_ext_instance_entry* e = &g_registry->instances[i];
        if (!e->used) continue;
        if (!tc_scene_handle_eq(e->scene, scene)) continue;
        if (!e->vtable.on_scene_update) continue;
        e->vtable.on_scene_update(e->instance, dt, e->type_userdata);
    }
}

void tc_scene_ext_on_scene_before_render(tc_scene_handle scene) {
    if (!tc_scene_alive(scene)) return;
    if (!g_registry) return;

    for (size_t i = 0; i < g_registry->instance_count; i++) {
        tc_scene_ext_instance_entry* e = &g_registry->instances[i];
        if (!e->used) continue;
        if (!tc_scene_handle_eq(e->scene, scene)) continue;
        if (!e->vtable.on_scene_before_render) continue;
        e->vtable.on_scene_before_render(e->instance, e->type_userdata);
    }
}
