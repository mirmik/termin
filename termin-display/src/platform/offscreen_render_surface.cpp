#include "termin/platform/offscreen_render_surface.hpp"

#include <algorithm>
#include <new>

#include <tcbase/tc_log.hpp>
#include "render/tc_display.h"
#include "render/tc_render_surface.h"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/handles.hpp"
#include "tgfx2/i_render_device.hpp"

namespace termin {
namespace {

class OffscreenRenderSurface {
public:
    OffscreenRenderSurface(tgfx::IRenderDevice* device, int width, int height)
        : device_(device)
        , width_(std::max(1, width))
        , height_(std::max(1, height)) {
        tc_render_surface_init(&surface_, &s_vtable, &delete_storage);
        surface_.body = this;
        allocate_textures();
    }

    ~OffscreenRenderSurface() = default;

    tc_render_surface* tc_surface() { return &surface_; }
    bool is_valid() const { return device_ && color_tex_ && depth_tex_; }

private:
    tgfx::IRenderDevice* device_ = nullptr;
    tc_render_surface surface_{};
    tgfx::TextureHandle color_tex_{};
    tgfx::TextureHandle depth_tex_{};
    int width_ = 0;
    int height_ = 0;

    static const tc_render_surface_vtable s_vtable;

    void allocate_textures() {
        if (!device_) {
            tc::Log::error("OffscreenRenderSurface::allocate_textures: device is null");
            return;
        }

        tgfx::TextureDesc color_desc;
        color_desc.width = static_cast<uint32_t>(width_);
        color_desc.height = static_cast<uint32_t>(height_);
        color_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        color_desc.usage = tgfx::TextureUsage::Sampled |
                           tgfx::TextureUsage::ColorAttachment |
                           tgfx::TextureUsage::CopySrc |
                           tgfx::TextureUsage::CopyDst;
        color_tex_ = device_->create_texture(color_desc);

        tgfx::TextureDesc depth_desc;
        depth_desc.width = static_cast<uint32_t>(width_);
        depth_desc.height = static_cast<uint32_t>(height_);
        depth_desc.format = tgfx::PixelFormat::D24_UNorm;
        depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment |
                           tgfx::TextureUsage::Sampled |
                           tgfx::TextureUsage::CopySrc |
                           tgfx::TextureUsage::CopyDst;
        depth_tex_ = device_->create_texture(depth_desc);
        if (!color_tex_ || !depth_tex_) {
            tc::Log::error("OffscreenRenderSurface: texture allocation failed");
        }
    }

    void release_textures() {
        if (!device_) {
            color_tex_ = {};
            depth_tex_ = {};
            return;
        }
        if (color_tex_) {
            device_->destroy(color_tex_);
            color_tex_ = {};
        }
        if (depth_tex_) {
            device_->destroy(depth_tex_);
            depth_tex_ = {};
        }
        device_->invalidate_render_target_cache();
    }

    bool resize(int width, int height) {
        if (!device_ || width <= 0 || height <= 0) return false;
        if (width == width_ && height == height_) return true;
        release_textures();
        width_ = width;
        height_ = height;
        allocate_textures();
        if (!is_valid()) return false;
        tc_render_surface_notify_resize(&surface_, width_, height_);
        return true;
    }

    static OffscreenRenderSurface* from_surface(tc_render_surface* surface) {
        return surface
            ? static_cast<OffscreenRenderSurface*>(surface->body)
            : nullptr;
    }

    static void get_size(tc_render_surface* surface, int* width, int* height) {
        OffscreenRenderSurface* self = from_surface(surface);
        if (width) *width = self ? self->width_ : 0;
        if (height) *height = self ? self->height_ : 0;
    }

    static bool resize_surface(tc_render_surface* surface, int width, int height) {
        OffscreenRenderSurface* self = from_surface(surface);
        return self && self->resize(width, height);
    }

    static uint32_t get_color_texture_id(tc_render_surface* surface) {
        OffscreenRenderSurface* self = from_surface(surface);
        return self ? self->color_tex_.id : 0u;
    }

    static uintptr_t get_graphics_domain_key(tc_render_surface* surface) {
        OffscreenRenderSurface* self = from_surface(surface);
        return reinterpret_cast<uintptr_t>(self ? self->device_ : nullptr);
    }

    static void destroy(tc_render_surface* surface) {
        OffscreenRenderSurface* self = from_surface(surface);
        if (!self) return;
        self->release_textures();
        self->device_ = nullptr;
    }

    static void delete_storage(tc_render_surface* surface) {
        delete from_surface(surface);
    }
};

const tc_render_surface_vtable OffscreenRenderSurface::s_vtable = {
    .get_size = &OffscreenRenderSurface::get_size,
    .resize = &OffscreenRenderSurface::resize_surface,
    .get_color_texture_id = &OffscreenRenderSurface::get_color_texture_id,
    .get_graphics_domain_key = &OffscreenRenderSurface::get_graphics_domain_key,
    .destroy = &OffscreenRenderSurface::destroy,
};

} // namespace

tc_display_handle create_offscreen_display(
    tgfx::IRenderDevice* device,
    int width,
    int height,
    const char* name
) {
    if (!device || width <= 0 || height <= 0) {
        tc::Log::error("create_offscreen_display: device and positive dimensions are required");
        return TC_DISPLAY_HANDLE_INVALID;
    }
    auto* surface = new (std::nothrow) OffscreenRenderSurface(device, width, height);
    if (!surface) {
        tc::Log::error("create_offscreen_display: surface allocation failed");
        return TC_DISPLAY_HANDLE_INVALID;
    }
    if (!surface->is_valid()) {
        tc::Log::error("create_offscreen_display: texture allocation failed");
        tc_render_surface_delete_unowned(surface->tc_surface());
        return TC_DISPLAY_HANDLE_INVALID;
    }
    tc_display_handle display = tc_display_new(name ? name : "Display", surface->tc_surface());
    if (!tc_display_handle_valid(display)) {
        tc_render_surface_delete_unowned(surface->tc_surface());
    }
    return display;
}

} // namespace termin
