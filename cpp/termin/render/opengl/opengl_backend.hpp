#pragma once

#include <glad/glad.h>
#include <array>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <unordered_map>
#include <vector>

#include "tc_log.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/opengl/opengl_shader.hpp"
#include "termin/render/opengl/opengl_texture.hpp"
#include "termin/render/opengl/opengl_mesh.hpp"
#include "termin/render/opengl/opengl_framebuffer.hpp"

namespace termin {

/**
 * Initialize OpenGL function pointers via glad.
 * Must be called after OpenGL context is created.
 * Returns true on success.
 */
inline bool init_opengl() {
    return gladLoaderLoadGL() != 0;
}

/**
 * OpenGL 3.3+ graphics backend implementation.
 */
class OpenGLGraphicsBackend : public GraphicsBackend {
public:
    OpenGLGraphicsBackend() : initialized_(false) {}

    ~OpenGLGraphicsBackend() override {
        // Clean up UI buffers
        for (auto& [key, bufs] : ui_buffers_) {
            glDeleteVertexArrays(1, &bufs.first);
            glDeleteBuffers(1, &bufs.second);
        }
    }

    void ensure_ready() override {
        if (initialized_) return;

        // Initialize GLAD if not already done
        if (!glad_initialized_) {
            if (!gladLoaderLoadGL()) {
                throw std::runtime_error("Failed to initialize GLAD");
            }
            glad_initialized_ = true;
        }

        glEnable(GL_DEPTH_TEST);
        glEnable(GL_CULL_FACE);
        glCullFace(GL_BACK);
        glFrontFace(GL_CCW);

        initialized_ = true;
    }

    // --- Viewport ---

    void set_viewport(int x, int y, int width, int height) override {
        glViewport(x, y, width, height);
    }

    void enable_scissor(int x, int y, int width, int height) override {
        glEnable(GL_SCISSOR_TEST);
        glScissor(x, y, width, height);
    }

    void disable_scissor() override {
        glDisable(GL_SCISSOR_TEST);
    }

    // --- Clear ---

    void clear_color_depth(float r, float g, float b, float a) override {
        glClearColor(r, g, b, a);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    }

    void clear_color(float r, float g, float b, float a) override {
        glClearColor(r, g, b, a);
        glClear(GL_COLOR_BUFFER_BIT);
    }

    void clear_depth(float value) override {
        glClearDepth(static_cast<double>(value));
        glClear(GL_DEPTH_BUFFER_BIT);
    }

    // --- Color mask ---

    void set_color_mask(bool r, bool g, bool b, bool a) override {
        glColorMask(r ? GL_TRUE : GL_FALSE, g ? GL_TRUE : GL_FALSE,
                    b ? GL_TRUE : GL_FALSE, a ? GL_TRUE : GL_FALSE);
    }

    // --- Depth ---

    void set_depth_test(bool enabled) override {
        if (enabled) {
            glEnable(GL_DEPTH_TEST);
        } else {
            glDisable(GL_DEPTH_TEST);
        }
    }

    void set_depth_mask(bool enabled) override {
        glDepthMask(enabled ? GL_TRUE : GL_FALSE);
    }

    void set_depth_func(DepthFunc func) override {
        static const GLenum gl_funcs[] = {
            GL_LESS, GL_LEQUAL, GL_EQUAL, GL_GREATER,
            GL_GEQUAL, GL_NOTEQUAL, GL_ALWAYS, GL_NEVER
        };
        glDepthFunc(gl_funcs[static_cast<int>(func)]);
    }

    // --- Culling ---

    void set_cull_face(bool enabled) override {
        if (enabled) {
            glEnable(GL_CULL_FACE);
        } else {
            glDisable(GL_CULL_FACE);
        }
    }

    // --- Blending ---

    void set_blend(bool enabled) override {
        if (enabled) {
            glEnable(GL_BLEND);
        } else {
            glDisable(GL_BLEND);
        }
    }

    void set_blend_func(BlendFactor src, BlendFactor dst) override {
        static const GLenum gl_factors[] = {
            GL_ZERO, GL_ONE, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA
        };
        glBlendFunc(gl_factors[static_cast<int>(src)], gl_factors[static_cast<int>(dst)]);
    }

    // --- Polygon mode ---

    void set_polygon_mode(PolygonMode mode) override {
        GLenum gl_mode = (mode == PolygonMode::Line) ? GL_LINE : GL_FILL;
        glPolygonMode(GL_FRONT_AND_BACK, gl_mode);
    }

    // --- State management ---

    void reset_state() override {
        glEnable(GL_DEPTH_TEST);
        glDepthFunc(GL_LESS);
        glDepthMask(GL_TRUE);

        glDisable(GL_BLEND);

        glEnable(GL_CULL_FACE);
        glCullFace(GL_BACK);
        glFrontFace(GL_CCW);

        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL);

        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);

