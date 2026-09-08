// Exact CPU picking permutation (tc_picking.c). Kept C-compatible so the
// picking unit test executes this shader source against the canonical decoder.
uint termin_pick_round(uint half_value, uint key) {
    uint x = (half_value ^ key) & 0xfffu;
    x ^= (x << 5) & 0xfffu;
    x ^= x >> 7;
    x = (x * 0x09e5u + 0x07f4u) & 0xfffu;
    x ^= x >> 4;
    return x & 0xfffu;
}
uint termin_pick_permute(uint value) {
    const uint keys[5] = {0x2c3u, 0xa51u, 0x7e9u, 0x13bu, 0xd74u};
    uint left = (value >> 12) & 0xfffu;
    uint right = value & 0xfffu;
    for (uint i = 0; i < 5; ++i) {
        uint next_left = right;
        right = (left ^ termin_pick_round(right, keys[i])) & 0xfffu;
        left = next_left;
    }
    return (left << 12) | right;
}
uint termin_pick_encode(uint id) {
    if (id == 0 || id > 0xffffffu) return 0;
    uint color = termin_pick_permute(id);
    while (color == 0) color = termin_pick_permute(color);
    return color;
}
