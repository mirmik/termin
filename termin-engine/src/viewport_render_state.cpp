#include <termin/render/viewport_render_state.hpp>

namespace termin {

ViewportRenderState::~ViewportRenderState() {
    release_textures();
}

ViewportRenderState::ViewportRenderState(ViewportRenderState&& other) noexcept
    : output_color_tex(other.output_color_tex),
      output_depth_tex(other.output_depth_tex),
      output_width(other.output_width),
      output_height(other.output_height),
      output_color_format(other.output_color_format),
      output_depth_format(other.output_depth_format),
      device_(other.device_) {
    other.output_color_tex = {};
    other.output_depth_tex = {};
    other.output_width = 0;
    other.output_height = 0;
    other.output_color_format = tgfx::PixelFormat::RGBA8_UNorm;
    other.output_depth_format = tgfx::PixelFormat::D24_UNorm;
    other.device_ = nullptr;
}

ViewportRenderState& ViewportRenderState::operator=(ViewportRenderState&& other) noexcept {
    if (this == &other) {
        return *this;
    }

    release_textures();
    output_color_tex = other.output_color_tex;
    output_depth_tex = other.output_depth_tex;
    output_width = other.output_width;
    output_height = other.output_height;
    output_color_format = other.output_color_format;
    output_depth_format = other.output_depth_format;
    device_ = other.device_;

    other.output_color_tex = {};
    other.output_depth_tex = {};
    other.output_width = 0;
    other.output_height = 0;
    other.output_color_format = tgfx::PixelFormat::RGBA8_UNorm;
    other.output_depth_format = tgfx::PixelFormat::D24_UNorm;
    other.device_ = nullptr;
    return *this;
}

void ViewportRenderState::ensure_output_textures(
    tgfx::IRenderDevice& device,
    int width,
    int height
) {
    ensure_output_textures(
        device,
        width,
        height,
        tgfx::PixelFormat::RGBA8_UNorm,
        tgfx::PixelFormat::D24_UNorm);
}

void ViewportRenderState::ensure_output_textures(
    tgfx::IRenderDevice& device,
    int width,
    int height,
    tgfx::PixelFormat color_format,
    tgfx::PixelFormat depth_format
) {
    if (output_color_tex && output_width == width && output_height == height
        && output_color_format == color_format
        && output_depth_format == depth_format
        && device_ == &device) {
        return;
    }
    release_textures();

    device_ = &device;
    output_color_format = color_format;
    output_depth_format = depth_format;

    tgfx::TextureDesc color_desc;
    color_desc.width = static_cast<uint32_t>(width);
    color_desc.height = static_cast<uint32_t>(height);
    color_desc.format = color_format;
    color_desc.usage = tgfx::TextureUsage::Sampled |
                       tgfx::TextureUsage::ColorAttachment |
                       tgfx::TextureUsage::CopySrc |
                       tgfx::TextureUsage::CopyDst;
    output_color_tex = device.create_texture(color_desc);

    tgfx::TextureDesc depth_desc;
    depth_desc.width = static_cast<uint32_t>(width);
    depth_desc.height = static_cast<uint32_t>(height);
    depth_desc.format = depth_format;
    depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment |
                       tgfx::TextureUsage::Sampled |
                       tgfx::TextureUsage::CopySrc |
                       tgfx::TextureUsage::CopyDst;
    output_depth_tex = device.create_texture(depth_desc);

    output_width = width;
    output_height = height;
}

void ViewportRenderState::clear_all() {
    release_textures();
}

void ViewportRenderState::release_textures() {
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
    output_color_format = tgfx::PixelFormat::RGBA8_UNorm;
    output_depth_format = tgfx::PixelFormat::D24_UNorm;
    device_ = nullptr;
}

} // namespace termin
