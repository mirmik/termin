// tc_picking.c - Entity picking utilities implementation
#include "tc_picking.h"
#include <stddef.h>

#define PICKING_COLOR_MASK 0x00FFFFFFu
#define PICKING_HALF_MASK  0x00000FFFu

static const uint32_t PICKING_ROUND_KEYS[5] = {
    0x2C3u, 0xA51u, 0x7E9u, 0x13Bu, 0xD74u
};

static uint32_t picking_round_fn(uint32_t half, uint32_t key) {
    uint32_t x = (half ^ key) & PICKING_HALF_MASK;
    x ^= (x << 5) & PICKING_HALF_MASK;
    x ^= x >> 7;
    x = (x * 0x09E5u + 0x07F4u) & PICKING_HALF_MASK;
    x ^= x >> 4;
    return x & PICKING_HALF_MASK;
}

static uint32_t picking_permute24(uint32_t value) {
    uint32_t left = (value >> 12) & PICKING_HALF_MASK;
    uint32_t right = value & PICKING_HALF_MASK;

    for (size_t i = 0; i < sizeof(PICKING_ROUND_KEYS) / sizeof(PICKING_ROUND_KEYS[0]); i++) {
        uint32_t next_left = right;
        uint32_t next_right = (left ^ picking_round_fn(right, PICKING_ROUND_KEYS[i])) & PICKING_HALF_MASK;
        left = next_left;
        right = next_right;
    }

    return ((left & PICKING_HALF_MASK) << 12) | (right & PICKING_HALF_MASK);
}

static uint32_t picking_unpermute24(uint32_t value) {
    uint32_t left = (value >> 12) & PICKING_HALF_MASK;
    uint32_t right = value & PICKING_HALF_MASK;

    for (size_t i = sizeof(PICKING_ROUND_KEYS) / sizeof(PICKING_ROUND_KEYS[0]); i > 0; i--) {
        uint32_t previous_right = left;
        uint32_t previous_left = (right ^ picking_round_fn(previous_right, PICKING_ROUND_KEYS[i - 1])) & PICKING_HALF_MASK;
        left = previous_left;
        right = previous_right;
    }

    return ((left & PICKING_HALF_MASK) << 12) | (right & PICKING_HALF_MASK);
}

static uint32_t picking_encode_nonzero(uint32_t pick_id) {
    uint32_t color = picking_permute24(pick_id);
    while (color == 0) {
        color = picking_permute24(color);
    }
    return color;
}

static uint32_t picking_decode_nonzero(uint32_t color) {
    uint32_t pick_id = picking_unpermute24(color);
    while (pick_id == 0) {
        pick_id = picking_unpermute24(pick_id);
    }
    return pick_id;
}

void tc_picking_id_to_rgb(int id, int* r, int* g, int* b) {
    uint32_t color = 0;
    if (id > 0 && (uint32_t)id <= PICKING_COLOR_MASK) {
        color = picking_encode_nonzero((uint32_t)id);
    }

    if (r) *r = (int)(color & 0x0000FFu);
    if (g) *g = (int)((color >> 8) & 0x0000FFu);
    if (b) *b = (int)((color >> 16) & 0x0000FFu);
}

void tc_picking_id_to_rgb_float(int id, float* r, float* g, float* b) {
    int r_int, g_int, b_int;
    tc_picking_id_to_rgb(id, &r_int, &g_int, &b_int);

    if (r) *r = (float)r_int / 255.0f;
    if (g) *g = (float)g_int / 255.0f;
    if (b) *b = (float)b_int / 255.0f;
}

int tc_picking_rgb_to_id(int r, int g, int b) {
    uint32_t color = ((uint32_t)(r & 0xFF))
                   | ((uint32_t)(g & 0xFF) << 8)
                   | ((uint32_t)(b & 0xFF) << 16);
    if (color == 0) {
        return 0;
    }
    return (int)picking_decode_nonzero(color);
}

void tc_picking_cache_clear(void) {
    // Kept for API compatibility. Picking color decode is deterministic now.
}
