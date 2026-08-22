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
    }

    void SkeletonController::set_skeleton(const TcSkeleton& skel) {
        skeleton = skel;
        _skeleton_instance.reset();
    }

    void SkeletonController::set_bone_entities(std::vector<Entity> entities) {
        bone_entities = std::move(entities);
        _skeleton_instance.reset();
    }

    void SkeletonController::set_skeleton_root(Entity root) {
        skeleton_root = root;
        _skeleton_instance.reset();
    }

    SkeletonInstance* SkeletonController::skeleton_instance() {
        // Ensure skeleton is loaded (trigger lazy loading if needed)
        skeleton.ensure_loaded();

        const tc_skeleton* skel = skeleton.get();
        if (_skeleton_instance == nullptr && skel != nullptr) {
            if (!bone_entities.empty()) {
                _skeleton_instance = std::make_unique<SkeletonInstance>(skel);
                update_skeleton_instance(skeleton_root.valid() ? skeleton_root : entity());
            } else {
                tc::Log::warn("[SkeletonController::skeleton_instance] bone_entities is empty! skel=%p", (void*)skel);
            }
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
        if (_skeleton_instance == nullptr) {
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
        return _skeleton_instance->update_from_world_matrices(
            entity_world_matrix(skinning_root), bone_world_matrices);
    }

    void SkeletonController::invalidate_instance() {
        _skeleton_instance.reset();
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
        _skeleton_instance.reset();
    }

} // namespace termin
