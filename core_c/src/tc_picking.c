// tc_picking.c - Entity picking utilities implementation
#include "tc_picking.h"
#include <string.h>

// Hash function (same as in id_pass.cpp and picking.py)
static uint32_t hash_int(uint32_t i) {
    i = ((i >> 16) ^ i) * 0x45d9f3b;
    i = ((i >> 16) ^ i) * 0x45d9f3b;
    i = (i >> 16) ^ i;
    return i;
}

// Simple hash map for RGB -> ID cache
// Key: (r << 16) | (g << 8) | b
// Value: entity ID

#define CACHE_SIZE 4096
#define CACHE_MASK (CACHE_SIZE - 1)

typedef struct {
    uint32_t key;
    int value;
    bool occupied;
} cache_entry;

static cache_entry g_cache[CACHE_SIZE];

static uint32_t rgb_to_key(int r, int g, int b) {
    return ((uint32_t)r << 16) | ((uint32_t)g << 8) | (uint32_t)b;
}

static void cache_put(uint32_t key, int value) {
    uint32_t idx = key & CACHE_MASK;
    // Linear probing
    for (int i = 0; i < CACHE_SIZE; i++) {
        uint32_t probe = (idx + i) & CACHE_MASK;
        if (!g_cache[probe].occupied || g_cache[probe].key == key) {
            g_cache[probe].key = key;
            g_cache[probe].value = value;
            g_cache[probe].occupied = true;
            return;
        }
    }
    // Cache full - overwrite at original index
    g_cache[idx].key = key;
    g_cache[idx].value = value;
    g_cache[idx].occupied = true;
}

static int cache_get(uint32_t key) {
    uint32_t idx = key & CACHE_MASK;
    // Linear probing
    for (int i = 0; i < CACHE_SIZE; i++) {
        uint32_t probe = (idx + i) & CACHE_MASK;
        if (!g_cache[probe].occupied) {
            return 0;  // Not found
        }
        if (g_cache[probe].key == key) {
            return g_cache[probe].value;
        }
    }
    return 0;  // Not found
}

void tc_picking_id_to_rgb(int id, int* r, int* g, int* b) {
    uint32_t pid = hash_int((uint32_t)id);

    int r_int = pid & 0x000000FF;
    int g_int = (pid & 0x0000FF00) >> 8;
    int b_int = (pid & 0x00FF0000) >> 16;

    // Cache the mapping
    uint32_t key = rgb_to_key(r_int, g_int, b_int);
    cache_put(key, id);

    if (r) *r = r_int;
    if (g) *g = g_int;
    if (b) *b = b_int;
}

void tc_picking_id_to_rgb_float(int id, float* r, float* g, float* b) {
    int r_int, g_int, b_int;
    tc_picking_id_to_rgb(id, &r_int, &g_int, &b_int);

    if (r) *r = (float)r_int / 255.0f;
    if (g) *g = (float)g_int / 255.0f;
    if (b) *b = (float)b_int / 255.0f;
}

int tc_picking_rgb_to_id(int r, int g, int b) {
    uint32_t key = rgb_to_key(r, g, b);
    return cache_get(key);
}

void tc_picking_cache_clear(void) {
    memset(g_cache, 0, sizeof(g_cache));
}
