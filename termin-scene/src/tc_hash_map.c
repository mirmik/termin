#include "tc_hash_map.h"
#include <stdlib.h>
#include <string.h>

// Cross-platform strdup
#ifdef _WIN32
#define tc_strdup _strdup
#else
#define tc_strdup strdup
#endif

// ============================================================================
// Hash functions
// ============================================================================

// FNV-1a hash for strings
static uint64_t hash_string(const char* str) {
    uint64_t hash = 14695981039346656037ULL; // FNV offset basis
    while (*str) {
        hash ^= (uint8_t)*str++;
        hash *= 1099511628211ULL; // FNV prime
    }
    return hash;
}

// Simple hash for uint32
static uint64_t hash_u32(uint32_t key) {
    uint64_t x = key;
    x = (x ^ (x >> 16)) * 0x45d9f3bULL;
    x = (x ^ (x >> 16)) * 0x45d9f3bULL;
    x = x ^ (x >> 16);
    return x;
}

// ============================================================================
// tc_str_map implementation
// ============================================================================

#define STR_MAP_EMPTY    0
#define STR_MAP_OCCUPIED 1
#define STR_MAP_DELETED  2

typedef struct {
    char* key;
    uint64_t value;
    uint8_t state;
} str_entry;

struct tc_str_map {
    str_entry* entries;
    size_t capacity;
    size_t count;
    size_t deleted;
};

static size_t next_power_of_2(size_t n) {
    size_t p = 1;
    while (p < n) p <<= 1;
    return p;
}

tc_str_map* tc_str_map_new(size_t initial_capacity) {
    tc_str_map* map = (tc_str_map*)calloc(1, sizeof(tc_str_map));
    if (!map) return NULL;

    size_t cap = next_power_of_2(initial_capacity < 8 ? 8 : initial_capacity);
    map->entries = (str_entry*)calloc(cap, sizeof(str_entry));
    if (!map->entries) {
        free(map);
        return NULL;
    }
    map->capacity = cap;
    map->count = 0;
    map->deleted = 0;
    return map;
}

void tc_str_map_free(tc_str_map* map) {
    if (!map) return;
    if (map->entries) {
        for (size_t i = 0; i < map->capacity; i++) {
            if (map->entries[i].state == STR_MAP_OCCUPIED) {
                free(map->entries[i].key);
            }
        }
        free(map->entries);
    }
    free(map);
}

static void str_map_resize(tc_str_map* map, size_t new_capacity) {
    str_entry* old_entries = map->entries;
    size_t old_capacity = map->capacity;

    map->entries = (str_entry*)calloc(new_capacity, sizeof(str_entry));
    if (!map->entries) {
        map->entries = old_entries;
        return;
    }
    map->capacity = new_capacity;
    map->count = 0;
    map->deleted = 0;

    for (size_t i = 0; i < old_capacity; i++) {
        if (old_entries[i].state == STR_MAP_OCCUPIED) {
            tc_str_map_set(map, old_entries[i].key, old_entries[i].value);
            free(old_entries[i].key);
        }
    }
    free(old_entries);
}

void tc_str_map_set(tc_str_map* map, const char* key, uint64_t value) {
    if (!map || !key) return;

    // Resize if load factor > 0.7
    if ((map->count + map->deleted) * 10 > map->capacity * 7) {
        str_map_resize(map, map->capacity * 2);
    }

    uint64_t hash = hash_string(key);
    size_t mask = map->capacity - 1;
    size_t idx = hash & mask;
    size_t first_deleted = SIZE_MAX;

    for (size_t i = 0; i < map->capacity; i++) {
        size_t probe = (idx + i) & mask;
        str_entry* e = &map->entries[probe];

        if (e->state == STR_MAP_EMPTY) {
            if (first_deleted != SIZE_MAX) {
                probe = first_deleted;
                e = &map->entries[probe];
                map->deleted--;
            }
            e->key = tc_strdup(key);
            e->value = value;
            e->state = STR_MAP_OCCUPIED;
            map->count++;
            return;
        } else if (e->state == STR_MAP_DELETED) {
            if (first_deleted == SIZE_MAX) first_deleted = probe;
        } else if (strcmp(e->key, key) == 0) {
            e->value = value;
            return;
        }
    }
}

