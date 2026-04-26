#pragma once

#include <cstdint>
#include <utility>

#include "termin/platform/offscreen_render_surface.hpp"
#include "tgfx2/handles.hpp"

namespace nanobind {
class module_;
}

namespace tgfx {
class IRenderDevice;
}

namespace termin {

class FBOSurfaceRef {
private:
    OffscreenRenderSurfaceHandle handle_{};

public:
    FBOSurfaceRef() = default;
    FBOSurfaceRef(tgfx::IRenderDevice& device, int width, int height);
    explicit FBOSurfaceRef(OffscreenRenderSurfaceHandle handle);

    bool is_valid() const;
    OffscreenRenderSurfaceHandle handle() const { return handle_; }
    OffscreenRenderSurface* surface() const;
    void resize(int width, int height);
    std::pair<int, int> framebuffer_size() const;
    std::pair<int, int> window_size() const;
    tgfx::TextureHandle color_tex() const;
    tgfx::TextureHandle depth_tex() const;
    uintptr_t tc_surface_ptr() const;
    uint32_t get_tgfx_color_tex_id() const;
    uint32_t get_framebuffer_id() const;
    void set_input_manager(uintptr_t input_manager_ptr);
    void make_current();
    void swap_buffers();
    bool should_close() const;
    void set_should_close(bool value);
    std::pair<double, double> get_cursor_pos() const;
    uintptr_t share_group_key() const;
    bool close();
};

void bind_offscreen_render_surface(nanobind::module_& m);

} // namespace termin
