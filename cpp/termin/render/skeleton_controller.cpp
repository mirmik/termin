#include "skeleton_controller.hpp"
#include "termin/entity/entity.hpp"
#include <iostream>

namespace termin {

SkeletonController::SkeletonController()
    : CxxComponent()
{
    _type_name = "SkeletonController";
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
                entity  // Use controller's entity as skeleton root
            );
        }
    }
    return _skeleton_instance.get();
}

void SkeletonController::invalidate_instance() {
    _skeleton_instance.reset();
}

} // namespace termin
