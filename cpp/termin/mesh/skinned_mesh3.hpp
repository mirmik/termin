#pragma once

#include "mesh3.hpp"

namespace termin {

// Skinned triangle mesh with skeletal animation data.
// Extends Mesh3 with joint indices and weights for GPU skinning.
// Layout: pos(3) + normal(3) + uv(2) + joints(4) + weights(4) = 16 floats per vertex
class SkinnedMesh3 : public Mesh3 {
public:
    SkinnedMesh3() = default;

    // Construct from separate arrays - name is REQUIRED
    SkinnedMesh3(const char* name,
                 const float* vertices, size_t vertex_count,
                 const uint32_t* indices, size_t index_count,
                 const float* normals = nullptr,
                 const float* uvs = nullptr,
                 const float* joint_indices = nullptr,
                 const float* joint_weights = nullptr)
    {
        init_skinned_data(name, vertices, vertex_count, indices, index_count,
                         normals, uvs, joint_indices, joint_weights);
    }

    // Construct from std::vectors
    SkinnedMesh3(const char* name, std::vector<float> verts, std::vector<uint32_t> tris)
    {
        init_skinned_data(name, verts.data(), verts.size() / 3,
                         tris.data(), tris.size(),
                         nullptr, nullptr, nullptr, nullptr);
    }

    // Check if has skinning data
    bool has_skinning() const {
        if (!_mesh) return false;
        return tc_vertex_layout_find(&_mesh->layout, "joints") != nullptr &&
               tc_vertex_layout_find(&_mesh->layout, "weights") != nullptr;
    }

    // Get joint indices (Nx4 floats)
    std::vector<float> get_joint_indices() const {
        std::vector<float> result;
        if (!_mesh) return result;

        const tc_vertex_attrib* attr = tc_vertex_layout_find(&_mesh->layout, "joints");
        if (!attr || attr->size != 4) return result;

        result.resize(_mesh->vertex_count * 4);
        const uint8_t* data = (const uint8_t*)_mesh->vertices;

        for (size_t i = 0; i < _mesh->vertex_count; i++) {
            const float* joints = (const float*)(data + i * _mesh->layout.stride + attr->offset);
            result[i * 4] = joints[0];
            result[i * 4 + 1] = joints[1];
            result[i * 4 + 2] = joints[2];
            result[i * 4 + 3] = joints[3];
        }
        return result;
    }

    // Get joint weights (Nx4 floats)
    std::vector<float> get_joint_weights() const {
        std::vector<float> result;
        if (!_mesh) return result;

        const tc_vertex_attrib* attr = tc_vertex_layout_find(&_mesh->layout, "weights");
        if (!attr || attr->size != 4) return result;

        result.resize(_mesh->vertex_count * 4);
        const uint8_t* data = (const uint8_t*)_mesh->vertices;

        for (size_t i = 0; i < _mesh->vertex_count; i++) {
            const float* weights = (const float*)(data + i * _mesh->layout.stride + attr->offset);
            result[i * 4] = weights[0];
            result[i * 4 + 1] = weights[1];
            result[i * 4 + 2] = weights[2];
            result[i * 4 + 3] = weights[3];
        }
        return result;
    }

    // Set joint indices
    void set_joint_indices(const float* data, size_t count) {
        if (!_mesh || count != _mesh->vertex_count) return;
        const tc_vertex_attrib* attr = tc_vertex_layout_find(&_mesh->layout, "joints");
        if (!attr) return;

        uint8_t* vdata = (uint8_t*)_mesh->vertices;
        for (size_t i = 0; i < count; i++) {
            float* joints = (float*)(vdata + i * _mesh->layout.stride + attr->offset);
            joints[0] = data[i * 4];
            joints[1] = data[i * 4 + 1];
            joints[2] = data[i * 4 + 2];
            joints[3] = data[i * 4 + 3];
        }
        _mesh->version++;
    }

    // Set joint weights
    void set_joint_weights(const float* data, size_t count) {
        if (!_mesh || count != _mesh->vertex_count) return;
        const tc_vertex_attrib* attr = tc_vertex_layout_find(&_mesh->layout, "weights");
        if (!attr) return;

        uint8_t* vdata = (uint8_t*)_mesh->vertices;
        for (size_t i = 0; i < count; i++) {
            float* weights = (float*)(vdata + i * _mesh->layout.stride + attr->offset);
            weights[0] = data[i * 4];
            weights[1] = data[i * 4 + 1];
            weights[2] = data[i * 4 + 2];
            weights[3] = data[i * 4 + 3];
        }
        _mesh->version++;
    }

