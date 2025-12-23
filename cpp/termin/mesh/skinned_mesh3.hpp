#pragma once

#include "mesh3.hpp"

namespace termin {

/**
 * Skinned triangle mesh with skeletal animation data.
 * Extends Mesh3 with joint indices and weights for GPU skinning.
 */
class SkinnedMesh3 : public Mesh3 {
public:
    // Joint indices per vertex (Nx4 flattened)
    // Each vertex can be influenced by up to 4 bones
    std::vector<float> joint_indices;  // Stored as float for shader compatibility

    // Joint weights per vertex (Nx4 flattened)
    // Weights should sum to 1.0 per vertex
    std::vector<float> joint_weights;

    SkinnedMesh3() = default;

    SkinnedMesh3(std::vector<float> verts, std::vector<uint32_t> tris)
        : Mesh3(std::move(verts), std::move(tris)) {
        init_default_skinning();
    }

    // Check if has skinning data
    bool has_skinning() const {
        return !joint_indices.empty() && !joint_weights.empty();
    }

    // Initialize default skinning (bone 0, weight 1.0)
    void init_default_skinning() {
        size_t num_verts = get_vertex_count();
        joint_indices.resize(num_verts * 4, 0.0f);
        joint_weights.resize(num_verts * 4, 0.0f);
        // Set first weight to 1.0 for each vertex
        for (size_t v = 0; v < num_verts; ++v) {
            joint_weights[v * 4] = 1.0f;
        }
    }

    // Normalize weights to sum to 1.0 per vertex
    void normalize_weights() {
        size_t num_verts = get_vertex_count();
        for (size_t v = 0; v < num_verts; ++v) {
            size_t base = v * 4;
            float sum = joint_weights[base] + joint_weights[base + 1] +
                       joint_weights[base + 2] + joint_weights[base + 3];
            if (sum > 1e-6f) {
                joint_weights[base] /= sum;
                joint_weights[base + 1] /= sum;
                joint_weights[base + 2] /= sum;
                joint_weights[base + 3] /= sum;
            }
        }
    }

    // Build interleaved buffer: pos(3) + normal(3) + uv(2) + joints(4) + weights(4) = 16 floats
    std::vector<float> build_interleaved_buffer() const {
        size_t num_verts = get_vertex_count();
        std::vector<float> buffer(num_verts * 16);

        for (size_t v = 0; v < num_verts; ++v) {
            size_t src3 = v * 3;
            size_t src4 = v * 4;
            size_t dst = v * 16;

            // Position (3 floats)
            buffer[dst] = vertices[src3];
            buffer[dst + 1] = vertices[src3 + 1];
            buffer[dst + 2] = vertices[src3 + 2];

            // Normal (3 floats)
            if (!vertex_normals.empty()) {
                buffer[dst + 3] = vertex_normals[src3];
                buffer[dst + 4] = vertex_normals[src3 + 1];
                buffer[dst + 5] = vertex_normals[src3 + 2];
            } else {
                buffer[dst + 3] = 0.0f;
                buffer[dst + 4] = 0.0f;
                buffer[dst + 5] = 0.0f;
            }

            // UV (2 floats)
            if (!uvs.empty()) {
                buffer[dst + 6] = uvs[v * 2];
                buffer[dst + 7] = uvs[v * 2 + 1];
            } else {
                buffer[dst + 6] = 0.0f;
                buffer[dst + 7] = 0.0f;
            }

            // Joint indices (4 floats)
            if (!joint_indices.empty()) {
                buffer[dst + 8] = joint_indices[src4];
                buffer[dst + 9] = joint_indices[src4 + 1];
                buffer[dst + 10] = joint_indices[src4 + 2];
                buffer[dst + 11] = joint_indices[src4 + 3];
            } else {
                buffer[dst + 8] = 0.0f;
                buffer[dst + 9] = 0.0f;
                buffer[dst + 10] = 0.0f;
                buffer[dst + 11] = 0.0f;
            }

            // Joint weights (4 floats)
            if (!joint_weights.empty()) {
                buffer[dst + 12] = joint_weights[src4];
                buffer[dst + 13] = joint_weights[src4 + 1];
                buffer[dst + 14] = joint_weights[src4 + 2];
                buffer[dst + 15] = joint_weights[src4 + 3];
            } else {
                buffer[dst + 12] = 1.0f;  // Default: first weight = 1
                buffer[dst + 13] = 0.0f;
                buffer[dst + 14] = 0.0f;
                buffer[dst + 15] = 0.0f;
            }
        }

        return buffer;
    }

    // Create a deep copy
    SkinnedMesh3 copy() const {
        SkinnedMesh3 result;
        result.vertices = vertices;
        result.indices = indices;
        result.uvs = uvs;
        result.vertex_normals = vertex_normals;
        result.face_normals = face_normals;
        result.source_path = source_path;
        result.joint_indices = joint_indices;
        result.joint_weights = joint_weights;
        return result;
    }
};

} // namespace termin
