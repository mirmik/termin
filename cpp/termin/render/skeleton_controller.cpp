#include "skeleton_controller.hpp"
#include "termin/entity/entity.hpp"
#include "tc_log.hpp"

namespace termin {

SkeletonController::SkeletonController()
    : CxxComponent()
{
    _type_name = "SkeletonController";
    _c.has_before_render = true;
}

void SkeletonController::start() {
    CxxComponent::start();

    // Debug: check skeleton state after deserialization
    tc::Log::info("[SkeletonController::start] skeleton.is_valid=%d skeleton.get()=%p bone_entities.size=%zu",
                  skeleton.is_valid(), (void*)skeleton.get(), bone_entities.size());

    if (skeleton.is_valid() && skeleton.get() != nullptr) {
        tc::Log::info("[SkeletonController::start] skeleton bones=%zu", skeleton.get()->bones().size());
    }

    // Check bone entities validity
    int valid_count = 0;
    for (size_t i = 0; i < bone_entities.size(); ++i) {
        if (bone_entities[i].valid()) {
            valid_count++;
        }
    }
    tc::Log::info("[SkeletonController::start] valid bone entities: %d/%zu", valid_count, bone_entities.size());
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
    if (_skeleton_instance != nullptr) {
        _skeleton_instance->update();
    }
}

} // namespace termin
