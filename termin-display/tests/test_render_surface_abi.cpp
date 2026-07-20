#include "render/tc_display.h"
#include "render/tc_render_surface.h"

#include <cassert>
#include <cstddef>
#include <cstdint>

namespace {

struct AdapterState {
    int width = 320;
    int height = 200;
    uint32_t texture_id = 17;
    uintptr_t domain_key = 0x1234;
    int destroy_count = 0;
};

AdapterState* state(tc_render_surface* surface) {
    return static_cast<AdapterState*>(surface->body);
}

void get_size(tc_render_surface* surface, int* width, int* height) {
    AdapterState* adapter = state(surface);
    if (width) *width = adapter->width;
    if (height) *height = adapter->height;
}

bool resize(tc_render_surface* surface, int width, int height) {
    AdapterState* adapter = state(surface);
    adapter->width = width;
    adapter->height = height;
    tc_render_surface_notify_resize(surface, width, height);
    return true;
}

uint32_t get_color_texture_id(tc_render_surface* surface) {
    return state(surface)->texture_id;
}

uintptr_t get_graphics_domain_key(tc_render_surface* surface) {
    return state(surface)->domain_key;
}

void destroy(tc_render_surface* surface) {
    state(surface)->destroy_count++;
}

const tc_render_surface_vtable valid_vtable = {
    .get_size = get_size,
    .resize = resize,
    .get_color_texture_id = get_color_texture_id,
    .get_graphics_domain_key = get_graphics_domain_key,
    .destroy = destroy,
};

struct NativeSurface {
    tc_render_surface surface{};
    AdapterState state{};
    int* delete_count = nullptr;
};

void delete_native_with_state(tc_render_surface* surface) {
    AdapterState* adapter = state(surface);
    auto* native = reinterpret_cast<NativeSurface*>(
        reinterpret_cast<char*>(adapter) - offsetof(NativeSurface, state));
    (*native->delete_count)++;
    delete native;
}

NativeSurface* make_owned_native(int* delete_count) {
    auto* native = new NativeSurface;
    native->delete_count = delete_count;
    tc_render_surface_init(&native->surface, &valid_vtable, delete_native_with_state);
    native->surface.body = &native->state;
    return native;
}

} // namespace

int main() {
    tc_display_pool_init();

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
    malformed.resize = nullptr;
    assert(tc_render_surface_new_external(
        &adapter, &malformed, sizeof(malformed), TC_RENDER_SURFACE_ABI_VERSION) == nullptr);

    tc_display_handle first = tc_display_new("first", external);
    assert(tc_display_handle_valid(first));
    assert(tc_display_validate_output(first, adapter.domain_key, &texture_id));
    assert(!tc_display_validate_output(first, 0x5678, &texture_id));
    assert(!tc_render_surface_delete_unowned(external));
    assert(adapter.destroy_count == 0);
    assert(tc_display_resize(first, 640, 360));
    assert(adapter.width == 640 && adapter.height == 360);

    AdapterState rejected_state;
    tc_render_surface* rejected = tc_render_surface_new_external(
        &rejected_state, &valid_vtable, sizeof(valid_vtable), TC_RENDER_SURFACE_ABI_VERSION);
    tc_display_handle second = tc_display_new("second", rejected);
    assert(tc_display_handle_valid(second));
    assert(!tc_display_set_surface(first, rejected));
    assert(tc_display_get_surface(first) == external);
    assert(tc_display_get_surface(second) == rejected);
    assert(adapter.destroy_count == 0);
    assert(rejected_state.destroy_count == 0);

    assert(tc_display_free(first));
    assert(adapter.destroy_count == 1);
    assert(tc_display_free(second));
    assert(rejected_state.destroy_count == 1);

    int native_delete_count = 0;
    NativeSurface* native = make_owned_native(&native_delete_count);
    tc_display_handle native_display = tc_display_new("native", &native->surface);
    assert(tc_display_handle_valid(native_display));
    assert(tc_display_free(native_display));
    assert(native_delete_count == 1);

    tc_display_pool_shutdown();
    return 0;
}
