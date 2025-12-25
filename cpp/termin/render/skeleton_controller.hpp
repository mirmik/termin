#pragma once

#include <vector>
#include <string>
#include <memory>

#include "termin/entity/component.hpp"
#include "termin/entity/component_registry.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/entity_handle.hpp"
#include "termin/assets/handles.hpp"
#include "termin/skeleton/skeleton_data.hpp"
#include "termin/skeleton/skeleton_instance.hpp"
#include "termin/inspect/inspect_registry.hpp"

namespace termin {

/**
 * SkeletonController - Component that manages skeleton for skinned meshes.
 *
 * Holds SkeletonHandle and bone Entity references.
 * Creates SkeletonInstance lazily on first access.
 * SkinnedMeshRenderer uses this to get bone matrices.
 */
class SkeletonController : public Component {
public:
    // Skeleton handle (wraps SkeletonAsset)
    SkeletonHandle skeleton;

    // Bone entity handles (same order as skeleton_data.bones)
    std::vector<EntityHandle> bone_entities;

private:
    // Cached skeleton instance (created lazily)
    std::unique_ptr<SkeletonInstance> _skeleton_instance;

public:
    SkeletonController();
    ~SkeletonController() override = default;

    /**
     * Get skeleton data pointer (from handle).
     */
    SkeletonData* skeleton_data() const { return skeleton.get(); }

    /**
     * Set skeleton data via handle. Invalidates cached instance.
     */
    void set_skeleton(const SkeletonHandle& handle);

    /**
     * Set bone entities from handles. Invalidates cached instance.
     */
    void set_bone_entities(std::vector<EntityHandle> handles);

    /**
     * Set bone entities from Entity pointers. Invalidates cached instance.
     */
    void set_bone_entities_from_ptrs(std::vector<Entity*> entities);

    /**
     * Get resolved bone entities (for SkeletonInstance).
     */
    std::vector<Entity*> get_resolved_bone_entities() const;

    /**
     * Get or create SkeletonInstance.
     *
     * Creates instance lazily on first access using:
     * - skeleton handle
     * - bone_entities
     * - this->entity as skeleton root
     */
    SkeletonInstance* skeleton_instance();

    /**
     * Invalidate cached skeleton instance.
     * Call when bone transforms change structurally.
     */
    void invalidate_instance();

    INSPECT_FIELD(SkeletonController, skeleton, "Skeleton", "skeleton_handle")
    INSPECT_FIELD(SkeletonController, bone_entities, "Bone Entities", "list[entity_handle]")
};

REGISTER_COMPONENT(SkeletonController);

} // namespace termin
