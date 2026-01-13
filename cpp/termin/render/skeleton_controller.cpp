#include "skeleton_controller.hpp"
#include "termin/entity/entity.hpp"
#include "tc_log.hpp"

namespace termin {

SkeletonController::SkeletonController()
    : CxxComponent()
{
    set_type_name("SkeletonController");
    _c.has_before_render = true;
}

void SkeletonController::start() {
    CxxComponent::start();
}

void SkeletonController::set_skeleton(const SkeletonHandle& handle) {
    skeleton = handle;
    _skeleton_instance.reset();
}

void SkeletonController::set_bone_entities(std::vector<Entity> entities) {
    bone_entities = std::move(entities);
    _skeleton_instance.reset();
}

SkeletonInstance* SkeletonController::skeleton_instance() {
    SkeletonData* skel_data = skeleton.get();
    if (_skeleton_instance == nullptr && skel_data != nullptr) {
        if (!bone_entities.empty()) {
            _skeleton_instance = std::make_unique<SkeletonInstance>(
                skel_data,
                bone_entities,
                entity
            );
            _skeleton_instance->update();
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
    }
}

void SkeletonController::on_removed_from_entity() {
    CxxComponent::on_removed_from_entity();
    _skeleton_instance.reset();
}

} // namespace termin
