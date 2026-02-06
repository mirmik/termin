#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// tc_str_map: String -> uint64 hash map
// ============================================================================

typedef struct tc_str_map tc_str_map;

// Create a new string map with initial capacity (will grow as needed)
TC_API tc_str_map* tc_str_map_new(size_t initial_capacity);

// Free the map and all keys
TC_API void tc_str_map_free(tc_str_map* map);

// Set a key-value pair (copies the key string)
TC_API void tc_str_map_set(tc_str_map* map, const char* key, uint64_t value);

// Get value by key. Returns true if found, false otherwise.
TC_API bool tc_str_map_get(const tc_str_map* map, const char* key, uint64_t* out_value);

// Remove a key. Returns true if key existed.
TC_API bool tc_str_map_remove(tc_str_map* map, const char* key);

// Get number of entries
TC_API size_t tc_str_map_count(const tc_str_map* map);

// Clear all entries
TC_API void tc_str_map_clear(tc_str_map* map);

// ============================================================================
// tc_u32_map: uint32 -> uint64 hash map
// ============================================================================

typedef struct tc_u32_map tc_u32_map;

// Create a new uint32 map with initial capacity
TC_API tc_u32_map* tc_u32_map_new(size_t initial_capacity);

// Free the map
TC_API void tc_u32_map_free(tc_u32_map* map);

// Set a key-value pair
TC_API void tc_u32_map_set(tc_u32_map* map, uint32_t key, uint64_t value);

// Get value by key. Returns true if found, false otherwise.
TC_API bool tc_u32_map_get(const tc_u32_map* map, uint32_t key, uint64_t* out_value);

// Remove a key. Returns true if key existed.
TC_API bool tc_u32_map_remove(tc_u32_map* map, uint32_t key);

// Get number of entries
TC_API size_t tc_u32_map_count(const tc_u32_map* map);

// Clear all entries
TC_API void tc_u32_map_clear(tc_u32_map* map);

// ============================================================================
// tc_u64_map: uint64 -> uint64 hash map
// ============================================================================

typedef struct tc_u64_map tc_u64_map;

// Create a new uint64 map with initial capacity
TC_API tc_u64_map* tc_u64_map_new(size_t initial_capacity);

// Free the map
TC_API void tc_u64_map_free(tc_u64_map* map);

// Set a key-value pair
TC_API void tc_u64_map_set(tc_u64_map* map, uint64_t key, uint64_t value);

// Get value by key. Returns true if found, false otherwise.
TC_API bool tc_u64_map_get(const tc_u64_map* map, uint64_t key, uint64_t* out_value);

// Remove a key. Returns true if key existed.
TC_API bool tc_u64_map_remove(tc_u64_map* map, uint64_t key);

// Get number of entries
TC_API size_t tc_u64_map_count(const tc_u64_map* map);

// Clear all entries
TC_API void tc_u64_map_clear(tc_u64_map* map);

#ifdef __cplusplus
}
#endif
