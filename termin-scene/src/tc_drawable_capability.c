#include "core/tc_drawable_capability.h"
#include "core/tc_component.h"

tc_component_cap_id tc_drawable_capability_id(void) {
    static tc_component_cap_id drawable_cap = TC_COMPONENT_CAPABILITY_INVALID_ID;
    if (drawable_cap == TC_COMPONENT_CAPABILITY_INVALID_ID) {
        drawable_cap = tc_component_capability_register("drawable");
    }
    return drawable_cap;
}

bool tc_drawable_capability_attach(tc_component* c, const tc_drawable_vtable* vtable) {
    if (!c || !vtable) return false;
    return tc_component_attach_capability(c, tc_drawable_capability_id(), (void*)vtable);
}

const tc_drawable_vtable* tc_drawable_capability_get(const tc_component* c) {
    if (!c) return NULL;
    return (const tc_drawable_vtable*)tc_component_get_capability(c, tc_drawable_capability_id());
}
