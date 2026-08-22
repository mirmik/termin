#pragma once

#include <memory>
#include <string>
#include <vector>

#include "termin/skeleton/skeleton_instance.hpp"
#include "termin/skeleton/tc_skeleton_handle.hpp"
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include <termin/render/render_lifecycle.hpp>

namespace termin {

    // SkeletonController - Component that manages skeleton for skinned meshes.
    //
    // Holds TcSkeleton and bone Entity references.
    // Creates SkeletonInstance lazily on first access.
    // SkinnedMeshRenderer uses this to get bone matrices.
    class ENTITY_API SkeletonController : public CxxComponent, public RenderLifecycle {
    public:
        // Skeleton (RAII wrapper over tc_skeleton)
        TcSkeleton skeleton;

        // Bone entities (same order as skeleton bones)
        std::vector<Entity> bone_entities;

        // Entity whose local space is used as the skeleton skinning root.
        // If unset, the controller owner entity is used for compatibility.
        Entity skeleton_root;

    private:
        // Cached skeleton instance (created lazily and kept at a stable address
        // for the lifetime of this controller).
        std::unique_ptr<SkeletonInstance> _skeleton_instance;

        // Bone mappings are positional. Keep the skeleton name/order signature
        // that bone_entities was published against so live resource replacement
        // cannot silently apply entity transforms to different bones.
        std::vector<std::string> _bone_mapping_signature;
        tc_skeleton_handle _bone_mapping_skeleton = tc_skeleton_handle_invalid();
        uint32_t _bone_mapping_version = 0;
        bool _has_bone_mapping_signature = false;
        bool _bone_mapping_requires_republish = false;
        bool _bone_mapping_error_reported = false;

        bool ensure_skeleton_ready(const char* operation);
        void synchronize_cached_instance_resource();
        bool try_publish_bone_mapping(const char* operation, bool report_count_mismatch);
        bool validate_bone_mapping(const char* operation);

    public:
        SkeletonController();
        ~SkeletonController() override = default;

        static void register_type();

        /**
         * Get a borrowed tc_skeleton pointer.
         *
         * The pointer is valid only until the next skeleton registry mutation
         * and must never be cached.
         */
        const tc_skeleton* get_skeleton() const {
            return skeleton.get();
        }

        /**
         * Set skeleton and rebind an already-created instance in place.
         */
        void set_skeleton(const TcSkeleton& skel);

        /**
         * Publish bone entities for the current skeleton name/order mapping.
         */
        void set_bone_entities(std::vector<Entity> entities);

        /**
         * Set skeleton root entity without replacing the cached instance.
         */
        void set_skeleton_root(Entity root);

        /**
         * Get or create SkeletonInstance.
         *
         * Creates the instance lazily on first access and keeps its address
         * stable until controller destruction. Uses:
         * - skeleton
         * - bone_entities
         * - skeleton_root if valid, otherwise this->entity as skeleton root
         */
        SkeletonInstance* skeleton_instance();

        /**
         * Refresh the portable instance from the current Entity transforms in
         * the requested skinning-root space.
         */
        bool update_skeleton_instance(Entity skinning_root);

        Entity bone_entity(int bone_index) const;

        /**
         * Component lifecycle: check skeleton state after deserialization.
         */
        void start() override;

        /**
         * Called before render to update bone matrices once per frame.
         */
        void prepare_render(const RenderPrepareContext& context) override;

        void on_removed_from_entity() override;
    };

} // namespace termin
