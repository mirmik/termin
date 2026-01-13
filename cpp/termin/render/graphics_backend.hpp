#pragma once

#include <array>
#include <memory>
#include <optional>
#include <cstdint>

#include "termin/render/render_state.hpp"
#include "termin/render/handles.hpp"
#include "termin/render/types.hpp"

extern "C" {
#include "termin_core.h"
}

namespace termin {

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

    // Convenience overloads with Color4
    void clear_color_depth(const Color4& c) { clear_color_depth(c.r, c.g, c.b, c.a); }
    void clear_color(const Color4& c) { clear_color(c.r, c.g, c.b, c.a); }

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

    // Reset full GL state (textures, shader, etc.) for PyOpenGL compatibility
    virtual void reset_gl_state() = 0;

    // --- Resource creation ---
    virtual ShaderHandlePtr create_shader(
        const char* vertex_source,
        const char* fragment_source,
        const char* geometry_source = nullptr
    ) = 0;

    virtual GPUMeshHandlePtr create_mesh(const tc_mesh* mesh) = 0;

    virtual GPUTextureHandlePtr create_texture(
        const uint8_t* data,
        int width,
        int height,
        int channels = 4,
        bool mipmap = true,
        bool clamp = false
    ) = 0;

    // Convenience overload with Size2i
    GPUTextureHandlePtr create_texture(
        const uint8_t* data,
        Size2i size,
        int channels = 4,
        bool mipmap = true,
        bool clamp = false
    ) {
        return create_texture(data, size.width, size.height, channels, mipmap, clamp);
    }

    virtual FramebufferHandlePtr create_framebuffer(int width, int height, int samples = 1, const std::string& format = "") = 0;
    virtual FramebufferHandlePtr create_shadow_framebuffer(int width, int height) = 0;
    virtual UniformBufferHandlePtr create_uniform_buffer(size_t size) = 0;

    // Convenience overloads with Size2i
    FramebufferHandlePtr create_framebuffer(Size2i size, int samples = 1, const std::string& format = "") {
        return create_framebuffer(size.width, size.height, samples, format);
    }
    FramebufferHandlePtr create_shadow_framebuffer(Size2i size) {
        return create_shadow_framebuffer(size.width, size.height);
    }

    // --- Framebuffer operations ---
    virtual void bind_framebuffer(FramebufferHandle* fbo) = 0;
    virtual void blit_framebuffer(
        FramebufferHandle* src,
        FramebufferHandle* dst,
        int src_x0, int src_y0, int src_x1, int src_y1,
        int dst_x0, int dst_y0, int dst_x1, int dst_y1,
        bool blit_color = true,
        bool blit_depth = false
    ) = 0;

    // Convenience overload with Rect2i
    void blit_framebuffer(FramebufferHandle* src, FramebufferHandle* dst,
                          const Rect2i& src_rect, const Rect2i& dst_rect,
                          bool blit_color = true, bool blit_depth = false) {
        blit_framebuffer(src, dst,
            src_rect.x0, src_rect.y0, src_rect.x1, src_rect.y1,
            dst_rect.x0, dst_rect.y0, dst_rect.x1, dst_rect.y1,
            blit_color, blit_depth);
    }

    // --- Read operations ---
    virtual std::array<float, 4> read_pixel(FramebufferHandle* fbo, int x, int y) = 0;
    virtual std::optional<float> read_depth_pixel(FramebufferHandle* fbo, int x, int y) = 0;

    /**
     * Read entire depth buffer into external buffer.
     * Buffer must be pre-allocated with size width * height.
     * Output is flipped vertically (top-left origin).
     * Returns true on success.
     */
    virtual bool read_depth_buffer(FramebufferHandle* fbo, float* out_data) = 0;

    /**
     * Read entire color buffer as RGBA floats into external buffer.
     * Buffer must be pre-allocated with size width * height * 4.
     * Output is flipped vertically (top-left origin).
     * Returns true on success.
     */
    virtual bool read_color_buffer_float(FramebufferHandle* fbo, float* out_data) = 0;

    // --- UI drawing (for immediate mode) ---
    virtual void draw_ui_vertices(int64_t context_key, const float* vertices, int vertex_count) = 0;
    virtual void draw_ui_textured_quad(int64_t context_key) = 0;

    // --- Immediate mode rendering ---
    // Vertices: x, y, z, r, g, b, a (7 floats per vertex)
    // Shader must have u_view and u_projection uniforms
    virtual void draw_immediate_lines(
        const float* vertices,
        int vertex_count
    ) = 0;

    virtual void draw_immediate_triangles(
        const float* vertices,
        int vertex_count
    ) = 0;

    // --- Debug ---
    // Check for GL errors and log them. Returns true if error was found.
    virtual bool check_gl_error(const char* location) = 0;

    // --- GPU Timer Queries ---
    // Begin a GPU timer query section (non-blocking)
    virtual void begin_gpu_query(const char* name) = 0;
    // End current GPU timer query section
    virtual void end_gpu_query() = 0;
    // Get result of GPU query in milliseconds (may return -1 if not ready yet)
    // Returns -1.0 if query doesn't exist or isn't ready
    virtual double get_gpu_query_ms(const char* name) = 0;
    // Synchronize and get all query results (blocking)
    virtual void sync_gpu_queries() = 0;
};

using GraphicsBackendPtr = std::unique_ptr<GraphicsBackend>;

} // namespace termin
