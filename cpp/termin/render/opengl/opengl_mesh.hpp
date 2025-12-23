#pragma once

#include <glad/glad.h>
#include <vector>
#include <cstdint>

#include "termin/render/handles.hpp"
#include "termin/mesh/mesh3.hpp"

namespace termin {

/**
 * Draw mode for mesh rendering.
 */
enum class DrawMode {
    Triangles,
    Lines
};

class OpenGLMeshHandle : public MeshHandle {
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
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, reinterpret_cast<void*>(0));

        // Normal: location 1
        glEnableVertexAttribArray(1);
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, reinterpret_cast<void*>(3 * sizeof(float)));

        // UV: location 2
        glEnableVertexAttribArray(2);
        glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, stride, reinterpret_cast<void*>(6 * sizeof(float)));

        glBindVertexArray(0);
    }

    GLuint vao_;
    GLuint vbo_;
    GLuint ebo_;
    GLsizei index_count_;
    DrawMode draw_mode_;
};

} // namespace termin