bool tc_str_map_get(const tc_str_map* map, const char* key, uint64_t* out_value) {
    if (!map || !key) return false;

    uint64_t hash = hash_string(key);
    size_t mask = map->capacity - 1;
    size_t idx = hash & mask;

    for (size_t i = 0; i < map->capacity; i++) {
        size_t probe = (idx + i) & mask;
        const str_entry* e = &map->entries[probe];

        if (e->state == STR_MAP_EMPTY) {
            return false;
        } else if (e->state == STR_MAP_OCCUPIED && strcmp(e->key, key) == 0) {
            if (out_value) *out_value = e->value;
            return true;
        }
    }
    return false;
}

bool tc_str_map_remove(tc_str_map* map, const char* key) {
    if (!map || !key) return false;

    uint64_t hash = hash_string(key);
    size_t mask = map->capacity - 1;
    size_t idx = hash & mask;

    for (size_t i = 0; i < map->capacity; i++) {
        size_t probe = (idx + i) & mask;
        str_entry* e = &map->entries[probe];

        if (e->state == STR_MAP_EMPTY) {
            return false;
        } else if (e->state == STR_MAP_OCCUPIED && strcmp(e->key, key) == 0) {
            free(e->key);
            e->key = NULL;
            e->state = STR_MAP_DELETED;
            map->count--;
            map->deleted++;
            return true;
        }
    }
    return false;
}

size_t tc_str_map_count(const tc_str_map* map) {
    return map ? map->count : 0;
}

void tc_str_map_clear(tc_str_map* map) {
    if (!map) return;
    for (size_t i = 0; i < map->capacity; i++) {
        if (map->entries[i].state == STR_MAP_OCCUPIED) {
            free(map->entries[i].key);
        }
        map->entries[i].key = NULL;
        map->entries[i].state = STR_MAP_EMPTY;
    }
    map->count = 0;
    map->deleted = 0;
}

// ============================================================================
// tc_u32_map implementation
// ============================================================================

#define U32_MAP_EMPTY    0xFFFFFFFF
#define U32_MAP_DELETED  0xFFFFFFFE

typedef struct {
    uint32_t key;
    uint64_t value;
} u32_entry;

struct tc_u32_map {
    u32_entry* entries;
    size_t capacity;
    size_t count;
    size_t deleted;
};

tc_u32_map* tc_u32_map_new(size_t initial_capacity) {
    tc_u32_map* map = (tc_u32_map*)calloc(1, sizeof(tc_u32_map));
    if (!map) return NULL;

    size_t cap = next_power_of_2(initial_capacity < 8 ? 8 : initial_capacity);
    map->entries = (u32_entry*)malloc(cap * sizeof(u32_entry));
    if (!map->entries) {
        free(map);
        return NULL;
    }

    for (size_t i = 0; i < cap; i++) {
        map->entries[i].key = U32_MAP_EMPTY;
    }

    map->capacity = cap;
    map->count = 0;
    map->deleted = 0;
    return map;
}

void tc_u32_map_free(tc_u32_map* map) {
    if (!map) return;
    free(map->entries);
    free(map);
}

static void u32_map_resize(tc_u32_map* map, size_t new_capacity) {
    u32_entry* old_entries = map->entries;
    size_t old_capacity = map->capacity;

    map->entries = (u32_entry*)malloc(new_capacity * sizeof(u32_entry));
    if (!map->entries) {
        map->entries = old_entries;
        return;
    }

    for (size_t i = 0; i < new_capacity; i++) {
        map->entries[i].key = U32_MAP_EMPTY;
    }

    map->capacity = new_capacity;
    map->count = 0;
    map->deleted = 0;

    for (size_t i = 0; i < old_capacity; i++) {
        if (old_entries[i].key != U32_MAP_EMPTY && old_entries[i].key != U32_MAP_DELETED) {
            tc_u32_map_set(map, old_entries[i].key, old_entries[i].value);
        }
    }
    free(old_entries);
}

