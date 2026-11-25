#include "termin/platform/offscreen_render_surface.hpp"

#include <exception>
#include <limits>
#include <new>
#include <vector>

#include "geom/tc_color.h"
#include "render/tc_display.h"
#include "render/tc_render_surface.h"
#include "tgfx/tgfx2_interop.h"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/handles.hpp"
#include "tgfx2/i_command_list.hpp"
#include "tgfx2/i_render_device.hpp"
#include <tcbase/tc_log.hpp>

namespace termin {
    namespace {

        bool read_error(const char* message) {
            tc::Log::error("tc_display_read_offscreen_bgra_current: %s", message);
            return false;
        }

        uint8_t srgb_byte(float value) {
            if (!(value > 0.0f))
                return 0;
            if (value >= 1.0f)
                return 255;
            return static_cast<uint8_t>(value * 255.0f + 0.5f);
        }

        class OffscreenRenderSurface {
        public:
            OffscreenRenderSurface(tgfx::IRenderDevice* device, int width, int height)
                : device_(device),
                  width_(width),
                  height_(height) {
                tc_render_surface_init(&surface_, &s_vtable, &delete_storage);
                surface_.body = this;
                color_tex_ = allocate_texture(width, height);
            }

            ~OffscreenRenderSurface() = default;

            tc_render_surface* tc_surface() {
                return &surface_;
            }
            bool is_valid() const {
                return device_ && color_tex_;
            }

            static OffscreenRenderSurface* get(tc_display_handle display) {
                auto* surface = tc_display_get_surface(display);
                return surface && surface->vtable == &s_vtable ? from_surface(surface) : nullptr;
            }

            bool read_bgra(tgfx::IRenderDevice* device,
                           int width,
                           int height,
                           uint8_t* destination,
                           size_t row_stride,
                           size_t destination_size);

        private:
            tgfx::IRenderDevice* device_ = nullptr;
            tc_render_surface surface_{};
            tgfx::TextureHandle color_tex_{};
            int width_ = 0;
            int height_ = 0;
            std::vector<float> readback_;

            static const tc_render_surface_vtable s_vtable;

            tgfx::TextureHandle allocate_texture(int width, int height) {
                tgfx::TextureDesc color_desc;
                color_desc.width = static_cast<uint32_t>(width);
                color_desc.height = static_cast<uint32_t>(height);
                // An offscreen display is a compositing boundary, not an encoded
                // presentation surface. Preserve DisplayLinear precision until
                // the eventual physical sink performs its output transform.
                // The surface exposes only color; pipeline render targets own
                // any depth attachments needed while rendering the viewports.
                color_desc.format = tgfx::PixelFormat::RGBA16F;
                color_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::ColorAttachment |
                                   tgfx::TextureUsage::CopySrc | tgfx::TextureUsage::CopyDst;
                return device_->create_texture(color_desc);
            }

            void release_texture() {
                if (!device_) {
                    color_tex_ = {};
                    return;
                }
                if (color_tex_) {
                    device_->destroy(color_tex_);
                    color_tex_ = {};
                }
                device_->invalidate_render_target_cache();
            }

            bool resize(int width, int height) {
                if (!device_ || width <= 0 || height <= 0)
                    return false;
                if (width == width_ && height == height_)
                    return true;
                auto replacement = allocate_texture(width, height);
                if (!replacement)
                    return false;
                release_texture();
                color_tex_ = replacement;
                width_ = width;
                height_ = height;
                tc_render_surface_notify_resize(&surface_, width_, height_);
                return true;
            }

            static OffscreenRenderSurface* from_surface(tc_render_surface* surface) {
                return surface ? static_cast<OffscreenRenderSurface*>(surface->body) : nullptr;
            }

            static void get_size(tc_render_surface* surface, int* width, int* height) {
                OffscreenRenderSurface* self = from_surface(surface);
                if (width)
                    *width = self ? self->width_ : 0;
                if (height)
                    *height = self ? self->height_ : 0;
            }

            static bool resize_surface(tc_render_surface* surface, int width, int height) {
                OffscreenRenderSurface* self = from_surface(surface);
                try {
                    return self && self->resize(width, height);
                } catch (const std::exception& error) {
                    tc::Log::error("OffscreenRenderSurface::resize: %s", error.what());
                } catch (...) {
                    tc::Log::error("OffscreenRenderSurface::resize: unexpected error");
                }
                return false;
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
                if (!self)
                    return;
                self->release_texture();
                self->device_ = nullptr;
            }

            static void delete_storage(tc_render_surface* surface) {
                delete from_surface(surface);
            }
        };

