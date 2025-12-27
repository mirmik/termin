#include "general_transform3.hpp"
#include "../entity/entity.hpp"
#include "../../../core_c/include/tc_entity.h"

namespace termin {

Entity* GeneralTransform3::entity() const {
    if (!_t) return nullptr;
    tc_entity* e = tc_transform_entity(_t);
    if (!e) return nullptr;
    // Get C++ Entity from tc_entity's data pointer
    return static_cast<Entity*>(tc_entity_data(e));
}

void GeneralTransform3::set_entity(Entity* e) {
    if (!_t) return;
    if (e) {
        tc_transform_set_entity(_t, e->c_entity());
        // Store C++ Entity pointer in tc_entity's data
        tc_entity_set_data(e->c_entity(), e);
    } else {
        tc_transform_set_entity(_t, nullptr);
    }
}

const char* GeneralTransform3::name() const {
    if (!_t) return "";
    tc_entity* e = tc_transform_entity(_t);
    if (!e) return "";
    return tc_entity_name(e);
}

} // namespace termin
