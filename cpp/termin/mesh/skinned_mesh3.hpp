#pragma once

#include "custom_mesh.hpp"

namespace termin {

// Skinned triangle mesh with skeletal animation data.
// Layout: pos(3) + normal(3) + uv(2) + joints(4) + weights(4) = 16 floats per vertex
class SkinnedMesh3 : public CustomMesh {
public:
    SkinnedMesh3() = default;

    // Construct from separate arrays (computes UUID from data hash)
    SkinnedMesh3(const float* vertices, size_t vertex_count,
                 const uint32_t* indices, size_t index_count,
                 const float* normals = nullptr,
                 const float* uvs = nullptr,
                 const float* joint_indices = nullptr,
                 const float* joint_weights = nullptr,
                 const char* name = nullptr)
    {
        init_skinned(vertices, vertex_count, indices, index_count,
                     normals, uvs, joint_indices, joint_weights, name);
    }

    // Construct from std::vectors
    SkinnedMesh3(std::vector<float> verts, std::vector<uint32_t> tris, const char* name = nullptr)
    {
        init_skinned(verts.data(), verts.size() / 3,
                     tris.data(), tris.size(),
                     nullptr, nullptr, nullptr, nullptr, name);
    }

    // Construct with explicit UUID
    SkinnedMesh3(const char* uuid,
                 const float* vertices, size_t vertex_count,
                 const uint32_t* indices, size_t index_count,
                 const float* normals = nullptr,
                 const float* uvs = nullptr,
                 const float* joint_indices = nullptr,
                 const float* joint_weights = nullptr,
                 const char* name = nullptr)
    {
        init_skinned_with_uuid(uuid, vertices, vertex_count, indices, index_count,
                               normals, uvs, joint_indices, joint_weights, name);
    }

    // Get existing mesh by UUID
    static SkinnedMesh3 from_uuid(const char* uuid) {
        SkinnedMesh3 m;
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

    std::vector<float> get_joint_indices() const {
        return get_attribute("joints").to_vector();
    }

    std::vector<float> get_joint_weights() const {
        return get_attribute("weights").to_vector();
    }

    // ========== Setters ==========

    void set_joint_indices(const float* data, size_t count) {
        auto view = get_mutable_attribute("joints");
        if (!view.valid() || count != view.count) return;
        for (size_t i = 0; i < count; i++) {
            view.set(i, data + i * 4);
        }
        bump_version();
    }

    void set_joint_weights(const float* data, size_t count) {
        auto view = get_mutable_attribute("weights");
        if (!view.valid() || count != view.count) return;
        for (size_t i = 0; i < count; i++) {
            view.set(i, data + i * 4);
        }
        bump_version();
    }

    // ========== Skinning Helpers ==========

    bool has_skinning() const {
        return has_attribute("joints") && has_attribute("weights");
    }

    // Initialize default skinning (bone 0, weight 1.0)
    void init_default_skinning() {
        auto joints_view = get_mutable_attribute("joints");
        auto weights_view = get_mutable_attribute("weights");
        if (!joints_view.valid() || !weights_view.valid()) return;

        for (size_t v = 0; v < vertex_count(); v++) {
            float* joints = joints_view.at(v);
            float* weights = weights_view.at(v);

            joints[0] = joints[1] = joints[2] = joints[3] = 0.0f;
            weights[0] = 1.0f;
            weights[1] = weights[2] = weights[3] = 0.0f;
        }
        bump_version();
    }

    // Normalize weights to sum to 1.0 per vertex
    void normalize_weights() {
        auto view = get_mutable_attribute("weights");
        if (!view.valid()) return;

        for (size_t v = 0; v < vertex_count(); v++) {
            float* w = view.at(v);
            float sum = w[0] + w[1] + w[2] + w[3];
            if (sum > 1e-6f) {
                w[0] /= sum;
                w[1] /= sum;
                w[2] /= sum;
                w[3] /= sum;
            }
        }
        bump_version();
    }

    // Build interleaved buffer for GPU: pos(3) + normal(3) + uv(2) + joints(4) + weights(4)
    std::vector<float> build_interleaved_buffer() const {
        if (!_mesh) return {};

        size_t num_verts = vertex_count();
        std::vector<float> buffer(num_verts * 16);

        auto pos = get_attribute("position");
        auto norm = get_attribute("normal");
        auto uv = get_attribute("uv");
        auto joints = get_attribute("joints");
        auto weights = get_attribute("weights");

        for (size_t v = 0; v < num_verts; v++) {
            size_t dst = v * 16;

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

            // Joints (4)
            if (joints.valid()) {
                const float* j = joints.at(v);
                buffer[dst + 8] = j[0];
                buffer[dst + 9] = j[1];
                buffer[dst + 10] = j[2];
                buffer[dst + 11] = j[3];
            }

            // Weights (4)
            if (weights.valid()) {
                const float* wt = weights.at(v);
                buffer[dst + 12] = wt[0];
                buffer[dst + 13] = wt[1];
                buffer[dst + 14] = wt[2];
                buffer[dst + 15] = wt[3];
            } else {
                buffer[dst + 12] = 1.0f;  // Default weight
            }
        }

        return buffer;
    }

    // ========== Copy ==========

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

        return SkinnedMesh3(
            verts.data(), verts.size() / 3,
            indices.data(), indices.size(),
            normals.empty() ? nullptr : normals.data(),
            uvs.empty() ? nullptr : uvs.data(),
            joints.empty() ? nullptr : joints.data(),
            weights.empty() ? nullptr : weights.data(),
            copy_name.c_str()
        );
    }

private:
    void init_skinned(
        const float* vertices, size_t vertex_count,
        const uint32_t* indices, size_t index_count,
        const float* normals,
        const float* uvs,
        const float* joint_indices,
        const float* joint_weights,
        const char* name
    ) {
        if (vertex_count == 0) return;

        tc_vertex_layout layout = tc_vertex_layout_skinned();
        std::vector<uint8_t> buffer = build_buffer(
            layout, vertex_count, vertices, normals, uvs, joint_indices, joint_weights);

        init_from_data(buffer.data(), vertex_count, &layout, indices, index_count, name);
    }

