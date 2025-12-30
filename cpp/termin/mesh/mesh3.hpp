#pragma once

#include "custom_mesh.hpp"
#include <cmath>

namespace termin {

// Triangle mesh with positions, normals, and UVs.
// Layout: pos(3) + normal(3) + uv(2) = 8 floats per vertex
class Mesh3 : public CustomMesh {
public:
    Mesh3() = default;

    // Construct from separate arrays (computes UUID from data hash)
    Mesh3(const float* vertices, size_t vertex_count,
          const uint32_t* indices, size_t index_count,
          const float* normals = nullptr,
          const float* uvs = nullptr,
          const char* name = nullptr)
    {
        init_mesh3(vertices, vertex_count, indices, index_count, normals, uvs, name);
    }

    // Construct from std::vectors (convenience)
    Mesh3(std::vector<float> verts, std::vector<uint32_t> tris, const char* name = nullptr)
    {
        init_mesh3(verts.data(), verts.size() / 3,
                   tris.data(), tris.size(),
                   nullptr, nullptr, name);
    }

    // Construct with explicit UUID (for primitives with precomputed UUID)
    Mesh3(const char* uuid,
          const float* vertices, size_t vertex_count,
          const uint32_t* indices, size_t index_count,
          const float* normals = nullptr,
          const float* uvs = nullptr,
          const char* name = nullptr)
    {
        init_mesh3_with_uuid(uuid, vertices, vertex_count, indices, index_count, normals, uvs, name);
    }

    // Get existing mesh by UUID
    static Mesh3 from_uuid(const char* uuid) {
        Mesh3 m;
        m._mesh = tc_mesh_get(uuid);
        if (m._mesh) tc_mesh_add_ref(m._mesh);
        return m;
    }

    // ========== Typed Accessors ==========

    std::vector<float> get_vertices() const {
        return get_attribute("position").to_vector();
    }

    std::vector<float> get_normals() const {
        return get_attribute("normal").to_vector();
    }

    std::vector<float> get_uvs() const {
        return get_attribute("uv").to_vector();
    }

    // ========== Setters ==========

    void set_vertices(const float* data, size_t count) {
        auto view = get_mutable_attribute("position");
        if (!view.valid() || count != view.count) return;
        for (size_t i = 0; i < count; i++) {
            view.set(i, data + i * 3);
        }
        bump_version();
    }

    void set_normals(const float* data, size_t count) {
        auto view = get_mutable_attribute("normal");
        if (!view.valid() || count != view.count) return;
        for (size_t i = 0; i < count; i++) {
            view.set(i, data + i * 3);
        }
        bump_version();
    }

    void set_uvs(const float* data, size_t count) {
        auto view = get_mutable_attribute("uv");
        if (!view.valid() || count != view.count) return;
        for (size_t i = 0; i < count; i++) {
            view.set(i, data + i * 2);
        }
        bump_version();
    }

    // ========== Query Methods ==========

    bool has_uvs() const { return has_attribute("uv"); }
    bool has_vertex_normals() const { return has_attribute("normal"); }

    size_t get_vertex_count() const { return vertex_count(); }
    size_t get_face_count() const { return triangle_count(); }

    // Build interleaved buffer for GPU: pos(3) + normal(3) + uv(2) = 8 floats per vertex
    std::vector<float> build_interleaved_buffer() const {
        if (!_mesh) return {};

        size_t num_verts = vertex_count();
        std::vector<float> buffer(num_verts * 8);

        auto pos = get_attribute("position");
        auto norm = get_attribute("normal");
        auto uv = get_attribute("uv");

        for (size_t v = 0; v < num_verts; v++) {
            size_t dst = v * 8;

            // Position (3)
            if (pos.valid()) {
                const float* p = pos.at(v);
                buffer[dst] = p[0];
                buffer[dst + 1] = p[1];
                buffer[dst + 2] = p[2];
            }

            // Normal (3)
            if (norm.valid()) {
                const float* n = norm.at(v);
                buffer[dst + 3] = n[0];
                buffer[dst + 4] = n[1];
                buffer[dst + 5] = n[2];
            }

            // UV (2)
            if (uv.valid()) {
                const float* u = uv.at(v);
                buffer[dst + 6] = u[0];
                buffer[dst + 7] = u[1];
            }
        }

        return buffer;
    }

    // ========== Transformations ==========

    void translate(float x, float y, float z) {
        auto view = get_mutable_attribute("position");
        if (!view.valid()) return;

        for (size_t i = 0; i < view.count; i++) {
            float* p = view.at(i);
            p[0] += x;
            p[1] += y;
            p[2] += z;
        }
        bump_version();
    }

    void scale(float factor) {
        auto view = get_mutable_attribute("position");
        if (!view.valid()) return;

        for (size_t i = 0; i < view.count; i++) {
            float* p = view.at(i);
            p[0] *= factor;
            p[1] *= factor;
            p[2] *= factor;
        }
        bump_version();
    }

    // ========== Operations ==========

