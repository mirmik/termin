#ifndef TC_SCENE_UI_DOCUMENT_CAPABILITY_H
#define TC_SCENE_UI_DOCUMENT_CAPABILITY_H

#include <stdbool.h>
#include <stdint.h>

#include <core/tc_component.h>
#include <core/tc_component_capability.h>
#include <termin/gui_native/tc_ui_document.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_scene_ui_document_snapshot {
    tc_ui_document_handle document;
    uint32_t asset_index;
    uint32_t asset_generation;
    int priority;
    uint32_t input_source_mask;
} tc_scene_ui_document_snapshot;

typedef struct tc_scene_ui_document_vtable {
    bool (*get_snapshot)(
        tc_component* component,
        tc_scene_ui_document_snapshot* out_snapshot);
} tc_scene_ui_document_vtable;

typedef struct tc_scene_ui_document_capability {
    const tc_scene_ui_document_vtable* vtable;
    void* userdata;
} tc_scene_ui_document_capability;

TC_API tc_component_cap_id tc_scene_ui_document_capability_id(void);

TC_API bool tc_scene_ui_document_capability_attach(
    tc_component* component,
    const tc_scene_ui_document_vtable* vtable,
    void* userdata);

TC_API const tc_scene_ui_document_capability*
tc_scene_ui_document_capability_get(const tc_component* component);

TC_API bool tc_scene_ui_document_snapshot_get(
    tc_component* component,
    tc_scene_ui_document_snapshot* out_snapshot);

#ifdef __cplusplus
}
#endif

#endif
