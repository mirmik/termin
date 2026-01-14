#pragma once

#include <glad/glad.h>
#include <array>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

extern "C" {
#include "tc_gpu.h"
}

#include "tc_log.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/opengl/opengl_shader.hpp"
#include "termin/render/opengl/opengl_texture.hpp"
#include "termin/render/opengl/opengl_mesh.hpp"
#include "termin/render/opengl/opengl_framebuffer.hpp"
#include "termin/render/opengl/opengl_uniform_buffer.hpp"

namespace termin {

/**
 * Initialize OpenGL function pointers via glad.
 * Must be called after OpenGL context is created.
 * Returns true on success.
 */
inline bool init_opengl() {
    return gladLoaderLoadGL() != 0;
}

// ============================================================================
// tc_gpu_ops implementation functions
// ============================================================================

namespace gpu_ops_impl {

inline uint32_t texture_upload(
    const uint8_t* data,
    int width,
    int height,
    int channels,
    bool mipmap,
    bool clamp_wrap
) {
    GLuint texture;
    glGenTextures(1, &texture);
    glBindTexture(GL_TEXTURE_2D, texture);

    // Determine format
    GLenum format = GL_RGBA;
    GLenum internal_format = GL_RGBA8;
    switch (channels) {
        case 1: format = GL_RED; internal_format = GL_R8; break;
        case 2: format = GL_RG; internal_format = GL_RG8; break;
        case 3: format = GL_RGB; internal_format = GL_RGB8; break;
        case 4: format = GL_RGBA; internal_format = GL_RGBA8; break;
    }

    glTexImage2D(GL_TEXTURE_2D, 0, internal_format, width, height, 0, format, GL_UNSIGNED_BYTE, data);

    // Set wrapping mode
    GLenum wrap_mode = clamp_wrap ? GL_CLAMP_TO_EDGE : GL_REPEAT;
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrap_mode);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrap_mode);

    // Set filtering
    if (mipmap) {
        glGenerateMipmap(GL_TEXTURE_2D);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    } else {
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    }

    glBindTexture(GL_TEXTURE_2D, 0);
    return texture;
}

inline void texture_bind(uint32_t gpu_id, int unit) {
    glActiveTexture(GL_TEXTURE0 + unit);
    glBindTexture(GL_TEXTURE_2D, gpu_id);
}

inline void texture_delete(uint32_t gpu_id) {
    glDeleteTextures(1, &gpu_id);
}

inline uint32_t shader_compile(
    const char* vertex_source,
    const char* fragment_source,
    const char* geometry_source
) {
    auto compile_shader = [](GLenum type, const char* source) -> GLuint {
        GLuint shader = glCreateShader(type);
        glShaderSource(shader, 1, &source, nullptr);
        glCompileShader(shader);

        GLint success;
        glGetShaderiv(shader, GL_COMPILE_STATUS, &success);
        if (!success) {
            char info_log[512];
            glGetShaderInfoLog(shader, 512, nullptr, info_log);
            tc::Log::error("Shader compile error: %s", info_log);
            glDeleteShader(shader);
            return 0;
        }
        return shader;
    };

    GLuint vs = compile_shader(GL_VERTEX_SHADER, vertex_source);
    if (vs == 0) return 0;

    GLuint fs = compile_shader(GL_FRAGMENT_SHADER, fragment_source);
    if (fs == 0) {
        glDeleteShader(vs);
        return 0;
    }

    GLuint gs = 0;
    if (geometry_source && geometry_source[0] != '\0') {
        gs = compile_shader(GL_GEOMETRY_SHADER, geometry_source);
        if (gs == 0) {
            glDeleteShader(vs);
            glDeleteShader(fs);
            return 0;
        }
    }

    GLuint program = glCreateProgram();
    glAttachShader(program, vs);
    glAttachShader(program, fs);
    if (gs != 0) {
        glAttachShader(program, gs);
    }
    glLinkProgram(program);

    GLint success;
    glGetProgramiv(program, GL_LINK_STATUS, &success);
    if (!success) {
        char info_log[512];
        glGetProgramInfoLog(program, 512, nullptr, info_log);
        tc::Log::error("Shader link error: %s", info_log);
        glDeleteProgram(program);
        glDeleteShader(vs);
        glDeleteShader(fs);
        if (gs != 0) glDeleteShader(gs);
        return 0;
    }

    glDeleteShader(vs);
    glDeleteShader(fs);
    if (gs != 0) glDeleteShader(gs);

    return program;
}

inline void shader_use(uint32_t gpu_id) {
    glUseProgram(gpu_id);
}

inline void shader_delete(uint32_t gpu_id) {
    glDeleteProgram(gpu_id);
}

