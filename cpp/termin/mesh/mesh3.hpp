#pragma once

#include <vector>
#include <string>
#include <cmath>
#include <cstring>

// Include C API from core_c
extern "C" {
#include "termin_core.h"
}

namespace termin {

// Triangle mesh with positions, normals, and UVs.
// This is a handle to tc_mesh in the global registry.
class Mesh3 {
public:
    tc_mesh* _mesh = nullptr;

    Mesh3() = default;

    // Construct from separate arrays (computes UUID from data hash)
    // name is REQUIRED for debugging
    Mesh3(const char* name,
          const float* vertices, size_t vertex_count,
          const uint32_t* indices, size_t index_count,
          const float* normals = nullptr,
          const float* uvs = nullptr)
    {
        init_from_data(name, vertices, vertex_count, indices, index_count, normals, uvs);
    }

    // Construct from std::vectors (convenience)
    Mesh3(const char* name, std::vector<float> verts, std::vector<uint32_t> tris)
    {
        init_from_data(name, verts.data(), verts.size() / 3,
                       tris.data(), tris.size(),
                       nullptr, nullptr);
    }

    // Construct from existing UUID (for cached primitives)
    static Mesh3 from_uuid(const char* uuid) {
        Mesh3 m;
        m._mesh = tc_mesh_get(uuid);
        if (m._mesh) {
            tc_mesh_add_ref(m._mesh);
        }
        return m;
    }

    // Construct with explicit UUID (for primitives with precomputed UUID)
    Mesh3(const char* uuid, const char* name,
          const float* vertices, size_t vertex_count,
          const uint32_t* indices, size_t index_count,
          const float* normals = nullptr,
          const float* uvs = nullptr)
    {
        init_from_data_with_uuid(uuid, name, vertices, vertex_count, indices, index_count, normals, uvs);
    }

    // Copy constructor - increments ref count
    Mesh3(const Mesh3& other) : _mesh(other._mesh) {
        if (_mesh) {
            tc_mesh_add_ref(_mesh);
        }
    }

    // Move constructor
    Mesh3(Mesh3&& other) noexcept : _mesh(other._mesh) {
        other._mesh = nullptr;
    }

    // Copy assignment
    Mesh3& operator=(const Mesh3& other) {
        if (this != &other) {
            if (_mesh) tc_mesh_release(_mesh);
            _mesh = other._mesh;
            if (_mesh) tc_mesh_add_ref(_mesh);
        }
        return *this;
    }

    // Move assignment
    Mesh3& operator=(Mesh3&& other) noexcept {
        if (this != &other) {
            if (_mesh) tc_mesh_release(_mesh);
            _mesh = other._mesh;
            other._mesh = nullptr;
        }
        return *this;
    }

    // Destructor - decrements ref count
    ~Mesh3() {
        if (_mesh) {
            tc_mesh_release(_mesh);
            _mesh = nullptr;
        }
    }

    // Check if valid
    bool is_valid() const { return _mesh != nullptr; }

    // Get UUID
    const char* uuid() const {
        return _mesh ? _mesh->uuid : "";
    }

    // Get name (for debugging)
    const char* name() const {
        return _mesh && _mesh->name ? _mesh->name : "";
    }

    // Set name (interned for efficiency)
    void set_name(const char* n) {
        if (_mesh && n) {
            _mesh->name = tc_intern_string(n);
        }
    }

    // Get version (for GPU sync)
    uint32_t version() const {
        return _mesh ? _mesh->version : 0;
    }

    // Number of vertices
    size_t get_vertex_count() const {
        return _mesh ? _mesh->vertex_count : 0;
    }

    // Number of triangles
    size_t get_face_count() const {
        return _mesh ? _mesh->index_count / 3 : 0;
    }

    // Check if has UVs
    bool has_uvs() const {
        if (!_mesh) return false;
        return tc_vertex_layout_find(&_mesh->layout, "uv") != nullptr;
    }

    // Check if has vertex normals
    bool has_vertex_normals() const {
        if (!_mesh) return false;
        return tc_vertex_layout_find(&_mesh->layout, "normal") != nullptr;
    }

    // Get raw vertex data pointer
    const void* raw_vertices() const {
        return _mesh ? _mesh->vertices : nullptr;
    }

    // Get raw index data pointer
    const uint32_t* raw_indices() const {
        return _mesh ? _mesh->indices : nullptr;
    }

    // Get vertex layout
    const tc_vertex_layout* layout() const {
        return _mesh ? &_mesh->layout : nullptr;
    }

    // Get stride
    uint16_t stride() const {
        return _mesh ? _mesh->layout.stride : 0;
    }

