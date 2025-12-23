#pragma once

#include <array>
#include <memory>
#include <optional>
#include <cstdint>

#include "termin/render/render_state.hpp"
#include "termin/render/handles.hpp"

namespace termin {

// Forward declarations
class Mesh3;

/**
 * Abstract graphics backend interface.
 *
 * Provides GPU resource management and render state control.
 * Concrete implementations: OpenGLGraphicsBackend.
 */
class GraphicsBackend {
public:
    virtual ~GraphicsBackend() = default;

    // --- Initialization ---
    virtual void ensure_ready() = 0;

    // --- Viewport ---
    virtual void set_viewport(int x, int y, int width, int height) = 0;
    virtual void enable_scissor(int x, int y, int width, int height) = 0;
    virtual void disable_scissor() = 0;

    // --- Clear ---
    virtual void clear_color_depth(float r, float g, float b, float a) = 0;
    virtual void clear_color(float r, float g, float b, float a) = 0;
    virtual void clear_depth(float value = 1.0f) = 0;

    // --- Color mask ---
    virtual void set_color_mask(bool r, bool g, bool b, bool a) = 0;

    // --- Depth ---
    virtual void set_depth_test(bool enabled) = 0;
    virtual void set_depth_mask(bool enabled) = 0;
    virtual void set_depth_func(DepthFunc func) = 0;

    // --- Culling ---
    virtual void set_cull_face(bool enabled) = 0;

    // --- Blending ---
    virtual void set_blend(bool enabled) = 0;
    virtual void set_blend_func(BlendFactor src, BlendFactor dst) = 0;

    // --- Polygon mode ---
    virtual void set_polygon_mode(PolygonMode mode) = 0;

    // --- State management ---
    virtual void reset_state() = 0;
    virtual void apply_render_state(const RenderState& state) = 0;

    // --- Resource creation ---
    virtual ShaderHandlePtr create_shader(
        const char* vertex_source,
        const char* fragment_source,
        const char* geometry_source = nullptr
    ) = 0;

    virtual MeshHandlePtr create_mesh(const Mesh3& mesh) = 0;

    virtual TextureHandlePtr create_texture(
        const uint8_t* data,
        int width,
        int height,
        int channels = 4,
        bool mipmap = true,
        bool clamp = false
    ) = 0;

    virtual FramebufferHandlePtr create_framebuffer(int width, int height, int samples = 1) = 0;
    virtual FramebufferHandlePtr create_shadow_framebuffer(int width, int height) = 0;

    // --- Framebuffer operations ---
    virtual void bind_framebuffer(FramebufferHandle* fbo) = 0;
    virtual void blit_framebuffer(
        FramebufferHandle* src,
        FramebufferHandle* dst,
        int src_x0, int src_y0, int src_x1, int src_y1,
        int dst_x0, int dst_y0, int dst_x1, int dst_y1
    ) = 0;

    // --- Read operations ---
    virtual std::array<float, 4> read_pixel(FramebufferHandle* fbo, int x, int y) = 0;
    virtual std::optional<float> read_depth_pixel(FramebufferHandle* fbo, int x, int y) = 0;

    // --- UI drawing (for immediate mode) ---
    virtual void draw_ui_vertices(int context_key, const float* vertices, int vertex_count) = 0;
    virtual void draw_ui_textured_quad(int context_key) = 0;
};

using GraphicsBackendPtr = std::unique_ptr<GraphicsBackend>;

} // namespace termin
