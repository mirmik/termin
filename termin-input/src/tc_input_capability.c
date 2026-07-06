#include "core/tc_input_capability.h"
#include "core/tc_input_component.h"

tc_component_cap_id tc_input_capability_id(void) {
    static tc_component_cap_id input_cap = TC_COMPONENT_CAPABILITY_INVALID_ID;
    if (input_cap == TC_COMPONENT_CAPABILITY_INVALID_ID) {
        input_cap = tc_component_capability_register("input");
    }
    return input_cap;
}

bool tc_input_capability_attach(tc_component* c, const tc_input_vtable* vtable) {
    if (!c || !vtable) return false;
    return tc_component_attach_capability(c, tc_input_capability_id(), (void*)vtable);
}

const tc_input_vtable* tc_input_capability_get(const tc_component* c) {
    if (!c) return NULL;
    return (const tc_input_vtable*)tc_component_get_capability(c, tc_input_capability_id());
}

int tc_component_get_input_priority(const tc_component* c) {
    return tc_component_get_capability_priority(c, tc_input_capability_id());
}

bool tc_component_set_input_priority(tc_component* c, int priority) {
    return tc_component_set_capability_priority(c, tc_input_capability_id(), priority);
}