    // Get vertices as flat vector (Nx3 floats)
    std::vector<float> get_vertices() const {
        std::vector<float> result;
        if (!_mesh) return result;

        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&_mesh->layout, "position");
        if (!pos_attr || pos_attr->size != 3) return result;

        result.resize(_mesh->vertex_count * 3);
        const uint8_t* data = (const uint8_t*)_mesh->vertices;

        for (size_t i = 0; i < _mesh->vertex_count; i++) {
            const float* pos = (const float*)(data + i * _mesh->layout.stride + pos_attr->offset);
            result[i * 3] = pos[0];
            result[i * 3 + 1] = pos[1];
            result[i * 3 + 2] = pos[2];
        }
        return result;
    }

    // Get indices as flat vector
    std::vector<uint32_t> get_indices() const {
        if (!_mesh || !_mesh->indices) return {};
        return std::vector<uint32_t>(_mesh->indices, _mesh->indices + _mesh->index_count);
    }

    // Get normals as flat vector (Nx3 floats)
    std::vector<float> get_normals() const {
        std::vector<float> result;
        if (!_mesh) return result;

        const tc_vertex_attrib* norm_attr = tc_vertex_layout_find(&_mesh->layout, "normal");
        if (!norm_attr || norm_attr->size != 3) return result;

        result.resize(_mesh->vertex_count * 3);
        const uint8_t* data = (const uint8_t*)_mesh->vertices;

        for (size_t i = 0; i < _mesh->vertex_count; i++) {
            const float* norm = (const float*)(data + i * _mesh->layout.stride + norm_attr->offset);
            result[i * 3] = norm[0];
            result[i * 3 + 1] = norm[1];
            result[i * 3 + 2] = norm[2];
        }
        return result;
    }

    // Get UVs as flat vector (Nx2 floats)
    std::vector<float> get_uvs() const {
        std::vector<float> result;
        if (!_mesh) return result;

        const tc_vertex_attrib* uv_attr = tc_vertex_layout_find(&_mesh->layout, "uv");
        if (!uv_attr || uv_attr->size != 2) return result;

        result.resize(_mesh->vertex_count * 2);
        const uint8_t* data = (const uint8_t*)_mesh->vertices;

        for (size_t i = 0; i < _mesh->vertex_count; i++) {
            const float* uv = (const float*)(data + i * _mesh->layout.stride + uv_attr->offset);
            result[i * 2] = uv[0];
            result[i * 2 + 1] = uv[1];
        }
        return result;
    }

