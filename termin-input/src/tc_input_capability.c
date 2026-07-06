#include "core/tc_input_capability.h"
#include "core/tc_input_component.h"
#include <tcbase/tc_log.h>
#include <stdlib.h>

typedef struct tc_input_capability_payload {
    const tc_input_vtable* vtable;
    uint32_t source_mask;
} tc_input_capability_payload;

static void tc_input_capability_destroy(void* ptr) {
    free(ptr);
}

tc_component_cap_id tc_input_capability_id(void) {
    static tc_component_cap_id input_cap = TC_COMPONENT_CAPABILITY_INVALID_ID;
    if (input_cap == TC_COMPONENT_CAPABILITY_INVALID_ID) {
        input_cap = tc_component_capability_register_with_destructor("input", tc_input_capability_destroy);
    }
    return input_cap;
}

bool tc_input_capability_attach(tc_component* c, const tc_input_vtable* vtable) {
    if (!c || !vtable) return false;

    tc_component_cap_id cap_id = tc_input_capability_id();
    tc_input_capability_payload* existing =
        (tc_input_capability_payload*)tc_component_get_capability(c, cap_id);
    if (existing) {
        existing->vtable = vtable;
        return true;
    }

    tc_input_capability_payload* payload =
        (tc_input_capability_payload*)calloc(1, sizeof(tc_input_capability_payload));
    if (!payload) {
        tc_log_error("[tc_input_capability] allocation failed");
        return false;
    }

    payload->vtable = vtable;
    payload->source_mask = TC_INPUT_SOURCE_RUNTIME;

    if (!tc_component_attach_capability(c, cap_id, payload)) {
        free(payload);
        return false;
    }

    return true;
}

const tc_input_vtable* tc_input_capability_get(const tc_component* c) {
    if (!c) return NULL;
    const tc_input_capability_payload* payload =
        (const tc_input_capability_payload*)tc_component_get_capability(c, tc_input_capability_id());
    return payload ? payload->vtable : NULL;
}

uint32_t tc_component_get_input_source_mask(const tc_component* c) {
    if (!c) return 0;
    const tc_input_capability_payload* payload =
        (const tc_input_capability_payload*)tc_component_get_capability(c, tc_input_capability_id());
    return payload ? payload->source_mask : 0;
}

bool tc_component_set_input_source_mask(tc_component* c, uint32_t source_mask) {
    if (!c) return false;
    tc_input_capability_payload* payload =
        (tc_input_capability_payload*)tc_component_get_capability(c, tc_input_capability_id());
    if (!payload) return false;
    payload->source_mask = source_mask;
    return true;
}

bool tc_component_accepts_input_source(const tc_component* c, uint32_t source) {
    if (!source) return false;
    return (tc_component_get_input_source_mask(c) & source) != 0;
}

int tc_component_get_input_priority(const tc_component* c) {
    return tc_component_get_capability_priority(c, tc_input_capability_id());
}

bool tc_component_set_input_priority(tc_component* c, int priority) {
    return tc_component_set_capability_priority(c, tc_input_capability_id(), priority);
}