inline void shader_set_int(uint32_t gpu_id, const char* name, int value) {
    GLint loc = glGetUniformLocation(gpu_id, name);
    if (loc != -1) {
        glUniform1i(loc, value);
    }
}

inline void shader_set_float(uint32_t gpu_id, const char* name, float value) {
    GLint loc = glGetUniformLocation(gpu_id, name);
    if (loc != -1) {
        glUniform1f(loc, value);
    }
}

inline void shader_set_vec2(uint32_t gpu_id, const char* name, float x, float y) {
    GLint loc = glGetUniformLocation(gpu_id, name);
    if (loc != -1) {
        glUniform2f(loc, x, y);
    }
}

inline void shader_set_vec3(uint32_t gpu_id, const char* name, float x, float y, float z) {
    GLint loc = glGetUniformLocation(gpu_id, name);
    if (loc != -1) {
        glUniform3f(loc, x, y, z);
    }
}

inline void shader_set_vec4(uint32_t gpu_id, const char* name, float x, float y, float z, float w) {
    GLint loc = glGetUniformLocation(gpu_id, name);
    if (loc != -1) {
        glUniform4f(loc, x, y, z, w);
    }
}

inline void shader_set_mat4(uint32_t gpu_id, const char* name, const float* data, bool transpose) {
    GLint loc = glGetUniformLocation(gpu_id, name);
    if (loc != -1) {
        glUniformMatrix4fv(loc, 1, transpose ? GL_TRUE : GL_FALSE, data);
    }
}

inline void shader_set_mat4_array(uint32_t gpu_id, const char* name, const float* data, int count, bool transpose) {
    GLint loc = glGetUniformLocation(gpu_id, name);
    if (loc != -1) {
        glUniformMatrix4fv(loc, count, transpose ? GL_TRUE : GL_FALSE, data);
    }
}

inline void shader_set_block_binding(uint32_t gpu_id, const char* block_name, int binding_point) {
    GLuint block_index = glGetUniformBlockIndex(gpu_id, block_name);
    if (block_index != GL_INVALID_INDEX) {
        glUniformBlockBinding(gpu_id, block_index, binding_point);
    }
}

inline uint32_t mesh_upload(const tc_mesh* mesh) {
    if (!mesh || !mesh->vertices || mesh->vertex_count == 0) {
        return 0;
    }

    GLuint vao, vbo, ebo;
    glGenVertexArrays(1, &vao);
    glGenBuffers(1, &vbo);
    glGenBuffers(1, &ebo);

    glBindVertexArray(vao);

    // Upload vertex data
    glBindBuffer(GL_ARRAY_BUFFER, vbo);
    glBufferData(GL_ARRAY_BUFFER,
                 mesh->vertex_count * mesh->layout.stride,
                 mesh->vertices, GL_STATIC_DRAW);

    // Upload index data
    if (mesh->indices && mesh->index_count > 0) {
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo);
        glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                     mesh->index_count * sizeof(uint32_t),
                     mesh->indices, GL_STATIC_DRAW);
    }

    // Setup vertex attributes
    for (uint8_t i = 0; i < mesh->layout.attrib_count; ++i) {
        const tc_vertex_attrib& attr = mesh->layout.attribs[i];

        GLenum gl_type = GL_FLOAT;
        switch (attr.type) {
            case TC_ATTRIB_FLOAT32: gl_type = GL_FLOAT; break;
            case TC_ATTRIB_INT32: gl_type = GL_INT; break;
            case TC_ATTRIB_UINT32: gl_type = GL_UNSIGNED_INT; break;
            case TC_ATTRIB_INT16: gl_type = GL_SHORT; break;
            case TC_ATTRIB_UINT16: gl_type = GL_UNSIGNED_SHORT; break;
            case TC_ATTRIB_INT8: gl_type = GL_BYTE; break;
            case TC_ATTRIB_UINT8: gl_type = GL_UNSIGNED_BYTE; break;
        }

        glEnableVertexAttribArray(attr.location);
        glVertexAttribPointer(
            attr.location,
            attr.size,
            gl_type,
            GL_FALSE,
            mesh->layout.stride,
            reinterpret_cast<void*>(static_cast<size_t>(attr.offset))
        );
    }

    glBindVertexArray(0);
    glBindBuffer(GL_ARRAY_BUFFER, 0);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0);

    // Store VBO and EBO in mesh (for later deletion)
    // Note: This is a bit hacky - we store them in the mesh struct
    const_cast<tc_mesh*>(mesh)->gpu_vbo = vbo;
    const_cast<tc_mesh*>(mesh)->gpu_ebo = ebo;

    return vao;
}

