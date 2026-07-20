#include "termin/render/tc_display_handle.hpp"

#include <cassert>
#include <vector>

namespace {

struct FixedSurface {
    tc_render_surface surface{};
    int width = 320;
    int height = 200;
};

void get_size(tc_render_surface* surface, int* width, int* height) {
    auto* fixed = static_cast<FixedSurface*>(surface->body);
    if (width) *width = fixed->width;
    if (height) *height = fixed->height;
}

uint32_t get_texture(tc_render_surface*) { return 1u; }
uintptr_t get_domain(tc_render_surface*) { return 1u; }
void destroy_surface(tc_render_surface*) {}
bool resize_surface(tc_render_surface* surface, int width, int height) {
    auto* fixed = static_cast<FixedSurface*>(surface->body);
    fixed->width = width;
    fixed->height = height;
    tc_render_surface_notify_resize(surface, width, height);
    return true;
}
void delete_surface(tc_render_surface* surface) {
    delete static_cast<FixedSurface*>(surface->body);
}

const tc_render_surface_vtable surface_vtable = {
    .get_size = get_size,
    .resize = resize_surface,
    .get_color_texture_id = get_texture,
    .get_graphics_domain_key = get_domain,
    .destroy = destroy_surface,
};

} // namespace

int main() {
    tc_display_pool_init();

    tc_display_handle first = tc_display_new("first", nullptr);
    assert(tc_display_alive(first));
    {
        termin::TcDisplay original(first);
        termin::TcDisplay copy = original;
        assert(original.is_valid());
        assert(copy.is_valid());
    }
    assert(tc_display_alive(first));
    assert(tc_display_free(first));
    assert(!tc_display_alive(first));
    assert(!tc_display_free(first));

    tc_display_handle reused = tc_display_new("reused", nullptr);
    assert(reused.index == first.index);
    assert(reused.generation != first.generation);
    assert(tc_display_get_name(first) == nullptr);

    auto* fixed = new FixedSurface;
    tc_render_surface_init(&fixed->surface, &surface_vtable, delete_surface);
    fixed->surface.body = fixed;
    tc_display_handle resized = tc_display_new("resized", &fixed->surface);
    tc_viewport_handle viewport = tc_viewport_new("viewport", TC_SCENE_HANDLE_INVALID);
    tc_display_add_viewport(resized, viewport);

    std::vector<tc_display_handle> growth;
    for (int i = 0; i < 20; ++i) {
        growth.push_back(tc_display_new("growth", nullptr));
    }
    fixed->width = 640;
    fixed->height = 360;
    tc_render_surface_notify_resize(&fixed->surface, fixed->width, fixed->height);
    int x = 0;
    int y = 0;
    int width = 0;
    int height = 0;
    tc_viewport_get_pixel_rect(viewport, &x, &y, &width, &height);
    assert(width == 640);
    assert(height == 360);

    assert(tc_display_free(resized));
    for (tc_display_handle handle : growth) assert(tc_display_free(handle));
    assert(tc_display_free(reused));
    assert(tc_display_pool_count() == 0u);
    tc_display_pool_shutdown();
    return 0;
}