    void compute_normals() {
        if (!_mesh || !_mesh->vertices || !_mesh->indices) return;

        auto pos_view = get_attribute("position");
        auto norm_view = get_mutable_attribute("normal");
        if (!pos_view.valid() || !norm_view.valid()) return;

        size_t num_verts = vertex_count();
        size_t num_tris = triangle_count();

        // Zero out normals
        for (size_t i = 0; i < num_verts; i++) {
            float* n = norm_view.at(i);
            n[0] = n[1] = n[2] = 0.0f;
        }

        // Accumulate face normals
        const uint32_t* idx = _mesh->indices;
        for (size_t t = 0; t < num_tris; t++) {
            uint32_t i0 = idx[t * 3];
            uint32_t i1 = idx[t * 3 + 1];
            uint32_t i2 = idx[t * 3 + 2];

            const float* p0 = pos_view.at(i0);
            const float* p1 = pos_view.at(i1);
            const float* p2 = pos_view.at(i2);

            float e1[3] = { p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2] };
            float e2[3] = { p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2] };

            float fn[3] = {
                e1[1] * e2[2] - e1[2] * e2[1],
                e1[2] * e2[0] - e1[0] * e2[2],
                e1[0] * e2[1] - e1[1] * e2[0]
            };

            float* n0 = norm_view.at(i0);
            float* n1 = norm_view.at(i1);
            float* n2 = norm_view.at(i2);

            for (int k = 0; k < 3; k++) {
                n0[k] += fn[k];
                n1[k] += fn[k];
                n2[k] += fn[k];
            }
        }

        // Normalize
        for (size_t i = 0; i < num_verts; i++) {
            float* n = norm_view.at(i);
            float len = std::sqrt(n[0]*n[0] + n[1]*n[1] + n[2]*n[2]);
            if (len > 1e-8f) {
                n[0] /= len;
                n[1] /= len;
                n[2] /= len;
            }
        }

        bump_version();
    }

    // ========== Copy ==========

    Mesh3 copy(const char* new_name = nullptr) const {
        if (!_mesh) return Mesh3();

        auto verts = get_vertices();
        auto indices = get_indices();
        auto normals = get_normals();
        auto uvs = get_uvs();

        std::string copy_name;
        if (new_name) {
            copy_name = new_name;
        } else {
            copy_name = _mesh->name ? std::string(_mesh->name) + "_copy" : "mesh_copy";
        }

        return Mesh3(
            verts.data(), verts.size() / 3,
            indices.data(), indices.size(),
            normals.empty() ? nullptr : normals.data(),
            uvs.empty() ? nullptr : uvs.data(),
            copy_name.c_str()
        );
    }

private:
    // Build interleaved buffer and initialize
    void init_mesh3(
        const float* vertices, size_t vertex_count,
        const uint32_t* indices, size_t index_count,
        const float* normals,
        const float* uvs,
        const char* name
    ) {
        if (vertex_count == 0) return;

        tc_vertex_layout layout = tc_vertex_layout_pos_normal_uv();
        std::vector<uint8_t> buffer = build_interleaved_buffer(
            layout, vertex_count, vertices, normals, uvs);

        init_from_data(buffer.data(), vertex_count, &layout, indices, index_count, name);
    }

    // Build interleaved buffer with explicit UUID
    void init_mesh3_with_uuid(
        const char* uuid,
        const float* vertices, size_t vertex_count,
        const uint32_t* indices, size_t index_count,
        const float* normals,
        const float* uvs,
        const char* name
    ) {
        if (vertex_count == 0) return;

        tc_vertex_layout layout = tc_vertex_layout_pos_normal_uv();
        std::vector<uint8_t> buffer = build_interleaved_buffer(
            layout, vertex_count, vertices, normals, uvs);

        init_with_uuid(uuid, buffer.data(), vertex_count, &layout, indices, index_count, name);
    }

    static std::vector<uint8_t> build_interleaved_buffer(
        const tc_vertex_layout& layout,
        size_t vertex_count,
        const float* vertices,
        const float* normals,
        const float* uvs
    ) {
        std::vector<uint8_t> buffer(vertex_count * layout.stride, 0);

        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&layout, "position");
        const tc_vertex_attrib* norm_attr = tc_vertex_layout_find(&layout, "normal");
        const tc_vertex_attrib* uv_attr = tc_vertex_layout_find(&layout, "uv");

        for (size_t i = 0; i < vertex_count; i++) {
            uint8_t* dst = buffer.data() + i * layout.stride;

            if (pos_attr && vertices) {
                float* pos = reinterpret_cast<float*>(dst + pos_attr->offset);
                pos[0] = vertices[i * 3];
                pos[1] = vertices[i * 3 + 1];
                pos[2] = vertices[i * 3 + 2];
            }

            if (norm_attr && normals) {
                float* norm = reinterpret_cast<float*>(dst + norm_attr->offset);
                norm[0] = normals[i * 3];
                norm[1] = normals[i * 3 + 1];
                norm[2] = normals[i * 3 + 2];
            }

            if (uv_attr && uvs) {
                float* uv = reinterpret_cast<float*>(dst + uv_attr->offset);
                uv[0] = uvs[i * 2];
                uv[1] = uvs[i * 2 + 1];
            }
        }

        return buffer;
    }
};

} // namespace termin
