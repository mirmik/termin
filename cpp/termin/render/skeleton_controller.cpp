#include "skeleton_controller.hpp"
#include "termin/entity/entity.hpp"
#include <iostream>

namespace termin {

SkeletonController::SkeletonController()
    : Component()
{
    _type_name = "SkeletonController";
    is_native = true;
    std::cout << "[SkeletonController] Created, this=" << this << std::endl;
}

void SkeletonController::set_skeleton(const SkeletonHandle& handle) {
    std::cout << "[SkeletonController::set_skeleton] this=" << this
              << " handle.is_valid=" << handle.is_valid() << std::endl;
    skeleton = handle;
    _skeleton_instance.reset();
}

void SkeletonController::set_bone_entities(std::vector<EntityHandle> handles) {
    std::cout << "[SkeletonController::set_bone_entities] this=" << this
              << " count=" << handles.size() << std::endl;
    for (size_t i = 0; i < handles.size(); ++i) {
        std::cout << "  [" << i << "] uuid=" << handles[i].uuid << std::endl;
    }
    bone_entities = std::move(handles);
    _skeleton_instance.reset();
    std::cout << "[SkeletonController::set_bone_entities] after move, bone_entities.size="
              << bone_entities.size() << std::endl;
}

void SkeletonController::set_bone_entities_from_ptrs(std::vector<Entity*> entities) {
    std::vector<EntityHandle> handles;
    handles.reserve(entities.size());
    for (Entity* e : entities) {
        handles.push_back(EntityHandle::from_entity(e));
    }
    set_bone_entities(std::move(handles));
}

std::vector<Entity*> SkeletonController::get_resolved_bone_entities() const {
    std::vector<Entity*> result;
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
