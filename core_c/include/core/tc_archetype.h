// tc_archetype.h - SoA archetype storage for data-only components
#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "tc_types.h"
#include "core/tc_entity_pool.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// SoA Type Registry - tracks registered data-only component types
// ============================================================================

typedef uint8_t tc_soa_type_id;
#define TC_SOA_TYPE_INVALID 0xFF
#define TC_SOA_MAX_TYPES 64

// Descriptor for registering a SoA component type
typedef struct tc_soa_type_desc {
    const char* name;              // type name (copied on register)
    size_t element_size;           // sizeof one element
    size_t alignment;              // alignof one element (0 = default)
    void (*init)(void* ptr);       // default initializer (NULL = zero-init)
    void (*destroy)(void* ptr);    // destructor (NULL = no-op)
} tc_soa_type_desc;

// Registry holding up to 64 SoA types
typedef struct {
    tc_soa_type_desc types[TC_SOA_MAX_TYPES];
    size_t count;
} tc_soa_type_registry;

// Register a new SoA type. Returns type id (0..63) or TC_SOA_TYPE_INVALID if full.
// If a type with the same name is already registered, returns the existing id.
TC_POOL_API tc_soa_type_id tc_soa_register_type(tc_soa_type_registry* reg, const tc_soa_type_desc* desc);

// Get type descriptor by id. Returns NULL if invalid.
TC_POOL_API const tc_soa_type_desc* tc_soa_get_type(const tc_soa_type_registry* reg, tc_soa_type_id id);

// Global SoA type registry (singleton, zero-initialized).
TC_POOL_API tc_soa_type_registry* tc_soa_global_registry(void);

// ============================================================================
// Archetype - dense storage for entities sharing same SoA component set
// ============================================================================

typedef struct tc_archetype {
    uint64_t type_mask;            // bitmask of which SoA types are present

    tc_soa_type_id* type_ids;      // [type_count], sorted by id
    size_t type_count;

    size_t capacity;               // allocated slots
    size_t count;                  // occupied slots

    tc_entity_id* entities;        // [capacity] entity in each row
    void** data;                   // [type_count] pointers to data arrays
} tc_archetype;

// Create archetype for given type set. Initial capacity = 16.
TC_POOL_API tc_archetype* tc_archetype_create(
    uint64_t type_mask,
    const tc_soa_type_id* type_ids,
    size_t type_count,
    const tc_soa_type_registry* reg
);

// Destroy archetype: call destroy on all live elements, free memory.
TC_POOL_API void tc_archetype_destroy(tc_archetype* arch, const tc_soa_type_registry* reg);

// Allocate a row for entity. Returns row index. Grows if needed.
TC_POOL_API uint32_t tc_archetype_alloc_row(
    tc_archetype* arch,
    tc_entity_id entity,
    const tc_soa_type_registry* reg
);

// Free a row (swap-remove + destroy). Returns entity_id of the entity that was
// swapped into the freed row, or TC_ENTITY_ID_INVALID if row was last.
TC_POOL_API tc_entity_id tc_archetype_free_row(
    tc_archetype* arch,
    uint32_t row,
    const tc_soa_type_registry* reg
);

// Detach a row (swap-remove WITHOUT destroy). Use when data was already copied
// to another archetype. Returns swapped entity_id or TC_ENTITY_ID_INVALID.
TC_POOL_API tc_entity_id tc_archetype_detach_row(
    tc_archetype* arch,
    uint32_t row,
    const tc_soa_type_registry* reg
);

// Get pointer to data array for a given type in this archetype.
// Returns NULL if type not present.
TC_POOL_API void* tc_archetype_get_array(const tc_archetype* arch, tc_soa_type_id type_id);

// Get pointer to element at row for a given type.
// Returns NULL if type not present.
TC_POOL_API void* tc_archetype_get_element(
    const tc_archetype* arch,
    uint32_t row,
    tc_soa_type_id type_id,
    const tc_soa_type_registry* reg
);

// ============================================================================
// SoA Query - iterate entities matching a component set
// ============================================================================

typedef struct {
    tc_entity_id* entities;        // array of entity_ids in this chunk
    void** data;                   // [required_count] pointers to data arrays
    size_t count;                  // number of entities in chunk
} tc_soa_chunk;

typedef struct {
    // Public (set by init)
    uint64_t required_mask;
    uint64_t excluded_mask;
    const tc_soa_type_id* required_types;
    size_t required_count;

    // Internal state
    tc_archetype** _archetypes;
    size_t _archetype_count;
    size_t _archetype_idx;
} tc_soa_query;

// Initialize a query. required/excluded arrays must remain valid for query lifetime.
TC_POOL_API tc_soa_query tc_soa_query_init(
    tc_archetype** archetypes,
    size_t archetype_count,
    const tc_soa_type_id* required,
    size_t required_count,
    const tc_soa_type_id* excluded,
    size_t excluded_count
);

// Get next matching chunk. Returns false when no more chunks.
// out->data must point to an array of at least required_count void* pointers.
TC_POOL_API bool tc_soa_query_next(tc_soa_query* q, tc_soa_chunk* out);

#ifdef __cplusplus
}
#endif
