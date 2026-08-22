#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include <termin/render/skeleton_controller.hpp>

namespace termin {
    namespace {
        Mat44 entity_world_matrix(Entity entity) {
            double values[16];
            entity.transform().world_matrix(values);
            Mat44 result;
            for (int i = 0; i < 16; ++i) {
                result.data[i] = values[i];
            }
            return result;
        }
    } // namespace

    SkeletonController::SkeletonController()
        : CxxComponent("SkeletonController") {
        install_render_lifecycle(&_c);
    }

    bool SkeletonController::ensure_skeleton_ready(const char* operation) {
        if (!skeleton.has_handle()) {
            return false;
        }

        const tc_skeleton_handle handle = skeleton.native_handle();
        if (!skeleton.is_valid()) {
            tc::Log::error("[SkeletonController::%s] skeleton handle is stale (index=%u, generation=%u)",
                           operation,
                           handle.index,
                           handle.generation);
            return false;
        }
        if (!skeleton.ensure_loaded()) {
            tc::Log::error("[SkeletonController::%s] failed to load skeleton '%s'", operation, skeleton.uuid());
            return false;
        }

        const tc_skeleton* resource = skeleton.get();
        if (resource == nullptr) {
            tc::Log::error(
                "[SkeletonController::%s] skeleton '%s' disappeared while resolving it", operation, skeleton.uuid());
            return false;
        }
        if (resource->bone_count > 0 && resource->bones == nullptr) {
            tc::Log::error("[SkeletonController::%s] skeleton '%s' has %zu bones but no bone payload",
                           operation,
                           resource->header.uuid,
                           resource->bone_count);
            return false;
        }
        return true;
    }

    void SkeletonController::synchronize_cached_instance_resource() {
        if (_skeleton_instance != nullptr && !_skeleton_instance->skeleton_resource().refers_to(skeleton)) {
            _skeleton_instance->set_skeleton(skeleton);
        }
    }

    bool SkeletonController::try_publish_bone_mapping(const char* operation, bool report_count_mismatch) {
        if (!skeleton.has_handle() || !ensure_skeleton_ready(operation)) {
            return false;
        }

        const tc_skeleton* resource = skeleton.get();
        if (resource == nullptr) {
            tc::Log::error("[SkeletonController::%s] skeleton disappeared before publishing the bone mapping",
                           operation);
            return false;
        }
        if (bone_entities.size() != resource->bone_count) {
            if (report_count_mismatch) {
                tc::Log::error("[SkeletonController::%s] cannot publish bone mapping: entity count=%zu, skeleton '%s' "
                               "bone_count=%zu; call set_bone_entities with one entity per bone",
                               operation,
                               bone_entities.size(),
                               resource->header.uuid,
                               resource->bone_count);
                _bone_mapping_requires_republish = true;
                _bone_mapping_error_reported = true;
            }
            return false;
        }

        std::vector<std::string> signature;
        signature.reserve(resource->bone_count);
        for (size_t index = 0; index < resource->bone_count; ++index) {
            signature.emplace_back(resource->bones[index].name);
        }

        _bone_mapping_signature = std::move(signature);
        _bone_mapping_skeleton = skeleton.native_handle();
        _bone_mapping_version = resource->header.version;
        _has_bone_mapping_signature = true;
        _bone_mapping_requires_republish = false;
        _bone_mapping_error_reported = false;
        return true;
    }

    bool SkeletonController::validate_bone_mapping(const char* operation) {
        if (_bone_mapping_requires_republish) {
            if (!_bone_mapping_error_reported) {
                tc::Log::error("[SkeletonController::%s] bone mapping is stale; call set_bone_entities to publish the "
                               "mapping for the current skeleton",
                               operation);
                _bone_mapping_error_reported = true;
            }
            return false;
        }
        if (!_has_bone_mapping_signature) {
            return try_publish_bone_mapping(operation, true);
        }
        if (!ensure_skeleton_ready(operation)) {
            return false;
        }

        const tc_skeleton* resource = skeleton.get();
        if (resource == nullptr) {
            tc::Log::error("[SkeletonController::%s] skeleton disappeared while validating the bone mapping",
                           operation);
            return false;
        }

        if (bone_entities.size() != resource->bone_count) {
            tc::Log::error("[SkeletonController::%s] entity count=%zu does not match skeleton '%s' bone_count=%zu; "
                           "call set_bone_entities to publish the new mapping",
                           operation,
                           bone_entities.size(),
                           resource->header.uuid,
                           resource->bone_count);
            _bone_mapping_requires_republish = true;
            _bone_mapping_error_reported = true;
            return false;
        }

        const tc_skeleton_handle current_handle = skeleton.native_handle();
        const bool resource_revision_changed = !tc_skeleton_handle_eq(_bone_mapping_skeleton, current_handle) ||
                                               _bone_mapping_version != resource->header.version;
        if (!resource_revision_changed) {
            return true;
        }

        if (_bone_mapping_signature.size() != resource->bone_count) {
            tc::Log::error("[SkeletonController::%s] skeleton '%s' mapping count changed from %zu to %zu; "
                           "call set_bone_entities to publish the new mapping",
                           operation,
                           resource->header.uuid,
                           _bone_mapping_signature.size(),
                           resource->bone_count);
            _bone_mapping_requires_republish = true;
            _bone_mapping_error_reported = true;
            return false;
        }

        for (size_t index = 0; index < resource->bone_count; ++index) {
            const std::string& expected_name = _bone_mapping_signature[index];
            const char* current_name = resource->bones[index].name;
            if (expected_name != current_name) {
                tc::Log::error("[SkeletonController::%s] skeleton '%s' mapping changed at bone %zu from '%s' to '%s'; "
                               "call set_bone_entities to publish the new mapping",
                               operation,
                               resource->header.uuid,
                               index,
                               expected_name.c_str(),
                               current_name);
                _bone_mapping_requires_republish = true;
                _bone_mapping_error_reported = true;
                return false;
            }
        }

        // Bind-pose/inverse-bind changes with the same name/order mapping are
        // compatible. Record the accepted revision without republishing the
        // Entity mapping.
        _bone_mapping_skeleton = current_handle;
        _bone_mapping_version = resource->header.version;
        return true;
    }

