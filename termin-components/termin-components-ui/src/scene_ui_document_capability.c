#include <termin/ui/tc_scene_ui_document_capability.h>

#include <stdlib.h>

static void tc_scene_ui_document_capability_destroy(void* ptr) {
    free(ptr);
}

tc_component_cap_id tc_scene_ui_document_capability_id(void) {
    static tc_component_cap_id capability =
        TC_COMPONENT_CAPABILITY_INVALID_ID;
    if (capability == TC_COMPONENT_CAPABILITY_INVALID_ID) {
        capability = tc_component_capability_register_with_destructor(
            "scene_ui_document",
            tc_scene_ui_document_capability_destroy);
    }
    return capability;
}

bool tc_scene_ui_document_capability_attach(
    tc_component* component,
    const tc_scene_ui_document_vtable* vtable,
    void* userdata
) {
    if (!component || !vtable || !vtable->get_snapshot) {
        return false;
    }
    const tc_component_cap_id id = tc_scene_ui_document_capability_id();
    tc_scene_ui_document_capability* capability =
        (tc_scene_ui_document_capability*)tc_component_get_capability(
            component, id);
    if (!capability) {
        capability = (tc_scene_ui_document_capability*)calloc(
            1, sizeof(tc_scene_ui_document_capability));
        if (!capability) {
            return false;
        }
        if (!tc_component_attach_capability(component, id, capability)) {
            free(capability);
            return false;
        }
    }
    capability->vtable = vtable;
    capability->userdata = userdata;
    return true;
}

const tc_scene_ui_document_capability*
tc_scene_ui_document_capability_get(const tc_component* component) {
    if (!component) {
        return NULL;
    }
    return (const tc_scene_ui_document_capability*)tc_component_get_capability(
        component, tc_scene_ui_document_capability_id());
}

bool tc_scene_ui_document_snapshot_get(
    tc_component* component,
    tc_scene_ui_document_snapshot* out_snapshot
) {
    const tc_scene_ui_document_capability* capability =
        tc_scene_ui_document_capability_get(component);
    if (!capability || !capability->vtable ||
        !capability->vtable->get_snapshot || !out_snapshot) {
        return false;
    }
    return capability->vtable->get_snapshot(component, out_snapshot);
}
