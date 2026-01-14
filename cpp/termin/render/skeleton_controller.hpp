#pragma once

#include <vector>
#include <string>
#include <memory>

#include "termin/entity/component.hpp"
#include "termin/entity/component_registry.hpp"
#include "termin/entity/entity.hpp"
#include "termin/skeleton/tc_skeleton_handle.hpp"
#include "termin/skeleton/skeleton_instance.hpp"
#include "termin/inspect/inspect_registry.hpp"

namespace termin {

// SkeletonController - Component that manages skeleton for skinned meshes.
//
// Holds TcSkeleton and bone Entity references.
// Creates SkeletonInstance lazily on first access.
// SkinnedMeshRenderer uses this to get bone matrices.
class SkeletonController : public CxxComponent {
public:
    // Skeleton (RAII wrapper over tc_skeleton)
    TcSkeleton skeleton;

    // Bone entities (same order as skeleton bones)
    std::vector<Entity> bone_entities;

private:
    // Cached skeleton instance (created lazily)
    std::unique_ptr<SkeletonInstance> _skeleton_instance;

public:
    INSPECT_FIELD(SkeletonController, skeleton, "Skeleton", "tc_skeleton")
    INSPECT_FIELD(SkeletonController, bone_entities, "Bone Entities", "list[entity]")

public:
    SkeletonController();
    ~SkeletonController() override = default;

    /**
     * Get tc_skeleton pointer.
     */
    tc_skeleton* get_skeleton() const { return skeleton.get(); }

    /**
     * Set skeleton. Invalidates cached instance.
     */
    void set_skeleton(const TcSkeleton& skel);

    /**
     * Set bone entities. Invalidates cached instance.
     */
    void set_bone_entities(std::vector<Entity> entities);

    /**
     * Get or create SkeletonInstance.
     *
     * Creates instance lazily on first access using:
     * - skeleton
     * - bone_entities
     * - this->entity as skeleton root
     */
    SkeletonInstance* skeleton_instance();

    /**
     * Invalidate cached skeleton instance.
     * Call when bone transforms change structurally.
     */
    void invalidate_instance();

    /**
     * Component lifecycle: check skeleton state after deserialization.
     */
    void start() override;

    /**
     * Called before render to update bone matrices once per frame.
     */
    void before_render() override;

    void on_removed_from_entity() override;
};

REGISTER_COMPONENT(SkeletonController, Component);

} // namespace termin