    // Get vertex at index
    void get_vertex(size_t idx, float& x, float& y, float& z) const {
        if (!_mesh || idx >= _mesh->vertex_count) {
            x = y = z = 0.0f;
            return;
        }
        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&_mesh->layout, "position");
        if (!pos_attr) {
            x = y = z = 0.0f;
            return;
        }
        const uint8_t* data = (const uint8_t*)_mesh->vertices;
        const float* pos = (const float*)(data + idx * _mesh->layout.stride + pos_attr->offset);
        x = pos[0];
        y = pos[1];
        z = pos[2];
    }

    // Set vertex at index (bumps version)
    void set_vertex(size_t idx, float x, float y, float z) {
        if (!_mesh || idx >= _mesh->vertex_count) return;
        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&_mesh->layout, "position");
        if (!pos_attr) return;
        uint8_t* data = (uint8_t*)_mesh->vertices;
        float* pos = (float*)(data + idx * _mesh->layout.stride + pos_attr->offset);
        pos[0] = x;
        pos[1] = y;
        pos[2] = z;
        _mesh->version++;
    }

    // Translate all vertices
    void translate(float dx, float dy, float dz) {
        if (!_mesh) return;
        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&_mesh->layout, "position");
        if (!pos_attr) return;

        uint8_t* data = (uint8_t*)_mesh->vertices;
        for (size_t i = 0; i < _mesh->vertex_count; i++) {
            float* pos = (float*)(data + i * _mesh->layout.stride + pos_attr->offset);
            pos[0] += dx;
            pos[1] += dy;
            pos[2] += dz;
        }
        _mesh->version++;
    }

    // Scale all vertices
    void scale(float factor) {
        if (!_mesh) return;
        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&_mesh->layout, "position");
        if (!pos_attr) return;

        uint8_t* data = (uint8_t*)_mesh->vertices;
        for (size_t i = 0; i < _mesh->vertex_count; i++) {
            float* pos = (float*)(data + i * _mesh->layout.stride + pos_attr->offset);
            pos[0] *= factor;
            pos[1] *= factor;
            pos[2] *= factor;
        }
        _mesh->version++;
    }

    // Compute vertex normals from geometry
    void compute_vertex_normals() {
        if (!_mesh) return;

        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&_mesh->layout, "position");
        const tc_vertex_attrib* norm_attr = tc_vertex_layout_find(&_mesh->layout, "normal");
        if (!pos_attr || !norm_attr) return;

        size_t num_verts = _mesh->vertex_count;
        size_t num_faces = _mesh->index_count / 3;
        uint8_t* data = (uint8_t*)_mesh->vertices;

        // Accumulate normals (use double for precision)
        std::vector<double> accum(num_verts * 3, 0.0);

        for (size_t f = 0; f < num_faces; f++) {
            uint32_t i0 = _mesh->indices[f * 3];
            uint32_t i1 = _mesh->indices[f * 3 + 1];
            uint32_t i2 = _mesh->indices[f * 3 + 2];

            const float* v0 = (const float*)(data + i0 * _mesh->layout.stride + pos_attr->offset);
            const float* v1 = (const float*)(data + i1 * _mesh->layout.stride + pos_attr->offset);
            const float* v2 = (const float*)(data + i2 * _mesh->layout.stride + pos_attr->offset);

            // Edge vectors
            float e1x = v1[0] - v0[0], e1y = v1[1] - v0[1], e1z = v1[2] - v0[2];
            float e2x = v2[0] - v0[0], e2y = v2[1] - v0[1], e2z = v2[2] - v0[2];

            // Cross product (area-weighted normal)
            double nx = e1y * e2z - e1z * e2y;
            double ny = e1z * e2x - e1x * e2z;
            double nz = e1x * e2y - e1y * e2x;

            // Accumulate to each vertex
            accum[i0 * 3] += nx; accum[i0 * 3 + 1] += ny; accum[i0 * 3 + 2] += nz;
            accum[i1 * 3] += nx; accum[i1 * 3 + 1] += ny; accum[i1 * 3 + 2] += nz;
            accum[i2 * 3] += nx; accum[i2 * 3 + 1] += ny; accum[i2 * 3 + 2] += nz;
        }

        // Normalize and store
        for (size_t v = 0; v < num_verts; v++) {
            double nx = accum[v * 3];
            double ny = accum[v * 3 + 1];
            double nz = accum[v * 3 + 2];
            double len = std::sqrt(nx * nx + ny * ny + nz * nz);
            if (len < 1e-8) len = 1.0;

            float* norm = (float*)(data + v * _mesh->layout.stride + norm_attr->offset);
            norm[0] = static_cast<float>(nx / len);
            norm[1] = static_cast<float>(ny / len);
            norm[2] = static_cast<float>(nz / len);
        }
        _mesh->version++;
    }

    // Build interleaved buffer: pos(3) + normal(3) + uv(2) = 8 floats per vertex
    // Returns a copy of the vertex data in interleaved format
    std::vector<float> build_interleaved_buffer() const {
        if (!_mesh) return {};

        size_t num_verts = _mesh->vertex_count;
        std::vector<float> buffer(num_verts * 8);

        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&_mesh->layout, "position");
        const tc_vertex_attrib* norm_attr = tc_vertex_layout_find(&_mesh->layout, "normal");
        const tc_vertex_attrib* uv_attr = tc_vertex_layout_find(&_mesh->layout, "uv");

        const uint8_t* data = (const uint8_t*)_mesh->vertices;

        for (size_t v = 0; v < num_verts; v++) {
            size_t dst = v * 8;

            // Position
            if (pos_attr) {
                const float* pos = (const float*)(data + v * _mesh->layout.stride + pos_attr->offset);
                buffer[dst] = pos[0];
                buffer[dst + 1] = pos[1];
                buffer[dst + 2] = pos[2];
            } else {
                buffer[dst] = buffer[dst + 1] = buffer[dst + 2] = 0.0f;
            }

            // Normal
            if (norm_attr) {
                const float* norm = (const float*)(data + v * _mesh->layout.stride + norm_attr->offset);
                buffer[dst + 3] = norm[0];
                buffer[dst + 4] = norm[1];
                buffer[dst + 5] = norm[2];
            } else {
                buffer[dst + 3] = buffer[dst + 4] = buffer[dst + 5] = 0.0f;
            }

            // UV
            if (uv_attr) {
                const float* uv = (const float*)(data + v * _mesh->layout.stride + uv_attr->offset);
                buffer[dst + 6] = uv[0];
                buffer[dst + 7] = uv[1];
            } else {
                buffer[dst + 6] = buffer[dst + 7] = 0.0f;
            }
        }

        return buffer;
    }

    // Create a deep copy (new tc_mesh with new UUID)
    Mesh3 copy(const char* new_name = nullptr) const {
        if (!_mesh) return Mesh3();

        auto verts = get_vertices();
        auto indices = get_indices();
        auto normals = get_normals();
        auto uvs = get_uvs();

        // Use provided name, or append "_copy" to original
        std::string copy_name;
        if (new_name) {
            copy_name = new_name;
        } else {
            copy_name = _mesh->name ? std::string(_mesh->name) + "_copy" : "mesh_copy";
        }

        Mesh3 result;
        result.init_from_data(
            copy_name.c_str(),
            verts.data(), verts.size() / 3,
            indices.data(), indices.size(),
            normals.empty() ? nullptr : normals.data(),
            uvs.empty() ? nullptr : uvs.data()
        );
        return result;
    }

    // Source path (for compatibility - stored externally now)
    std::string source_path;

