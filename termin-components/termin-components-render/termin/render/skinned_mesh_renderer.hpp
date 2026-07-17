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
 * - Per-instance std140 UBO (bone_block/BoneBlock) uploaded before drawing
 * - Skinned shader variant injection via get_skinned_material()
 */
class ENTITY_API SkinnedMeshRenderer : public MeshRenderer {
public:
    // C++ SkeletonController reference (CmpRef validates entity liveness)
    CmpRef<SkeletonController> _skeleton_controller;

    // Cached bone matrices (column-major, ready for shader)
    std::vector<float> _bone_matrices_flat;
    int _bone_count = 0;

private:
    void resolve_skeleton_controller();

protected:
    void populate_mesh_render_item(tc_render_item& item) override;

public:
    // Note: material and cast_shadow are inherited from MeshRenderer;
    // mesh data lives on the required MeshComponent.
    // MeshRenderer::register_type() owns their inspect serialization.

    SkinnedMeshRenderer();
    ~SkinnedMeshRenderer() override;

    static void register_type();

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
     * Component lifecycle: find skeleton controller on start.
     */
    void start() override;

    void on_editor_start() override 
    {
        start();
    }
};

} // namespace termin
