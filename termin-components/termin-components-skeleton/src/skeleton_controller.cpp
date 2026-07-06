#include <termin/render/skeleton_controller.hpp>
#include <termin/entity/entity.hpp>
#include <termin/entity/component_registry.hpp>
#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>

namespace termin {

SkeletonController::SkeletonController()
    : CxxComponent("SkeletonController")
{
    _c.has_before_render = true;
}

void SkeletonController::register_type() {
    register_component_type<SkeletonController>("SkeletonController", "Component");
    tc::register_inspect_field(
        &SkeletonController::skeleton,
        "SkeletonController",
        "skeleton",
        "Skeleton",
        "tc_skeleton"
    );
    tc::register_inspect_field(
        &SkeletonController::bone_entities,
        "SkeletonController",
        "bone_entities",
        "Bone Entities",
        "list[entity]"
    );
    tc::register_inspect_field(
        &SkeletonController::skeleton_root,
        "SkeletonController",
        "skeleton_root",
        "Skeleton Root",
        "entity"
    );
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

    tc_skeleton* skel = skeleton.get();
    Entity effective_root = skeleton_root.valid() ? skeleton_root : entity();
    if (_skeleton_instance != nullptr && _skeleton_instance->skeleton_root() != effective_root) {
        _skeleton_instance.reset();
    }

    if (_skeleton_instance == nullptr && skel != nullptr) {
        if (!bone_entities.empty()) {
            _skeleton_instance = std::make_unique<SkeletonInstance>(
                skel,
                bone_entities,
                effective_root
            );
            _skeleton_instance->update();
        } else {
            tc::Log::warn("[SkeletonController::skeleton_instance] bone_entities is empty! skel=%p",
                (void*)skel);
        }
    }
    return _skeleton_instance.get();
}

void SkeletonController::invalidate_instance() {
    _skeleton_instance.reset();
}

void SkeletonController::before_render() {
    if (_skeleton_instance == nullptr) {
        skeleton_instance(); // Try to create instance
    }

    if (_skeleton_instance != nullptr) {
        _skeleton_instance->update();
    } else {
        tc::Log::warn("[SkeletonController::before_render] no skeleton instance");
    }
}

void SkeletonController::on_removed_from_entity() {
    CxxComponent::on_removed_from_entity();
    _skeleton_instance.reset();
}

} // namespace termin
