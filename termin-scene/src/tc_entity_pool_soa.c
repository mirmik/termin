#include "tc_entity_pool_internal.h"

#include <tcbase/tc_log.h>

#include <stdlib.h>
#include <string.h>

tc_soa_type_id tc_entity_pool_register_soa_type(
    tc_entity_pool* pool,
    const tc_soa_type_desc* desc
) {
    (void)pool;
    if (!desc) return TC_SOA_TYPE_INVALID;
    return tc_soa_register_type(tc_soa_global_registry(), desc);
}

static tc_archetype* pool_get_or_create_archetype(
    tc_entity_pool* pool,
    uint64_t mask
) {
    uint64_t arch_idx;
    if (tc_u64_map_get(pool->archetype_by_mask, mask, &arch_idx)) {
        return pool->archetypes[(size_t)arch_idx];
    }

    tc_soa_type_id type_ids[TC_SOA_MAX_TYPES];
    size_t type_count = 0;
    for (int bit = 0; bit < TC_SOA_MAX_TYPES; ++bit) {
        if (mask & (1ULL << bit)) {
            type_ids[type_count++] = (tc_soa_type_id)bit;
        }
    }

    tc_archetype* archetype = tc_archetype_create(
        mask,
        type_ids,
        type_count,
        tc_soa_global_registry()
    );
    if (!archetype) return NULL;

    if (pool->archetype_count >= pool->archetype_capacity) {
        size_t new_capacity = pool->archetype_capacity == 0
            ? 8
            : pool->archetype_capacity * 2;
        tc_archetype** archetypes = realloc(
            pool->archetypes,
            new_capacity * sizeof(tc_archetype*)
        );
        if (!archetypes) {
            tc_log_error(
                "[tc_entity_pool] failed to grow archetype storage to %zu entries",
                new_capacity
            );
            tc_archetype_destroy(archetype, tc_soa_global_registry());
            return NULL;
        }
        pool->archetypes = archetypes;
        pool->archetype_capacity = new_capacity;
    }

    size_t index = pool->archetype_count++;
    pool->archetypes[index] = archetype;
    tc_u64_map_set(pool->archetype_by_mask, mask, (uint64_t)index);
    return archetype;
}

static void pool_move_entity_archetype(
    tc_entity_pool* pool,
    uint32_t entity_index,
    tc_archetype* old_archetype,
    uint32_t old_row,
    tc_archetype* new_archetype
) {
    tc_entity_id entity = {
        entity_index,
        pool->generations[entity_index]
    };
    uint32_t new_row = tc_archetype_alloc_row(
        new_archetype,
        entity,
        tc_soa_global_registry()
    );

    if (old_archetype) {
        for (size_t i = 0; i < new_archetype->type_count; ++i) {
            tc_soa_type_id type_id = new_archetype->type_ids[i];
            void* source = tc_archetype_get_array(old_archetype, type_id);
            if (!source) continue;

            const tc_soa_type_desc* desc = tc_soa_get_type(
                tc_soa_global_registry(),
                type_id
            );
            void* destination = (char*)new_archetype->data[i]
                + new_row * desc->element_size;
            void* source_element = NULL;
            for (size_t j = 0; j < old_archetype->type_count; ++j) {
                if (old_archetype->type_ids[j] == type_id) {
                    source_element = (char*)old_archetype->data[j]
                        + old_row * desc->element_size;
                    break;
                }
            }
            if (source_element) {
                memcpy(destination, source_element, desc->element_size);
            }
        }

        tc_entity_id swapped = tc_archetype_detach_row(
            old_archetype,
            old_row,
            tc_soa_global_registry()
        );
        if (tc_entity_id_valid(swapped)) {
            pool->soa_archetype_rows[swapped.index] = old_row;
        }
    }

    uint64_t new_archetype_index;
    tc_u64_map_get(
        pool->archetype_by_mask,
        new_archetype->type_mask,
        &new_archetype_index
    );
    pool->soa_archetype_ids[entity_index] = (uint32_t)new_archetype_index;
    pool->soa_archetype_rows[entity_index] = new_row;
}

