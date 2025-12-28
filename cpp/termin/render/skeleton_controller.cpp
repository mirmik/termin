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

void SkeletonController::set_bone_entities(std::vector<EntityHandle> handles) {
    bone_entities = std::move(handles);
    _skeleton_instance.reset();
}

void SkeletonController::set_bone_entities_from_entities(std::vector<Entity> entities) {
    std::vector<EntityHandle> handles;
    handles.reserve(entities.size());
    for (const Entity& e : entities) {
        handles.push_back(EntityHandle::from_entity(e));
    }
    set_bone_entities(std::move(handles));
}

std::vector<Entity> SkeletonController::get_resolved_bone_entities() const {
    std::vector<Entity> result;
    result.reserve(bone_entities.size());
    for (const auto& handle : bone_entities) {
        result.push_back(handle.get());
    }
    return result;
}

SkeletonInstance* SkeletonController::skeleton_instance() {
    SkeletonData* skel_data = skeleton.get();
    if (_skeleton_instance == nullptr && skel_data != nullptr) {
        if (!bone_entities.empty()) {
            auto resolved = get_resolved_bone_entities();
            _skeleton_instance = std::make_unique<SkeletonInstance>(
                skel_data,
                resolved,
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
