#include "skeleton_controller.hpp"
#include "termin/entity/entity.hpp"
#include "tc_log.hpp"

namespace termin {

SkeletonController::SkeletonController()
    : CxxComponent()
{
    // type_entry is set by registry when component is created via factory
    _c.has_before_render = true;
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

SkeletonInstance* SkeletonController::skeleton_instance() {
    // Ensure skeleton is loaded (trigger lazy loading if needed)
    skeleton.ensure_loaded();

    tc_skeleton* skel = skeleton.get();
    if (_skeleton_instance == nullptr && skel != nullptr) {
        if (!bone_entities.empty()) {
            _skeleton_instance = std::make_unique<SkeletonInstance>(
                skel,
                bone_entities,
                entity()
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
