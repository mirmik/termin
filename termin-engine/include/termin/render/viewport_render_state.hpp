// viewport_render_state.hpp - Runtime GPU output state helper
#pragma once

#include <tgfx2/handles.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/i_render_device.hpp>
#include <termin/engine/termin_engine_api.hpp>

namespace termin {

// Holds runtime-owned GPU output resources:
// - output_color_tex / output_depth_tex: native tgfx2 textures used
//   as final render output where textures are not owned by persistent
//   scene configuration. They are owned by this state and destroyed on
//   resize / destruction.
// - Intermediate FBOs are managed separately by the pipeline's FBOPool.
class TERMIN_ENGINE_API ViewportRenderState {
public:
    tgfx::TextureHandle output_color_tex;
    tgfx::TextureHandle output_depth_tex;
    int output_width = 0;
    int output_height = 0;
    tgfx::PixelFormat output_color_format = tgfx::PixelFormat::RGBA8_UNorm;
    tgfx::PixelFormat output_depth_format = tgfx::PixelFormat::D24_UNorm;

private:
    tgfx::IRenderDevice* device_ = nullptr;

public:
    ViewportRenderState() = default;

    ~ViewportRenderState();

    // Non-copyable
    ViewportRenderState(const ViewportRenderState&) = delete;
    ViewportRenderState& operator=(const ViewportRenderState&) = delete;

    // Movable — transfer ownership and null the source so the moved-from
    // destructor doesn't double-free.
    ViewportRenderState(ViewportRenderState&& other) noexcept;

    ViewportRenderState& operator=(ViewportRenderState&& other) noexcept;

    // Ensure output color+depth textures exist at the given size.
    // Reallocates on size change via the provided tgfx2 device.
    void ensure_output_textures(tgfx::IRenderDevice& device, int width, int height);

    void ensure_output_textures(
        tgfx::IRenderDevice& device,
        int width,
        int height,
        tgfx::PixelFormat color_format,
        tgfx::PixelFormat depth_format
    );

    void clear_all();

    bool has_output() const {
        return static_cast<bool>(output_color_tex);
    }

private:
    void release_textures();
};

} // namespace termin