void tc_u32_map_set(tc_u32_map* map, uint32_t key, uint64_t value) {
    if (!map) return;

    // Reserved values cannot be used as keys
    if (key == U32_MAP_EMPTY || key == U32_MAP_DELETED) return;

    // Resize if load factor > 0.7
    if ((map->count + map->deleted) * 10 > map->capacity * 7) {
        u32_map_resize(map, map->capacity * 2);
    }

    uint64_t hash = hash_u32(key);
    size_t mask = map->capacity - 1;
    size_t idx = hash & mask;
    size_t first_deleted = SIZE_MAX;

    for (size_t i = 0; i < map->capacity; i++) {
        size_t probe = (idx + i) & mask;
        u32_entry* e = &map->entries[probe];

        if (e->key == U32_MAP_EMPTY) {
            if (first_deleted != SIZE_MAX) {
                probe = first_deleted;
                e = &map->entries[probe];
                map->deleted--;
            }
            e->key = key;
            e->value = value;
            map->count++;
            return;
        } else if (e->key == U32_MAP_DELETED) {
            if (first_deleted == SIZE_MAX) first_deleted = probe;
        } else if (e->key == key) {
            e->value = value;
            return;
        }
    }
}

bool tc_u32_map_get(const tc_u32_map* map, uint32_t key, uint64_t* out_value) {
    if (!map) return false;
    if (key == U32_MAP_EMPTY || key == U32_MAP_DELETED) return false;

    uint64_t hash = hash_u32(key);
    size_t mask = map->capacity - 1;
    size_t idx = hash & mask;

    for (size_t i = 0; i < map->capacity; i++) {
        size_t probe = (idx + i) & mask;
        const u32_entry* e = &map->entries[probe];

        if (e->key == U32_MAP_EMPTY) {
            return false;
        } else if (e->key == key) {
            if (out_value) *out_value = e->value;
            return true;
        }
    }
    return false;
}

bool tc_u32_map_remove(tc_u32_map* map, uint32_t key) {
    if (!map) return false;
    if (key == U32_MAP_EMPTY || key == U32_MAP_DELETED) return false;

    uint64_t hash = hash_u32(key);
    size_t mask = map->capacity - 1;
    size_t idx = hash & mask;

    for (size_t i = 0; i < map->capacity; i++) {
        size_t probe = (idx + i) & mask;
        u32_entry* e = &map->entries[probe];

        if (e->key == U32_MAP_EMPTY) {
            return false;
        } else if (e->key == key) {
            e->key = U32_MAP_DELETED;
            map->count--;
            map->deleted++;
            return true;
        }
    }
    return false;
}

size_t tc_u32_map_count(const tc_u32_map* map) {
    return map ? map->count : 0;
}

void tc_u32_map_clear(tc_u32_map* map) {
    if (!map) return;
    for (size_t i = 0; i < map->capacity; i++) {
        map->entries[i].key = U32_MAP_EMPTY;
    }
    map->count = 0;
    map->deleted = 0;
}

// ============================================================================
// tc_u64_map implementation
// ============================================================================

#define U64_MAP_EMPTY   0xFFFFFFFFFFFFFFFFULL
#define U64_MAP_DELETED 0xFFFFFFFFFFFFFFFEULL

typedef struct {
    uint64_t key;
    uint64_t value;
} u64_entry;

struct tc_u64_map {
    u64_entry* entries;
    size_t capacity;
    size_t count;
    size_t deleted;
};

// splitmix64 hash
static uint64_t hash_u64(uint64_t x) {
    x ^= x >> 30;
    x *= 0xbf58476d1ce4e5b9ULL;
    x ^= x >> 27;
    x *= 0x94d049bb133111ebULL;
    x ^= x >> 31;
    return x;
}

tc_u64_map* tc_u64_map_new(size_t initial_capacity) {
    tc_u64_map* map = (tc_u64_map*)calloc(1, sizeof(tc_u64_map));
    if (!map) return NULL;

    size_t cap = next_power_of_2(initial_capacity < 8 ? 8 : initial_capacity);
    map->entries = (u64_entry*)malloc(cap * sizeof(u64_entry));
    if (!map->entries) {
        free(map);
        return NULL;
    }

    for (size_t i = 0; i < cap; i++) {
        map->entries[i].key = U64_MAP_EMPTY;
    }

    map->capacity = cap;
    map->count = 0;
    map->deleted = 0;
    return map;
}