    // Initialize default skinning (bone 0, weight 1.0)
    void init_default_skinning() {
        if (!_mesh) return;
        const tc_vertex_attrib* joints_attr = tc_vertex_layout_find(&_mesh->layout, "joints");
        const tc_vertex_attrib* weights_attr = tc_vertex_layout_find(&_mesh->layout, "weights");
        if (!joints_attr || !weights_attr) return;

        uint8_t* data = (uint8_t*)_mesh->vertices;
        for (size_t v = 0; v < _mesh->vertex_count; v++) {
            float* joints = (float*)(data + v * _mesh->layout.stride + joints_attr->offset);
            float* weights = (float*)(data + v * _mesh->layout.stride + weights_attr->offset);

            joints[0] = joints[1] = joints[2] = joints[3] = 0.0f;
            weights[0] = 1.0f;
            weights[1] = weights[2] = weights[3] = 0.0f;
        }
        _mesh->version++;
    }

    // Normalize weights to sum to 1.0 per vertex
    void normalize_weights() {
        if (!_mesh) return;
        const tc_vertex_attrib* attr = tc_vertex_layout_find(&_mesh->layout, "weights");
        if (!attr) return;

        uint8_t* data = (uint8_t*)_mesh->vertices;
        for (size_t v = 0; v < _mesh->vertex_count; v++) {
            float* w = (float*)(data + v * _mesh->layout.stride + attr->offset);
            float sum = w[0] + w[1] + w[2] + w[3];
            if (sum > 1e-6f) {
                w[0] /= sum;
                w[1] /= sum;
                w[2] /= sum;
                w[3] /= sum;
            }
        }
        _mesh->version++;
    }

    // Build interleaved buffer: pos(3) + normal(3) + uv(2) + joints(4) + weights(4) = 16 floats
    std::vector<float> build_interleaved_buffer() const {
        if (!_mesh) return {};

        size_t num_verts = _mesh->vertex_count;
        std::vector<float> buffer(num_verts * 16);

        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&_mesh->layout, "position");
        const tc_vertex_attrib* norm_attr = tc_vertex_layout_find(&_mesh->layout, "normal");
        const tc_vertex_attrib* uv_attr = tc_vertex_layout_find(&_mesh->layout, "uv");
        const tc_vertex_attrib* joints_attr = tc_vertex_layout_find(&_mesh->layout, "joints");
        const tc_vertex_attrib* weights_attr = tc_vertex_layout_find(&_mesh->layout, "weights");

        const uint8_t* data = (const uint8_t*)_mesh->vertices;

        for (size_t v = 0; v < num_verts; v++) {
            size_t dst = v * 16;

            // Position (3 floats)
            if (pos_attr) {
                const float* pos = (const float*)(data + v * _mesh->layout.stride + pos_attr->offset);
                buffer[dst] = pos[0];
                buffer[dst + 1] = pos[1];
                buffer[dst + 2] = pos[2];
            } else {
                buffer[dst] = buffer[dst + 1] = buffer[dst + 2] = 0.0f;
            }

            // Normal (3 floats)
            if (norm_attr) {
                const float* norm = (const float*)(data + v * _mesh->layout.stride + norm_attr->offset);
                buffer[dst + 3] = norm[0];
                buffer[dst + 4] = norm[1];
                buffer[dst + 5] = norm[2];
            } else {
                buffer[dst + 3] = buffer[dst + 4] = buffer[dst + 5] = 0.0f;
            }

            // UV (2 floats)
            if (uv_attr) {
                const float* uv = (const float*)(data + v * _mesh->layout.stride + uv_attr->offset);
                buffer[dst + 6] = uv[0];
                buffer[dst + 7] = uv[1];
            } else {
                buffer[dst + 6] = buffer[dst + 7] = 0.0f;
            }

            // Joint indices (4 floats)
            if (joints_attr) {
                const float* joints = (const float*)(data + v * _mesh->layout.stride + joints_attr->offset);
                buffer[dst + 8] = joints[0];
                buffer[dst + 9] = joints[1];
                buffer[dst + 10] = joints[2];
                buffer[dst + 11] = joints[3];
            } else {
                buffer[dst + 8] = buffer[dst + 9] = buffer[dst + 10] = buffer[dst + 11] = 0.0f;
            }

            // Joint weights (4 floats)
            if (weights_attr) {
                const float* weights = (const float*)(data + v * _mesh->layout.stride + weights_attr->offset);
                buffer[dst + 12] = weights[0];
                buffer[dst + 13] = weights[1];
                buffer[dst + 14] = weights[2];
                buffer[dst + 15] = weights[3];
            } else {
                buffer[dst + 12] = 1.0f;  // Default: first weight = 1
                buffer[dst + 13] = buffer[dst + 14] = buffer[dst + 15] = 0.0f;
            }
        }

