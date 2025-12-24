#include "skinned_mesh_renderer.hpp"

#include <cstdio>

namespace termin {

void SkinnedMeshRenderer::update_bone_matrices() {
    if (!skeleton_instance) {
        bone_count = 0;
        bone_matrices_flat.clear();
        return;
    }

    // Update skeleton (computes matrices from entity transforms)
    skeleton_instance->update();

    // Get bone count
    bone_count = skeleton_instance->bone_count();
    if (bone_count == 0) {
        bone_matrices_flat.clear();
        return;
    }

    // Resize buffer
    bone_matrices_flat.resize(bone_count * 16);

    // Copy matrices (column-major for OpenGL)
    for (int i = 0; i < bone_count; ++i) {
        const Mat44& m = skeleton_instance->get_bone_matrix(i);
        // Mat44 is column-major, copy directly
        for (int j = 0; j < 16; ++j) {
            bone_matrices_flat[i * 16 + j] = static_cast<float>(m.data[j]);
        }
    }

    // Debug: check if matrices are identity
    static int debug_count = 0;
    if (debug_count < 3 && bone_count > 0) {
        debug_count++;
        float* m = bone_matrices_flat.data();
        bool is_identity = (m[0] == 1.0f && m[5] == 1.0f && m[10] == 1.0f && m[15] == 1.0f &&
                           m[12] == 0.0f && m[13] == 0.0f && m[14] == 0.0f);
        printf("[SkinnedMeshRenderer] bone_count=%d, first matrix is_identity=%d\n",
               bone_count, is_identity);
        printf("  translation: %f %f %f\n", m[12], m[13], m[14]);
    }
}

void SkinnedMeshRenderer::upload_bone_matrices(ShaderProgram& shader) {
    if (bone_count == 0 || bone_matrices_flat.empty()) {
        return;
    }

    shader.set_uniform_matrix4_array("u_bone_matrices", bone_matrices_flat.data(), bone_count, false);
    shader.set_uniform_int("u_bone_count", bone_count);
}

void SkinnedMeshRenderer::draw(
    const RenderContext& context,
    const Mesh3& mesh,
    MeshGPU& mesh_gpu,
    int mesh_version,
    ShaderProgram& shader
) {
    // Update bone matrices
    update_bone_matrices();

    // Ensure shader is ready and active
    // (caller should handle this, but we upload uniforms)

    // Upload bone matrices
    upload_bone_matrices(shader);

    // Draw mesh
    mesh_gpu.draw(context, mesh, mesh_version);
}

} // namespace termin