        glDisable(GL_STENCIL_TEST);
        glDisable(GL_SCISSOR_TEST);
    }

    void reset_gl_state() override {
        // Reset active texture unit to 0
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, 0);

        // Unbind shader program
        glUseProgram(0);

        // Unbind VAO
        glBindVertexArray(0);

        // Unbind buffers
        glBindBuffer(GL_ARRAY_BUFFER, 0);
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0);

        // Reset render state
        reset_state();

    }

    void apply_render_state(const RenderState& state) override {
        set_polygon_mode(state.polygon_mode);
        set_cull_face(state.cull);
        set_depth_test(state.depth_test);
        set_depth_mask(state.depth_write);
        set_blend(state.blend);
        if (state.blend) {
            set_blend_func(state.blend_src, state.blend_dst);
        }
    }

    // --- Resource creation ---

    ShaderHandlePtr create_shader(
        const char* vertex_source,
        const char* fragment_source,
        const char* geometry_source
    ) override {
        return std::make_unique<OpenGLShaderHandle>(vertex_source, fragment_source, geometry_source);
    }

    GPUMeshHandlePtr create_mesh(const tc_mesh* mesh) override {
        return std::make_unique<OpenGLTcMeshHandle>(mesh);
    }

    GPUTextureHandlePtr create_texture(
        const uint8_t* data,
        int width,
        int height,
        int channels,
        bool mipmap,
        bool clamp
    ) override {
        return std::make_unique<OpenGLTextureHandle>(data, width, height, channels, mipmap, clamp);
    }

    FramebufferHandlePtr create_framebuffer(int width, int height, int samples, const std::string& format = "") override {
        FBOFormat fmt = format.empty() ? FBOFormat::RGBA8 : parse_fbo_format(format);
        return std::make_unique<OpenGLFramebufferHandle>(width, height, samples, fmt);
    }

    FramebufferHandlePtr create_shadow_framebuffer(int width, int height) override {
        return std::make_unique<OpenGLShadowFramebufferHandle>(width, height);
    }

    /**
     * Create a handle that wraps an external FBO (e.g., window default FBO).
     * Does not allocate any resources - useful for window backends.
     */
    FramebufferHandlePtr create_external_framebuffer(uint32_t fbo_id, int width, int height) {
        return OpenGLFramebufferHandle::create_external(fbo_id, width, height);
    }

    // --- Framebuffer operations ---

    void bind_framebuffer(FramebufferHandle* fbo) override {
        if (fbo == nullptr) {
            glBindFramebuffer(GL_FRAMEBUFFER, 0);
        } else {
            glBindFramebuffer(GL_FRAMEBUFFER, fbo->get_fbo_id());
        }
    }

    void blit_framebuffer(
        FramebufferHandle* src,
        FramebufferHandle* dst,
        int src_x0, int src_y0, int src_x1, int src_y1,
        int dst_x0, int dst_y0, int dst_x1, int dst_y1,
        bool blit_color = true,
        bool blit_depth = false
    ) override {
        GLuint src_fbo = src ? src->get_fbo_id() : 0;
        GLuint dst_fbo = dst ? dst->get_fbo_id() : 0;

        glBindFramebuffer(GL_READ_FRAMEBUFFER, src_fbo);
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, dst_fbo);

        GLbitfield mask = 0;
        if (blit_color) mask |= GL_COLOR_BUFFER_BIT;
        if (blit_depth) mask |= GL_DEPTH_BUFFER_BIT;

        if (mask != 0) {
            glBlitFramebuffer(
                src_x0, src_y0, src_x1, src_y1,
                dst_x0, dst_y0, dst_x1, dst_y1,
                mask,
                GL_NEAREST
            );
        }

        glBindFramebuffer(GL_FRAMEBUFFER, 0);
    }

    // --- Read operations ---

    std::array<float, 4> read_pixel(FramebufferHandle* fbo, int x, int y) override {
        bind_framebuffer(fbo);

        uint8_t data[4];
        glReadPixels(x, y, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, data);

        return {
            data[0] / 255.0f,
            data[1] / 255.0f,
            data[2] / 255.0f,
            data[3] / 255.0f
        };
    }

    std::optional<float> read_depth_pixel(FramebufferHandle* fbo, int x, int y) override {
        if (fbo == nullptr) return std::nullopt;

        bind_framebuffer(fbo);

        float depth;
        glReadPixels(x, y, 1, 1, GL_DEPTH_COMPONENT, GL_FLOAT, &depth);

        return depth;
    }

    bool read_depth_buffer(FramebufferHandle* fbo, float* out_data) override {
        if (fbo == nullptr || out_data == nullptr) return false;

        int width = fbo->get_width();
        int height = fbo->get_height();
        if (width <= 0 || height <= 0) return false;

        bind_framebuffer(fbo);

        // Read into temporary buffer (OpenGL origin is bottom-left)
        std::vector<float> temp(width * height);
        glReadPixels(0, 0, width, height, GL_DEPTH_COMPONENT, GL_FLOAT, temp.data());

        // Flip vertically to top-left origin
        for (int y = 0; y < height; ++y) {
            int src_row = height - 1 - y;
            std::memcpy(
                out_data + y * width,
                temp.data() + src_row * width,
                width * sizeof(float)
            );
        }

        return true;
    }

    // --- UI drawing ---

    void draw_ui_vertices(int64_t context_key, const float* vertices, int vertex_count) override {
        auto& [vao, vbo] = get_ui_buffers(context_key);

        glBindVertexArray(vao);
        glBindBuffer(GL_ARRAY_BUFFER, vbo);
        glBufferData(GL_ARRAY_BUFFER, vertex_count * 2 * sizeof(float), vertices, GL_DYNAMIC_DRAW);

        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, nullptr);
        glDisableVertexAttribArray(1);

        glDrawArrays(GL_TRIANGLE_STRIP, 0, vertex_count);
        glBindVertexArray(0);
    }

    void draw_ui_textured_quad(int64_t context_key) override {
        static const float fs_verts[] = {
            -1, -1, 0, 0,
             1, -1, 1, 0,
            -1,  1, 0, 1,
             1,  1, 1, 1
        };
        draw_ui_textured_quad_impl(context_key, fs_verts, 4);
    }

    void draw_ui_textured_quad(int64_t context_key, const float* vertices, int vertex_count) {
        draw_ui_textured_quad_impl(context_key, vertices, vertex_count);
    }

    // --- Immediate mode rendering ---

    void draw_immediate_lines(
        const float* vertices,
        int vertex_count
    ) override {
        draw_immediate_impl(vertices, vertex_count, GL_LINES);
    }

    void draw_immediate_triangles(
        const float* vertices,
        int vertex_count
    ) override {
        draw_immediate_impl(vertices, vertex_count, GL_TRIANGLES);
    }