private:
    void init_from_data(
        const char* name,
        const float* vertices, size_t vertex_count,
        const uint32_t* indices, size_t index_count,
        const float* normals,
        const float* uvs
    ) {
        if (vertex_count == 0) return;

        // Build interleaved vertex buffer: pos(3) + normal(3) + uv(2)
        tc_vertex_layout layout = tc_vertex_layout_pos_normal_uv();
        size_t vertex_size = vertex_count * layout.stride;

        std::vector<uint8_t> buffer(vertex_size, 0);

        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&layout, "position");
        const tc_vertex_attrib* norm_attr = tc_vertex_layout_find(&layout, "normal");
        const tc_vertex_attrib* uv_attr = tc_vertex_layout_find(&layout, "uv");

        for (size_t i = 0; i < vertex_count; i++) {
            uint8_t* dst = buffer.data() + i * layout.stride;

            // Position
            if (pos_attr && vertices) {
                float* pos = (float*)(dst + pos_attr->offset);
                pos[0] = vertices[i * 3];
                pos[1] = vertices[i * 3 + 1];
                pos[2] = vertices[i * 3 + 2];
            }

            // Normal
            if (norm_attr && normals) {
                float* norm = (float*)(dst + norm_attr->offset);
                norm[0] = normals[i * 3];
                norm[1] = normals[i * 3 + 1];
                norm[2] = normals[i * 3 + 2];
            }

            // UV
            if (uv_attr && uvs) {
                float* uv = (float*)(dst + uv_attr->offset);
                uv[0] = uvs[i * 2];
                uv[1] = uvs[i * 2 + 1];
            }
        }

        // Compute UUID from data
        char uuid[40];
        tc_mesh_compute_uuid(buffer.data(), vertex_size, indices, index_count, uuid);

        // Debug
        printf("[Mesh3] [1] name='%s' uuid=%.16s...\n", name, uuid);
        fflush(stdout);

        // Get or create mesh
        _mesh = tc_mesh_get_or_create(uuid);
        if (!_mesh) return;

        // Set data if newly created (version == 1 means fresh)
        if (_mesh->version == 1 && _mesh->vertices == nullptr) {
            tc_mesh_set_data(_mesh, name, buffer.data(), vertex_count, &layout, indices, index_count);
        }
    }

    void init_from_data_with_uuid(
        const char* uuid,
        const char* name,
        const float* vertices, size_t vertex_count,
        const uint32_t* indices, size_t index_count,
        const float* normals,
        const float* uvs
    ) {
        
        printf("[Mesh3] [2] name='%s' uuid=%.16s...\n", name, uuid);
        // Try to get existing mesh first
        _mesh = tc_mesh_get_or_create(uuid);
        if (!_mesh) return;

        // If already has data, we're done
        if (_mesh->vertices != nullptr) {
            return;
        }

        // Build data for new mesh
        if (vertex_count == 0) return;

        tc_vertex_layout layout = tc_vertex_layout_pos_normal_uv();
        size_t vertex_size = vertex_count * layout.stride;

        std::vector<uint8_t> buffer(vertex_size, 0);

        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&layout, "position");
        const tc_vertex_attrib* norm_attr = tc_vertex_layout_find(&layout, "normal");
        const tc_vertex_attrib* uv_attr = tc_vertex_layout_find(&layout, "uv");

        for (size_t i = 0; i < vertex_count; i++) {
            uint8_t* dst = buffer.data() + i * layout.stride;

            if (pos_attr && vertices) {
                float* pos = (float*)(dst + pos_attr->offset);
                pos[0] = vertices[i * 3];
                pos[1] = vertices[i * 3 + 1];
                pos[2] = vertices[i * 3 + 2];
            }

            if (norm_attr && normals) {
                float* norm = (float*)(dst + norm_attr->offset);
                norm[0] = normals[i * 3];
                norm[1] = normals[i * 3 + 1];
                norm[2] = normals[i * 3 + 2];
            }

            if (uv_attr && uvs) {
                float* uv = (float*)(dst + uv_attr->offset);
                uv[0] = uvs[i * 2];
                uv[1] = uvs[i * 2 + 1];
            }
        }

        tc_mesh_set_data(_mesh, name, buffer.data(), vertex_count, &layout, indices, index_count);
    }
};

} // namespace termin
