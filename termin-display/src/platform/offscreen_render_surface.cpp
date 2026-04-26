#include "termin/platform/offscreen_render_surface.hpp"

#include <algorithm>
#include <memory>
#include <vector>

#include <tcbase/tc_log.hpp>
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"

namespace termin {

namespace {

struct OffscreenSurfacePoolEntry {
    std::unique_ptr<OffscreenRenderSurface> surface;
    uint32_t generation = 1;
};

std::vector<OffscreenSurfacePoolEntry>& offscreen_surface_pool() {
    static auto* pool = new std::vector<OffscreenSurfacePoolEntry>();
    return *pool;
}

} // namespace

const tc_render_surface_vtable OffscreenRenderSurface::s_vtable = {
    .get_framebuffer = &OffscreenRenderSurface::vtable_get_framebuffer,
    .get_size = &OffscreenRenderSurface::vtable_get_size,
    .make_current = &OffscreenRenderSurface::vtable_make_current,
    .swap_buffers = &OffscreenRenderSurface::vtable_swap_buffers,
    .context_key = &OffscreenRenderSurface::vtable_context_key,
    .poll_events = &OffscreenRenderSurface::vtable_poll_events,
    .get_window_size = &OffscreenRenderSurface::vtable_get_window_size,
    .should_close = &OffscreenRenderSurface::vtable_should_close,
    .set_should_close = &OffscreenRenderSurface::vtable_set_should_close,
    .get_cursor_pos = &OffscreenRenderSurface::vtable_get_cursor_pos,
    .destroy = &OffscreenRenderSurface::vtable_destroy,
    .share_group_key = &OffscreenRenderSurface::vtable_share_group_key,
    .get_tgfx_color_tex_id = &OffscreenRenderSurface::vtable_get_tgfx_color_tex_id,
};

OffscreenRenderSurface::OffscreenRenderSurface(tgfx::IRenderDevice* device, int width, int height)
    : device_(device)
    , width_(std::max(1, width))
    , height_(std::max(1, height))
{
    tc_render_surface_init(&surface_, &s_vtable);
    surface_.body = this;
    allocate_textures();
}

OffscreenRenderSurface::~OffscreenRenderSurface() {
    if (surface_.gpu_context) {
        tc_gpu_context_free(surface_.gpu_context);
        surface_.gpu_context = nullptr;
    }
    release_textures();
}

void OffscreenRenderSurface::resize(int width, int height) {
    int next_width = std::max(1, width);
    int next_height = std::max(1, height);
    if (next_width == width_ && next_height == height_) {
        return;
    }

    release_textures();
    width_ = next_width;
    height_ = next_height;
    allocate_textures();
    tc_render_surface_notify_resize(&surface_, width_, height_);
}

std::pair<int, int> OffscreenRenderSurface::size() const {
    return {width_, height_};
}

void OffscreenRenderSurface::set_input_manager(tc_input_manager* manager) {
    tc_render_surface_set_input_manager(&surface_, manager);
}

void OffscreenRenderSurface::allocate_textures() {
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
                       tgfx::TextureUsage::Sampled;
    depth_tex_ = device_->create_texture(depth_desc);
}

void OffscreenRenderSurface::release_textures() {
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

OffscreenRenderSurface* OffscreenRenderSurface::from_tc_surface(tc_render_surface* s) {
    if (!s) return nullptr;
    return reinterpret_cast<OffscreenRenderSurface*>(s->body);
}

uint32_t OffscreenRenderSurface::vtable_get_framebuffer(tc_render_surface* self) {
    (void)self;
    return 0;
}

void OffscreenRenderSurface::vtable_get_size(tc_render_surface* self, int* width, int* height) {
    auto* surface = from_tc_surface(self);
    if (!surface) {
        if (width) *width = 0;
        if (height) *height = 0;
        return;
    }
    if (width) *width = surface->width_;
    if (height) *height = surface->height_;
}

void OffscreenRenderSurface::vtable_make_current(tc_render_surface* self) {
    (void)self;
}

void OffscreenRenderSurface::vtable_swap_buffers(tc_render_surface* self) {
    (void)self;
}

uintptr_t OffscreenRenderSurface::vtable_context_key(tc_render_surface* self) {
    auto* surface = from_tc_surface(self);
    return reinterpret_cast<uintptr_t>(surface ? surface->device_ : nullptr);
}

void OffscreenRenderSurface::vtable_poll_events(tc_render_surface* self) {
    (void)self;
}

void OffscreenRenderSurface::vtable_get_window_size(tc_render_surface* self, int* width, int* height) {
    vtable_get_size(self, width, height);
}

bool OffscreenRenderSurface::vtable_should_close(tc_render_surface* self) {
    (void)self;
    return false;
}

void OffscreenRenderSurface::vtable_set_should_close(tc_render_surface* self, bool value) {
    (void)self;
    (void)value;
}

void OffscreenRenderSurface::vtable_get_cursor_pos(tc_render_surface* self, double* x, double* y) {
    (void)self;
    if (x) *x = 0.0;
    if (y) *y = 0.0;
}

void OffscreenRenderSurface::vtable_destroy(tc_render_surface* self) {
    (void)self;
}

uintptr_t OffscreenRenderSurface::vtable_share_group_key(tc_render_surface* self) {
    auto* surface = from_tc_surface(self);
    return reinterpret_cast<uintptr_t>(surface ? surface->device_ : nullptr);
}

uint32_t OffscreenRenderSurface::vtable_get_tgfx_color_tex_id(tc_render_surface* self) {
    auto* surface = from_tc_surface(self);
    return surface ? surface->color_tex_.id : 0;
}

bool offscreen_render_surface_handle_valid(OffscreenRenderSurfaceHandle handle) {
    auto& pool = offscreen_surface_pool();
    return handle.index < pool.size() &&
           pool[handle.index].generation == handle.generation &&
           pool[handle.index].surface != nullptr;
}

OffscreenRenderSurfaceHandle offscreen_render_surface_create(
    tgfx::IRenderDevice* device,
    int width,
    int height
) {
    auto& pool = offscreen_surface_pool();
    for (uint32_t i = 0; i < pool.size(); ++i) {
        auto& entry = pool[i];
        if (!entry.surface) {
            entry.surface = std::make_unique<OffscreenRenderSurface>(device, width, height);
            return {i, entry.generation};
        }
    }

    OffscreenSurfacePoolEntry entry;
    entry.surface = std::make_unique<OffscreenRenderSurface>(device, width, height);
    pool.push_back(std::move(entry));
    return {static_cast<uint32_t>(pool.size() - 1), pool.back().generation};
}

OffscreenRenderSurface* offscreen_render_surface_get(OffscreenRenderSurfaceHandle handle) {
    if (!offscreen_render_surface_handle_valid(handle)) {
        return nullptr;
    }
    return offscreen_surface_pool()[handle.index].surface.get();
}

OffscreenRenderSurfaceHandle offscreen_render_surface_find(tc_render_surface* surface) {
    if (!surface) {
        return {};
    }
    auto& pool = offscreen_surface_pool();
    for (uint32_t i = 0; i < pool.size(); ++i) {
        auto& entry = pool[i];
        if (entry.surface && entry.surface->tc_surface() == surface) {
            return {i, entry.generation};
        }
    }
    return {};
}

void offscreen_render_surface_retain(OffscreenRenderSurfaceHandle handle) {
    if (auto* surface = offscreen_render_surface_get(handle)) {
        surface->retain();
    }
}

void offscreen_render_surface_release(OffscreenRenderSurfaceHandle handle) {
    if (auto* surface = offscreen_render_surface_get(handle)) {
        surface->release();
    }
}

bool offscreen_render_surface_destroy(OffscreenRenderSurfaceHandle handle) {
    if (!offscreen_render_surface_handle_valid(handle)) {
        return false;
    }

    auto& entry = offscreen_surface_pool()[handle.index];
    if (entry.surface->ref_count() > 0) {
        tc::Log::error("offscreen_render_surface_destroy: surface is still referenced");
        return false;
    }

    entry.surface.reset();
    entry.generation++;
    if (entry.generation == 0) {
        entry.generation = 1;
    }
    return true;
}

} // namespace termin
