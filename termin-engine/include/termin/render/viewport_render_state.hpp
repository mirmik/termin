// viewport_render_state.hpp - Per-viewport GPU resource state
#pragma once

#include <tgfx2/handles.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/i_render_device.hpp>

namespace termin {

// Holds GPU resources for a single viewport:
// - output_color_tex / output_depth_tex: native tgfx2 textures used
//   as the viewport's final render target (color + depth). They are
//   owned by this state and destroyed on resize / destruction.
// - Intermediate FBOs are managed separately by the pipeline's FBOPool.
class ViewportRenderState {
public:
    tgfx::TextureHandle output_color_tex;
    tgfx::TextureHandle output_depth_tex;
    int output_width = 0;
    int output_height = 0;

private:
    tgfx::IRenderDevice* device_ = nullptr;

public:
    ViewportRenderState() = default;

    ~ViewportRenderState() {
        release_textures();
    }

    // Non-copyable
    ViewportRenderState(const ViewportRenderState&) = delete;
    ViewportRenderState& operator=(const ViewportRenderState&) = delete;

    // Movable — transfer ownership and null the source so the moved-from
    // destructor doesn't double-free.
    ViewportRenderState(ViewportRenderState&& other) noexcept
        : output_color_tex(other.output_color_tex),
          output_depth_tex(other.output_depth_tex),
          output_width(other.output_width),
          output_height(other.output_height),
          device_(other.device_) {
        other.output_color_tex = {};
        other.output_depth_tex = {};
        other.output_width = 0;
        other.output_height = 0;
        other.device_ = nullptr;
    }

    ViewportRenderState& operator=(ViewportRenderState&& other) noexcept {
        if (this != &other) {
            release_textures();
            output_color_tex = other.output_color_tex;
            output_depth_tex = other.output_depth_tex;
            output_width = other.output_width;
            output_height = other.output_height;
            device_ = other.device_;
            other.output_color_tex = {};
            other.output_depth_tex = {};
            other.output_width = 0;
            other.output_height = 0;
            other.device_ = nullptr;
        }
        return *this;
    }

    // Ensure output color+depth textures exist at the given size.
    // Reallocates on size change via the provided tgfx2 device.
    void ensure_output_textures(tgfx::IRenderDevice& device, int width, int height) {
        if (output_color_tex && output_width == width && output_height == height &&
            device_ == &device) {
            return;
        }
        release_textures();

        device_ = &device;

        tgfx::TextureDesc color_desc;
        color_desc.width = static_cast<uint32_t>(width);
        color_desc.height = static_cast<uint32_t>(height);
        color_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        color_desc.usage = tgfx::TextureUsage::Sampled |
                           tgfx::TextureUsage::ColorAttachment |
                           tgfx::TextureUsage::CopySrc |
                           tgfx::TextureUsage::CopyDst;
        output_color_tex = device.create_texture(color_desc);

        tgfx::TextureDesc depth_desc;
        depth_desc.width = static_cast<uint32_t>(width);
        depth_desc.height = static_cast<uint32_t>(height);
        depth_desc.format = tgfx::PixelFormat::D24_UNorm;
        depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment |
                           tgfx::TextureUsage::Sampled;
        output_depth_tex = device.create_texture(depth_desc);

        output_width = width;
        output_height = height;
    }

    void clear_all() {
        release_textures();
    }

    bool has_output() const {
        return static_cast<bool>(output_color_tex);
    }

private:
    void release_textures() {
        if (device_) {
            if (output_color_tex) {
                device_->destroy(output_color_tex);
                output_color_tex = {};
            }
            if (output_depth_tex) {
                device_->destroy(output_depth_tex);
                output_depth_tex = {};
            }
        } else {
            output_color_tex = {};
            output_depth_tex = {};
        }
        output_width = 0;
        output_height = 0;
        device_ = nullptr;
    }
};

} // namespace termin
