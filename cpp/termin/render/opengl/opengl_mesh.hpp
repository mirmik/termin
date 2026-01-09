#pragma once

#include <glad/glad.h>
#include <vector>
#include <cstdint>
#include <cstring>

#include "termin/render/handles.hpp"

extern "C" {
#include "termin_core.h"
}

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

/**
 * Generic mesh handle for raw vertex data with custom layout.
 * Used for Mesh2 and other Python mesh types.
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

/**
 * Mesh handle that works directly with tc_mesh.
 * Uses tc_mesh's layout to set up vertex attributes automatically.
 * Reads draw_mode from tc_mesh (TC_DRAW_TRIANGLES or TC_DRAW_LINES).
 */
class OpenGLTcMeshHandle : public GPUMeshHandle {
public:
    OpenGLTcMeshHandle(const tc_mesh* mesh)
        : vao_(0), vbo_(0), ebo_(0), index_count_(0), draw_mode_(DrawMode::Triangles) {
        if (mesh) {
            draw_mode_ = (mesh->draw_mode == TC_DRAW_LINES) ? DrawMode::Lines : DrawMode::Triangles;
            upload(mesh);
        }
    }

    ~OpenGLTcMeshHandle() override {
        release();
    }

    void draw() override {
        if (vao_ == 0) return;
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
    void upload(const tc_mesh* mesh) {
        if (!mesh || !mesh->vertices || mesh->vertex_count == 0) return;

        glGenVertexArrays(1, &vao_);
        glGenBuffers(1, &vbo_);
        glGenBuffers(1, &ebo_);

        glBindVertexArray(vao_);

        // Upload raw vertex data from tc_mesh
        size_t vertex_bytes = mesh->vertex_count * mesh->layout.stride;
        glBindBuffer(GL_ARRAY_BUFFER, vbo_);
        glBufferData(GL_ARRAY_BUFFER, vertex_bytes, mesh->vertices, GL_STATIC_DRAW);

        // Upload indices
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_);
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, mesh->index_count * sizeof(uint32_t), mesh->indices, GL_STATIC_DRAW);
        index_count_ = static_cast<GLsizei>(mesh->index_count);

        // Set up vertex attributes based on tc_mesh layout
        // Standard attribute locations:
        // 0 = position, 1 = normal, 2 = uv, 3 = joints, 4 = weights, 5 = color
        const tc_vertex_layout& layout = mesh->layout;
        GLsizei stride = layout.stride;

        for (uint8_t i = 0; i < layout.attrib_count; i++) {
            const tc_vertex_attrib& attr = layout.attribs[i];

            // Map attribute name to location
            GLuint location = 255;
            if (strcmp(attr.name, "position") == 0) location = 0;
            else if (strcmp(attr.name, "normal") == 0) location = 1;
            else if (strcmp(attr.name, "uv") == 0) location = 2;
            else if (strcmp(attr.name, "joints") == 0) location = 3;
            else if (strcmp(attr.name, "weights") == 0) location = 4;
            else if (strcmp(attr.name, "color") == 0) location = 5;

            if (location == 255) continue;  // Unknown attribute, skip

            glEnableVertexAttribArray(location);

            // Determine GL type
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

            glVertexAttribPointer(location, attr.size, gl_type, GL_FALSE, stride, gl_offset(attr.offset));
        }

        glBindVertexArray(0);
    }

    GLuint vao_;
    GLuint vbo_;
    GLuint ebo_;
    GLsizei index_count_;
    DrawMode draw_mode_;
};

} // namespace termin
