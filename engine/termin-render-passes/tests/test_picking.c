#include <stdlib.h>

#include "guard_c.h"
#include "tc_picking.h"

typedef uint32_t uint;
#include "../../../graphics/termin-graphics/resources/builtin_shaders/termin_pick_encoding.slang"

static int color_distance(int ar, int ag, int ab, int br, int bg, int bb) {
    return abs(ar - br) + abs(ag - bg) + abs(ab - bb);
}

GUARD_C_TEST(test_picking_zero_is_background) {
    int r = -1;
    int g = -1;
    int b = -1;

    tc_picking_id_to_rgb(0, &r, &g, &b);

    GUARD_C_CHECK_EQ_INT(0, r);
    GUARD_C_CHECK_EQ_INT(0, g);
    GUARD_C_CHECK_EQ_INT(0, b);
    GUARD_C_CHECK_EQ_INT(0, tc_picking_rgb_to_id(0, 0, 0));
    return 0;
}

GUARD_C_TEST(test_picking_roundtrip_without_cache) {
    const int ids[] = {
        1,
        2,
        3,
        5,
        6,
        22,
        25,
        249,
        1024,
        4096,
        65535,
        1048576,
        16777215,
    };

    for (size_t i = 0; i < sizeof(ids) / sizeof(ids[0]); i++) {
        int r = 0;
        int g = 0;
        int b = 0;
        tc_picking_id_to_rgb(ids[i], &r, &g, &b);
        tc_picking_cache_clear();
        GUARD_C_CHECK_EQ_INT(ids[i], tc_picking_rgb_to_id(r, g, b));
    }

    return 0;
}

GUARD_C_TEST(test_picking_low_ids_are_visually_distinct) {
    for (int id = 1; id < 16; id++) {
        int ar = 0;
        int ag = 0;
        int ab = 0;
        int br = 0;
        int bg = 0;
        int bb = 0;

        tc_picking_id_to_rgb(id, &ar, &ag, &ab);
        tc_picking_id_to_rgb(id + 1, &br, &bg, &bb);

        GUARD_C_CHECK(color_distance(ar, ag, ab, br, bg, bb) >= 64);
    }

    int id5_r = 0;
    int id5_g = 0;
    int id5_b = 0;
    int id6_r = 0;
    int id6_g = 0;
    int id6_b = 0;
    tc_picking_id_to_rgb(5, &id5_r, &id5_g, &id5_b);
    tc_picking_id_to_rgb(6, &id6_r, &id6_g, &id6_b);
    GUARD_C_CHECK(color_distance(id5_r, id5_g, id5_b, id6_r, id6_g, id6_b) >= 128);

    return 0;
}

GUARD_C_TEST(test_shader_picking_encoding_matches_cpu) {
    // Cover consecutive low IDs, the full 24-bit range at varied strides, and
    // the zero-permutation edge case by checking every valid ID.
    for (uint32_t id = 0; id <= 0xffffffu; ++id) {
        int r, g, b;
        tc_picking_id_to_rgb((int)id, &r, &g, &b);
        uint32_t expected = (uint32_t)r | ((uint32_t)g << 8) | ((uint32_t)b << 16);
        GUARD_C_CHECK_EQ_INT(expected, termin_pick_encode(id));
    }
    GUARD_C_CHECK_EQ_INT(0, termin_pick_encode(0x1000000u));
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_shader_picking_encoding_matches_cpu);
    GUARD_C_RUN(test_picking_zero_is_background);
    GUARD_C_RUN(test_picking_roundtrip_without_cache);
    GUARD_C_RUN(test_picking_low_ids_are_visually_distinct);
    return GUARD_C_END();
}