    void init_skinned_with_uuid(
        const char* uuid,
        const float* vertices, size_t vertex_count,
        const uint32_t* indices, size_t index_count,
        const float* normals,
        const float* uvs,
        const float* joint_indices,
        const float* joint_weights,
        const char* name
    ) {
        if (vertex_count == 0) return;

        tc_vertex_layout layout = tc_vertex_layout_skinned();
        std::vector<uint8_t> buffer = build_buffer(
            layout, vertex_count, vertices, normals, uvs, joint_indices, joint_weights);

        init_with_uuid(uuid, buffer.data(), vertex_count, &layout, indices, index_count, name);
    }

    static std::vector<uint8_t> build_buffer(
        const tc_vertex_layout& layout,
        size_t vertex_count,
        const float* vertices,
        const float* normals,
        const float* uvs,
        const float* joint_indices,
        const float* joint_weights
    ) {
        std::vector<uint8_t> buffer(vertex_count * layout.stride, 0);

        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&layout, "position");
        const tc_vertex_attrib* norm_attr = tc_vertex_layout_find(&layout, "normal");
        const tc_vertex_attrib* uv_attr = tc_vertex_layout_find(&layout, "uv");
        const tc_vertex_attrib* joints_attr = tc_vertex_layout_find(&layout, "joints");
        const tc_vertex_attrib* weights_attr = tc_vertex_layout_find(&layout, "weights");

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

            if (joints_attr) {
                float* j = reinterpret_cast<float*>(dst + joints_attr->offset);
                if (joint_indices) {
                    j[0] = joint_indices[i * 4];
                    j[1] = joint_indices[i * 4 + 1];
                    j[2] = joint_indices[i * 4 + 2];
                    j[3] = joint_indices[i * 4 + 3];
                } else {
                    j[0] = j[1] = j[2] = j[3] = 0.0f;
                }
            }

            if (weights_attr) {
                float* w = reinterpret_cast<float*>(dst + weights_attr->offset);
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

        return buffer;
    }
};

} // namespace termin
