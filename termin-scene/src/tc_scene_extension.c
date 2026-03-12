// tc_scene_extension.c - Scene extension registry and scene-local slot storage
#include "core/tc_scene_extension.h"
#include "core/tc_scene.h"
#include <tcbase/tc_log.h>
#include <stdlib.h>

typedef struct {
    const char* debug_name;
    const char* persistence_key;
    tc_scene_ext_vtable vtable;
    void* type_userdata;
    bool registered;
} tc_scene_ext_type_entry;

typedef struct {
    tc_scene_ext_type_entry* types;
    size_t type_capacity;
} tc_scene_ext_registry;

static tc_scene_ext_registry* g_registry = NULL;

static void ensure_registry(void) {
    if (g_registry) return;
    g_registry = (tc_scene_ext_registry*)calloc(1, sizeof(tc_scene_ext_registry));
}

static tc_scene_ext_type_entry* find_type(tc_scene_ext_type_id type_id) {
    if (!g_registry) return NULL;
    if (type_id >= g_registry->type_capacity) return NULL;
    if (!g_registry->types[type_id].registered) return NULL;
    return &g_registry->types[type_id];
}

void tc_scene_ext_registry_init(void) {
    ensure_registry();
    if (g_registry->types) return;
    g_registry->types = (tc_scene_ext_type_entry*)calloc(TC_SCENE_EXT_TYPE_COUNT, sizeof(tc_scene_ext_type_entry));
    g_registry->type_capacity = TC_SCENE_EXT_TYPE_COUNT;
}

void tc_scene_ext_registry_shutdown(void) {
    if (!g_registry) return;
    free(g_registry->types);
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
    if (!g_registry->types) {
        tc_scene_ext_registry_init();
    }

    if (type_id >= g_registry->type_capacity) {
        tc_log_error("[tc_scene_ext_register] type_id out of range: %llu", (unsigned long long) type_id);
        return false;
    }

    tc_scene_ext_type_entry* entry = &g_registry->types[type_id];
    if (entry->registered) {
        tc_log_error("[tc_scene_ext_register] type_id already registered: %llu", (unsigned long long) type_id);
        return false;
    }

    entry->debug_name = debug_name;
    entry->persistence_key = persistence_key ? persistence_key : debug_name;
    entry->vtable = *vtable;
    entry->type_userdata = type_userdata;
    entry->registered = true;
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
        tc_log_error("[tc_scene_ext_attach] type_id is not registered: %llu", (unsigned long long) type_id);
        return false;
    }

    if (tc_scene_ext_slot_get(scene, type_id) != NULL) {
        return true;
    }

    void* instance = type_entry->vtable.create(scene, type_entry->type_userdata);
    if (!instance) {
        tc_log_error("[tc_scene_ext_attach] create returned NULL for type_id=%llu", (unsigned long long) type_id);
        return false;
    }

    if (!tc_scene_ext_slot_set(scene, type_id, instance)) {
        if (type_entry->vtable.destroy) {
            type_entry->vtable.destroy(instance, type_entry->type_userdata);
        }
        tc_log_error("[tc_scene_ext_attach] failed to store instance for type_id=%llu", (unsigned long long) type_id);
        return false;
    }

    return true;
}

void tc_scene_ext_detach(tc_scene_handle scene, tc_scene_ext_type_id type_id) {
    if (!g_registry) return;
    tc_scene_ext_type_entry* type_entry = find_type(type_id);
    if (!type_entry) return;

    void* instance = tc_scene_ext_slot_get(scene, type_id);
    if (!instance) return;

    if (type_entry->vtable.destroy) {
        type_entry->vtable.destroy(instance, type_entry->type_userdata);
    }

    tc_scene_ext_slot_clear(scene, type_id);
}

void tc_scene_ext_detach_all(tc_scene_handle scene) {
    if (!g_registry) return;
    if (!tc_scene_alive(scene)) return;

    for (size_t i = 0; i < g_registry->type_capacity; i++) {
        tc_scene_ext_type_entry* type_entry = &g_registry->types[i];
        if (!type_entry->registered) continue;

        void* instance = tc_scene_ext_slot_get(scene, (tc_scene_ext_type_id) i);
        if (!instance) continue;

        if (type_entry->vtable.destroy) {
            type_entry->vtable.destroy(instance, type_entry->type_userdata);
        }

        tc_scene_ext_slot_clear(scene, (tc_scene_ext_type_id) i);
    }
}

void* tc_scene_ext_get(tc_scene_handle scene, tc_scene_ext_type_id type_id) {
    if (!tc_scene_alive(scene)) return NULL;
    return tc_scene_ext_slot_get(scene, type_id);
}

