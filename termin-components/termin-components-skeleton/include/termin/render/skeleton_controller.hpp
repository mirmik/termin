#pragma once

#include <vector>
#include <string>
#include <memory>

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include "termin/skeleton/tc_skeleton_handle.hpp"
#include "termin/skeleton/skeleton_instance.hpp"

namespace termin {

// SkeletonController - Component that manages skeleton for skinned meshes.
//
// Holds TcSkeleton and bone Entity references.
// Creates SkeletonInstance lazily on first access.
// SkinnedMeshRenderer uses this to get bone matrices.
class ENTITY_API SkeletonController : public CxxComponent {
public:
    // Skeleton (RAII wrapper over tc_skeleton)
    TcSkeleton skeleton;

    // Bone entities (same order as skeleton bones)
    std::vector<Entity> bone_entities;

    // Entity whose local space is used as the skeleton skinning root.
    // If unset, the controller owner entity is used for compatibility.
    Entity skeleton_root;

private:
    // Cached skeleton instance (created lazily)
    std::unique_ptr<SkeletonInstance> _skeleton_instance;

public:
    SkeletonController();
    ~SkeletonController() override = default;

    static void register_type();

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
     * Set skeleton root entity. Invalidates cached instance.
     */
    void set_skeleton_root(Entity root);

    /**
     * Get or create SkeletonInstance.
     *
     * Creates instance lazily on first access using:
     * - skeleton
     * - bone_entities
     * - skeleton_root if valid, otherwise this->entity as skeleton root
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

} // namespace termin
