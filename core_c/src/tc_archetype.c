// tc_archetype.c - SoA archetype storage implementation
#include "core/tc_archetype.h"
#include "tc_log.h"
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define tc_strdup _strdup
#else
#define tc_strdup strdup
#endif

#define ARCHETYPE_INITIAL_CAPACITY 16

// ============================================================================
// SoA Type Registry
// ============================================================================

static tc_soa_type_registry g_soa_registry;

tc_soa_type_registry* tc_soa_global_registry(void) {
    return &g_soa_registry;
}

tc_soa_type_id tc_soa_register_type(tc_soa_type_registry* reg, const tc_soa_type_desc* desc) {
    if (!reg || !desc) return TC_SOA_TYPE_INVALID;
    if (desc->element_size == 0) {
        tc_log_error("[tc_soa] Cannot register type '%s': element_size is 0",
                     desc->name ? desc->name : "?");
        return TC_SOA_TYPE_INVALID;
    }

    // Dedup: if a type with the same name already exists, return its id
    if (desc->name) {
        for (size_t i = 0; i < reg->count; i++) {
            if (reg->types[i].name && strcmp(reg->types[i].name, desc->name) == 0) {
                return (tc_soa_type_id)i;
            }
        }
    }

    if (reg->count >= TC_SOA_MAX_TYPES) {
        tc_log_error("[tc_soa] Cannot register type '%s': max %d types reached",
                     desc->name ? desc->name : "?", TC_SOA_MAX_TYPES);
        return TC_SOA_TYPE_INVALID;
    }

    tc_soa_type_id id = (tc_soa_type_id)reg->count;
    tc_soa_type_desc* slot = &reg->types[id];
    slot->name = desc->name ? tc_strdup(desc->name) : NULL;
    slot->element_size = desc->element_size;
    slot->alignment = desc->alignment > 0 ? desc->alignment : 8;
    slot->init = desc->init;
    slot->destroy = desc->destroy;
    reg->count++;
    return id;
}

const tc_soa_type_desc* tc_soa_get_type(const tc_soa_type_registry* reg, tc_soa_type_id id) {
    if (!reg || id >= reg->count) return NULL;
    return &reg->types[id];
}

// ============================================================================
// Archetype internals
// ============================================================================

// Find index of type_id in archetype's type_ids array. Returns -1 if not found.
static int archetype_find_type_index(const tc_archetype* arch, tc_soa_type_id type_id) {
    for (size_t i = 0; i < arch->type_count; i++) {
        if (arch->type_ids[i] == type_id) return (int)i;
        if (arch->type_ids[i] > type_id) return -1; // sorted, no point continuing
    }
    return -1;
}

static void archetype_grow(tc_archetype* arch, const tc_soa_type_registry* reg) {
    size_t new_cap = arch->capacity == 0 ? ARCHETYPE_INITIAL_CAPACITY : arch->capacity * 2;

    arch->entities = (tc_entity_id*)realloc(arch->entities, new_cap * sizeof(tc_entity_id));

    for (size_t i = 0; i < arch->type_count; i++) {
        const tc_soa_type_desc* desc = tc_soa_get_type(reg, arch->type_ids[i]);
        size_t elem_size = desc->element_size;

        arch->data[i] = realloc(arch->data[i], new_cap * elem_size);
        // Zero-init new slots
        memset((char*)arch->data[i] + arch->capacity * elem_size, 0,
               (new_cap - arch->capacity) * elem_size);
    }

    arch->capacity = new_cap;
}

// ============================================================================
// Archetype public API
// ============================================================================

tc_archetype* tc_archetype_create(
    uint64_t type_mask,
    const tc_soa_type_id* type_ids,
    size_t type_count,
    const tc_soa_type_registry* reg
) {
    tc_archetype* arch = (tc_archetype*)calloc(1, sizeof(tc_archetype));
    if (!arch) return NULL;

    arch->type_mask = type_mask;
    arch->type_count = type_count;
    arch->capacity = ARCHETYPE_INITIAL_CAPACITY;
    arch->count = 0;

    // Copy and sort type_ids
    arch->type_ids = (tc_soa_type_id*)malloc(type_count * sizeof(tc_soa_type_id));
    memcpy(arch->type_ids, type_ids, type_count * sizeof(tc_soa_type_id));
    // Simple insertion sort (type_count <= 64)
    for (size_t i = 1; i < type_count; i++) {
        tc_soa_type_id key = arch->type_ids[i];
        size_t j = i;
        while (j > 0 && arch->type_ids[j - 1] > key) {
            arch->type_ids[j] = arch->type_ids[j - 1];
            j--;
        }
        arch->type_ids[j] = key;
    }

    // Allocate entity array
    arch->entities = (tc_entity_id*)calloc(arch->capacity, sizeof(tc_entity_id));

    // Allocate data arrays
    arch->data = (void**)calloc(type_count, sizeof(void*));
    for (size_t i = 0; i < type_count; i++) {
        const tc_soa_type_desc* desc = tc_soa_get_type(reg, arch->type_ids[i]);
        if (!desc) {
            tc_log_error("[tc_archetype] Invalid type_id %d during create", arch->type_ids[i]);
            continue;
        }
        arch->data[i] = calloc(arch->capacity, desc->element_size);
    }

    return arch;
}