    void SkeletonController::register_type() {
        auto descriptor = ComponentTypeDescriptorBuilder::native<SkeletonController>(
            "SkeletonController", "termin-components-skeleton", "Component");
        descriptor.category("Animation");
        tc::stage_inspect_field(descriptor.inspect(),
                                &SkeletonController::skeleton,
                                "SkeletonController",
                                "skeleton",
                                "Skeleton",
                                "tc_skeleton");
        tc::stage_inspect_field(descriptor.inspect(),
                                &SkeletonController::bone_entities,
                                "SkeletonController",
                                "bone_entities",
                                "Bone Entities",
                                "list[entity]");
        tc::stage_inspect_field(descriptor.inspect(),
                                &SkeletonController::skeleton_root,
                                "SkeletonController",
                                "skeleton_root",
                                "Skeleton Root",
                                "entity");
        (void)descriptor.commit();
    }

    void SkeletonController::start() {
        CxxComponent::start();
        synchronize_cached_instance_resource();
        if (!_has_bone_mapping_signature && !_bone_mapping_requires_republish) {
            (void)try_publish_bone_mapping("start", false);
        }
    }

    void SkeletonController::set_skeleton(const TcSkeleton& skel) {
        skeleton = skel;
        synchronize_cached_instance_resource();
    }

    void SkeletonController::set_bone_entities(std::vector<Entity> entities) {
        bone_entities = std::move(entities);
        _bone_mapping_signature.clear();
        _bone_mapping_skeleton = tc_skeleton_handle_invalid();
        _bone_mapping_version = 0;
        _has_bone_mapping_signature = false;
        _bone_mapping_requires_republish = false;
        _bone_mapping_error_reported = false;
        (void)try_publish_bone_mapping("set_bone_entities", true);
    }

    void SkeletonController::set_skeleton_root(Entity root) {
        skeleton_root = root;
    }

    SkeletonInstance* SkeletonController::skeleton_instance() {
        synchronize_cached_instance_resource();
        if (!ensure_skeleton_ready("skeleton_instance")) {
            return _skeleton_instance.get();
        }

        bool created = false;
        if (_skeleton_instance == nullptr) {
            _skeleton_instance = std::make_unique<SkeletonInstance>(skeleton);
            created = true;
        }
        if (!_skeleton_instance->synchronize()) {
            tc::Log::error("[SkeletonController::skeleton_instance] failed to synchronize the skeleton instance");
            return _skeleton_instance.get();
        }

        if (created) {
            (void)update_skeleton_instance(skeleton_root.valid() ? skeleton_root : entity());
        }
        return _skeleton_instance.get();
    }

    Entity SkeletonController::bone_entity(int bone_index) const {
        if (bone_index < 0 || bone_index >= static_cast<int>(bone_entities.size())) {
            tc::Log::warn("[SkeletonController::bone_entity] invalid bone_index=%d", bone_index);
            return Entity();
        }
        return bone_entities[static_cast<size_t>(bone_index)];
    }

    bool SkeletonController::update_skeleton_instance(Entity skinning_root) {
        synchronize_cached_instance_resource();
        if (_skeleton_instance == nullptr) {
            return false;
        }
        if (!ensure_skeleton_ready("update_skeleton_instance")) {
            return false;
        }
        if (!_skeleton_instance->synchronize()) {
            tc::Log::error(
                "[SkeletonController::update_skeleton_instance] failed to synchronize the skeleton instance");
            return false;
        }
        if (!validate_bone_mapping("update_skeleton_instance")) {
            return false;
        }
        if (!skinning_root.valid()) {
            tc::Log::error("[SkeletonController::update_skeleton_instance] skinning root is invalid");
            return false;
        }
        if (bone_entities.size() != static_cast<size_t>(_skeleton_instance->bone_count())) {
            tc::Log::error(
                "[SkeletonController::update_skeleton_instance] entity count=%zu does not match bone_count=%d",
                bone_entities.size(),
                _skeleton_instance->bone_count());
            return false;
        }

        std::vector<Mat44> bone_world_matrices;
        bone_world_matrices.reserve(bone_entities.size());
        for (size_t index = 0; index < bone_entities.size(); ++index) {
            const Entity bone = bone_entities[index];
            if (!bone.valid()) {
                tc::Log::error("[SkeletonController::update_skeleton_instance] bone entity %zu is invalid", index);
                return false;
            }
            bone_world_matrices.push_back(entity_world_matrix(bone));
        }
        return _skeleton_instance->update_from_world_matrices(entity_world_matrix(skinning_root), bone_world_matrices);
    }

    void SkeletonController::prepare_render(const RenderPrepareContext& context) {
        (void)context;
        if (_skeleton_instance == nullptr) {
            skeleton_instance(); // Try to create instance
        }

        if (_skeleton_instance != nullptr) {
            update_skeleton_instance(skeleton_root.valid() ? skeleton_root : entity());
        } else {
            tc::Log::warn("[SkeletonController::prepare_render] no skeleton instance");
        }
    }

    void SkeletonController::on_removed_from_entity() {
        CxxComponent::on_removed_from_entity();
    }

} // namespace termin
