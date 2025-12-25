#pragma once

#include <vector>
#include <string>
#include <memory>

#include "termin/entity/component.hpp"
#include "termin/entity/component_registry.hpp"
#include "termin/entity/entity.hpp"
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

    // Bone entities (same order as skeleton_data.bones)
    std::vector<Entity*> _bone_entities;

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
     * Get bone entities.
     */
    const std::vector<Entity*>& bone_entities() const { return _bone_entities; }

    /**
     * Set bone entities. Invalidates cached instance.
     */
    void set_bone_entities(std::vector<Entity*> entities);

    /**
     * Get or create SkeletonInstance.
     *
     * Creates instance lazily on first access using:
     * - skeleton handle
     * - _bone_entities
     * - this->entity as skeleton root
     */
    SkeletonInstance* skeleton_instance();

    /**
     * Invalidate cached skeleton instance.
     * Call when bone transforms change structurally.
     */
    void invalidate_instance();

    INSPECT_FIELD(SkeletonController, skeleton, "Skeleton", "skeleton")
    INSPECT_FIELD(SkeletonController, _bone_entities, "Bone Entities", "entity_list")
};

REGISTER_COMPONENT(SkeletonController);

} // namespace termin
