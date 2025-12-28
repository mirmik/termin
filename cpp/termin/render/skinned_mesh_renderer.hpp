#pragma once

#include <vector>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

#include "termin/render/mesh_renderer.hpp"
#include "termin/skeleton/skeleton_instance.hpp"

namespace py = pybind11;

namespace termin {

// Forward declaration
class SkeletonController;

/**
 * SkinnedMeshRenderer - renders skinned mesh with bone matrices.
 *
 * Extends MeshRenderer with:
 * - skeleton_controller: Reference to SkeletonController for bone matrices
 * - Automatic upload of u_bone_matrices uniform before drawing
 * - Skinned shader variant injection via get_skinned_material()
 */
class SkinnedMeshRenderer : public MeshRenderer {
public:
    // C++ SkeletonController pointer (not owned)
    SkeletonController* _skeleton_controller = nullptr;

    // Cached bone matrices (column-major, ready for shader)
    std::vector<float> _bone_matrices_flat;
    int _bone_count = 0;

    // Cached skinned material
    Material* _skinned_material_cache = nullptr;
    int _cached_base_material_id = 0;

    // Note: mesh, material, cast_shadow are inherited from MeshRenderer
    // and already have INSPECT_FIELD registrations there

    SkinnedMeshRenderer();
    ~SkinnedMeshRenderer() override = default;

    /**
     * Get skeleton controller.
     */
    SkeletonController* skeleton_controller() const { return _skeleton_controller; }

    /**
     * Set skeleton controller.
     */
    void set_skeleton_controller(SkeletonController* controller);

    /**
     * Get skeleton instance from controller.
     */
    SkeletonInstance* skeleton_instance();

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
     * Get skinned variant of the current material.
     * Caches the result for performance.
     */
    Material* get_skinned_material();

    /**
     * Draw skinned geometry with bone matrices.
     * Overrides MeshRenderer::draw_geometry.
     */
    void draw_geometry(const RenderContext& context, const std::string& geometry_id = "") override;

    /**
     * Get geometry draw calls using skinned material.
     * Overrides MeshRenderer to use get_skinned_material().
     */
    std::vector<GeometryDrawCall> get_geometry_draws(const std::string* phase_mark = nullptr) override;

    /**
     * Component lifecycle: find skeleton controller on start.
     */
    void start() override;
};

REGISTER_COMPONENT(SkinnedMeshRenderer, MeshRenderer);

} // namespace termin