inline void mesh_draw(uint32_t vao_id) {
    // This is a simplified draw - actual implementation needs mesh info
    // For now just bind VAO; actual draw happens elsewhere with index count
    glBindVertexArray(vao_id);
}

inline void mesh_delete(uint32_t vao_id) {
    // Note: we need VBO/EBO stored somewhere to delete them
    // For now just delete VAO
    glDeleteVertexArrays(1, &vao_id);
}

inline void register_gpu_ops() {
    static tc_gpu_ops ops = {
        // Texture operations
        texture_upload,
        texture_bind,
        texture_delete,
        // Shader operations
        nullptr,  // shader_preprocess - set from Python via tc_gpu_set_shader_preprocess
        shader_compile,
        shader_use,
        shader_delete,
        // Uniform setters
        shader_set_int,
        shader_set_float,
        shader_set_vec2,
        shader_set_vec3,
        shader_set_vec4,
        shader_set_mat4,
        shader_set_mat4_array,
        shader_set_block_binding,
        // Mesh operations
        mesh_upload,
        mesh_draw,
        mesh_delete,
        // User data
        nullptr
    };
    tc_gpu_set_ops(&ops);
}

} // namespace gpu_ops_impl

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

            // Register GPU ops for tc_gpu module
            gpu_ops_impl::register_gpu_ops();
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

    UniformBufferHandlePtr create_uniform_buffer(size_t size) override {
        return std::make_unique<OpenGLUniformBufferHandle>(size);
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

    bool read_color_buffer_float(FramebufferHandle* fbo, float* out_data) override {
        if (fbo == nullptr || out_data == nullptr) return false;

        int width = fbo->get_width();
        int height = fbo->get_height();
        if (width <= 0 || height <= 0) return false;

        GLuint read_fbo = fbo->get_fbo_id();
        GLuint temp_fbo = 0;
        GLuint temp_tex = 0;

        // If MSAA, resolve to temporary non-MSAA FBO first
        if (fbo->is_msaa()) {
            // Create temporary texture
            glGenTextures(1, &temp_tex);
            glBindTexture(GL_TEXTURE_2D, temp_tex);
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA16F, width, height, 0, GL_RGBA, GL_FLOAT, nullptr);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);

            // Create temporary FBO
            glGenFramebuffers(1, &temp_fbo);
            glBindFramebuffer(GL_FRAMEBUFFER, temp_fbo);
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, temp_tex, 0);

            // Blit from MSAA to non-MSAA (resolve)
            glBindFramebuffer(GL_READ_FRAMEBUFFER, fbo->get_fbo_id());
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER, temp_fbo);
            glBlitFramebuffer(0, 0, width, height, 0, 0, width, height, GL_COLOR_BUFFER_BIT, GL_NEAREST);

            read_fbo = temp_fbo;
        }

        // Bind the FBO to read from
        glBindFramebuffer(GL_FRAMEBUFFER, read_fbo);

        // Read into temporary buffer (OpenGL origin is bottom-left)
        // RGBA = 4 floats per pixel
        std::vector<float> temp(width * height * 4);
        glReadPixels(0, 0, width, height, GL_RGBA, GL_FLOAT, temp.data());

        // Flip vertically to top-left origin
        size_t row_size = width * 4 * sizeof(float);
        for (int y = 0; y < height; ++y) {
            int src_row = height - 1 - y;
            std::memcpy(
                out_data + y * width * 4,
                temp.data() + src_row * width * 4,
                row_size
            );
        }

        // Cleanup temporary resources
        if (temp_fbo != 0) {
            glDeleteFramebuffers(1, &temp_fbo);
        }
        if (temp_tex != 0) {
            glDeleteTextures(1, &temp_tex);
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

    bool check_gl_error(const char* location) override {
        GLenum err = glGetError();
        if (err == GL_NO_ERROR) {
            return false;
        }

        const char* name = "UNKNOWN";
        switch (err) {
            case GL_INVALID_ENUM: name = "GL_INVALID_ENUM"; break;
            case GL_INVALID_VALUE: name = "GL_INVALID_VALUE"; break;
            case GL_INVALID_OPERATION: name = "GL_INVALID_OPERATION"; break;
            case GL_OUT_OF_MEMORY: name = "GL_OUT_OF_MEMORY"; break;
            case GL_INVALID_FRAMEBUFFER_OPERATION: name = "GL_INVALID_FRAMEBUFFER_OPERATION"; break;
        }

        GLint fbo = 0, program = 0, vao = 0;
        glGetIntegerv(GL_FRAMEBUFFER_BINDING, &fbo);
        glGetIntegerv(GL_CURRENT_PROGRAM, &program);
        glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &vao);

        tc::Log::error("GL error %s (0x%x) at '%s' [FBO=%d, program=%d, VAO=%d]",
                       name, err, location, fbo, program, vao);
        return true;
    }

    // --- GPU Timer Queries ---

    void begin_gpu_query(const char* name) override {
        std::string key(name);

        // Get or create query object
        auto it = gpu_queries_.find(key);
        if (it == gpu_queries_.end()) {
            GLuint query;
            glGenQueries(1, &query);
            gpu_queries_[key] = {query, 0.0, false};
            it = gpu_queries_.find(key);
        }

        // Begin query
        glBeginQuery(GL_TIME_ELAPSED, it->second.query_id);
        current_gpu_query_ = key;
    }

    void end_gpu_query() override {
        if (current_gpu_query_.empty()) return;
        glEndQuery(GL_TIME_ELAPSED);
        gpu_queries_[current_gpu_query_].pending = true;
        current_gpu_query_.clear();
    }

    double get_gpu_query_ms(const char* name) override {
        auto it = gpu_queries_.find(name);
        if (it == gpu_queries_.end()) return -1.0;

        auto& q = it->second;

        // If pending, try to get result
        if (q.pending) {
            GLint available = 0;
            glGetQueryObjectiv(q.query_id, GL_QUERY_RESULT_AVAILABLE, &available);
            if (available) {
                GLuint64 elapsed_ns;
                glGetQueryObjectui64v(q.query_id, GL_QUERY_RESULT, &elapsed_ns);
                q.result_ms = elapsed_ns / 1000000.0;
                q.pending = false;
            }
        }

        return q.pending ? -1.0 : q.result_ms;
    }

    void sync_gpu_queries() override {
        for (auto& [name, q] : gpu_queries_) {
            if (q.pending) {
                GLuint64 elapsed_ns;
                glGetQueryObjectui64v(q.query_id, GL_QUERY_RESULT, &elapsed_ns);
                q.result_ms = elapsed_ns / 1000000.0;
                q.pending = false;
            }
        }
    }