void tc_entity_pool_add_soa(
    tc_entity_pool* pool,
    tc_entity_id id,
    tc_soa_type_id type
) {
    if (!pool || !tc_entity_pool_alive(pool, id)) return;
    if (type >= tc_soa_global_registry()->count) {
        tc_log_error("[tc_entity_pool] add_soa: invalid type_id %d", type);
        return;
    }

    uint32_t index = id.index;
    uint64_t old_mask = pool->soa_type_masks[index];
    uint64_t new_mask = old_mask | (1ULL << type);
    if (new_mask == old_mask) return;

    tc_archetype* old_archetype = NULL;
    uint32_t old_row = 0;
    if (pool->soa_archetype_ids[index] != UINT32_MAX) {
        old_archetype = pool->archetypes[pool->soa_archetype_ids[index]];
        old_row = pool->soa_archetype_rows[index];
    }

    tc_archetype* new_archetype = pool_get_or_create_archetype(pool, new_mask);
    if (!new_archetype) {
        tc_log_error(
            "[tc_entity_pool] add_soa: failed to create archetype for mask 0x%llx",
            (unsigned long long)new_mask
        );
        return;
    }

    pool_move_entity_archetype(
        pool,
        index,
        old_archetype,
        old_row,
        new_archetype
    );
    pool->soa_type_masks[index] = new_mask;
}

void tc_entity_pool_remove_soa(
    tc_entity_pool* pool,
    tc_entity_id id,
    tc_soa_type_id type
) {
    if (!pool || !tc_entity_pool_alive(pool, id)) return;
    if (type >= tc_soa_global_registry()->count) return;

    uint32_t index = id.index;
    uint64_t old_mask = pool->soa_type_masks[index];
    uint64_t new_mask = old_mask & ~(1ULL << type);
    if (new_mask == old_mask) return;

    tc_archetype* old_archetype =
        pool->archetypes[pool->soa_archetype_ids[index]];
    uint32_t old_row = pool->soa_archetype_rows[index];

    if (new_mask == 0) {
        tc_entity_id swapped = tc_archetype_free_row(
            old_archetype,
            old_row,
            tc_soa_global_registry()
        );
        if (tc_entity_id_valid(swapped)) {
            pool->soa_archetype_rows[swapped.index] = old_row;
        }
        pool->soa_archetype_ids[index] = UINT32_MAX;
        pool->soa_archetype_rows[index] = 0;
        pool->soa_type_masks[index] = 0;
        return;
    }

    tc_archetype* new_archetype = pool_get_or_create_archetype(pool, new_mask);
    if (!new_archetype) {
        tc_log_error(
            "[tc_entity_pool] remove_soa: failed to create archetype for mask 0x%llx",
            (unsigned long long)new_mask
        );
        return;
    }

    pool_move_entity_archetype(
        pool,
        index,
        old_archetype,
        old_row,
        new_archetype
    );
    pool->soa_type_masks[index] = new_mask;
}

bool tc_entity_pool_has_soa(
    const tc_entity_pool* pool,
    tc_entity_id id,
    tc_soa_type_id type
) {
    if (!pool || !tc_entity_pool_alive(pool, id)) return false;
    if (type >= TC_SOA_MAX_TYPES) return false;
    return (pool->soa_type_masks[id.index] & (1ULL << type)) != 0;
}

void* tc_entity_pool_get_soa(
    const tc_entity_pool* pool,
    tc_entity_id id,
    tc_soa_type_id type
) {
    if (!pool || !tc_entity_pool_alive(pool, id)) return NULL;
    if (type >= tc_soa_global_registry()->count) return NULL;

    uint32_t index = id.index;
    if (pool->soa_archetype_ids[index] == UINT32_MAX) return NULL;
    if (!(pool->soa_type_masks[index] & (1ULL << type))) return NULL;

    tc_archetype* archetype =
        pool->archetypes[pool->soa_archetype_ids[index]];
    uint32_t row = pool->soa_archetype_rows[index];
    return tc_archetype_get_element(
        archetype,
        row,
        type,
        tc_soa_global_registry()
    );
}

uint64_t tc_entity_pool_soa_mask(
    const tc_entity_pool* pool,
    tc_entity_id id
) {
    if (!pool || !tc_entity_pool_alive(pool, id)) return 0;
    return pool->soa_type_masks[id.index];
}
