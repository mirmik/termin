#pragma once

#include <cstdint>
#include <utility>

#include "render/termin_display_api.h"
#include "render/tc_input_manager.h"
#include "render/tc_render_surface.h"
#include "tgfx2/handles.hpp"

namespace tgfx {
class IRenderDevice;
}

namespace termin {

struct OffscreenRenderSurfaceHandle {
    uint32_t index = UINT32_MAX;
    uint32_t generation = 0;
};

class TERMIN_DISPLAY_API OffscreenRenderSurface {
private:
    tgfx::IRenderDevice* device_ = nullptr;
    tc_render_surface surface_;
    tgfx::TextureHandle color_tex_{};
    tgfx::TextureHandle depth_tex_{};
    int width_ = 0;
    int height_ = 0;
    uint32_t ref_count_ = 0;

public:
    OffscreenRenderSurface(tgfx::IRenderDevice* device, int width, int height);
    ~OffscreenRenderSurface();

    OffscreenRenderSurface(const OffscreenRenderSurface&) = delete;
    OffscreenRenderSurface& operator=(const OffscreenRenderSurface&) = delete;

    void resize(int width, int height);
    std::pair<int, int> size() const;
    tgfx::TextureHandle color_tex() const { return color_tex_; }
    tgfx::TextureHandle depth_tex() const { return depth_tex_; }
    tc_render_surface* tc_surface() { return &surface_; }
    const tc_render_surface* tc_surface() const { return &surface_; }
    uint32_t ref_count() const { return ref_count_; }
    void retain() { ref_count_++; }
    void release() { if (ref_count_ > 0) ref_count_--; }
    void set_input_manager(tc_input_manager* manager);

private:
    void allocate_textures();
    void release_textures();

    static OffscreenRenderSurface* from_tc_surface(tc_render_surface* s);
    static uint32_t vtable_get_framebuffer(tc_render_surface* self);
    static void vtable_get_size(tc_render_surface* self, int* width, int* height);
    static void vtable_make_current(tc_render_surface* self);
    static void vtable_swap_buffers(tc_render_surface* self);
    static uintptr_t vtable_context_key(tc_render_surface* self);
    static void vtable_poll_events(tc_render_surface* self);
    static void vtable_get_window_size(tc_render_surface* self, int* width, int* height);
    static bool vtable_should_close(tc_render_surface* self);
    static void vtable_set_should_close(tc_render_surface* self, bool value);
    static void vtable_get_cursor_pos(tc_render_surface* self, double* x, double* y);
    static void vtable_destroy(tc_render_surface* self);
    static uintptr_t vtable_share_group_key(tc_render_surface* self);
    static uint32_t vtable_get_tgfx_color_tex_id(tc_render_surface* self);

    static const tc_render_surface_vtable s_vtable;
};

TERMIN_DISPLAY_API bool offscreen_render_surface_handle_valid(OffscreenRenderSurfaceHandle handle);
TERMIN_DISPLAY_API OffscreenRenderSurfaceHandle offscreen_render_surface_create(
    tgfx::IRenderDevice* device,
    int width,
    int height
);
TERMIN_DISPLAY_API OffscreenRenderSurface* offscreen_render_surface_get(
    OffscreenRenderSurfaceHandle handle
);
TERMIN_DISPLAY_API OffscreenRenderSurfaceHandle offscreen_render_surface_find(
    tc_render_surface* surface
);
TERMIN_DISPLAY_API void offscreen_render_surface_retain(OffscreenRenderSurfaceHandle handle);
TERMIN_DISPLAY_API void offscreen_render_surface_release(OffscreenRenderSurfaceHandle handle);
TERMIN_DISPLAY_API bool offscreen_render_surface_destroy(OffscreenRenderSurfaceHandle handle);

} // namespace termin