private:
    void draw_ui_textured_quad_impl(int64_t context_key, const float* vertices, int vertex_count) {
        auto& [vao, vbo] = get_ui_buffers(context_key);

        glBindVertexArray(vao);

        GLenum err_after_bind = glGetError();
        if (err_after_bind != GL_NO_ERROR) {
            tc::Log::error("draw_ui_textured_quad: GL error after glBindVertexArray(vao=%u, context_key=%lld): 0x%x",
                           vao, (long long)context_key, err_after_bind);
        }

        glBindBuffer(GL_ARRAY_BUFFER, vbo);
        glBufferData(GL_ARRAY_BUFFER, vertex_count * 4 * sizeof(float), vertices, GL_DYNAMIC_DRAW);

        constexpr GLsizei stride = 4 * sizeof(float);
        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, nullptr);
        glEnableVertexAttribArray(1);
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, reinterpret_cast<void*>(2 * sizeof(float)));

        glDrawArrays(GL_TRIANGLE_STRIP, 0, vertex_count);

        GLenum err_after_draw = glGetError();
        if (err_after_draw != GL_NO_ERROR) {
            tc::Log::error("draw_ui_textured_quad: GL error after glDrawArrays(context_key=%lld, vao=%u): 0x%x",
                           (long long)context_key, vao, err_after_draw);
        }

        glBindVertexArray(0);
    }

    std::pair<GLuint, GLuint>& get_ui_buffers(int64_t context_key) {
        auto it = ui_buffers_.find(context_key);
        if (it != ui_buffers_.end()) {
            // Check if VAO is still valid (may be invalid after context change)
            if (glIsVertexArray(it->second.first)) {
                return it->second;
            }
            // VAO invalid - remove stale entry
            tc::Log::warn("get_ui_buffers: VAO %u invalid for context_key=%lld, recreating",
                          it->second.first, (long long)context_key);
            ui_buffers_.erase(it);
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
        // Check if VAO exists and is still valid (may be invalid after context change)
        if (immediate_vao_ != 0) {
            if (glIsVertexArray(immediate_vao_)) {
                return;
            }
            tc::Log::warn("ensure_immediate_buffers: VAO %u invalid, recreating", immediate_vao_);
        }

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

    // GPU timer query data
    struct GPUQueryData {
        GLuint query_id;
        double result_ms;
        bool pending;
    };
    std::unordered_map<std::string, GPUQueryData> gpu_queries_;
    std::string current_gpu_query_;

    // Static flag for GLAD initialization (shared across all backends)
    static inline bool glad_initialized_ = false;
};

} // namespace termin
