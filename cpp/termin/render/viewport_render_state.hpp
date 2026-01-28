// viewport_render_state.hpp - Per-viewport GPU resource state
#pragma once

#include "termin/render/handles.hpp"
#include "termin/render/graphics_backend.hpp"
#include <memory>

namespace termin {

// Holds GPU resources for a single viewport
// - output_fbo: Final rendered result (for blit to display)
// - Intermediate FBOs managed by pipeline's FBOPool
class ViewportRenderState {
public:
    // Output FBO for final render result
    FramebufferHandlePtr output_fbo;
    int output_width = 0;
    int output_height = 0;

    ViewportRenderState() = default;
    ~ViewportRenderState() = default;

    // Non-copyable
    ViewportRenderState(const ViewportRenderState&) = delete;
    ViewportRenderState& operator=(const ViewportRenderState&) = delete;

    // Movable
    ViewportRenderState(ViewportRenderState&&) = default;
    ViewportRenderState& operator=(ViewportRenderState&&) = default;

    // Ensure output FBO exists and has correct size
    // Returns pointer to output FBO (never null after call)
    FramebufferHandle* ensure_output_fbo(GraphicsBackend* graphics, int width, int height) {
        if (!output_fbo || output_width != width || output_height != height) {
            // Create or recreate FBO (samples=1, format="" for default RGBA)
            auto fbo_ptr = graphics->create_framebuffer(width, height, 1, "");
            output_fbo = std::move(fbo_ptr);
            output_width = width;
            output_height = height;
        }
        return output_fbo.get();
    }

    // Clear all GPU resources
    void clear_all() {
        output_fbo.reset();
        output_width = 0;
        output_height = 0;
    }

    // Check if has valid output FBO
    bool has_output_fbo() const {
        return output_fbo != nullptr && output_fbo->get_fbo_id() != 0;
    }
};

} // namespace termin