void tc_u64_map_free(tc_u64_map* map) {
    if (!map) return;
    free(map->entries);
    free(map);
}

static void u64_map_resize(tc_u64_map* map, size_t new_capacity) {
    u64_entry* old_entries = map->entries;
    size_t old_capacity = map->capacity;

    map->entries = (u64_entry*)malloc(new_capacity * sizeof(u64_entry));
    if (!map->entries) {
        map->entries = old_entries;
        return;
    }

    for (size_t i = 0; i < new_capacity; i++) {
        map->entries[i].key = U64_MAP_EMPTY;
    }

    map->capacity = new_capacity;
    map->count = 0;
    map->deleted = 0;

    for (size_t i = 0; i < old_capacity; i++) {
        if (old_entries[i].key != U64_MAP_EMPTY && old_entries[i].key != U64_MAP_DELETED) {
            tc_u64_map_set(map, old_entries[i].key, old_entries[i].value);
        }
    }
    free(old_entries);
}

void tc_u64_map_set(tc_u64_map* map, uint64_t key, uint64_t value) {
    if (!map) return;
    if (key == U64_MAP_EMPTY || key == U64_MAP_DELETED) return;

    if ((map->count + map->deleted) * 10 > map->capacity * 7) {
        u64_map_resize(map, map->capacity * 2);
    }

    uint64_t h = hash_u64(key);
    size_t mask = map->capacity - 1;
    size_t idx = h & mask;
    size_t first_deleted = SIZE_MAX;

    for (size_t i = 0; i < map->capacity; i++) {
        size_t probe = (idx + i) & mask;
        u64_entry* e = &map->entries[probe];

        if (e->key == U64_MAP_EMPTY) {
            if (first_deleted != SIZE_MAX) {
                probe = first_deleted;
                e = &map->entries[probe];
                map->deleted--;
            }
            e->key = key;
            e->value = value;
            map->count++;
            return;
        } else if (e->key == U64_MAP_DELETED) {
            if (first_deleted == SIZE_MAX) first_deleted = probe;
        } else if (e->key == key) {
            e->value = value;
            return;
        }
    }
}

bool tc_u64_map_get(const tc_u64_map* map, uint64_t key, uint64_t* out_value) {
    if (!map) return false;
    if (key == U64_MAP_EMPTY || key == U64_MAP_DELETED) return false;

    uint64_t h = hash_u64(key);
    size_t mask = map->capacity - 1;
    size_t idx = h & mask;

    for (size_t i = 0; i < map->capacity; i++) {
        size_t probe = (idx + i) & mask;
        const u64_entry* e = &map->entries[probe];

        if (e->key == U64_MAP_EMPTY) {
            return false;
        } else if (e->key == key) {
            if (out_value) *out_value = e->value;
            return true;
        }
    }
    return false;
}

bool tc_u64_map_remove(tc_u64_map* map, uint64_t key) {
    if (!map) return false;
    if (key == U64_MAP_EMPTY || key == U64_MAP_DELETED) return false;

    uint64_t h = hash_u64(key);
    size_t mask = map->capacity - 1;
    size_t idx = h & mask;

    for (size_t i = 0; i < map->capacity; i++) {
        size_t probe = (idx + i) & mask;
        u64_entry* e = &map->entries[probe];

        if (e->key == U64_MAP_EMPTY) {
            return false;
        } else if (e->key == key) {
            e->key = U64_MAP_DELETED;
            map->count--;
            map->deleted++;
            return true;
        }
    }
    return false;
}

size_t tc_u64_map_count(const tc_u64_map* map) {
    return map ? map->count : 0;
}

void tc_u64_map_clear(tc_u64_map* map) {
    if (!map) return;
    for (size_t i = 0; i < map->capacity; i++) {
        map->entries[i].key = U64_MAP_EMPTY;
    }
    map->count = 0;
    map->deleted = 0;
}
