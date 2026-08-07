#include <termin/input/tc_world_pointer_surface.h>

#include <tcbase/tc_log.h>

#include <stdlib.h>

static void tc_world_pointer_surface_capability_destroy(void* ptr) {
    free(ptr);
}

tc_component_cap_id tc_world_pointer_surface_capability_id(void) {
    static tc_component_cap_id capability =
        TC_COMPONENT_CAPABILITY_INVALID_ID;
    if (capability == TC_COMPONENT_CAPABILITY_INVALID_ID) {
        capability = tc_component_capability_register_with_destructor(
            "world_pointer_surface",
            tc_world_pointer_surface_capability_destroy);
    }
    return capability;
}

bool tc_world_pointer_surface_capability_attach(
    tc_component* component,
    const tc_world_pointer_surface_vtable* vtable,
    void* userdata
) {
    if (!component || !vtable || !vtable->project_ray ||
        !vtable->dispatch_pointer) {
        tc_log_error(
            "[world_pointer_surface] cannot attach an incomplete capability");
        return false;
    }
    const tc_component_cap_id id =
        tc_world_pointer_surface_capability_id();
    tc_world_pointer_surface_capability* capability =
        (tc_world_pointer_surface_capability*)tc_component_get_capability(
            component, id);
    if (!capability) {
        capability = (tc_world_pointer_surface_capability*)calloc(
            1, sizeof(tc_world_pointer_surface_capability));
        if (!capability) {
            tc_log_error("[world_pointer_surface] capability allocation failed");
            return false;
        }
        if (!tc_component_attach_capability(component, id, capability)) {
            tc_log_error("[world_pointer_surface] capability attach failed");
            free(capability);
            return false;
        }
    }
    capability->vtable = vtable;
    capability->userdata = userdata;
    return true;
}

const tc_world_pointer_surface_capability*
tc_world_pointer_surface_capability_get(const tc_component* component) {
    if (!component) return NULL;
    return (const tc_world_pointer_surface_capability*)
        tc_component_get_capability(
            component, tc_world_pointer_surface_capability_id());
}

bool tc_world_pointer_surface_project_ray(
    tc_component* component,
    const tc_world_pointer_ray* ray,
    tc_world_pointer_hit* out_hit
) {
    const tc_world_pointer_surface_capability* capability =
        tc_world_pointer_surface_capability_get(component);
    if (!capability || !capability->vtable ||
        !capability->vtable->project_ray || !ray || !out_hit) {
        return false;
    }
    return capability->vtable->project_ray(component, ray, out_hit);
}

bool tc_world_pointer_surface_dispatch_pointer(
    tc_component* component,
    const tc_world_pointer_event* event
) {
    const tc_world_pointer_surface_capability* capability =
        tc_world_pointer_surface_capability_get(component);
    if (!capability || !capability->vtable ||
        !capability->vtable->dispatch_pointer || !event) {
        return false;
    }
    return capability->vtable->dispatch_pointer(component, event);
}
