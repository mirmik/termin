#include "core/tc_component_capability.h"
#include "core/tc_component.h"
#include "core/tc_entity_pool.h"
#include "core/tc_entity_pool_registry.h"
#include "core/tc_scene.h"
#include <tcbase/tgfx_intern_string.h>
#include <tcbase/tc_log.h>
#include <string.h>

typedef struct {
    const char* names[TC_COMPONENT_MAX_CAPABILITIES];
    tc_component_capability_destroy_fn destroy_fns[TC_COMPONENT_MAX_CAPABILITIES];
    size_t count;
} tc_component_capability_registry;

static tc_component_capability_registry g_registry = {0};

static bool capability_slot_from_id(tc_component_cap_id id, uint32_t* out_slot) {
    if (id == TC_COMPONENT_CAPABILITY_INVALID_ID) return false;
    uint32_t slot = id - 1;
    if (slot >= g_registry.count) return false;
    if (out_slot) *out_slot = slot;
    return true;
}

tc_component_cap_id tc_component_capability_register(const char* debug_name) {
    return tc_component_capability_register_with_destructor(debug_name, NULL);
}

tc_component_cap_id tc_component_capability_register_with_destructor(
    const char* debug_name,
    tc_component_capability_destroy_fn destroy_fn
) {
    if (!debug_name || !debug_name[0]) {
        return TC_COMPONENT_CAPABILITY_INVALID_ID;
    }

    for (size_t i = 0; i < g_registry.count; i++) {
        if (g_registry.names[i] && strcmp(g_registry.names[i], debug_name) == 0) {
            if (destroy_fn && g_registry.destroy_fns[i] == NULL) {
                g_registry.destroy_fns[i] = destroy_fn;
            }
            return (tc_component_cap_id)(i + 1);
        }
    }

    if (g_registry.count >= TC_COMPONENT_MAX_CAPABILITIES) {
        tc_log(TC_LOG_ERROR, "[tc_component_capability] max capability count reached");
        return TC_COMPONENT_CAPABILITY_INVALID_ID;
    }

    size_t slot = g_registry.count++;
    g_registry.names[slot] = tgfx_intern_string(debug_name);
    g_registry.destroy_fns[slot] = destroy_fn;
    return (tc_component_cap_id)(slot + 1);
}

const char* tc_component_capability_name(tc_component_cap_id id) {
    uint32_t slot = 0;
    return capability_slot_from_id(id, &slot) ? g_registry.names[slot] : NULL;
}

bool tc_component_capability_valid(tc_component_cap_id id) {
    return capability_slot_from_id(id, NULL);
}

size_t tc_component_capability_count(void) {
    return g_registry.count;
}

bool tc_component_capability_slot(tc_component_cap_id id, uint32_t* out_slot) {
    return capability_slot_from_id(id, out_slot);
}

bool tc_component_has_capability(const tc_component* c, tc_component_cap_id id) {
    uint32_t slot = 0;
    if (!c || !capability_slot_from_id(id, &slot)) return false;
    return (c->capability_mask & (UINT64_C(1) << slot)) != 0;
}

void* tc_component_get_capability(const tc_component* c, tc_component_cap_id id) {
    uint32_t slot = 0;
    if (!c || !capability_slot_from_id(id, &slot)) return NULL;
    if ((c->capability_mask & (UINT64_C(1) << slot)) == 0) return NULL;
    return c->capability_ptrs[slot];
}

bool tc_component_attach_capability(tc_component* c, tc_component_cap_id id, void* cap_ptr) {
    uint32_t slot = 0;
    if (!c || !capability_slot_from_id(id, &slot)) return false;

    if ((c->capability_mask & (UINT64_C(1) << slot)) != 0) {
        c->capability_ptrs[slot] = cap_ptr;
        return true;
    }

    c->capability_ptrs[slot] = cap_ptr;
    c->capability_mask |= (UINT64_C(1) << slot);

    if (tc_entity_handle_valid(c->owner)) {
        tc_entity_pool* pool = tc_entity_pool_registry_get(c->owner.pool);
        if (pool) {
            tc_scene_handle scene = tc_entity_pool_get_scene(pool);
            if (tc_scene_handle_valid(scene)) {
                tc_scene_reindex_component_capabilities(scene, c);
            }
        }
    }
    return true;
}

void tc_component_detach_capability(tc_component* c, tc_component_cap_id id) {
    uint32_t slot = 0;
    if (!c || !capability_slot_from_id(id, &slot)) return;
    if ((c->capability_mask & (UINT64_C(1) << slot)) == 0) return;

    void* cap_ptr = c->capability_ptrs[slot];
    c->capability_ptrs[slot] = NULL;
    c->capability_prev[slot] = NULL;
    c->capability_next[slot] = NULL;
    c->capability_mask &= ~(UINT64_C(1) << slot);

    if (cap_ptr && g_registry.destroy_fns[slot]) {
        g_registry.destroy_fns[slot](cap_ptr);
    }

    if (tc_entity_handle_valid(c->owner)) {
        tc_entity_pool* pool = tc_entity_pool_registry_get(c->owner.pool);
        if (pool) {
            tc_scene_handle scene = tc_entity_pool_get_scene(pool);
            if (tc_scene_handle_valid(scene)) {
                tc_scene_reindex_component_capabilities(scene, c);
            }
        }
    }
}

void tc_component_clear_capabilities(tc_component* c) {
    if (!c) return;
    for (uint32_t slot = 0; slot < g_registry.count; slot++) {
        if ((c->capability_mask & (UINT64_C(1) << slot)) == 0) {
            continue;
        }
        void* cap_ptr = c->capability_ptrs[slot];
        c->capability_ptrs[slot] = NULL;
        c->capability_prev[slot] = NULL;
        c->capability_next[slot] = NULL;
        if (cap_ptr && g_registry.destroy_fns[slot]) {
            g_registry.destroy_fns[slot](cap_ptr);
        }
    }
    c->capability_mask = 0;
}