private:
    void draw_ui_textured_quad_impl(int64_t context_key, const float* vertices, int vertex_count) {
        auto& [vao, vbo] = get_ui_buffers(context_key);

        glBindVertexArray(vao);
        glBindBuffer(GL_ARRAY_BUFFER, vbo);
        glBufferData(GL_ARRAY_BUFFER, vertex_count * 4 * sizeof(float), vertices, GL_DYNAMIC_DRAW);

        constexpr GLsizei stride = 4 * sizeof(float);
        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, nullptr);
        glEnableVertexAttribArray(1);
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, reinterpret_cast<void*>(2 * sizeof(float)));

        glDrawArrays(GL_TRIANGLE_STRIP, 0, vertex_count);
        glBindVertexArray(0);
    }

    std::pair<GLuint, GLuint>& get_ui_buffers(int64_t context_key) {
        auto it = ui_buffers_.find(context_key);
        if (it != ui_buffers_.end()) {
            return it->second;
        }

        GLuint vao, vbo;
        glGenVertexArrays(1, &vao);
        glGenBuffers(1, &vbo);
        ui_buffers_[context_key] = {vao, vbo};
        return ui_buffers_[context_key];
    }

    void draw_immediate_impl(const float* vertices, int vertex_count, GLenum mode) {
        if (vertex_count <= 0 || !vertices) return;

        ensure_immediate_buffers();

        glBindVertexArray(immediate_vao_);
        glBindBuffer(GL_ARRAY_BUFFER, immediate_vbo_);
        glBufferData(GL_ARRAY_BUFFER, vertex_count * 7 * sizeof(float), vertices, GL_DYNAMIC_DRAW);

        glDrawArrays(mode, 0, vertex_count);

        glBindBuffer(GL_ARRAY_BUFFER, 0);
        glBindVertexArray(0);
    }

    void ensure_immediate_buffers() {
        if (immediate_vao_ != 0) return;

        glGenVertexArrays(1, &immediate_vao_);
        glGenBuffers(1, &immediate_vbo_);

        glBindVertexArray(immediate_vao_);
        glBindBuffer(GL_ARRAY_BUFFER, immediate_vbo_);

        constexpr GLsizei stride = 7 * sizeof(float);
        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, nullptr);
        glEnableVertexAttribArray(1);
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, stride, reinterpret_cast<void*>(3 * sizeof(float)));

        glBindBuffer(GL_ARRAY_BUFFER, 0);
        glBindVertexArray(0);
    }

    bool initialized_;
    std::unordered_map<int64_t, std::pair<GLuint, GLuint>> ui_buffers_;

    // Immediate mode rendering resources
    GLuint immediate_vao_ = 0;
    GLuint immediate_vbo_ = 0;

    // Static flag for GLAD initialization (shared across all backends)
    static inline bool glad_initialized_ = false;
};

} // namespace termin
