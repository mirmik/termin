#include "render/tc_display.h"
#include "render/tc_render_surface.h"

#include <cassert>
#include <cstdint>

namespace {

struct AdapterState {
    int width = 320;
    int height = 200;
    uint32_t texture_id = 17;
    uintptr_t domain_key = 0x1234;
    bool destroyed = false;
};

AdapterState* state(tc_render_surface* surface) {
    return static_cast<AdapterState*>(surface->body);
}

void get_size(tc_render_surface* surface, int* width, int* height) {
    AdapterState* adapter = state(surface);
    if (width) *width = adapter->width;
    if (height) *height = adapter->height;
}

uint32_t get_color_texture_id(tc_render_surface* surface) {
    return state(surface)->texture_id;
}

uintptr_t get_graphics_domain_key(tc_render_surface* surface) {
    return state(surface)->domain_key;
}

void destroy(tc_render_surface* surface) {
    state(surface)->destroyed = true;
}

const tc_render_surface_vtable valid_vtable = {
    .get_size = get_size,
    .get_color_texture_id = get_color_texture_id,
    .get_graphics_domain_key = get_graphics_domain_key,
    .destroy = destroy,
};

} // namespace

int main() {
    AdapterState adapter;
    tc_render_surface* external = tc_render_surface_new_external(
        &adapter, &valid_vtable, sizeof(valid_vtable), TC_RENDER_SURFACE_ABI_VERSION);
    assert(external != nullptr);

    uint32_t texture_id = 0;
    assert(tc_render_surface_validate_output(external, adapter.domain_key, &texture_id));
    assert(texture_id == adapter.texture_id);
    assert(!tc_render_surface_validate_output(external, 0x5678, &texture_id));
    assert(texture_id == 0);

    assert(tc_render_surface_new_external(
        &adapter, &valid_vtable, sizeof(valid_vtable), TC_RENDER_SURFACE_ABI_VERSION + 1) == nullptr);
    assert(tc_render_surface_new_external(
        &adapter, &valid_vtable, sizeof(valid_vtable) - 1, TC_RENDER_SURFACE_ABI_VERSION) == nullptr);
    tc_render_surface_vtable malformed = valid_vtable;
    malformed.get_color_texture_id = nullptr;
    assert(tc_render_surface_new_external(
        &adapter, &malformed, sizeof(malformed), TC_RENDER_SURFACE_ABI_VERSION) == nullptr);

    tc_display* first = tc_display_new("first", external);
    assert(first != nullptr);
    tc_render_surface_resize_fn first_resize = external->on_resize;
    void* first_resize_userdata = external->on_resize_userdata;
    tc_display* duplicate = tc_display_new("duplicate", external);
    assert(duplicate == nullptr);
    assert(external->on_resize == first_resize);
    assert(external->on_resize_userdata == first_resize_userdata);
    assert(external->attached_display == first);
    assert(!tc_render_surface_free_external(external));
    assert(!adapter.destroyed);

    tc_display_free(first);
    assert(external->attached_display == nullptr);
    tc_display* second = tc_display_new("second", external);
    assert(second != nullptr);
    tc_display_free(second);

    assert(tc_render_surface_free_external(external));
    assert(adapter.destroyed);
    return 0;
}