bool tc_scene_ext_has(tc_scene_handle scene, tc_scene_ext_type_id type_id) {
    if (!tc_scene_alive(scene)) return false;
    return tc_scene_ext_slot_get(scene, type_id) != NULL;
}

size_t tc_scene_ext_get_attached_types(
    tc_scene_handle scene,
    tc_scene_ext_type_id* out_ids,
    size_t max_count
) {
    if (!tc_scene_alive(scene) || !out_ids || max_count == 0) return 0;
    if (!g_registry) return 0;

    size_t count = 0;
    for (size_t i = 0; i < g_registry->type_capacity && count < max_count; i++) {
        if (!g_registry->types[i].registered) continue;
        if (!tc_scene_ext_slot_get(scene, (tc_scene_ext_type_id) i)) continue;
        out_ids[count++] = (tc_scene_ext_type_id) i;
    }
    return count;
}

tc_value tc_scene_ext_serialize_scene(tc_scene_handle scene) {
    tc_value result = tc_value_dict_new();
    if (!tc_scene_alive(scene)) return result;
    if (!g_registry) return result;

    for (size_t i = 0; i < g_registry->type_capacity; i++) {
        tc_scene_ext_type_entry* type_entry = &g_registry->types[i];
        if (!type_entry->registered) continue;
        if (!type_entry->persistence_key || !type_entry->persistence_key[0]) continue;

        void* instance = tc_scene_ext_slot_get(scene, (tc_scene_ext_type_id) i);
        if (!instance) continue;

        tc_value payload = tc_value_dict_new();
        if (type_entry->vtable.serialize) {
            if (!type_entry->vtable.serialize(instance, &payload, type_entry->type_userdata)) {
                tc_log_warn(
                    "[tc_scene_ext_serialize_scene] serialize failed: type_id=%llu",
                    (unsigned long long) i
                );
            }
        }
        tc_value_dict_set(&result, type_entry->persistence_key, payload);
    }

    return result;
}

void tc_scene_ext_deserialize_scene(tc_scene_handle scene, const tc_value* extensions_dict) {
    if (!tc_scene_alive(scene)) return;
    if (!g_registry) return;
    if (!extensions_dict || extensions_dict->type != TC_VALUE_DICT) return;

    for (size_t i = 0; i < g_registry->type_capacity; i++) {
        tc_scene_ext_type_entry* type_entry = &g_registry->types[i];
        if (!type_entry->registered) continue;
        if (!type_entry->persistence_key || !type_entry->persistence_key[0]) continue;

        tc_value* payload = tc_value_dict_get((tc_value*) extensions_dict, type_entry->persistence_key);
        if (!payload) continue;
        if (payload->type != TC_VALUE_DICT) continue;

        if (!tc_scene_ext_has(scene, (tc_scene_ext_type_id) i)) {
            if (!tc_scene_ext_attach(scene, (tc_scene_ext_type_id) i)) {
                tc_log_warn(
                    "[tc_scene_ext_deserialize_scene] attach failed: type_id=%llu",
                    (unsigned long long) i
                );
                continue;
            }
        }

        void* instance = tc_scene_ext_slot_get(scene, (tc_scene_ext_type_id) i);
        if (!instance) continue;
        if (!type_entry->vtable.deserialize) continue;

        if (!type_entry->vtable.deserialize(instance, payload, type_entry->type_userdata)) {
            tc_log_warn(
                "[tc_scene_ext_deserialize_scene] deserialize failed: type_id=%llu",
                (unsigned long long) i
            );
        }
    }
}

void tc_scene_ext_on_scene_update(tc_scene_handle scene, double dt) {
    if (!tc_scene_alive(scene)) return;
    if (!g_registry) return;

    for (size_t i = 0; i < g_registry->type_capacity; i++) {
        tc_scene_ext_type_entry* type_entry = &g_registry->types[i];
        if (!type_entry->registered) continue;

        void* instance = tc_scene_ext_slot_get(scene, (tc_scene_ext_type_id) i);
        if (!instance) continue;
        if (!type_entry->vtable.on_scene_update) continue;

        type_entry->vtable.on_scene_update(instance, dt, type_entry->type_userdata);
    }
}

void tc_scene_ext_on_scene_before_render(tc_scene_handle scene) {
    if (!tc_scene_alive(scene)) return;
    if (!g_registry) return;

    for (size_t i = 0; i < g_registry->type_capacity; i++) {
        tc_scene_ext_type_entry* type_entry = &g_registry->types[i];
        if (!type_entry->registered) continue;

        void* instance = tc_scene_ext_slot_get(scene, (tc_scene_ext_type_id) i);
        if (!instance) continue;
        if (!type_entry->vtable.on_scene_before_render) continue;

        type_entry->vtable.on_scene_before_render(instance, type_entry->type_userdata);
    }
}