        return buffer;
    }

    // Create a deep copy
    SkinnedMesh3 copy(const char* new_name = nullptr) const {
        if (!_mesh) return SkinnedMesh3();

        auto verts = get_vertices();
        auto indices = get_indices();
        auto normals = get_normals();
        auto uvs = get_uvs();
        auto joints = get_joint_indices();
        auto weights = get_joint_weights();

        std::string copy_name;
        if (new_name) {
            copy_name = new_name;
        } else {
            copy_name = _mesh->name ? std::string(_mesh->name) + "_copy" : "skinned_mesh_copy";
        }

        SkinnedMesh3 result;
        result.init_skinned_data(
            copy_name.c_str(),
            verts.data(), verts.size() / 3,
            indices.data(), indices.size(),
            normals.empty() ? nullptr : normals.data(),
            uvs.empty() ? nullptr : uvs.data(),
            joints.empty() ? nullptr : joints.data(),
            weights.empty() ? nullptr : weights.data()
        );
        return result;
    }

private:
    void init_skinned_data(
        const char* name,
        const float* vertices, size_t vertex_count,
        const uint32_t* indices, size_t index_count,
        const float* normals,
        const float* uvs,
        const float* joint_indices,
        const float* joint_weights
    ) {
        if (vertex_count == 0) return;

        // Build interleaved buffer: pos(3) + normal(3) + uv(2) + joints(4) + weights(4)
        tc_vertex_layout layout = tc_vertex_layout_skinned();
        size_t vertex_size = vertex_count * layout.stride;

        std::vector<uint8_t> buffer(vertex_size, 0);

        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&layout, "position");
        const tc_vertex_attrib* norm_attr = tc_vertex_layout_find(&layout, "normal");
        const tc_vertex_attrib* uv_attr = tc_vertex_layout_find(&layout, "uv");
        const tc_vertex_attrib* joints_attr = tc_vertex_layout_find(&layout, "joints");
        const tc_vertex_attrib* weights_attr = tc_vertex_layout_find(&layout, "weights");

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

            // Joint indices
            if (joints_attr) {
                float* j = (float*)(dst + joints_attr->offset);
                if (joint_indices) {
                    j[0] = joint_indices[i * 4];
                    j[1] = joint_indices[i * 4 + 1];
                    j[2] = joint_indices[i * 4 + 2];
                    j[3] = joint_indices[i * 4 + 3];
                } else {
                    j[0] = j[1] = j[2] = j[3] = 0.0f;
                }
            }

            // Joint weights
            if (weights_attr) {
                float* w = (float*)(dst + weights_attr->offset);
                if (joint_weights) {
                    w[0] = joint_weights[i * 4];
                    w[1] = joint_weights[i * 4 + 1];
                    w[2] = joint_weights[i * 4 + 2];
                    w[3] = joint_weights[i * 4 + 3];
                } else {
                    w[0] = 1.0f;  // Default: weight 1 on first bone
                    w[1] = w[2] = w[3] = 0.0f;
                }
            }
        }

        // Compute UUID from data
        char uuid[40];
        tc_mesh_compute_uuid(buffer.data(), vertex_size, indices, index_count, uuid);

        // Debug
        printf("[SkinnedMesh3] name='%s' uuid=%.16s...\n", name, uuid);
        fflush(stdout);

        // Get or create mesh
        _mesh = tc_mesh_get_or_create(uuid);
        if (!_mesh) return;

        // Set data if newly created
        if (_mesh->version == 1 && _mesh->vertices == nullptr) {
            tc_mesh_set_data(_mesh, name, buffer.data(), vertex_count, &layout, indices, index_count);
        }
    }
};

} // namespace termin
