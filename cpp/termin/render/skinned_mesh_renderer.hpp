#pragma once

#include <vector>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

#include "termin/geom/mat44.hpp"
#include "termin/skeleton/skeleton_instance.hpp"
#include "termin/render/shader_program.hpp"
#include "termin/render/render_context.hpp"
#include "termin/mesh/mesh3.hpp"
#include "termin/render/mesh_gpu.hpp"

namespace py = pybind11;

namespace termin {

/**
 * SkinnedMeshRenderer - renders skinned mesh with bone matrices.
 *
 * Simplified C++ implementation focusing on the core rendering logic:
 * - Gets bone matrices from SkeletonInstance
 * - Uploads to shader
 * - Draws mesh
 */
class SkinnedMeshRenderer {
public:
    // Skeleton instance for bone matrices
    SkeletonInstance* skeleton_instance = nullptr;

    // Cached bone matrices (column-major, ready for shader)
    std::vector<float> bone_matrices_flat;
    int bone_count = 0;

    SkinnedMeshRenderer() = default;

    /**
     * Set skeleton instance.
     */
    void set_skeleton_instance(SkeletonInstance* si) {
        skeleton_instance = si;
    }

    /**
     * Update bone matrices from skeleton instance.
     * Call this before drawing.
     */
    void update_bone_matrices();

    /**
     * Upload bone matrices to shader.
     */
    void upload_bone_matrices(ShaderProgram& shader);

    /**
     * Draw skinned mesh.
     *
     * @param context Render context with graphics backend
     * @param mesh Mesh3 data
     * @param mesh_gpu GPU mesh wrapper
     * @param mesh_version Mesh version for re-upload check
     * @param shader Shader program to use (should have skinning support)
     */
    void draw(
        const RenderContext& context,
        const Mesh3& mesh,
        MeshGPU& mesh_gpu,
        int mesh_version,
        ShaderProgram& shader
    );
};

} // namespace termin