void tc_archetype_destroy(tc_archetype* arch, const tc_soa_type_registry* reg) {
    if (!arch) return;

    // Call destroy on all live elements
    for (size_t ti = 0; ti < arch->type_count; ti++) {
        const tc_soa_type_desc* desc = tc_soa_get_type(reg, arch->type_ids[ti]);
        if (desc && desc->destroy && arch->data[ti]) {
            for (size_t row = 0; row < arch->count; row++) {
                desc->destroy((char*)arch->data[ti] + row * desc->element_size);
            }
        }
        free(arch->data[ti]);
    }

    free(arch->data);
    free(arch->entities);
    free(arch->type_ids);
    free(arch);
}

uint32_t tc_archetype_alloc_row(
    tc_archetype* arch,
    tc_entity_id entity,
    const tc_soa_type_registry* reg
) {
    if (arch->count >= arch->capacity) {
        archetype_grow(arch, reg);
    }

    uint32_t row = (uint32_t)arch->count;
    arch->entities[row] = entity;

    // Init each component for this row
    for (size_t i = 0; i < arch->type_count; i++) {
        const tc_soa_type_desc* desc = tc_soa_get_type(reg, arch->type_ids[i]);
        void* ptr = (char*)arch->data[i] + row * desc->element_size;
        if (desc->init) {
            desc->init(ptr);
        }
        // else: already zeroed from calloc/memset in grow
    }

    arch->count++;
    return row;
}

// Internal swap-remove without calling destroy (shared by free_row and detach_row)
static tc_entity_id archetype_swap_remove(
    tc_archetype* arch,
    uint32_t row,
    const tc_soa_type_registry* reg
) {
    uint32_t last = (uint32_t)(arch->count - 1);
    tc_entity_id swapped = TC_ENTITY_ID_INVALID;

    if (row != last) {
        swapped = arch->entities[last];
        arch->entities[row] = swapped;

        for (size_t i = 0; i < arch->type_count; i++) {
            const tc_soa_type_desc* desc = tc_soa_get_type(reg, arch->type_ids[i]);
            size_t sz = desc->element_size;
            void* dst = (char*)arch->data[i] + row * sz;
            void* src = (char*)arch->data[i] + last * sz;
            memcpy(dst, src, sz);
        }
    }

    arch->count--;
    return swapped;
}

tc_entity_id tc_archetype_free_row(
    tc_archetype* arch,
    uint32_t row,
    const tc_soa_type_registry* reg
) {
    if (!arch || row >= arch->count) return TC_ENTITY_ID_INVALID;

    // Call destroy on elements being removed
    for (size_t i = 0; i < arch->type_count; i++) {
        const tc_soa_type_desc* desc = tc_soa_get_type(reg, arch->type_ids[i]);
        if (desc && desc->destroy) {
            void* ptr = (char*)arch->data[i] + row * desc->element_size;
            desc->destroy(ptr);
        }
    }

    return archetype_swap_remove(arch, row, reg);
}

tc_entity_id tc_archetype_detach_row(
    tc_archetype* arch,
    uint32_t row,
    const tc_soa_type_registry* reg
) {
    if (!arch || row >= arch->count) return TC_ENTITY_ID_INVALID;
    // Swap-remove WITHOUT calling destroy — data was already copied elsewhere
    return archetype_swap_remove(arch, row, reg);
}

void* tc_archetype_get_array(const tc_archetype* arch, tc_soa_type_id type_id) {
    if (!arch) return NULL;
    int idx = archetype_find_type_index(arch, type_id);
    if (idx < 0) return NULL;
    return arch->data[idx];
}

void* tc_archetype_get_element(
    const tc_archetype* arch,
    uint32_t row,
    tc_soa_type_id type_id,
    const tc_soa_type_registry* reg
) {
    if (!arch || row >= arch->count) return NULL;
    int idx = archetype_find_type_index(arch, type_id);
    if (idx < 0) return NULL;
    const tc_soa_type_desc* desc = tc_soa_get_type(reg, arch->type_ids[idx]);
    if (!desc) return NULL;
    return (char*)arch->data[idx] + row * desc->element_size;
}

// ============================================================================
// SoA Query
// ============================================================================

tc_soa_query tc_soa_query_init(
    tc_archetype** archetypes,
    size_t archetype_count,
    const tc_soa_type_id* required,
    size_t required_count,
    const tc_soa_type_id* excluded,
    size_t excluded_count
) {
    tc_soa_query q;
    memset(&q, 0, sizeof(q));

    q._archetypes = archetypes;
    q._archetype_count = archetype_count;
    q._archetype_idx = 0;
    q.required_types = required;
    q.required_count = required_count;

    // Build masks
    q.required_mask = 0;
    for (size_t i = 0; i < required_count; i++) {
        q.required_mask |= (1ULL << required[i]);
    }

    q.excluded_mask = 0;
    for (size_t i = 0; i < excluded_count; i++) {
        q.excluded_mask |= (1ULL << excluded[i]);
    }

    return q;
}

bool tc_soa_query_next(tc_soa_query* q, tc_soa_chunk* out) {
    if (!q || !out) return false;

    while (q->_archetype_idx < q->_archetype_count) {
        tc_archetype* arch = q->_archetypes[q->_archetype_idx];
        q->_archetype_idx++;

        if (!arch || arch->count == 0) continue;

        // Check masks
        if ((arch->type_mask & q->required_mask) != q->required_mask) continue;
        if (arch->type_mask & q->excluded_mask) continue;

        // Fill chunk
        out->entities = arch->entities;
        out->count = arch->count;

        // Map required types to data arrays
        for (size_t i = 0; i < q->required_count; i++) {
            out->data[i] = tc_archetype_get_array(arch, q->required_types[i]);
        }

        return true;
    }

    return false;
}