        bool OffscreenRenderSurface::read_bgra(tgfx::IRenderDevice* device,
                                               int width,
                                               int height,
                                               uint8_t* destination,
                                               size_t row_stride,
                                               size_t destination_size) {
            if (!device || device != device_ || !color_tex_)
                return read_error("display has no output in the active graphics domain");
            if (width <= 0 || height <= 0 || width != width_ || height != height_ || !destination)
                return read_error("destination and matching positive dimensions are required");

            const auto columns = static_cast<size_t>(width);
            const auto rows = static_cast<size_t>(height);
            constexpr auto max_size = std::numeric_limits<size_t>::max();
            if (columns > max_size / 4)
                return read_error("row size overflows");
            const size_t row_bytes = columns * 4;
            if (row_stride < row_bytes || rows - 1 > (max_size - row_bytes) / row_stride ||
                destination_size < (rows - 1) * row_stride + row_bytes)
                return read_error("destination buffer or row stride is too small");
            if (rows > max_size / sizeof(float) / row_bytes)
                return read_error("readback size overflows");

            const auto backend = device->backend_type();
            if (backend != tgfx::BackendType::D3D11 && backend != tgfx::BackendType::Vulkan)
                return read_error("offscreen readback requires D3D11 or Vulkan");

            readback_.resize(rows * row_bytes);
            if (backend == tgfx::BackendType::Vulkan) {
                // The display composite records a transfer after the scene's draw submission.
                // Submit it before synchronous readback uses its own command buffer.
                auto commands = device->create_command_list();
                if (!commands)
                    return read_error("could not create the Vulkan display submission");
                commands->begin();
                commands->end();
                device->submit(*commands);
            }
            if (!device->read_texture_rgba_float(color_tex_, readback_.data()))
                return read_error("graphics device could not read the display texture");

            for (size_t y = 0; y < rows; ++y) {
                const float* source = readback_.data() + y * row_bytes;
                uint8_t* pixel = destination + y * row_stride;
                for (size_t x = 0; x < columns; ++x, source += 4, pixel += 4) {
                    const tc_srgb_color srgb = tc_linear_to_srgb({source[0], source[1], source[2], 1.0f});
                    pixel[0] = srgb_byte(srgb.b);
                    pixel[1] = srgb_byte(srgb.g);
                    pixel[2] = srgb_byte(srgb.r);
                    pixel[3] = 255;
                }
            }
            return true;
        }

        const tc_render_surface_vtable OffscreenRenderSurface::s_vtable = {
            .get_size = &OffscreenRenderSurface::get_size,
            .resize = &OffscreenRenderSurface::resize_surface,
            .get_color_texture_id = &OffscreenRenderSurface::get_color_texture_id,
            .get_graphics_domain_key = &OffscreenRenderSurface::get_graphics_domain_key,
            .destroy = &OffscreenRenderSurface::destroy,
        };

        tc_display_handle create_host_offscreen_display(tgfx::IRenderDevice* device,
                                                        int width,
                                                        int height,
                                                        const char* name) {
            try {
                return create_offscreen_display(device, width, height, name);
            } catch (const std::exception& error) {
                tc::Log::error("create_offscreen_display: %s", error.what());
            } catch (...) {
                tc::Log::error("create_offscreen_display: unexpected error");
            }
            return TC_DISPLAY_HANDLE_INVALID;
        }

    } // namespace

    tc_display_handle create_offscreen_display(tgfx::IRenderDevice* device, int width, int height, const char* name) {
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

extern "C" tc_display_handle tc_display_new_offscreen_current(int width, int height, const char* name) {
    return termin::create_host_offscreen_display(tgfx::get_tgfx2_device(), width, height, name);
}

extern "C" tc_display_handle tc_display_new_d3d11_offscreen_current(int width, int height, const char* name) {
    auto* device = tgfx::get_tgfx2_device();
    if (!device) {
        tc::Log::error("tc_display_new_d3d11_offscreen_current: GraphicsHost has not claimed a tgfx2 device");
        return TC_DISPLAY_HANDLE_INVALID;
    }
    if (device->backend_type() != tgfx::BackendType::D3D11) {
        tc::Log::error("tc_display_new_d3d11_offscreen_current: the current tgfx2 device is not D3D11");
        return TC_DISPLAY_HANDLE_INVALID;
    }
    return termin::create_host_offscreen_display(device, width, height, name);
}

extern "C" bool tc_display_read_offscreen_bgra_current(tc_display_handle display,
                                                       int width,
                                                       int height,
                                                       uint8_t* destination,
                                                       size_t row_stride,
                                                       size_t destination_size) {
    auto* surface = termin::OffscreenRenderSurface::get(display);
    if (!surface)
        return termin::read_error("display does not own a live offscreen surface");

    try {
        return surface->read_bgra(tgfx::get_tgfx2_device(), width, height, destination, row_stride, destination_size);
    } catch (const std::exception& error) {
        return termin::read_error(error.what());
    } catch (...) {
        return termin::read_error("unexpected error");
    }
}
