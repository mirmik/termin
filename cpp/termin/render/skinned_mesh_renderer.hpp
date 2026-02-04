#pragma once

#include <vector>

#include "termin/render/mesh_renderer.hpp"
#include "termin/entity/cmp_ref.hpp"
#include "termin/skeleton/skeleton_instance.hpp"

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
    // C++ SkeletonController reference (CmpRef validates entity liveness)
    CmpRef<SkeletonController> _skeleton_controller;

    // Cached bone matrices (column-major, ready for shader)
    std::vector<float> _bone_matrices_flat;
    int _bone_count = 0;

    // Note: mesh, material, cast_shadow are inherited from MeshRenderer
    // and already have INSPECT_FIELD registrations there

    SkinnedMeshRenderer();
    ~SkinnedMeshRenderer() override = default;

    /**
     * Get skeleton controller (nullptr if entity is dead).
     */
    SkeletonController* skeleton_controller() const { return _skeleton_controller.get(); }

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
    void upload_bone_matrices(TcShader& shader);

    /**
     * Draw skinned geometry with bone matrices.
     * Overrides MeshRenderer::draw_geometry.
     */
    void draw_geometry(const RenderContext& context, int geometry_id = 0) override;

    /**
     * Get geometry draw calls.
     * Uses parent implementation - shader override happens in override_shader().
     */
    std::vector<GeometryDrawCall> get_geometry_draws(const std::string* phase_mark = nullptr) override;

    /**
     * Override shader to inject skinning if needed.
     * Called by passes before applying uniforms.
     */
    TcShader override_shader(
        const std::string& phase_mark,
        int geometry_id,
        TcShader original_shader
    ) override;

    /**
     * Component lifecycle: find skeleton controller on start.
     */
    void start() override;

    void on_editor_start() override 
    {
        start();
    }
};

REGISTER_COMPONENT(SkinnedMeshRenderer, MeshRenderer);

} // namespace termin
