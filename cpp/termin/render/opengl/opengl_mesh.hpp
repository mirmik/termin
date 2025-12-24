#pragma once

#include <glad/glad.h>
#include <vector>
#include <cstdint>

#include "termin/render/handles.hpp"
#include "termin/mesh/mesh3.hpp"

namespace termin {

// Helper to convert byte offset to void* for glVertexAttribPointer
// Avoids MSVC warning C4312 about int to void* conversion on 64-bit
inline const void* gl_offset(size_t offset) {
    return reinterpret_cast<const void*>(offset);
}

/**
 * Draw mode for mesh rendering.
 */
enum class DrawMode {
    Triangles,
    Lines
};

class OpenGLMeshHandle : public GPUMeshHandle {
public:
    OpenGLMeshHandle(const Mesh3& mesh, DrawMode mode = DrawMode::Triangles)
        : vao_(0), vbo_(0), ebo_(0), index_count_(0), draw_mode_(mode) {
        upload(mesh);
    }

    ~OpenGLMeshHandle() override {
        release();
    }

    void draw() override {
        glBindVertexArray(vao_);

        GLenum gl_mode = (draw_mode_ == DrawMode::Lines) ? GL_LINES : GL_TRIANGLES;
        glDrawElements(gl_mode, index_count_, GL_UNSIGNED_INT, nullptr);

        glBindVertexArray(0);
    }

    void release() override {
        if (vao_ != 0) {
            glDeleteVertexArrays(1, &vao_);
            vao_ = 0;
        }
        if (vbo_ != 0) {
            glDeleteBuffers(1, &vbo_);
            vbo_ = 0;
        }
        if (ebo_ != 0) {
            glDeleteBuffers(1, &ebo_);
            ebo_ = 0;
        }
    }

private:
    void upload(const Mesh3& mesh) {
        // Build interleaved buffer: pos(3) + normal(3) + uv(2)
        std::vector<float> buffer = mesh.build_interleaved_buffer();

        glGenVertexArrays(1, &vao_);
        glGenBuffers(1, &vbo_);
        glGenBuffers(1, &ebo_);

        glBindVertexArray(vao_);

        // Upload vertex data
        glBindBuffer(GL_ARRAY_BUFFER, vbo_);
        glBufferData(GL_ARRAY_BUFFER, buffer.size() * sizeof(float), buffer.data(), GL_STATIC_DRAW);

        // Upload indices
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_);
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, mesh.indices.size() * sizeof(uint32_t), mesh.indices.data(), GL_STATIC_DRAW);
        index_count_ = static_cast<GLsizei>(mesh.indices.size());

        // Vertex layout: pos(3) + normal(3) + uv(2) = 8 floats = 32 bytes stride
        constexpr GLsizei stride = 8 * sizeof(float);

        // Position: location 0
        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, gl_offset(0));

        // Normal: location 1
        glEnableVertexAttribArray(1);
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, gl_offset(3 * sizeof(float)));

        // UV: location 2
        glEnableVertexAttribArray(2);
        glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, stride, gl_offset(6 * sizeof(float)));

        glBindVertexArray(0);
    }

    GLuint vao_;
    GLuint vbo_;
    GLuint ebo_;
    GLsizei index_count_;
    DrawMode draw_mode_;
};

/**
 * Generic mesh handle for raw vertex data with custom layout.
 * Used for Mesh2, SkinnedMesh3, and other Python mesh types.
 */
class OpenGLRawMeshHandle : public GPUMeshHandle {
public:
    /**
     * Create mesh from raw data.
     * @param vertex_data Interleaved vertex data
     * @param vertex_bytes Number of bytes in vertex_data
     * @param indices Index data
     * @param index_count Number of indices
     * @param stride Vertex stride in bytes
     * @param position_offset Offset of position attribute in bytes
     * @param position_size Number of floats in position (2 or 3)
     * @param has_normal Whether normal attribute exists
     * @param normal_offset Offset of normal attribute in bytes
     * @param has_uv Whether UV attribute exists
     * @param uv_offset Offset of UV attribute in bytes
     * @param has_joints Whether joints attribute exists (for skinning)
     * @param joints_offset Offset of joints attribute in bytes
     * @param has_weights Whether weights attribute exists (for skinning)
     * @param weights_offset Offset of weights attribute in bytes
     * @param mode Draw mode (triangles or lines)
     */
    OpenGLRawMeshHandle(
        const float* vertex_data, size_t vertex_bytes,
        const uint32_t* indices, size_t index_count,
        int stride,
        int position_offset, int position_size,
        bool has_normal, int normal_offset,
        bool has_uv, int uv_offset,
        bool has_joints = false, int joints_offset = 0,
        bool has_weights = false, int weights_offset = 0,
        DrawMode mode = DrawMode::Triangles
    ) : vao_(0), vbo_(0), ebo_(0), index_count_(static_cast<GLsizei>(index_count)), draw_mode_(mode) {
        glGenVertexArrays(1, &vao_);
        glGenBuffers(1, &vbo_);
        glGenBuffers(1, &ebo_);

        glBindVertexArray(vao_);

        // Upload vertex data
        glBindBuffer(GL_ARRAY_BUFFER, vbo_);
        glBufferData(GL_ARRAY_BUFFER, vertex_bytes, vertex_data, GL_STATIC_DRAW);

        // Upload indices
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_);
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, index_count * sizeof(uint32_t), indices, GL_STATIC_DRAW);

        // Position: location 0
        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, position_size, GL_FLOAT, GL_FALSE, stride, gl_offset(position_offset));

        // Normal: location 1 (optional)
        if (has_normal) {
            glEnableVertexAttribArray(1);
            glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, gl_offset(normal_offset));
        }

        // UV: location 2 (optional)
        if (has_uv) {
            glEnableVertexAttribArray(2);
            glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, stride, gl_offset(uv_offset));
        }

        // Joints: location 3 (optional, for skinning)
        if (has_joints) {
            glEnableVertexAttribArray(3);
            glVertexAttribPointer(3, 4, GL_FLOAT, GL_FALSE, stride, gl_offset(joints_offset));
        }

        // Weights: location 4 (optional, for skinning)
        if (has_weights) {
            glEnableVertexAttribArray(4);
            glVertexAttribPointer(4, 4, GL_FLOAT, GL_FALSE, stride, gl_offset(weights_offset));
        }

        glBindVertexArray(0);
    }

    ~OpenGLRawMeshHandle() override {
        release();
    }

    void draw() override {
        glBindVertexArray(vao_);
        GLenum gl_mode = (draw_mode_ == DrawMode::Lines) ? GL_LINES : GL_TRIANGLES;
        glDrawElements(gl_mode, index_count_, GL_UNSIGNED_INT, nullptr);
        glBindVertexArray(0);
    }

    void release() override {
        if (vao_ != 0) { glDeleteVertexArrays(1, &vao_); vao_ = 0; }
        if (vbo_ != 0) { glDeleteBuffers(1, &vbo_); vbo_ = 0; }
        if (ebo_ != 0) { glDeleteBuffers(1, &ebo_); ebo_ = 0; }
    }

private:
    GLuint vao_;
    GLuint vbo_;
    GLuint ebo_;
    GLsizei index_count_;
    DrawMode draw_mode_;
};

} // namespace termin
