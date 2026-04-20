#pragma once

#include <vector>

#include <termin/render/mesh_renderer.hpp>
#include "termin/entity/cmp_ref.hpp"
#include "termin/skeleton/skeleton_instance.hpp"
#include <tgfx2/handles.hpp>

namespace tgfx {
class IRenderDevice;
}

namespace termin {

// Forward declaration
class SkeletonController;

/**
 * SkinnedMeshRenderer - renders skinned mesh with bone matrices.
 *
 * Extends MeshRenderer with:
 * - skeleton_controller: Reference to SkeletonController for bone matrices
 * - Per-instance std140 UBO (BoneBlock, binding=5) uploaded before drawing
 * - Skinned shader variant injection via get_skinned_material()
 */
class SkinnedMeshRenderer : public MeshRenderer {
public:
    // C++ SkeletonController reference (CmpRef validates entity liveness)
    CmpRef<SkeletonController> _skeleton_controller;

    // Cached bone matrices (column-major, ready for shader)
    std::vector<float> _bone_matrices_flat;
    int _bone_count = 0;

    // Per-instance BoneBlock UBO (lazy-created on first draw; one per
    // SkinnedMeshRenderer so multiple skinned drawables in the same
    // Vulkan command buffer don't clobber each other).
    tgfx::BufferHandle _bone_ubo{};
    tgfx::IRenderDevice* _bone_ubo_device = nullptr;

    // Note: mesh, material, cast_shadow are inherited from MeshRenderer
    // and already have INSPECT_FIELD registrations there

    SkinnedMeshRenderer();
    ~SkinnedMeshRenderer() override;

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
     * tgfx2 path: push u_bone_matrices and u_bone_count onto the
     * currently-bound ctx2 program right before ctx2->draw().
     */
    void upload_per_draw_uniforms_tgfx2(
        tgfx::RenderContext2& ctx2,
        int geometry_id
    ) override;

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
